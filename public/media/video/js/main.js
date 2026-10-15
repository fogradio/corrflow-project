/* Optional controls. The complete gallery is present in index.html. */
(() => {
  "use strict";
  const cases = Array.from(document.querySelectorAll(".case"));
  const taskButtons = Array.from(document.querySelectorAll("[data-task-filter]"));
  const benchmarkFilter = document.querySelector("#benchmark-filter");
  const search = document.querySelector("#search");
  const players = new Map();
  let task = "all";

  class CasePlayer {
    constructor(article) {
      this.article = article;
      this.videos = Array.from(article.querySelectorAll("video"));
      this.status = article.querySelector(".playback-status");
      this.speed = article.querySelector(".speed");
      this.generation = 0;
      this.grouped = false;
      this.starting = false;
      this.timer = null;
      this.videos.forEach(video => {
        video.muted = true;
        // Native controls remain independent. A manual pause leaves group mode.
        video.addEventListener("pause", () => {
          if (this.grouped && !this.starting && !video.ended) this.pause();
        });
        video.addEventListener("error", () => {
          this.pause();
          this.status.textContent = "This clip could not be loaded. Try its Open video link.";
        });
      });
      article.querySelectorAll("[data-action]").forEach(button => {
        button.addEventListener("click", () => {
          if (button.dataset.action === "pause") this.pause();
          else this.play();
        });
      });
      this.speed.addEventListener("change", () => {
        this.videos.forEach(video => { video.playbackRate = Number(this.speed.value); });
      });
    }

    pause(clearStatus = true) {
      this.generation += 1;
      this.grouped = false;
      this.starting = false;
      window.clearInterval(this.timer);
      this.timer = null;
      this.videos.forEach(video => {
        video.pause();
        video.loop = true;
      });
      this.article.querySelectorAll('[data-action="play"], [data-action="replay"]').forEach(button => {
        button.disabled = false;
      });
      if (clearStatus) this.status.textContent = "";
    }

    async ready(video) {
      video.preload = "auto";
      if (video.readyState < 1) {
        await new Promise((resolve, reject) => {
          const done = error => {
            clearTimeout(timeout);
            video.removeEventListener("loadedmetadata", success);
            video.removeEventListener("error", failure);
            error ? reject(error) : resolve();
          };
          const success = () => done();
          const failure = () => done(new Error("Media unavailable"));
          const timeout = setTimeout(() => done(new Error("Media timeout")), 15000);
          video.addEventListener("loadedmetadata", success, { once: true });
          video.addEventListener("error", failure, { once: true });
          video.load();
        });
      }
      if (video.currentTime > 0) {
        await new Promise((resolve, reject) => {
          const done = error => {
            clearTimeout(timeout);
            video.removeEventListener("seeked", success);
            error ? reject(error) : resolve();
          };
          const success = () => done();
          const timeout = setTimeout(() => done(new Error("Seek timeout")), 15000);
          video.addEventListener("seeked", success, { once: true });
          video.currentTime = 0;
        });
      }
      if (video.readyState >= 3) return;
      await new Promise((resolve, reject) => {
        const done = error => {
          clearTimeout(timeout);
          video.removeEventListener("canplay", success);
          video.removeEventListener("error", failure);
          error ? reject(error) : resolve();
        };
        const success = () => done();
        const failure = () => done(new Error("Media unavailable"));
        const timeout = setTimeout(() => done(new Error("Media timeout")), 15000);
        video.addEventListener("canplay", success, { once: true });
        video.addEventListener("error", failure, { once: true });
      });
    }

    async play() {
      // A single case plays at a time to keep a large local gallery responsive.
      players.forEach(player => player.pause());
      const token = this.generation;
      this.starting = true;
      this.status.textContent = "Preparing this comparison…";
      this.article.querySelectorAll('[data-action="play"], [data-action="replay"]').forEach(button => {
        button.disabled = true;
      });
      try {
        await Promise.all(this.videos.map(video => this.ready(video)));
        if (token !== this.generation) return;
        this.videos.forEach(video => {
          video.loop = false;
          video.playbackRate = Number(this.speed.value);
        });
        this.grouped = true;
        const outcomes = await Promise.allSettled(this.videos.map(video => video.play()));
        if (token !== this.generation) return;
        if (outcomes.some(result => result.status === "rejected")) {
          throw new Error("Playback interrupted");
        }
        this.starting = false;
        this.article.querySelectorAll('[data-action="play"], [data-action="replay"]').forEach(button => {
          button.disabled = false;
        });
        this.status.textContent = "Playing together · shorter clips hold their final frame until all clips finish.";
        // Correct modest decoder drift against the longest clip; never stretch durations.
        this.timer = window.setInterval(() => {
          if (!this.grouped) return;
          if (this.videos.every(video => video.ended)) {
            this.play();
            return;
          }
          const leader = this.videos.reduce((a, b) => a.duration >= b.duration ? a : b);
          const time = leader.currentTime;
          this.videos.forEach(video => {
            if (video !== leader && !video.ended && !video.seeking && video.readyState >= 3 &&
                time < video.duration && Math.abs(video.currentTime - time) > 0.2) {
              video.currentTime = time;
            }
          });
        }, 300);
      } catch (error) {
        if (token !== this.generation) return;
        this.pause();
        this.status.textContent = "Group playback is unavailable. Use the individual video controls or Open video links.";
      }
    }
  }

  cases.forEach(article => {
    players.set(article, new CasePlayer(article));
    article.dataset.search = article.textContent.toLocaleLowerCase();
  });

  function applyFilters() {
    const query = search.value.trim().toLocaleLowerCase();
    let shown = 0;
    cases.forEach(article => {
      const visible = (task === "all" || article.dataset.task === task) &&
        (benchmarkFilter.value === "all" || article.dataset.benchmark === benchmarkFilter.value) &&
        article.dataset.search.includes(query);
      article.hidden = !visible;
      if (visible) shown += 1;
      else players.get(article).pause();
    });
    document.querySelectorAll(".benchmark, .task-section").forEach(section => {
      section.hidden = !Array.from(section.querySelectorAll(".case")).some(article => !article.hidden);
    });
    taskButtons.forEach(button => {
      const active = button.dataset.taskFilter === task;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.querySelector("#result-count").textContent = `Showing ${shown} of ${cases.length} cases`;
    document.querySelector("#empty-state").hidden = shown > 0;
  }

  taskButtons.forEach(button => button.addEventListener("click", () => {
    task = button.dataset.taskFilter;
    benchmarkFilter.value = "all";
    applyFilters();
  }));
  benchmarkFilter.addEventListener("change", () => {
    if (benchmarkFilter.value !== "all") {
      task = cases.find(article => article.dataset.benchmark === benchmarkFilter.value).dataset.task;
    }
    applyFilters();
  });
  search.addEventListener("input", applyFilters);
  document.querySelector("#reset-filters").addEventListener("click", () => {
    task = "all";
    search.value = "";
    benchmarkFilter.value = "all";
    applyFilters();
  });
  document.querySelector("#pause-all").addEventListener("click", () => players.forEach(player => player.pause()));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) players.forEach(player => player.pause());
  });
  // Anchor navigation reveals its target even after a previous filter hid it.
  function revealAnchor() {
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!target || !target.closest(".task-section")) return;
    const section = target.closest(".task-section");
    task = section.id;
    search.value = "";
    benchmarkFilter.value = "all";
    applyFilters();
    requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
  }
  window.addEventListener("hashchange", revealAnchor);
  document.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener("click", () => {
    if (link.hash === location.hash) revealAnchor();
  }));
  document.documentElement.classList.add("js-ready");
  applyFilters();
  if (location.hash) revealAnchor();
})();
