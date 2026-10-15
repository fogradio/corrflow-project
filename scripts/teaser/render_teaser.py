#!/usr/bin/env python3
"""Deterministic, silent CorrFlow motion diagram, using the original SVG layers.

Requires Python + Pillow + numpy + PyGObject/librsvg, and FFmpeg.
No synthesis, no replacement result images, no audio, no GPU.
Use --stills to inspect keyframes before encoding. All output files are additive.
"""
import argparse, copy, hashlib, json, math, re, subprocess, time
from pathlib import Path
import xml.etree.ElementTree as ET
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
W, H, FPS, DURATION = 1920, 1080, 30, 52
INK, MUTED = '#17313d', '#71828a'
BLUE, GREEN, ORANGE, PURPLE = '#0072b2', '#008b6a', '#ce641d', '#8a63b6'
FONT_ROOT = ROOT / 'public/fonts'
FFMPEG_DEFAULT = '/home/hzhang093/.conda/envs/videogen/lib/python3.10/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2'


def clamp(x): return max(0., min(1., x))
def ease(x):
    x = clamp(x)
    return x*x*(3-2*x)
def ramp(t, start, length=.8): return ease((t-start)/length)
def between(t, start, end): return ramp(t,start,.65)*(1-ramp(t,end,.65))
def rgb(color): return tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))


