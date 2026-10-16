# CorrFlow method teaser

79 seconds · 1920 × 1080 · 30 fps · no audio tracks.

The animation uses the original paths and mathematical glyphs from these two supplied figures in `paper/corrflow_arxiv/figs/` (identical to the originally supplied copies in `paper/6a843d2839af97b2b532565f/figs/`):

- `fig_mistakeflow_intuition.svg` → `sources/intuition.svg`
- `mistakeflow_pure_vector_v2.svg` → `sources/method.svg`

The SVG copies are byte-identical to the originals. During rendering, “Real reference image” becomes “Training reference” to clarify its role. The SVG originals are never modified. Nodes appear progressively and vector arrows trace the data flow. The pipeline's static clean-prediction photographs are replaced with moving frames from the first captured step. A large, synchronized comparison then follows every recorded noise step.

## Sequence

| Time | Visual explanation |
| --- | --- |
| 0–17.3 s | Noise → sampling state → imperfect clean prediction → training discrepancy → learned correction. |
| 17.3–25.7 s | One base pass supplies the clean prediction and hidden states; conditioning also enters the refiner. |
| 25.7–37.7 s | Refiner detail: self-attention, hidden-state fusion and condition projection, cross-attention, residual head. |
| 37.7–43 s | Base velocity and predicted residual meet before the sampler; transition to the recorded sampling pair. |
| 43–73 s | All 50 recorded noise steps, 0.6 seconds each; without/with refiner in aligned rows, each with three moving temporal windows. |
| 73–73.8 s | Transition from the last clean prediction to the final videos. |
| 73.8–79 s | Both final videos play together at the source speed, followed by a brief last-frame hold. |

The reference is explanatory training supervision, never an inference input. The corrected clean prediction does not land exactly on the reference. `×K` denotes repetition inside the refiner. The diagram arrows and noisy-input icon remain schematic. From 43 seconds onward, the clean predictions, noise levels, and temporal motion all come from saved inference records.

## Recorded comparison

Source: `outputs/qualitative_clean_predictions/top10_nodynamic_v2_56405_vs_56065_20260914/cases/rank02_12_prompt_012`, the user-selected **V2-O02** watermelon-dessert pair used in the method figure. The without-refiner arm uses seed 3 and scale 0; the with-refiner arm uses seed 12 and scale 0.2. Both use the same prompt, backbone checkpoint, CFG, and schedule. The manifest retains each arm’s seed and initial-noise SHA-256. These details are not overlaid on the video.

These are two complete sampling trajectories from different initial noise, selected for qualitative illustration. The comparison is not a matched-noise causal ablation or a same-state one-step residual ablation. The displayed clean prediction is `x_sigma - sigma * v_guided`, decoded after CFG and the optional refiner, before the ODE update. Step 50 uses the recorded noise level 0.092592582; only the final endpoint is labeled zero. The capture's endpoint verification and identical final/step-50 MP4 hashes are checked during packaging.

Each of the 50 steps occupies exactly 18 output frames. The three panes play source frames 0–9, 36–45, and 71–80 at the source rate of 16 fps. Shared timestamps show the video time in each column; the upper rail shows sampling noise. Both arms always use the same step and source frame indices. There is no interpolation between sampling steps, no synthesized motion, and no cropping of the recorded frames. The last pair plays all 81 source frames.

`sources/sampling-pair.zip` contains 100 unchanged source MP4s plus a manifest with per-file hashes, the verified pairing, and all 50 noise levels. It is a renderer input, not a runtime website asset. It contains no quantitative evaluation scores.

## Reproduce

Dependencies: Python 3, Pillow, NumPy, PyGObject with librsvg/GdkPixbuf, and FFmpeg with libx264 and libvpx-vp9. The existing self-hosted fonts in `public/fonts/` are used. Rendering is CPU-only.

Run from the project root. Choose a new output directory; FFmpeg refuses to overwrite an existing MP4.

```bash
# Inspect 21 keyframes and a contact sheet first.
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

To rebuild the source package from the research workspace, use a new output path:

```bash
python3 scripts/teaser/prepare_sampling.py \
  --case /path/to/top10_nodynamic_v2_56405_vs_56065_20260914/cases/rank02_12_prompt_012 \
  --candidate-id V2-O02 \
  --output /tmp/sampling-pair.zip
```

The renderer checks source hashes and decodes all 100 clips during a complete render. Source MP4s require seekable input, so it creates a small additive cache in `/tmp/corrflow-sampling-clips-*`. It does not delete or change the research outputs.

The deployed assets live in `public/media/teaser/`. The webpage selects H.264 when supported and falls back to WebM. Animation stages and timing are defined in `render_teaser.py`; source SHA-256 hashes and scientific notes are recorded in `provenance.json`.
