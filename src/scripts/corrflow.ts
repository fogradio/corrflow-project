// Progressive enhancement: every sample and comparison remains usable without JS.
const all = <T extends Element>(
  selector: string,
  root: ParentNode = document,
) => Array.from(root.querySelectorAll<T>(selector));
const one = <T extends Element>(
  selector: string,
  root: ParentNode = document,
) => root.querySelector<T>(selector)!;

const teaser = one<HTMLVideoElement>("#method-teaser");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const connection = (
  navigator as Navigator & {
    connection?: { saveData?: boolean };
  }
).connection;
let teaserStarted = false;
teaser.muted = true;
teaser.addEventListener("play", () => {
  teaserStarted = true;
});
// Start once, only when the diagram is in view. Native controls remain in
// charge after a pause; returning to the section never overrides that choice.
const teaserObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) teaser.pause();
      else if (
        entry.intersectionRatio >= 0.55 &&
        !teaserStarted &&
        !reducedMotion.matches &&
        !connection?.saveData &&
        !document.hidden
      ) {
        void teaser.play().catch(() => {
          /* Native play remains available. */
        });
      }
    }
  },
  { threshold: [0, 0.55] },
);
teaserObserver.observe(teaser);
reducedMotion.addEventListener("change", (event) => {
  if (event.matches) teaser.pause();
});

const samples = all<HTMLButtonElement>(".sample");
const filters = all<HTMLButtonElement>("[data-image-filter]");
const expand = one<HTMLButtonElement>("#expand-gallery");
let imageFilter = "all";
let expanded = false;
let filteredSamples = samples;
function filterImages() {
  filteredSamples = samples.filter(
    (sample) =>
      imageFilter === "all" || sample.dataset.imageGroup === imageFilter,
  );
  samples.forEach((sample) => {
    sample.hidden =
      !filteredSamples.includes(sample) ||
      (!expanded && filteredSamples.indexOf(sample) >= 32);
  });
  expand.hidden = filteredSamples.length <= 32;
  expand.setAttribute("aria-expanded", String(expanded));
  expand.innerHTML = expanded
    ? 'Show fewer samples <span aria-hidden="true">↑</span>'
    : `View all ${filteredSamples.length} samples <span aria-hidden="true">↓</span>`;
  one(".sample-count").textContent =
    `Showing ${Math.min(filteredSamples.length, expanded ? Infinity : 32)} of ${filteredSamples.length} samples.`;
}
filters.forEach((button) =>
  button.addEventListener("click", () => {
    imageFilter = button.dataset.imageFilter!;
    expanded = false;
    filters.forEach((filter) => {
      const active = filter === button;
      filter.classList.toggle("active", active);
      filter.setAttribute("aria-pressed", String(active));
    });
    filterImages();
  }),
);
expand.addEventListener("click", () => {
  expanded = !expanded;
  filterImages();
  if (!expanded) one("#images").scrollIntoView({ block: "start" });
});
filterImages();

const dialog = one<HTMLDialogElement>("#image-viewer");
let currentImage = 0;
let focusedSample: HTMLButtonElement | null = null;
function renderImage() {
  const sample = filteredSamples[currentImage];
  const img = one<HTMLImageElement>("img", sample);
  const viewerImage = one<HTMLImageElement>("#viewer-image");
  viewerImage.src = img.src;
  viewerImage.alt = img.alt;
  one("#viewer-title").textContent =
    sample.querySelector(".sample-label")!.firstChild!.textContent;
  one("#viewer-position").textContent =
    `${currentImage + 1} / ${filteredSamples.length}`;
  one<HTMLAnchorElement>("#original-image").href = img.src;
}
function moveImage(direction: number) {
  currentImage =
    (currentImage + direction + filteredSamples.length) %
    filteredSamples.length;
  renderImage();
}
samples.forEach((sample) =>
  sample.addEventListener("click", () => {
    focusedSample = sample;
    currentImage = filteredSamples.indexOf(sample);
    renderImage();
    stopAll();
    dialog.showModal();
    document.body.classList.add("modal-open");
  }),
);
one("#close-viewer").addEventListener("click", () => dialog.close());
one("#previous-image").addEventListener("click", () => moveImage(-1));
one("#next-image").addEventListener("click", () => moveImage(1));
dialog.addEventListener("close", () => {
  document.body.classList.remove("modal-open");
  focusedSample?.focus({ preventScroll: true });
});
dialog.addEventListener("click", (event) => {
  if (event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (
    event.clientX < rect.left ||
    event.clientX > rect.right ||
    event.clientY < rect.top ||
    event.clientY > rect.bottom
  )
    dialog.close();
});
dialog.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    event.preventDefault();
    moveImage(event.key === "ArrowLeft" ? -1 : 1);
  }
});