class Scene:
    def __init__(self, name, file, box, viewport):
        self.name = name
        self.tree = ET.parse(file).getroot()
        self.index = {e.get('id'):e for e in self.tree.iter() if e.get('id')}
        self.box = box
        self.viewport = viewport
        self.scale = min(viewport[2]/box[2],viewport[3]/box[3])
        self.offset = (viewport[0]+(viewport[2]-box[2]*self.scale)/2,
                       viewport[1]+(viewport[3]-box[3]*self.scale)/2)
        self.layers = {}
        self.path_cache = {}

    def xy(self, p):
        return (self.offset[0]+(p[0]-self.box[0])*self.scale,
                self.offset[1]+(p[1]-self.box[1])*self.scale)

    def prepare(self, name, ids, clip=None):
        assert all(i in self.index for i in ids), (name, [i for i in ids if i not in self.index])
        chosen = set(ids)
        def prune(e):
            if e.get('id') in chosen or e.tag.rsplit('}',1)[-1] in ('defs','style'):
                return copy.deepcopy(e)
            c = ET.Element(e.tag, e.attrib)
            for child in e:
                out = prune(child)
                if out is not None: c.append(out)
            return c if len(c) else None
        selected = prune(self.tree)
        # Preserve the SVG's path geometry and embedded source images.
        # The single composite bitmap in the intuition figure is clipped by region.
        selected.set('viewBox',' '.join(map(str,self.box)))
        selected.set('width',str(round(self.box[2]*self.scale)))
        selected.set('height',str(round(self.box[3]*self.scale)))
        if clip:
            defs = ET.Element('{'+NS+'}defs')
            cp = ET.SubElement(defs,'{'+NS+'}clipPath',{'id':'teaser-clip','clipPathUnits':'userSpaceOnUse'})
            ET.SubElement(cp,'{'+NS+'}rect',dict(zip(['x','y','width','height'],map(str,clip))))
            g = ET.Element('{'+NS+'}g',{'clip-path':'url(#teaser-clip)'})
            for child in list(selected):
                if child.tag.rsplit('}',1)[-1] != 'defs':
                    selected.remove(child);g.append(child)
            selected.append(defs);selected.append(g)
        # The reference belongs to the explanatory training picture, never inference.
        for e in selected.iter():
            if e.tag.endswith('text') and e.text == 'Real reference image':
                e.text = 'Training reference'
        raw = ET.tostring(selected)
        handle=Rsvg.Handle.new_from_data(raw)
        pixbuf = handle.get_pixbuf()
        mode = 'RGBA' if pixbuf.get_has_alpha() else 'RGB'
        im = Image.frombytes(mode, (pixbuf.get_width(), pixbuf.get_height()),
                             pixbuf.get_pixels(), 'raw', mode,
                             pixbuf.get_rowstride()).convert('RGBA')
        bounds=im.getbbox()
        if bounds:
            self.layers[name]=(im.crop(bounds),(round(self.offset[0])+bounds[0],round(self.offset[1])+bounds[1]))
        else:
            self.layers[name]=(Image.new('RGBA',(1,1)),(0,0))

    def put(self, frame, name, alpha=1., dy=0):
        if alpha<=.001: return
        image,pos=self.layers[name]
        if alpha<.999:
            image=image.copy();image.putalpha(image.getchannel('A').point(lambda a:int(a*clamp(alpha))))
        frame.paste(image,(pos[0],pos[1]+round(dy)),image)

    def appear(self, frame, name, t, start, length=.8, alpha=1., lift=7):
        a=ramp(t,start,length)
        self.put(frame,name,a*alpha,dy=lift*(1-a))

    def path(self, name):
        if name in self.path_cache:return self.path_cache[name]
        elem=self.index[name]
        if not elem.tag.endswith('path'):elem=next(x for x in elem.iter() if x.tag.endswith('path'))
        tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?',elem.get('d'))
        points=[];i=0;current=None;cmd=None
        while i<len(tokens):
            if tokens[i].isalpha():cmd=tokens[i];i+=1
            if cmd in ('M','L'):
                p=np.array([float(tokens[i]),float(tokens[i+1])]);i+=2
                points.append(p);current=p
                if cmd=='M':cmd='L'
            elif cmd=='Q':
                q=np.array(list(map(float,tokens[i:i+2])));end=np.array(list(map(float,tokens[i+2:i+4])));i+=4
                p=current.copy()
                for t in np.linspace(0,1,81)[1:]:points.append((1-t)**2*p+2*(1-t)*t*q+t*t*end)
                current=end
            elif cmd=='C':
                q=np.array(list(map(float,tokens[i:i+2])));r=np.array(list(map(float,tokens[i+2:i+4])));end=np.array(list(map(float,tokens[i+4:i+6])));i+=6
                p=current.copy()
                for t in np.linspace(0,1,101)[1:]:points.append((1-t)**3*p+3*(1-t)**2*t*q+3*(1-t)*t*t*r+t**3*end)
                current=end
            else:break
        coords=np.array([self.xy(p) for p in points])
        distances=np.r_[0,np.cumsum(np.linalg.norm(np.diff(coords,axis=0),axis=1))]
        self.path_cache[name]=(coords,distances)
        return coords,distances

    def trail(self, frame, name, progress, color, alpha=1, width=4, tail=1., head=True):
        if progress<=0 or alpha<=0:return
        coords,dists=self.path(name)
        total=dists[-1];end=clamp(progress)*total;start=max(0,end-tail*total)
        def at(d):
            j=max(1,min(len(dists)-1,int(np.searchsorted(dists,d))))
            f=(d-dists[j-1])/max(1e-9,dists[j]-dists[j-1])
            return coords[j-1]*(1-f)+coords[j]*f
        ps=[at(start)]+[p for p,d in zip(coords,dists) if start<d<end]+[at(end)]
        # Draw only a small region to keep frame generation inexpensive.
        xs=[p[0] for p in ps];ys=[p[1] for p in ps]
        pad=22;box=(max(0,int(min(xs)-pad)),max(0,int(min(ys)-pad)),min(W,int(max(xs)+pad)),min(H,int(max(ys)+pad)))
        if box[2]<=box[0] or box[3]<=box[1]:return
        layer=Image.new('RGBA',(box[2]-box[0],box[3]-box[1]))
        d=ImageDraw.Draw(layer);p=[(float(q[0]-box[0]),float(q[1]-box[1])) for q in ps];col=(*rgb(color),round(255*alpha))
        d.line(p,fill=col,width=width,joint='curve')
        if head and len(ps)>1:
            endp=ps[-1];tangent=endp-at(max(start,end-5));norm=np.linalg.norm(tangent)
            if norm>1e-7:
                u=tangent/norm;v=np.array([-u[1],u[0]])
                tri=[endp,endp-u*12+v*5,endp-u*12-v*5]
                d.polygon([(q[0]-box[0],q[1]-box[1]) for q in tri],fill=col)
        frame.paste(layer,box[:2],layer)

    def pulse(self, frame, name, progress, color, alpha=1):
        if not 0<progress<1:return
        self.trail(frame,name,progress,color,alpha,5,tail=.13,head=False)
        coords,ds=self.path(name);target=progress*ds[-1]
        j=max(1,min(len(ds)-1,int(np.searchsorted(ds,target))));f=(target-ds[j-1])/max(1e-9,ds[j]-ds[j-1]);p=coords[j-1]*(1-f)+coords[j]*f
        d=ImageDraw.Draw(frame);x,y=map(float,p)
        d.ellipse((x-7,y-7,x+7,y+7),fill=color,outline='white',width=2)

    def halo(self, frame, center, t, start, color, duration=1.3):
        phase=clamp((t-start)/duration)
        if not 0<phase<1:return
        x,y=self.xy(center);rad=10+28*ease(phase)
        layer=Image.new('RGBA',(90,90));d=ImageDraw.Draw(layer)
        d.ellipse((45-rad,45-rad,45+rad,45+rad),outline=(*rgb(color),int(170*(1-phase))),width=3)
        frame.paste(layer,(int(x)-45,int(y)-45),layer)


