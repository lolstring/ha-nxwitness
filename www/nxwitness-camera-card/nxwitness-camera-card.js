class NxWitnessCameraCard extends HTMLElement {
  static getStubConfig() {
    return {
      mode: "single-camera",
      entity_id: "",
      title: "",
    };
  }

  static getConfigElement() {
    return document.createElement("nxwitness-camera-card-editor");
  }

  setConfig(config) {
    const prevEntityId = this._config?.entity_id;
    const prevMode = this._config?.mode;
    this._config = {
      mode: config.mode || (config.video_wall_id ? "video-wall" : "single-camera"),
      title: config.title || "NX Witness",
      stream: config.stream || "primary",
      format: config.format || "mp4",
      resolution: config.resolution || "1080p",
      duration_ms: config.duration_ms || 300000,
      show_name: true,
      show_timestamp: true,
      show_play: true,
      show_live: true,
      show_snapshot: true,
      show_mute: true,
      show_quality: true,
      show_fullscreen: true,
      ...config,
    };
    if (this._root && this._hass && (
      prevEntityId !== this._config.entity_id ||
      prevMode !== this._config.mode
    )) {
      this._resolveEntityAndLoad();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._root) {
      this._resolveEntityAndLoad();
    }
  }

  _resolveEntityAndLoad() {
    if (this._config.entity_id && !this._config.device_id) {
      const state = this._hass.states[this._config.entity_id];
      if (state?.attributes) {
        const snapPath = state.attributes.snapshot_request?.path ?? "";
        const parts = snapPath.split("/");
        this._config = {
          ...this._config,
          config_entry_id: parts[4] ?? "",
          device_id: state.attributes.nx_device_id ?? parts[5] ?? "",
          title: this._config.title || state.attributes.friendly_name || this._config.entity_id,
        };
      }
    }
    this._renderShell();
    this._load();
  }

  getCardSize() {
    return this._config.mode === "video-wall" ? 6 : 4;
  }

  disconnectedCallback() {
    if (this._cleanupFns) {
      this._cleanupFns.forEach(fn => { try { fn(); } catch (_) {} });
      this._cleanupFns = [];
    }
  }

  _renderShell() {
    if (!this._root) {
      this._root = this.attachShadow({ mode: "open" });
    }
    this._root.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          background:
            radial-gradient(circle at top left, rgba(28, 126, 214, 0.18), transparent 30%),
            linear-gradient(160deg, rgba(12, 18, 28, 0.96), rgba(22, 30, 45, 0.98));
          color: #eff4ff;
          overflow: hidden;
        }
        .wrap {
          padding: 16px;
          display: grid;
          gap: 14px;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
        }
        .title {
          font: 600 1.05rem/1.2 "Segoe UI", sans-serif;
          letter-spacing: 0.02em;
        }
        .controls {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          align-items: center;
        }
        button, input, select {
          background: rgba(255, 255, 255, 0.08);
          color: inherit;
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 10px;
          padding: 8px 10px;
        }
        button {
          cursor: pointer;
        }
        .video {
          width: 100%;
          min-height: 280px;
          border: 0;
          border-radius: 14px;
          background: #070b12;
          object-fit: cover;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 12px;
        }
        .tile {
          position: relative;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 14px;
          overflow: hidden;
          border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .tile img, .tile video {
          display: block;
          width: 100%;
          aspect-ratio: 16 / 9;
          object-fit: cover;
          background: #05070b;
        }
        .tile-name {
          position: absolute;
          left: 10px;
          bottom: 10px;
          padding: 6px 8px;
          border-radius: 8px;
          background: rgba(0, 0, 0, 0.52);
          font: 600 0.8rem/1.2 "Segoe UI", sans-serif;
        }
        .meta {
          opacity: 0.8;
          font: 500 0.82rem/1.4 "Segoe UI", sans-serif;
        }
        .hidden {
          display: none;
        }

        /* ===== Cinematic single-camera mode ===== */
        ha-card.nx-cinematic > .wrap {
          padding: 0;
          gap: 0;
        }
        ha-card.nx-cinematic .body {
          line-height: 0;
        }
        .nx-cinematic-body {
          position: relative;
          width: 100%;
          background: #05070b;
          overflow: hidden;
          user-select: none;
          -webkit-user-select: none;
        }
        .nx-c-video {
          width: 100%;
          display: block;
          aspect-ratio: 16 / 9;
          object-fit: cover;
          background: #05070b;
          cursor: default;
        }
        /* always-visible overlays */
        .nx-c-badge {
          position: absolute; top: 10px; left: 10px;
          display: flex; align-items: center; gap: 5px;
          background: rgba(192,57,43,.88);
          color: #fff;
          font: 700 10px/1 "Segoe UI", sans-serif;
          letter-spacing: .12em; text-transform: uppercase;
          padding: 4px 8px; border-radius: 4px;
          pointer-events: none; z-index: 3;
        }
        .nx-c-badge.nx-archive { background: rgba(28,96,180,.88); }
        .nx-c-badge::before {
          content: ""; width: 6px; height: 6px;
          border-radius: 50%; background: #fff; flex-shrink: 0;
          animation: nx-blink 1.4s infinite;
        }
        .nx-c-badge.nx-archive::before { animation: none; opacity: .65; }
        @keyframes nx-blink { 50% { opacity: .25; } }
        .nx-c-ts {
          position: absolute; top: 10px; right: 10px;
          background: rgba(0,0,0,.55); color: #fff;
          font: 500 10px/1 "Segoe UI", monospace;
          letter-spacing: .06em; padding: 4px 8px; border-radius: 4px;
          pointer-events: none; z-index: 3;
        }
        .nx-c-label {
          position: absolute; left: 10px; bottom: 10px;
          background: rgba(0,0,0,.52); color: #fff;
          font: 600 10px/1.2 "Segoe UI", monospace;
          letter-spacing: .06em; padding: 4px 8px; border-radius: 4px;
          transition: opacity .2s; pointer-events: none; z-index: 3;
        }
        .nx-cinematic-body.show-controls .nx-c-label { opacity: 0; }

        /* glass pill toolbar — top centre, hover-reveal */
        .nx-c-toolbar {
          position: absolute; top: 10px; left: 50%;
          transform: translateX(-50%) translateY(-6px);
          display: flex; gap: 5px; padding: 5px 8px;
          background: rgba(20,18,15,.84);
          border: 1px solid rgba(255,255,255,.18);
          border-radius: 999px;
          opacity: 0; pointer-events: none;
          transition: opacity .25s ease, transform .25s ease;
          z-index: 4; white-space: nowrap;
        }
        .nx-cinematic-body.show-controls .nx-c-toolbar {
          opacity: 1; transform: translateX(-50%) translateY(0);
          pointer-events: auto;
        }
        .nx-c-btn {
          width: 32px; height: 32px; border-radius: 50%;
          background: rgba(255,255,255,.10);
          border: 1px solid rgba(255,255,255,.14);
          color: #fff;
          display: flex; align-items: center; justify-content: center;
          cursor: pointer; flex-shrink: 0;
          transition: background .15s;
          position: relative; padding: 0;
        }
        .nx-c-btn:hover { background: rgba(255,255,255,.22); }
        .nx-c-btn.nx-active { background: rgba(192,57,43,.75); border-color: rgba(192,57,43,.5); }
        .nx-c-btn.nx-seeking { background: rgba(28,96,180,.82); border-color: rgba(28,96,180,.55); }
        .nx-c-btn svg {
          width: 15px; height: 15px;
          stroke: currentColor; fill: none;
          stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round;
          pointer-events: none;
        }
        .nx-c-btn[data-tip]:hover::after {
          content: attr(data-tip);
          position: absolute; top: calc(100% + 7px); left: 50%;
          transform: translateX(-50%);
          background: rgba(0,0,0,.88); color: #fff;
          font: 500 11px/1.3 "Segoe UI", sans-serif;
          white-space: nowrap; padding: 4px 8px; border-radius: 5px;
          pointer-events: none; z-index: 10;
        }

        /* glass timeline — bottom, hover-reveal */
        .nx-c-timeline {
          position: absolute; left: 12px; right: 12px; bottom: 12px;
          background: rgba(20,18,15,.86);
          border: 1px solid rgba(255,255,255,.18);
          border-radius: 12px;
          padding: 8px 12px 10px;
          color: #f0ece4;
          opacity: 0; pointer-events: none;
          transform: translateY(10px);
          transition: transform .28s ease, opacity .25s ease;
          z-index: 4;
        }
        .nx-cinematic-body.show-controls .nx-c-timeline {
          opacity: 1; transform: translateY(0); pointer-events: auto;
        }
        .nx-c-tl-meta {
          display: flex; justify-content: space-between; align-items: center;
          font: 500 10px/1 "Segoe UI", monospace; letter-spacing: .06em;
          color: rgba(255,255,255,.8); margin-bottom: 6px;
        }
        .nx-c-tl-mid {
          color: rgba(255,255,255,.5); font-size: 9px;
          text-transform: uppercase; letter-spacing: .1em;
        }
        .nx-c-tl-track {
          position: relative; height: 28px;
          background: repeating-linear-gradient(90deg,rgba(255,255,255,.06) 0 1px,transparent 1px 40px);
          border-radius: 5px; border: 1px solid rgba(255,255,255,.12);
          cursor: crosshair; overflow: visible;
        }
        .nx-c-tl-rec {
          position: absolute; top: 4px; bottom: 4px;
          background: rgba(255,255,255,.13); border-radius: 3px;
          pointer-events: none;
        }
        .nx-c-tl-mark {
          position: absolute; top: 3px; bottom: 3px; width: 3px;
          border-radius: 2px; cursor: pointer;
        }
        .nx-c-tl-mark.motion { background:#e64a3b; box-shadow:0 0 5px rgba(230,74,59,.6); }
        .nx-c-tl-mark.book   { background:#3aa376; box-shadow:0 0 5px rgba(58,163,118,.6); }
        .nx-c-tl-mark.audio  { background:#f5d76e; box-shadow:0 0 5px rgba(245,215,110,.6); }
        .nx-c-tl-head {
          position: absolute; top: -3px; bottom: -3px; width: 2px;
          background: #fff; pointer-events: none; z-index: 2;
          transition: left .08s linear;
        }
        .nx-c-tl-head::before {
          content: "";
          position: absolute; top: -3px; left: -5px; width: 12px; height: 6px;
          background: #fff; border-radius: 2px;
        }
        .nx-c-tl-bubble {
          position: absolute; bottom: calc(100% + 6px); left: 50%;
          transform: translateX(-50%);
          background: #fff; color: #1a1814;
          font: 600 10px/1 "Segoe UI", monospace;
          padding: 3px 7px; border-radius: 4px; white-space: nowrap;
          pointer-events: none;
        }
        .nx-c-tl-zoom-row {
          display: flex; justify-content: flex-end; margin-top: 7px;
        }
        .nx-c-tl-zoom { display: flex; gap: 2px; }
        .nx-c-tl-zoom-btn {
          background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.16);
          padding: 2px 7px; border-radius: 10px;
          color: rgba(255,255,255,.75); cursor: pointer;
          font: 500 10px/1.6 "Segoe UI", monospace;
          transition: background .15s;
        }
        .nx-c-tl-zoom-btn:hover,
        .nx-c-tl-zoom-btn.nx-active {
          background: rgba(255,255,255,.22); color: #fff;
        }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="header">
            <div class="title"></div>
            <div class="controls"></div>
          </div>
          <div class="body"></div>
          <div class="meta"></div>
        </div>
      </ha-card>
    `;
    this._titleEl = this._root.querySelector(".title");
    this._controlsEl = this._root.querySelector(".controls");
    this._bodyEl = this._root.querySelector(".body");
    this._metaEl = this._root.querySelector(".meta");
  }

  async _load() {
    if (this._cleanupFns) {
      this._cleanupFns.forEach(fn => { try { fn(); } catch (_) {} });
    }
    this._cleanupFns = [];

    this._titleEl.textContent = this._config.title;
    if (this._config.mode === "video-wall") {
      await this._loadVideoWall();
      return;
    }
    await this._loadSingleCamera();
  }

  async _loadSingleCamera() {
    await this._loadCinematic();
  }

  async _loadCinematic() {
    const cfg = this._config;

    const haCard = this._root.querySelector("ha-card");
    haCard.classList.add("nx-cinematic");
    this._titleEl.hidden = true;
    this._controlsEl.hidden = true;
    this._metaEl.hidden = true;

    this._bodyEl.innerHTML = `
      <div class="nx-cinematic-body" id="nx-cinematic">
        <video class="nx-c-video" autoplay muted playsinline></video>
        <div class="nx-c-badge" id="nx-c-badge">LIVE</div>
        ${cfg.show_timestamp !== false ? `<div class="nx-c-ts" id="nx-c-ts"></div>` : ""}
        ${cfg.show_name !== false ? `<div class="nx-c-label" id="nx-c-label">${esc(cfg.title)}</div>` : ""}

        <div class="nx-c-toolbar">
          ${cfg.show_play !== false ? `<button class="nx-c-btn" id="nx-c-play" data-tip="Pause" aria-label="Pause / play">
            <svg viewBox="0 0 24 24"><path d="M8 5v14M16 5v14"/></svg>
          </button>` : ""}
          ${cfg.show_live !== false ? `<button class="nx-c-btn" id="nx-c-golive" data-tip="Jump to live" aria-label="Jump to live">
            <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="7.5" stroke-dasharray="3 2"/></svg>
          </button>` : ""}
          ${cfg.show_snapshot !== false ? `<button class="nx-c-btn" id="nx-c-snap" data-tip="Open snapshot" aria-label="Snapshot">
            <svg viewBox="0 0 24 24"><path d="M4 8h4l2-2h4l2 2h4v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>
          </button>` : ""}
          ${cfg.show_mute !== false ? `<button class="nx-c-btn nx-active" id="nx-c-mute" data-tip="Unmute" aria-label="Toggle mute">
            <svg viewBox="0 0 24 24"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 8l4 8M21 8l-4 8"/></svg>
          </button>` : ""}
          ${cfg.show_quality !== false ? `<button class="nx-c-btn" id="nx-c-qual" data-tip="Switch to Secondary stream" aria-label="Toggle quality">
            <svg viewBox="0 0 24 24"><path d="M4 19l4-6 4 3 4-8 4 11"/></svg>
          </button>` : ""}
          ${cfg.show_fullscreen !== false ? `<button class="nx-c-btn" id="nx-c-full" data-tip="Fullscreen" aria-label="Fullscreen">
            <svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>
          </button>` : ""}
        </div>

        <div class="nx-c-timeline">
          <div class="nx-c-tl-meta">
            <span id="nx-c-tl-start">--:--:--</span>
            <span class="nx-c-tl-mid" id="nx-c-tl-mid">loading footage\u2026</span>
            <span id="nx-c-tl-end">NOW</span>
          </div>
          <div class="nx-c-tl-track" id="nx-c-tl-track">
            <div class="nx-c-tl-head" id="nx-c-tl-head" style="left:100%">
              <div class="nx-c-tl-bubble" id="nx-c-tl-bubble">LIVE</div>
            </div>
          </div>
          <div class="nx-c-tl-zoom-row">
            <div class="nx-c-tl-zoom" id="nx-c-tl-zoom">
              <button class="nx-c-tl-zoom-btn nx-active" data-hours="1">1H</button>
              <button class="nx-c-tl-zoom-btn" data-hours="6">6H</button>
              <button class="nx-c-tl-zoom-btn" data-hours="24">24H</button>
              <button class="nx-c-tl-zoom-btn" data-hours="168">7D</button>
            </div>
          </div>
        </div>
      </div>
    `;

    const body    = this._root.getElementById("nx-cinematic");
    const video   = body.querySelector(".nx-c-video");
    const badge   = body.querySelector("#nx-c-badge");
    const tsEl    = body.querySelector("#nx-c-ts");
    const playBtn = body.querySelector("#nx-c-play");
    const liveBtn = body.querySelector("#nx-c-golive");
    const snapBtn = body.querySelector("#nx-c-snap");
    const muteBtn = body.querySelector("#nx-c-mute");
    const qualBtn = body.querySelector("#nx-c-qual");
    const fullBtn = body.querySelector("#nx-c-full");
    const track   = body.querySelector("#nx-c-tl-track");
    const head    = body.querySelector("#nx-c-tl-head");
    const bubble  = body.querySelector("#nx-c-tl-bubble");
    const tlMid   = body.querySelector("#nx-c-tl-mid");
    const tlStart = body.querySelector("#nx-c-tl-start");

    let zoomHours    = 1;
    let tlStartMs    = 0;
    let tlEndMs      = 0;
    let activeStream = cfg.stream || "primary";
    let isMuted      = true;
    let isLive       = true;
    let positionMs   = null;   // null = live
    let liveStartWall = Date.now(); // wall-clock ms when live stream began

    if (qualBtn) {
      qualBtn.classList.toggle("nx-active", activeStream === "secondary");
      qualBtn.dataset.tip = activeStream === "secondary" ? "Switch to Primary stream" : "Switch to Secondary stream";
    }

    const buildLivePath = () =>
      `/api/nxwitness/stream/${cfg.config_entry_id}/${cfg.device_id}` +
      `?stream=${encodeURIComponent(activeStream)}` +
      `&format=${encodeURIComponent(cfg.format || "mp4")}` +
      `&resolution=${encodeURIComponent(cfg.resolution || "1080p")}` +
      `&realTimeOptimization=true&dropLateFrames=1`;

    const buildArchivePath = (posMs) =>
      buildLivePath() +
      `&position_ms=${posMs}` +
      `&duration_ms=${cfg.duration_ms || 300000}` +
      `&accurate_seek=true`;

    const buildImagePath = (tsMs = -1) => {
      let p = `/api/nxwitness/image/${cfg.config_entry_id}/${cfg.device_id}` +
              `?size=${encodeURIComponent(cfg.resolution || "1080p")}`;
      if (tsMs !== -1) p += `&timestamp_ms=${tsMs}`;
      return p;
    };

    const buildFootagePath = (startMs, endMs) =>
      `/api/nxwitness/footage/${cfg.config_entry_id}/${cfg.device_id}` +
      `?startTimeMs=${startMs}&endTimeMs=${endMs}`;

    const updateTs = () => {
      if (!tsEl) return;
      if (isLive) {
        // Sync to actual decoded video position to avoid wall-clock desync
        const videoMs = video.readyState >= 2 && video.currentTime > 0
          ? liveStartWall + video.currentTime * 1000
          : Date.now();
        tsEl.textContent = _nxFmtDateTime(videoMs);
      } else {
        tsEl.textContent = _nxFmtDateTime(positionMs ?? Date.now());
      }
    };
    updateTs();
    const tsTimer = setInterval(updateTs, 1000);
    this._cleanupFns.push(() => clearInterval(tsTimer));

    let idleTimer = null;
    const showCtrl = () => {
      body.classList.add("show-controls");
      clearTimeout(idleTimer);
      idleTimer = setTimeout(() => {
        if (!document.fullscreenElement) body.classList.remove("show-controls");
      }, 3000);
    };
    body.addEventListener("mousemove",  showCtrl);
    body.addEventListener("mouseenter", showCtrl);
    body.addEventListener("mouseleave", () => {
      clearTimeout(idleTimer);
      if (!document.fullscreenElement) body.classList.remove("show-controls");
    });

    const loadLive = async () => {
      const path = await this._signPath(buildLivePath());
      video.src = path;
      video.play().catch(() => {});
      isLive = true;
      positionMs = null;
      liveStartWall = Date.now();
      liveBtn?.classList.remove("nx-seeking");
      badge.className = "nx-c-badge";
      badge.textContent = "LIVE";
      head.style.left = "100%";
      bubble.textContent = "LIVE";
      updateTs();
    };
    await loadLive();

    const seekTo = async (ms) => {
      isLive = false;
      positionMs = ms;
      liveBtn?.classList.add("nx-seeking");
      badge.className = "nx-c-badge nx-archive";
      badge.textContent = "REC";
      const path = await this._signPath(buildArchivePath(ms));
      video.src = path;
      video.play().catch(() => {});
      updateTs();
      if (tlStartMs && tlEndMs) {
        const pct = Math.max(0, Math.min(100, ((ms - tlStartMs) / (tlEndMs - tlStartMs)) * 100));
        head.style.left = `${pct}%`;
        bubble.textContent = _nxFmtTime(ms);
      }
    };

    playBtn?.addEventListener("click", () => {
      if (video.paused) {
        video.play().catch(() => {});
        playBtn.querySelector("svg").innerHTML = `<path d="M8 5v14M16 5v14"/>`;
        playBtn.dataset.tip = "Pause";
      } else {
        video.pause();
        playBtn.querySelector("svg").innerHTML = `<path d="M5 3l14 9-14 9V3z"/>`;
        playBtn.dataset.tip = "Play";
      }
    });

    liveBtn?.addEventListener("click", loadLive);

    snapBtn?.addEventListener("click", async () => {
      const tsMs = isLive ? -1 : (positionMs ?? -1);
      const path = await this._signPath(buildImagePath(tsMs));
      window.open(path, "_blank", "noopener,noreferrer");
    });

    muteBtn?.addEventListener("click", () => {
      isMuted = !isMuted;
      video.muted = isMuted;
      muteBtn.querySelector("svg").innerHTML = isMuted
        ? `<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 8l4 8M21 8l-4 8"/>`
        : `<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M18 9c2 1.5 2 4.5 0 6"/><path d="M21 6c3 3 3 9 0 12"/>`;
      muteBtn.dataset.tip = isMuted ? "Unmute" : "Mute";
      muteBtn.classList.toggle("nx-active", isMuted);
    });

    qualBtn?.addEventListener("click", async () => {
      activeStream = activeStream === "primary" ? "secondary" : "primary";
      qualBtn.classList.toggle("nx-active", activeStream === "secondary");
      qualBtn.dataset.tip = activeStream === "secondary" ? "Switch to Primary stream" : "Switch to Secondary stream";
      if (isLive) {
        await loadLive();
      } else if (positionMs !== null) {
        await seekTo(positionMs);
      }
    });

    fullBtn?.addEventListener("click", () => {
      if (document.fullscreenElement) {
        document.exitFullscreen();
        fullBtn.querySelector("svg").innerHTML = `<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>`;
        fullBtn.dataset.tip = "Fullscreen";
      } else {
        (body.requestFullscreen ? body.requestFullscreen() : video.requestFullscreen?.());
        fullBtn.querySelector("svg").innerHTML = `<path d="M15 4v5h5M9 4v5H4M4 15h5v5M20 15h-5v5"/>`;
        fullBtn.dataset.tip = "Exit fullscreen";
      }
    });

    // A live stream is a single long-lived GET; the signed URL is only
    // checked at connection open. On a drop (network blip, tab resume, NX
    // hiccup, or an expired signature) re-sign and reopen rather than
    // failing \u2014 only fall back to a static snapshot after exhausting retries.
    const MAX_RECONNECTS = 4;
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let stableTimer = null;
    let gaveUp = false;

    // Only credit the retry budget back once playback has been stable for a
    // while. A flapping stream (playing -> error within seconds) must NOT
    // reset the counter, or the MAX cap never trips and we 502-loop forever.
    video.addEventListener("playing", () => {
      clearTimeout(stableTimer);
      stableTimer = setTimeout(() => {
        reconnectAttempts = 0;
      }, 20000);
    });

    video.addEventListener("error", () => {
      clearTimeout(stableTimer);
      if (gaveUp || reconnectTimer) return;
      if (reconnectAttempts >= MAX_RECONNECTS) {
        gaveUp = true;
        this._signPath(buildImagePath(-1)).then((imgPath) => {
          const img = Object.assign(document.createElement("img"), {
            className: "nx-c-video",
            src: imgPath,
            alt: cfg.title,
          });
          video.replaceWith(img);
          tlMid.textContent = "stream unavailable \u2014 snapshot only";
        });
        return;
      }
      reconnectAttempts += 1;
      tlMid.textContent = `reconnecting\u2026 (${reconnectAttempts}/${MAX_RECONNECTS})`;
      // Exponential backoff so a persistently-failing server is not hammered.
      const delay = Math.min(1500 * 2 ** (reconnectAttempts - 1), 15000);
      reconnectTimer = setTimeout(async () => {
        reconnectTimer = null;
        if (isLive) {
          await loadLive();
        } else if (positionMs !== null) {
          await seekTo(positionMs);
        } else {
          await loadLive();
        }
      }, delay);
    });
    this._cleanupFns.push(() => {
      clearTimeout(reconnectTimer);
      clearTimeout(stableTimer);
    });

    const renderFootage = (footage) => {
      track.querySelectorAll(".nx-c-tl-rec, .nx-c-tl-mark").forEach(el => el.remove());
      const span = tlEndMs - tlStartMs;
      if (span <= 0) return;
      for (const period of footage) {
        const pStart = period.startTimeMs ?? 0;
        const pEnd   = pStart + (period.durationMs ?? 0);
        const left   = Math.max(0, ((pStart - tlStartMs) / span) * 100);
        const width  = Math.min(100 - left, ((pEnd - pStart) / span) * 100);
        if (width < 0.05) continue;
        const el = document.createElement("div");
        el.className = "nx-c-tl-rec";
        el.style.left  = `${left}%`;
        el.style.width = `${width}%`;
        track.insertBefore(el, head);
      }
    };

    const loadFootage = async () => {
      const nowMs  = Date.now();
      tlEndMs      = nowMs;
      tlStartMs    = nowMs - zoomHours * 3_600_000;
      tlStart.textContent = _nxFmtTime(tlStartMs);
      tlMid.textContent   = "loading footage\u2026";
      if (isLive) {
        head.style.left   = "100%";
        bubble.textContent = "LIVE";
      } else if (positionMs !== null) {
        const pct = Math.max(0, Math.min(100, ((positionMs - tlStartMs) / (tlEndMs - tlStartMs)) * 100));
        head.style.left   = `${pct}%`;
        bubble.textContent = _nxFmtTime(positionMs);
      }
      if (!cfg.config_entry_id || !cfg.device_id) {
        tlMid.textContent = "no camera configured";
        return;
      }
      try {
        const resp = await this._hass.fetchWithAuth(
          buildFootagePath(tlStartMs, tlEndMs)
        );
        if (!resp.ok) throw new Error(String(resp.status));
        const footage = await resp.json();
        renderFootage(footage);
        tlMid.textContent = footage.length > 0 ? "drag or click to seek" : "no recordings in range";
      } catch (_) {
        tlMid.textContent = "footage unavailable";
      }
    };

    track.addEventListener("click", async (e) => {
      if (!tlStartMs || !tlEndMs) return;
      if (isDragging) return;
      const rect = track.getBoundingClientRect();
      const pct  = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const ms   = Math.round(tlStartMs + pct * (tlEndMs - tlStartMs));
      await seekTo(ms);
    });

    let isDragging = false;
    let dragMs     = null;

    const onTrackMousedown = (e) => {
      if (e.button !== 0) return;
      isDragging = true;
      dragMs = null;
      head.style.transition = "none";
      body.style.cursor = "ew-resize";
      e.preventDefault();
    };

    const onDocMousemove = (e) => {
      if (!isDragging || !tlStartMs || !tlEndMs) return;
      const rect = track.getBoundingClientRect();
      const pct  = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      dragMs = Math.round(tlStartMs + pct * (tlEndMs - tlStartMs));
      head.style.left    = `${pct * 100}%`;
      bubble.textContent = _nxFmtTime(dragMs);
    };

    const onDocMouseup = async (e) => {
      if (!isDragging) return;
      isDragging = false;
      head.style.transition = "";
      body.style.cursor = "";
      if (dragMs !== null && tlStartMs && tlEndMs) {
        await seekTo(dragMs);
      }
      dragMs = null;
    };

    track.addEventListener("mousedown", onTrackMousedown);
    document.addEventListener("mousemove", onDocMousemove);
    document.addEventListener("mouseup",   onDocMouseup);
    this._cleanupFns.push(() => {
      document.removeEventListener("mousemove", onDocMousemove);
      document.removeEventListener("mouseup",   onDocMouseup);
    });

    body.querySelector("#nx-c-tl-zoom").addEventListener("click", (e) => {
      const btn = e.target.closest(".nx-c-tl-zoom-btn");
      if (!btn) return;
      const hours = parseInt(btn.dataset.hours, 10);
      if (hours === zoomHours) return;
      zoomHours = hours;
      body.querySelectorAll(".nx-c-tl-zoom-btn").forEach(
        b => b.classList.toggle("nx-active", b === btn)
      );
      loadFootage();
    });

    await loadFootage();
  }

  async _loadVideoWall() {
    const planResponse = await this._hass.fetchWithAuth(this._buildVideoWallPath());
    if (!planResponse.ok) {
      throw new Error(`Failed to load video wall plan: ${planResponse.status}`);
    }
    const plan = await planResponse.json();

    const tiles = [];
    for (const matrix of plan.matrices || []) {
      for (const item of matrix.items || []) {
        for (const tile of item.tiles || []) {
          tiles.push(tile);
        }
      }
    }

    // Sign all tile paths in parallel before touching the DOM
    const signedPaths = await Promise.all(
      tiles.map(async (tile) => ({
        stream: await this._signPath(tile.stream_path),
        snapshot: await this._signPath(tile.snapshot_path),
      }))
    );

    this._controlsEl.innerHTML = `<button type="button" data-action="refresh">Refresh</button>`;
    this._bodyEl.innerHTML = `<div class="grid"></div>`;
    this._metaEl.textContent = `${plan.video_wall?.name || "Video wall"} with ${tiles.length} tiles.`;

    const grid = this._bodyEl.querySelector(".grid");
    tiles.forEach((tile, i) => {
      const { stream, snapshot } = signedPaths[i];
      const tileName = esc(tile.resource_name || tile.resource_id || "Unknown");
      const tileEl = document.createElement("div");
      tileEl.className = "tile";
      tileEl.innerHTML = `
        <video autoplay muted playsinline controls src="${stream}"></video>
        <div class="tile-name">${tileName}</div>
      `;
      const video = tileEl.querySelector("video");
      video.addEventListener("error", () => {
        tileEl.innerHTML = `
          <img src="${snapshot}" alt="${tileName}">
          <div class="tile-name">${tileName}</div>
        `;
      }, { once: true });
      grid.appendChild(tileEl);
    });

    this._controlsEl.querySelector("button").addEventListener("click", () => {
      this._loadVideoWall();
    });
  }

  async _signPath(path) {
    try {
      const result = await this._hass.callWS({ type: "auth/sign_path", path, expires: 300 });
      if (result?.path) return result.path;
    } catch (e) {
      console.warn("[nxwitness-camera-card] WS auth/sign_path failed, trying REST fallback:", e);
    }
    try {
      const resp = await this._hass.fetchWithAuth(
        `/api/nxwitness/sign?path=${encodeURIComponent(path)}`
      );
      if (resp.ok) {
        const data = await resp.json();
        if (data?.path) return data.path;
      }
    } catch (e) {
      console.error("[nxwitness-camera-card] REST sign fallback also failed:", e);
    }
    return path;
  }

  _buildVideoWallPath() {
    return `/api/nxwitness/video_wall/${this._config.config_entry_id}/${this._config.video_wall_id}?stream=${encodeURIComponent(this._config.stream)}&format=${encodeURIComponent(this._config.format)}&resolution=${encodeURIComponent(this._config.resolution)}`;
  }
}