class Comparison {
  article: HTMLElement;
  videos: HTMLVideoElement[];
  status: HTMLElement;
  speed: HTMLSelectElement;
  timer: number | undefined;
  generation = 0;
  grouped = false;
  starting = false;
  constructor(article: HTMLElement) {
    this.article = article;
    this.videos = all<HTMLVideoElement>("video", article);
    this.status = one(".playback-status", article);
    this.speed = one("[data-speed]", article);
    all<HTMLButtonElement>("[data-video-action]", article).forEach((button) =>
      button.addEventListener("click", () => {
        if (button.dataset.videoAction === "pause") this.pause();
        else void this.play();
      }),
    );
    this.speed.addEventListener("change", () =>
      this.videos.forEach((video) => {
        video.playbackRate = Number(this.speed.value);
      }),
    );
    this.videos.forEach((video) => {
      video.muted = true;
      video.addEventListener("pause", () => {
        if (this.grouped && !this.starting && !video.ended) this.pause();
      });
      video.addEventListener("error", () => {
        this.pause();
        this.status.textContent =
          "This clip could not be loaded. Try its Open video link.";
      });
    });
  }
  pause() {
    this.generation++;
    this.grouped = false;
    this.starting = false;
    window.clearInterval(this.timer);
    this.timer = undefined;
    this.videos.forEach((video) => {
      video.pause();
      video.loop = true;
    });
    all<HTMLButtonElement>("[data-video-action]", this.article).forEach(
      (button) => {
        button.disabled = false;
      },
    );
    this.status.textContent = "";
  }
  waitFor(video: HTMLVideoElement, event: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        clearTimeout(timeout);
        video.removeEventListener(event, success);
        video.removeEventListener("error", failure);
      };
      const success = () => {
        cleanup();
        resolve();
      };
      const failure = () => {
        cleanup();
        reject(new Error("Media unavailable"));
      };
      const timeout = window.setTimeout(failure, 20000);
      video.addEventListener(event, success, { once: true });
      video.addEventListener("error", failure, { once: true });
    });
  }
  async ready(video: HTMLVideoElement) {
    video.preload = "auto";
    if (video.readyState < 1) {
      const loaded = this.waitFor(video, "loadedmetadata");
      video.load();
      await loaded;
    }
    if (video.currentTime > 0) {
      const seeked = this.waitFor(video, "seeked");
      video.currentTime = 0;
      await seeked;
    }
    if (video.readyState < 3) await this.waitFor(video, "canplay");
  }
  async play() {
    stopAll();
    const token = this.generation;
    this.starting = true;
    this.status.textContent = "Preparing comparison…";
    all<HTMLButtonElement>(
      '[data-video-action="play"], [data-video-action="replay"]',
      this.article,
    ).forEach((button) => {
      button.disabled = true;
    });
    try {
      await Promise.all(this.videos.map((video) => this.ready(video)));
      if (token !== this.generation) return;
      this.videos.forEach((video) => {
        video.loop = false;
        video.playbackRate = Number(this.speed.value);
      });
      this.grouped = true;
      const outcomes = await Promise.allSettled(
        this.videos.map((video) => video.play()),
      );
      if (token !== this.generation) return;
      if (outcomes.some((outcome) => outcome.status === "rejected"))
        throw new Error("Playback interrupted");
      this.starting = false;
      all<HTMLButtonElement>("[data-video-action]", this.article).forEach(
        (button) => {
          button.disabled = false;
        },
      );
      this.status.textContent =
        "Playing together · shorter clips hold their final frame.";
      this.timer = window.setInterval(() => {
        if (!this.grouped) return;
        if (this.videos.every((video) => video.ended)) {
          void this.play();
          return;
        }
        const leader = this.videos.reduce((a, b) =>
          a.duration >= b.duration ? a : b,
        );
        this.videos.forEach((video) => {
          if (
            video !== leader &&
            !video.ended &&
            !video.seeking &&
            video.readyState >= 3 &&
            leader.currentTime < video.duration &&
            Math.abs(video.currentTime - leader.currentTime) > 0.2
          )
            video.currentTime = leader.currentTime;
        });
      }, 300);
    } catch {
      if (token !== this.generation) return;
      this.pause();
      this.status.textContent =
        "Group playback is unavailable. Use the individual video controls or Open video links.";
    }
  }
}
const comparisons = all<HTMLElement>(".video-case").map(
  (article) => new Comparison(article),
);
function stopAll() {
  teaser.pause();
  comparisons.forEach((comparison) => comparison.pause());
}
const tabs = all<HTMLButtonElement>("[data-benchmark]");
const panels = all<HTMLElement>("[data-panel]");
function selectCase(panel: HTMLElement) {
  const select = one<HTMLSelectElement>("[data-case-select]", panel);
  all<HTMLElement>(".video-case", panel).forEach((article) => {
    article.hidden = article.dataset.case !== select.value;
  });
}
panels.forEach((panel) => {
  selectCase(panel);
  const select = one<HTMLSelectElement>("[data-case-select]", panel);
  select.addEventListener("change", () => {
    stopAll();
    selectCase(panel);
  });
  all<HTMLButtonElement>("[data-case-direction]", panel).forEach((button) =>
    button.addEventListener("click", () => {
      stopAll();
      select.selectedIndex =
        (select.selectedIndex +
          Number(button.dataset.caseDirection) +
          select.options.length) %
        select.options.length;
      selectCase(panel);
    }),
  );
});
function activateTab(tab: HTMLButtonElement) {
  stopAll();
  tabs.forEach((other) => {
    other.setAttribute("aria-selected", String(other === tab));
    other.tabIndex = other === tab ? 0 : -1;
  });
  panels.forEach((panel) => {
    panel.hidden = panel.dataset.panel !== tab.dataset.benchmark;
  });
}
tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateTab(tab));
  tab.addEventListener("keydown", (event) => {
    let target = index;
    if (event.key === "ArrowRight") target = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft")
      target = (index + tabs.length - 1) % tabs.length;
    else if (event.key === "Home") target = 0;
    else if (event.key === "End") target = tabs.length - 1;
    else return;
    event.preventDefault();
    activateTab(tabs[target]);
    tabs[target].focus();
  });
});
activateTab(tabs[0]);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopAll();
});
// Observe all cases so scrolling away never leaves several decoders running.
const videoObserver = new IntersectionObserver(
  (entries) =>
    entries.forEach((entry) => {
      if (!entry.isIntersecting)
        comparisons
          .find((comparison) => comparison.article === entry.target)
          ?.pause();
    }),
  { threshold: 0 },
);
comparisons.forEach((comparison) => videoObserver.observe(comparison.article));

const copy = one<HTMLButtonElement>("#copy-citation");
copy.addEventListener("click", async () => {
  const content = one<HTMLElement>("#bibtex");
  try {
    if (!navigator.clipboard?.writeText)
      throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(content.textContent ?? "");
    copy.textContent = "Copied ✓";
    one("#copy-status").textContent = "Citation copied to clipboard.";
  } catch {
    const range = document.createRange();
    range.selectNodeContents(content);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
    copy.textContent = "Selected — press Ctrl/Cmd+C";
    one("#copy-status").textContent =
      "Citation selected. Press Control C or Command C to copy.";
  }
  window.setTimeout(() => {
    copy.textContent = "Copy citation";
  }, 3500);
});
