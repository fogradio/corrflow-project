# CorrFlow method teaser

52 seconds · 1920 × 1080 · 30 fps · no audio tracks.

The animation uses the original paths, mathematical glyphs, and embedded images from these two supplied figures in `paper/6a843d2839af97b2b532565f/figs/`:

- `fig_mistakeflow_intuition.svg` → `sources/intuition.svg`
- `mistakeflow_pure_vector_v2.svg` → `sources/method.svg`

The copies are byte-identical to the originals. During rendering, “Real reference image” becomes “Training reference” to clarify its role. The SVG originals are never modified. Nodes appear progressively; vector arrows trace the data flow; moving pulses mark successive operations and sampling steps.

## Sequence

| Time | Visual explanation |
| --- | --- |
| 0–17.3 s | Noise → sampling state → imperfect clean prediction → training discrepancy → learned correction. |
| 17.3–25.7 s | One base pass supplies the clean prediction and hidden states; conditioning also enters the refiner. |
| 25.7–37.7 s | Refiner detail: self-attention, hidden-state fusion and condition projection, cross-attention, residual head. |
| 37.7–52 s | Base velocity and predicted residual meet before the sampler; successive steps reduce the noise level; the final video appears. |

The reference is explanatory training supervision, never an inference input. The corrected clean prediction does not land exactly on the reference. `×K` denotes repetition inside the refiner. Pulses and the noise rail are schematic, not recorded inference traces. The still images come directly from the supplied method diagrams, not a separate results montage.

## Reproduce

Dependencies: Python 3, Pillow, NumPy, PyGObject with librsvg/GdkPixbuf, and FFmpeg with libx264 and libvpx-vp9. The existing self-hosted fonts in `public/fonts/` are used. Rendering is CPU-only.

Run from the project root. Choose a new output directory; FFmpeg refuses to overwrite an existing MP4.

```bash
# Inspect 15 keyframes and a contact sheet first.
python3 scripts/teaser/render_teaser.py --stills --output /tmp/corrflow-storyboard

# Render H.264, the poster, and provenance.
python3 scripts/teaser/render_teaser.py --ffmpeg /path/to/ffmpeg --output /tmp/corrflow-render

# Add the browser fallback.
/path/to/ffmpeg -n -i /tmp/corrflow-render/corrflow-teaser.mp4 \
  -an -c:v libvpx-vp9 -crf 28 -b:v 0 -row-mt 1 -cpu-used 4 -threads 4 \
  /tmp/corrflow-render/corrflow-teaser.webm

# Decode every frame to verify the deliverables.
/path/to/ffmpeg -v error -i /tmp/corrflow-render/corrflow-teaser.mp4 -f null -
/path/to/ffmpeg -v error -i /tmp/corrflow-render/corrflow-teaser.webm -f null -
```

The deployed assets live in `public/media/teaser/`. The webpage selects H.264 when supported and falls back to WebM. Animation stages and timing are defined in `render_teaser.py`; source SHA-256 hashes and scientific notes are recorded in `provenance.json`.