customElements.define("nxwitness-camera-card", NxWitnessCameraCard);


function esc(v) {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}


/** Format epoch ms as HH:MM:SS (24-hour, local time). */
function _nxFmtTime(ms) {
  const d = new Date(ms);
  const p = n => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** Format epoch ms as "Tue 19 May 2026 · 14:23:45" for the timestamp overlay. */
function _nxFmtDateTime(ms) {
  const d = new Date(ms);
  const days   = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const p = n => String(n).padStart(2, "0");
  return `${days[d.getDay()]} ${p(d.getDate())} ${months[d.getMonth()]} ${d.getFullYear()} \u00b7 ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}


class NxWitnessCameraCardEditor extends HTMLElement {
  setConfig(config) {
    const prevMode = this._config
      ? (this._config.mode || (this._config.video_wall_id ? "video-wall" : "single-camera"))
      : null;
    this._config = { ...config };
    const newMode = this._config.mode || (this._config.video_wall_id ? "video-wall" : "single-camera");
    if (prevMode !== newMode || !this._built) {
      this._build();
    }
    if (newMode === "video-wall" && !this._configEntries && this._hass) {
      this._loadConfigEntries();
    }
    if (newMode === "video-wall" && this._config.config_entry_id && this._hass) {
      this._loadVideoWalls(this._config.config_entry_id);
    }
  }

  set hass(hass) {
    const hadHass = !!this._hass;
    this._hass = hass;
    if (!hadHass && this._built) {
      this._build();
    }
    const mode = this._config?.mode || (this._config?.video_wall_id ? "video-wall" : "single-camera");
    if (mode === "video-wall" && !this._configEntries && !this._loadingConfigEntries) {
      this._loadConfigEntries();
    }
    const entryId = this._config?.config_entry_id;
    if (mode === "video-wall" && entryId && !this._videoWalls?.[entryId]) {
      this._loadVideoWalls(entryId);
    }
  }

  async _loadConfigEntries() {
    if (this._loadingConfigEntries || !this._hass) return;
    this._loadingConfigEntries = true;
    try {
      this._configEntries = await this._hass.callWS({
        type: "config_entries/get",
        domain: "nxwitness",
      });
    } catch (_) {
      this._configEntries = [];
    }
    this._loadingConfigEntries = false;
    if (this._built) this._build();
  }

  async _loadVideoWalls(entryId) {
    if (!entryId || !this._hass) return;
    if (this._videoWalls?.[entryId] !== undefined) return; // already loaded or loading
    this._videoWalls = { ...this._videoWalls, [entryId]: null }; // mark as loading
    try {
      const resp = await this._hass.fetchWithAuth(
        `/api/nxwitness/video_walls/${encodeURIComponent(entryId)}`
      );
      this._videoWalls = { ...this._videoWalls, [entryId]: resp.ok ? await resp.json() : [] };
    } catch (_) {
      this._videoWalls = { ...this._videoWalls, [entryId]: [] };
    }
    if (this._built) this._build();
  }

  _getCameraOptions() {
    if (!this._hass) return [];
    return Object.values(this._hass.states)
      .filter((s) => s.entity_id.startsWith("camera.") && s.attributes.nx_device_id)
      .map((s) => ({
        entity_id: s.entity_id,
        name: s.attributes.friendly_name || s.entity_id,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  _build() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    const c = this._config;
    const mode = c.mode || (c.video_wall_id ? "video-wall" : "single-camera");
    const stream = c.stream || "primary";
    const format = c.format || "mp4";
    const resolution = c.resolution || "1080p";
    const show_name      = c.show_name      !== false;
    const show_timestamp = c.show_timestamp !== false;
    const show_play      = c.show_play      !== false;
    const show_live      = c.show_live      !== false;
    const show_snapshot  = c.show_snapshot  !== false;
    const show_mute      = c.show_mute      !== false;
    const show_quality   = c.show_quality   !== false;
    const show_fullscreen = c.show_fullscreen !== false;

    const cameras = this._getCameraOptions();
    const cameraOptions = cameras
      .map((cam) => `<option value="${esc(cam.entity_id)}"${c.entity_id === cam.entity_id ? " selected" : ""}>${esc(cam.name)} (${esc(cam.entity_id)})</option>`)
      .join("");

    const configEntries = this._configEntries ?? [];
    const entryOptions = configEntries
      .map((e) => `<option value="${esc(e.entry_id)}"${c.config_entry_id === e.entry_id ? " selected" : ""}>${esc(e.title)}</option>`)
      .join("");

    const walls = this._videoWalls?.[c.config_entry_id] ?? null;
    const wallOptions = (walls ?? []).map((w) =>
      `<option value="${esc(w.id)}"${c.video_wall_id === w.id ? " selected" : ""}>${esc(w.name)}</option>`
    ).join("");

    this.shadowRoot.innerHTML = `
      <style>
        .form {
          display: grid;
          gap: 16px;
          padding: 8px 0;
        }
        .row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }
        label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 0.85rem;
          color: var(--secondary-text-color, #727272);
        }
        small {
          font-weight: normal;
          opacity: 0.7;
        }
        input, select {
          padding: 10px 12px;
          border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
          border-radius: 4px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #212121);
          font-size: 1rem;
          font-family: inherit;
          outline: none;
          transition: border-color 0.15s;
        }
        input:focus, select:focus {
          border-color: var(--primary-color, #03a9f4);
          box-shadow: 0 0 0 1px var(--primary-color, #03a9f4);
        }
        .section-title {
          font-size: 0.78rem;
          font-weight: 600;
          letter-spacing: .07em;
          text-transform: uppercase;
          color: var(--secondary-text-color, #727272);
          margin-bottom: -8px;
        }
        .checks {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 6px 16px;
        }
        .check {
          display: flex;
          flex-direction: row;
          align-items: center;
          gap: 8px;
          font-size: 0.85rem;
          color: var(--primary-text-color, #212121);
          cursor: pointer;
        }
        .check input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; flex-shrink: 0; }
      </style>
      <div class="form">
        <label>
          Mode
          <select name="mode">
            <option value="single-camera"${mode === "single-camera" ? " selected" : ""}>Single Camera</option>
            <option value="video-wall"${mode === "video-wall" ? " selected" : ""}>Video Wall</option>
          </select>
        </label>
        ${mode === "single-camera" ? `
        <label>
          Camera Entity
          <select name="entity_id">
            <option value="">\u2014 Select a camera \u2014</option>
            ${cameraOptions}
          </select>
        </label>
        ` : `
        <label>
          NX Witness Integration
          <select name="config_entry_id">
            <option value="">${configEntries.length === 0 ? "\u2026 Loading integrations" : "\u2014 Select an integration \u2014"}</option>
            ${entryOptions}
          </select>
        </label>
        <label>
          Video Wall
          <select name="video_wall_id">
            <option value="">${!c.config_entry_id ? "\u2190 Select an integration first" : walls === null ? "\u2026 Loading video walls" : walls.length === 0 ? "No video walls found" : "\u2014 Select a video wall \u2014"}</option>
            ${wallOptions}
          </select>
        </label>
        `}
        <label>
          Title <small>(optional \u2014 defaults to entity name)</small>
          <input name="title" type="text" value="${esc(c.title || "")}">
        </label>
        <div class="row">
          <label>
            Stream
            <select name="stream">
              <option value="primary"${stream === "primary" ? " selected" : ""}>Primary</option>
              <option value="secondary"${stream === "secondary" ? " selected" : ""}>Secondary</option>
            </select>
          </label>
          <label>
            Format
            <select name="format">
              <option value="mp4"${format === "mp4" ? " selected" : ""}>MP4</option>
              <option value="webm"${format === "webm" ? " selected" : ""}>WebM</option>
            </select>
          </label>
        </div>
        <div class="row">
          <label>
            Resolution
            <select name="resolution">
              ${["1080p", "720p", "480p", "360p"].map((r) => `<option value="${r}"${resolution === r ? " selected" : ""}>${r}</option>`).join("")}
            </select>
          </label>

        </div>
        ${mode === "single-camera" ? `
        <div class="section-title">Overlay controls</div>
        <div class="checks">
          <label class="check"><input type="checkbox" name="show_name"${show_name ? " checked" : ""}>Camera name</label>
          <label class="check"><input type="checkbox" name="show_timestamp"${show_timestamp ? " checked" : ""}>Timestamp</label>
          <label class="check"><input type="checkbox" name="show_play"${show_play ? " checked" : ""}>Play / pause</label>
          <label class="check"><input type="checkbox" name="show_live"${show_live ? " checked" : ""}>Jump to live</label>
          <label class="check"><input type="checkbox" name="show_snapshot"${show_snapshot ? " checked" : ""}>Snapshot</label>
          <label class="check"><input type="checkbox" name="show_mute"${show_mute ? " checked" : ""}>Mute</label>
          <label class="check"><input type="checkbox" name="show_quality"${show_quality ? " checked" : ""}>Quality toggle</label>
          <label class="check"><input type="checkbox" name="show_fullscreen"${show_fullscreen ? " checked" : ""}>Fullscreen</label>
        </div>
        ` : ""}
      </div>
    `;

    this.shadowRoot.querySelectorAll("input, select").forEach((el) => {
      el.addEventListener("change", (e) => this._valueChanged(e));
    });
    this._built = true;
  }

  _valueChanged(e) {
    const target = e.target;
    const name = target.getAttribute("name");
    if (!name) return;

    let value = target.type === "checkbox" ? target.checked : target.value;
    if (name === "config_entry_id") {
      this._loadVideoWalls(value);
    }

    const newConfig = { ...this._config, [name]: value };
    if (name === "mode") {
      if (value === "single-camera") {
        delete newConfig.config_entry_id;
        delete newConfig.video_wall_id;
      } else {
        delete newConfig.entity_id;
      }
    }

    this._config = newConfig;

    if (name === "mode") {
      if (value === "video-wall" && !this._configEntries) {
        this._loadConfigEntries();
      }
      this._build();
    }

    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true,
    }));
  }
}

customElements.define("nxwitness-camera-card-editor", NxWitnessCameraCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "nxwitness-camera-card",
  name: "NX Witness Camera Card",
  description: "Render a single NX Witness stream or a full video wall through Home Assistant.",
  preview: true,
});