def fonts(size,bold=False):
    return ImageFont.truetype(str(FONT_ROOT/('manrope-700.ttf' if bold else 'dm-sans-400.ttf')),size)
FONTS={n:fonts(n) for n in [20,22,24,26,28,32]}
FONTS['brand']=fonts(31,True)
FONTS['phase']=fonts(24,True)


def make_scenes():
    print('Preparing original SVG layers…',flush=True)
    a=Scene('intuition',HERE/'sources/intuition.svg',(0,0,486,243.36),(85,155,1750,876))
    a.prepare('surface',['patch_2']+[f'line2d_{i}' for i in range(1,46)]+['text_4'])
    a.prepare('reference',['PathCollection_1','text_1','text_2','text_3','line2d_47','patch_9'])
    a.prepare('noise',['PathCollection_2','text_8','text_9','line2d_49','patch_11'])
    a.prepare('interpolation',['line2d_46'])
    a.prepare('state',['PathCollection_3','text_6','text_7'])
    a.prepare('base',['PathCollection_4','text_5','text_12','line2d_48','patch_10'])
    a.prepare('base-label',['text_10','text_11'])
    a.prepare('error-label',['text_16'])
    a.prepare('correction-label',['patch_7','text_13','text_14'])
    a.prepare('refined',['PathCollection_5','text_15','text_17','line2d_50','patch_12'])
    for name,clip in [('reference',(29.68245,151.340175,82.4985,82.4985)),('base',(34.7895,47.234925,82.4985,82.4985)),('noise',(380.301075,21.049017,67.96305,38.229216)),('refined',(349.0695,130.911975,82.4985,82.4985))]:
        a.prepare(name+'-image',['image27f98d9a72'],clip)
    b=Scene('pipeline',HERE/'sources/method.svg',(8,67,896,379),(90,220,1740,736))
    b.prepare('base',['base-dit','base-label'])
    b.prepare('clean',['clean-box','clean-name-a1','clean-symbol-a']+[f'base-case-frame-{n}-1'+end for n in ['000','040','080'] for end in ['', '-outline']])
    b.prepare('input',['noisy-symbol','noisy-label-1','noisy-label-2']+[f'noisy-case-frame-{n}-1'+end for n in ['000','040','080'] for end in ['', '-outline']])
    b.prepare('refiner',['refiner','refiner-label'])
    b.prepare('sum',['velocity-sum','plus'])
    b.prepare('sampler',['sampler','sampler-label'])
    b.prepare('output',['video-label']+[f'refiner-case-frame-{n}-1'+end for n in ['000','040','080'] for end in ['', '-outline']])
    b.prepare('condition',['shared-condition','condition-a'])
    b.prepare('hidden-label',['hidden-a'])
    b.prepare('base-velocity',['base-velocity'])
    b.prepare('bypass-label',['bypass-velocity'])
    b.prepare('residual-label',['weighted-residual'])
    b.prepare('corrected-label',['corrected-velocity'])
    b.prepare('repeat',['repeat-note'])
    for name in ['noisy-to-base','base-to-clean','hidden-to-refiner','clean-to-refiner','base-bypass','residual-to-sum','corrected-to-sampler','sampler-to-video','condition-to-base','condition-to-refiner','sampler-loop']:
        b.prepare(name,[name,name+'-head'])
    c=Scene('refiner',HERE/'sources/method.svg',(918,58,748,390),(200,200,1520,792))
    for name,ids in {
        'boundary':['refiner-boundary','adaln-label-background','adaln-label'],
        'repeat':['repeat-bracket','repeat-count'],
        'input':['layer-267','clean-b-symbol'],
        'self':['self-attention','self-title-1'],
        'cross':['cross-attention','cross-title-1'],
        'head':['output-head','head-title'],
        'residual':['layer-321','residual-symbol'],
        'hidden':['hidden-b-symbol','fusion','fusion-name'],
        'condition':['condition-b','projection','projection-name'],
        'context':['context-box','context-name','context-junction'],
        'q':['query'], 'kv':['keys-values'],
    }.items():c.prepare(name,ids)
    for name in ['clean-to-self','self-to-cross','cross-to-head','head-to-residual','hidden-to-fusion','condition-to-projection','fusion-to-context','projection-to-context','merged-to-context','context-to-cross']:
        ids=[name]+([name+'-head'] if name+'-head' in c.index else [])
        c.prepare(name,ids)
    print('SVG layers ready.',flush=True)
    return a,b,c


