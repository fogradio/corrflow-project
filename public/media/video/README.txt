SUPPLEMENTARY QUALITATIVE RESULTS

Viewing
1. Extract the entire ZIP archive (if using the packaged version).
2. Open index.html in a modern browser such as Chrome, Firefox, Safari, or Edge.
No server, installation, account, or Internet connection is required.
Keep index.html and the accompanying folders together.

Contents
- Text to video: FinePhyEval (2 cases), VideoPhy2 (6), VBench (14).
- Image to video: Physics-IQ (10 cases), including input images and ground truth.
- 32 comparison cases, 158 MP4 videos, and 10 input images.

Controls
- Play together / Replay: start all videos in one case from the beginning.
- Pause: pause that case. Pause all: pause every video on the page.
- Speed: 0.5x, 1x, or 1.5x for all videos in the case.
- Starting a case pauses other cases to keep browsing responsive.
- Shorter videos hold their last frame until the longest ends, then the group repeats.
- Group playback uses elapsed video time, with approximate drift correction.
  Original durations and frame rates are retained; actions are not temporally aligned.
- Individual controls, fullscreen, and Open video links are also available.
- Comparisons show three videos per row on desktop, with Ours first.
- On smaller screens, videos wrap into two columns or one column.
- Image-to-video input images appear beside the prompt, above the video comparison.
- Use task, benchmark, and text filters to navigate; section links reveal hidden cases.
- With JavaScript disabled, all cases remain visible and native video controls work.

Media and prompts
This compact package retains all 32 cases and every comparison method.
Videos use H.264 presentation compression (CRF 23, slow preset) where it
reduces file size. Video resolution is capped at 1280 x 720 with the
aspect ratio preserved; videos already smaller than the re-encoded
version are kept unchanged. No videos are trimmed, retimed, or
interpolated; original frame counts and frame rates are retained.
Compression can affect fine texture details. Input images and prompt
files are unchanged. Thumbnails are first-frame previews only. Ours is highlighted in green; ground truth is marked as a reference.
VideoPhy2 displays the original benchmark prompt only, without the expanded
generation description. Original prompt text files remain in the input folders.
No author information, remote scripts, remote fonts, analytics, or network
dependencies have been added to the webpage.
