# CorrFlow project page

Project page for **CorrFlow: Self-Correcting Flow Matching** (Hangwei Zhang, Nathan Rouillé, Chuanxia Zheng).

## Run locally

Use Node.js 22.12+ (the existing GitHub Pages workflow uses Node 24).

```bash
npm install
ASTRO_TELEMETRY_DISABLED=1 npm run dev
```

Open the URL printed by Astro, including `/corrflow-project/`.

```bash
ASTRO_TELEMETRY_DISABLED=1 npm run build
ASTRO_TELEMETRY_DISABLED=1 npm run preview
```

`npm run build` runs Astro's type checks before generating the static site in `dist/`.

## Content

- `src/pages/index.astro`: paper information, method, image and video galleries, citation.
- `src/styles/corrflow.css`: responsive page styles.
- `src/scripts/corrflow.ts`: teaser playback, image filtering/viewer, video selection/synchronized playback, citation copying.
- `src/data/images.json`: 64 curated generated images with ImageNet class labels.
- `src/data/videos.json`: all 32 supplementary cases and their 158 comparison videos.
- `public/paper/corrflow.pdf`: supplied paper's `corrflow_arxiv/main.pdf`.
- `public/media/teaser/`: silent 79-second, 1920 × 1080, 30 fps method animation (H.264 MP4 and VP9 WebM), poster, and provenance.
- `scripts/teaser/`: reproducible animation renderer and the two exact SVG source files requested for this teaser. See [rendering instructions](scripts/teaser/README.md).
- `public/media/figures/`: earlier paper figure copies, retained as assets; the page now explains the method through the teaser.
- `public/media/images/provenance.json`: exact image source, checkpoint, sampling settings, sample indices, and pixel hashes.
- `public/media/video/`: a self-contained copy of `supplementary_anon_under100mb`; originals are unchanged.
- `public/fonts/`: self-hosted DM Sans and Manrope with their SIL Open Font Licenses.

Images come only from `RAEv2/results/stage2/offline_eval/gen_npz/in256-k7-ft-copilot-full-ep80_ema_copilot.npz`: final 80-epoch fine-tuning after 80-epoch base pretraining, EMA base + EMA refiner, internal guidance 1.78, 100 sampling steps. This is a curated showcase, not a random evaluation sample. Images are lossless WebP exports with unchanged pixels. No quantitative result tables or metrics are rendered on the page.

Video results appear before the image gallery in four expanded chapters: VideoPhy2, Physics-IQ, FinePhyEval, and VBench. Chapter links jump directly to each task; every chapter has its own case selector and synchronized playback controls. Page and chapter headings are centered. Playback starts only on request. Changing cases, scrolling away, or hiding the browser tab pauses playback. Native controls and video links remain available. Without JavaScript, all images and cases are visible.

The teaser sits before the abstract and replaces the static method section and hero sample strip. It animates prediction and correction, reuse of the base forward pass, and the refiner's attention blocks. It then follows all 50 captured sampling steps of the diagram's watermelon case, with synchronized without/with-refiner rows and three moving temporal windows. The selected pair is V2-O02 from the candidate review; its source provenance is recorded with the renderer. Text is limited to diagram labels, timing, and brief annotations. It contains no audio track or results montage. It starts once when sufficiently in view, respects reduced-motion and data-saving preferences, and pauses when scrolled away. Native controls support pause, seeking, fullscreen, and replay; a download link provides the MP4.

## GitHub Pages

The Astro config targets `https://fogradio.github.io/corrflow-project/`. Asset URLs respect Astro's `BASE_URL`. The existing `.github/workflows/astro.yml` builds and deploys on pushes to `main`. All runtime assets are local, with no external CDN or analytics requirement.

The site retains the original Astro research template and its reusable components; only `src/pages/index.astro` is the live page. `src/paper.mdx` and `documentation.md` are the original template examples.

## Validation in this workspace

- `npm run build`: passed (0 errors / 0 warnings; one pre-existing unused-field hint in a template component).
- Expanded video chapters: 49 Firefox checks passed, covering chapter order and visibility, independent example selection, chapter anchors, centered headings and overflow at 320–1440px, image viewer/filtering, citation copying, local assets, and the no-JavaScript fallback. All 32 cases and 158 comparison videos are retained.
- Playback recheck after the chapter update: Chromium timed out during page navigation, before the real playback checks could run. Synchronized video playback was not reverified in this environment for this update.
- Generated HTML: 567 local resource references checked; no missing assets, broken anchors, or duplicate IDs.
- Latest teaser: 12 Firefox checks passed, covering real playback, 11 scene seeks, temporal movement within a fixed noise step in both rows, changes across sampling steps, reduced-motion behavior, pause offscreen, desktop/mobile overflow, and browser/HTTP errors. Earlier page-wide checks also covered the image viewer, video gallery, citation action, and responsive layouts.
- Teaser: both Python scripts compile; MP4 and WebM fully decode (2,370 frames each, 79 seconds, no audio streams). All 100 packaged source clips match their hashes and decode during rendering. Every one of the 50 steps occupies exactly 18 frames, with matched temporal indices between arms. SVG source copies match the requested originals byte for byte.
- All 158 MP4 files passed a CPU first-frame decode check with FFmpeg.
- Chromium: real H.264 playback passed for a five-video comparison, including synchronized playback, speed changes, pause, replay, and stopping playback when switching benchmark tabs. Firefox was used for visual checks because its cluster installation lacks H.264 support.
- Teaser browser limitation: the subsequent Chromium check timed out both on whole-page navigation and isolated media readiness in this cluster. The new teaser's browser playback/seek checks passed in Firefox using WebM; its MP4 passed full FFmpeg decoding, but the new MP4's Chromium playback is not verified here.