def heading(frame, phase, progress, reference=False):
    d=ImageDraw.Draw(frame)
    d.text((78,46),'CorrFlow',fill=INK,font=FONTS['brand'])
    stages=['Predict','Reflect','Refine']
    for i,label in enumerate(stages):
        x=1330+i*164
        d.text((x,52),label,fill=GREEN if i==phase else '#a5b3b8',font=FONTS['phase'])
        if i<2:d.text((x+108,51),'›',fill='#c1cbce',font=FONTS[26])
    d.line((78,111,W-78,111),fill='#e5ecee',width=2)
    # A quiet time rail is useful even with the native video controls hidden.
    d.rounded_rectangle((80,1046,W-80,1050),radius=2,fill='#e5ecee')
    if progress>0:d.rounded_rectangle((80,1046,80+(W-160)*progress,1050),radius=2,fill=GREEN)
    if reference:d.text((80,1013),'Reference shown for training intuition',fill=MUTED,font=FONTS[20])
    else:d.text((80,1013),'One base forward pass + one lightweight refiner per sampling step',fill=MUTED,font=FONTS[20])
    text='Schematic';d.text((W-80-d.textlength(text,font=FONTS[20]),1013),text,fill='#8b9a9f',font=FONTS[20])


def intuition(a,t):
    frame=Image.new('RGB',(W,H),'white')
    a.appear(frame,'surface',t,0,1.8,alpha=.78,lift=0)
    a.appear(frame,'noise-image',t,.4,1.2)
    a.appear(frame,'noise',t,.4,1.2)
    a.trail(frame,'patch_3',ramp(t,1.8,1.5),'#879eae',width=4)
    a.appear(frame,'state',t,2.8,.75)
    a.halo(frame,(286.768233,84.670414),t,3.0,BLUE)
    a.trail(frame,'patch_4',ramp(t,3.6,2),BLUE,width=7)
    a.appear(frame,'base-label',t,3.9,.9)
    a.appear(frame,'base-image',t,5.1,1.1)
    a.appear(frame,'base',t,5.1,1.1)
    a.halo(frame,(170.32275,134.840475),t,5.2,BLUE)
    a.appear(frame,'reference-image',t,7,.9,alpha=.8)
    a.appear(frame,'reference',t,7,.9,alpha=.8)
    a.appear(frame,'interpolation',t,7.3,1,alpha=.5,lift=0)
    a.trail(frame,'patch_5',ramp(t,8,1.6),ORANGE,width=5)
    a.appear(frame,'error-label',t,8.8,.8)
    a.trail(frame,'patch_6',ramp(t,10.6,2.3),GREEN,width=8)
    a.appear(frame,'correction-label',t,11,.8)
    a.appear(frame,'refined-image',t,12.3,1.1)
    a.appear(frame,'refined',t,12.3,1.1)
    a.halo(frame,(213.53625,169.018425),t,12.7,GREEN,1.8)
    return frame


def edge(scene,frame,name,t,start,color,duration=.8):
    u=ramp(t,start,duration)
    if u>=.995:scene.put(frame,name,.6)
    scene.trail(frame,name,u,color,width=4)


def pipeline(b,t,complete=False):
    frame=Image.new('RGB',(W,H),'white')
    # Faint nodes establish the spatial layout without revealing later operations.
    for name in ['base','clean','refiner','sum','sampler']:
        b.put(frame,name,.075)
    schedule=[('input',0),('base',.6),('condition',1.2),('base-velocity',2.1),('clean',2.5),('hidden-label',3.9),('refiner',4.7)]
    for name,start in schedule:b.appear(frame,name,t,start,.7)
    edge(b,frame,'noisy-to-base',t,.45,BLUE,.65)
    edge(b,frame,'condition-to-base',t,1.6,GREEN,.6)
    edge(b,frame,'base-to-clean',t,1.9,BLUE,.8)
    edge(b,frame,'clean-to-refiner',t,3.7,ORANGE,1.0)
    edge(b,frame,'hidden-to-refiner',t,3.8,BLUE,1.4)
    edge(b,frame,'condition-to-refiner',t,4.1,GREEN,1.1)
    b.halo(frame,(513,253),t,4.9,PURPLE,1.6)
    if complete:
        # In the second visit, a predicted residual rejoins the base velocity.
        b.put(frame,'sum');b.put(frame,'sampler')
    return frame


def refiner(c,t):
    frame=Image.new('RGB',(W,H),'white')
    for n in ['boundary','self','cross','head','hidden','condition','context']:c.put(frame,n,.07)
    c.appear(frame,'boundary',t,0,.8)
    c.appear(frame,'input',t,.4,.8)
    c.appear(frame,'self',t,1.1,.7)
    edge(c,frame,'clean-to-self',t,.7,ORANGE,.9)
    c.appear(frame,'hidden',t,2.1,.8)
    c.appear(frame,'condition',t,2.8,.8)
    edge(c,frame,'hidden-to-fusion',t,2.1,BLUE,.6)
    edge(c,frame,'condition-to-projection',t,2.8,GREEN,.6)
    edge(c,frame,'fusion-to-context',t,3.1,BLUE,.8)
    edge(c,frame,'projection-to-context',t,3.4,GREEN,.8)
    c.appear(frame,'context',t,4.0,.8)
    edge(c,frame,'merged-to-context',t,4.1,GREEN,.9)
    c.appear(frame,'cross',t,4.9,.8)
    c.appear(frame,'q',t,4.8,.65)
    edge(c,frame,'self-to-cross',t,4.6,PURPLE,1.)
    c.appear(frame,'kv',t,5,.7)
    edge(c,frame,'context-to-cross',t,4.9,GREEN,.85)
    c.halo(frame,(1332,253),t,5.4,PURPLE,1.2)
    c.appear(frame,'repeat',t,6.0,.7)
    for delay in [6.2,7.05]:
        c.pulse(frame,'self-to-cross',clamp((t-delay)/.8),PURPLE)
    c.appear(frame,'head',t,7.2,.7)
    edge(c,frame,'cross-to-head',t,7.2,PURPLE,.8)
    edge(c,frame,'head-to-residual',t,8.1,PURPLE,.8)
    c.appear(frame,'residual',t,8.7,.9)
    c.halo(frame,(1600,253),t,9.1,PURPLE,1.2)
    return frame


def sampling(b,t):
    frame=pipeline(b,8,True)
    # The bypass and residual visibly meet BEFORE the sampler update.
    edge(b,frame,'base-bypass',t,.2,BLUE,1.5)
    b.appear(frame,'bypass-label',t,.5,.6)
    edge(b,frame,'residual-to-sum',t,.9,PURPLE,.8)
    b.appear(frame,'residual-label',t,.9,.8)
    b.halo(frame,(607,253),t,1.6,GREEN,1.1)
    b.appear(frame,'corrected-label',t,1.9,.6)
    edge(b,frame,'corrected-to-sampler',t,1.8,GREEN,.9)
    b.appear(frame,'repeat',t,2.6,.8)
    edge(b,frame,'sampler-loop',t,2.7,GREEN,1.)
    # Repeated pulses denote different sampling steps, not repeated base passes
    # for a single step. The sigma rail advances only after the update.
    for cycle in range(3):
        z=t-(3.4+cycle*1.6)
        for name,delay,length,color in [
            ('noisy-to-base',0,.25,BLUE),('base-to-clean',.2,.28,BLUE),
            ('clean-to-refiner',.44,.25,ORANGE),('hidden-to-refiner',.3,.4,BLUE),
            ('base-bypass',.2,.8,BLUE),('condition-to-refiner',.38,.32,GREEN),
            ('residual-to-sum',.7,.3,PURPLE),('corrected-to-sampler',.98,.25,GREEN),
            ('sampler-loop',1.1,.5,GREEN)]:
            b.pulse(frame,name,z/length-delay/length,color)
    edge(b,frame,'sampler-to-video',t,8.2,GREEN,.6)
    b.appear(frame,'output',t,8.6,.9)
    # A minimal schematic noise-level rail; no numerical sampling claims.
    d=ImageDraw.Draw(frame);x1,x2,y=1325,1755,175
    amount=1-clamp((t-3.3)/5.0)
    d.text((1215,y-17),'Noise',fill=MUTED,font=FONTS[24])
    d.line((x1,y,x2,y),fill='#d9e3e6',width=4)
    d.line((x1,y,x1+(x2-x1)*amount,y),fill=GREEN,width=4)
    cx=x1+(x2-x1)*amount;d.ellipse((cx-7,y-7,cx+7,y+7),fill=GREEN)
    d.text((x1-4,y+12),'0',fill=MUTED,font=FONTS[20]);d.text((x2-6,y+12),'1',fill=MUTED,font=FONTS[20])
    return frame


def frame_at(scenes,t):
    a,b,c=scenes
    # Scene cuts use short, calm dissolves. Geometry within scenes animates
    # progressively, with the exact paths and assets from the supplied figures.
    if t<16.3:
        im=intuition(a,t);phase=0 if t<9.8 else 1;reference=True
    elif t<17.3:
        im=Image.blend(intuition(a,16.3),pipeline(b,0),ease(t-16.3));phase=1;reference=t<16.8
    elif t<24.7:
        im=pipeline(b,t-17.3);phase=1;reference=False
    elif t<25.7:
        im=Image.blend(pipeline(b,7.4),refiner(c,0),ease(t-24.7));phase=1;reference=False
    elif t<36.7:
        im=refiner(c,t-25.7);phase=1;reference=False
    elif t<37.7:
        im=Image.blend(refiner(c,11),sampling(b,0),ease(t-36.7));phase=2;reference=False
    else:
        im=sampling(b,t-37.7);phase=2;reference=False
    heading(im,phase,t/DURATION,reference)
    # The final hold gives time to read the complete causal chain.
    return im


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stills',action='store_true',help='Render storyboard frames only.')
    parser.add_argument('--output',type=Path,default=ROOT/'public/media/teaser')
    parser.add_argument('--ffmpeg',default=FFMPEG_DEFAULT)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    scenes=make_scenes()
    timestamps=[0,3,6.5,9.7,13.8,16,19.3,23.9,28.3,31.8,35.6,39.8,43,47,51]
    frame_at(scenes,13.8).save(args.output/'poster.jpg',quality=94)
    if args.stills:
        for t in timestamps:frame_at(scenes,t).save(args.output/f'frame-{t:04.1f}.jpg',quality=92)
        thumbs=Image.new('RGB',(960,270*math.ceil(len(timestamps)/3)),'#edf2f3')
        for i,t in enumerate(timestamps):
            thumb=frame_at(scenes,t).resize((320,180),Image.LANCZOS)
            x=(i%3)*320;y=(i//3)*270
            thumbs.paste(thumb,(x,y+20));ImageDraw.Draw(thumbs).text((x+14,y+212),f'{t:04.1f} s',fill=INK,font=FONTS[22])
        thumbs.save(args.output/'storyboard.jpg',quality=93)
    manifest={'title':'CorrFlow — self-correction inside the sampling loop','durationSeconds':DURATION,'width':W,'height':H,'fps':FPS,'audioTracks':0,'sourceDirectory':'paper/6a843d2839af97b2b532565f/figs','sources':{n:hashlib.sha256((HERE/'sources'/n).read_bytes()).hexdigest() for n in ['intuition.svg','method.svg']},'chapters':[{'start':0,'title':'Prediction, discrepancy, correction'},{'start':17.3,'title':'Reuse the base forward pass'},{'start':25.7,'title':'Inside the refiner'},{'start':37.7,'title':'Correct the velocity, update, repeat'}],'notes':['The original embedded images and mathematical geometry are preserved.','Reference is shown only for training intuition, never as an inference input.','Animated pulses and the sigma rail are schematic, not recorded inference traces.','No synthesized images, score tables, audio, or qualitative-results montage.']}
    (args.output/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if args.stills:
        print('Storyboard ready:',args.output/'storyboard.jpg',flush=True);return
    path=args.output/'corrflow-teaser.mp4'
    command=[args.ffmpeg,'-hide_banner','-loglevel','warning','-n','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','medium','-crf','18','-profile:v','high','-level:v','4.0','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(path)]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    start=time.monotonic()
    try:
        for i in range(DURATION*FPS):
            proc.stdin.write(frame_at(scenes,i/FPS).tobytes())
            if i%(FPS*5)==0:print(f'Encoded {i/FPS:4.0f}/{DURATION}s · elapsed {time.monotonic()-start:.1f}s',flush=True)
        proc.stdin.close();code=proc.wait()
        if code:raise RuntimeError(f'ffmpeg failed: {code}')
    except BaseException:
        proc.terminate();raise
    print('Silent H.264 video ready:',path,flush=True)

if __name__=='__main__':main()
