(() => {
  "use strict";

  const PREVIEW_W = 1600;
  const PREFETCH = 3;
  const MAP_PAN_MS = 80;
  const IMAGE_SETTLE_MS = 140;
  const POSITION_SAVE_MS = 250;

  const state = {
    images: [],
    index: 0,
    map: null,
    trackLayer: null,
    currentMarker: null,
    lastPan: 0,
    prefetchCache: new Map(),
    spaceHeld: false,
    trackDirty: false,
    scrubbing: false,
    scrubberDragging: false,
    imageTimer: null,
    positionTimer: null,
    loadToken: 0,
    shownName: null,
  };

  const el = {
    meta: document.getElementById("meta"),
    markedBadge: document.getElementById("markedBadge"),
    deleteBtn: document.getElementById("deleteBtn"),
    mainImage: document.getElementById("mainImage"),
    viewerFrame: document.getElementById("viewerFrame"),
    markBanner: document.getElementById("markBanner"),
    scrubber: document.getElementById("scrubber"),
    scrubberLabel: document.getElementById("scrubberLabel"),
    busyOverlay: document.getElementById("busyOverlay"),
    busyTitle: document.getElementById("busyTitle"),
    busyMsg: document.getElementById("busyMsg"),
    busyBar: document.getElementById("busyBar"),
  };

  function imageUrl(name, w) {
    const q = w ? `?w=${w}` : "";
    return `/api/image/${encodeURIComponent(name)}${q}`;
  }

  function current() {
    return state.images[state.index] || null;
  }

  function markedCount() {
    return state.images.reduce((n, img) => n + (img.marked ? 1 : 0), 0);
  }

  function syncScrubber() {
    const total = state.images.length;
    const max = Math.max(0, total - 1);
    el.scrubber.max = String(max);
    el.scrubber.disabled = total === 0;
    if (!state.scrubberDragging) {
      el.scrubber.value = String(Math.min(state.index, max));
    }
    el.scrubberLabel.textContent = total
      ? `${state.index + 1} / ${total}`
      : "0 / 0";
  }

  function updateChrome() {
    const img = current();
    const total = state.images.length;
    const n = markedCount();
    el.markedBadge.textContent = `${n} marked`;
    el.markedBadge.classList.toggle("has-marks", n > 0);
    el.deleteBtn.disabled = n === 0;
    syncScrubber();

    if (!img) {
      el.meta.textContent = total ? "No image selected" : "No images in combined folder";
      el.viewerFrame.classList.remove("marked");
      el.markBanner.hidden = true;
      return;
    }

    const parts = [
      `<strong>${img.name}</strong>`,
      `<span class="dim">${state.index + 1} / ${total}</span>`,
    ];
    if (state.scrubbing) parts.push(`<span class="dim">scrubbing</span>`);
    if (img.waypoint) parts.push(`<span class="dim">${img.waypoint}</span>`);
    if (img.depth_m != null) parts.push(`<span class="dim">depth ${img.depth_m.toFixed(2)} m</span>`);
    if (img.heading_deg != null) parts.push(`<span class="dim">hdg ${img.heading_deg.toFixed(1)}°</span>`);
    if (img.lat != null && img.lon != null) {
      parts.push(`<span class="dim">${img.lat.toFixed(6)}, ${img.lon.toFixed(6)}</span>`);
    }
    el.meta.innerHTML = parts.join(" · ");

    const marked = !!img.marked;
    el.viewerFrame.classList.toggle("marked", marked);
    el.markBanner.hidden = !marked;
  }

  function setScrubbing(on) {
    state.scrubbing = on;
    el.viewerFrame.classList.toggle("scrubbing", on);
  }

  function prefetchAround(idx) {
    for (let d = -PREFETCH; d <= PREFETCH; d++) {
      const i = idx + d;
      if (i < 0 || i >= state.images.length) continue;
      const name = state.images[i].name;
      const url = imageUrl(name, PREVIEW_W);
      if (state.prefetchCache.has(url)) continue;
      const im = new Image();
      im.decoding = "async";
      im.src = url;
      state.prefetchCache.set(url, im);
      if (state.prefetchCache.size > 40) {
        const first = state.prefetchCache.keys().next().value;
        state.prefetchCache.delete(first);
      }
    }
  }

  function loadSettledImage() {
    const img = current();
    if (!img) {
      el.mainImage.removeAttribute("src");
      state.shownName = null;
      setScrubbing(false);
      updateChrome();
      return;
    }
    if (state.shownName === img.name && el.mainImage.getAttribute("src")) {
      setScrubbing(false);
      updateChrome();
      prefetchAround(state.index);
      return;
    }

    const token = ++state.loadToken;
    const name = img.name;
    const url = imageUrl(name, PREVIEW_W);
    const probe = new Image();
    probe.decoding = "async";
    probe.onload = () => {
      if (token !== state.loadToken) return;
      if (!current() || current().name !== name) return;
      el.mainImage.src = url;
      state.shownName = name;
      setScrubbing(false);
      updateChrome();
      prefetchAround(state.index);
    };
    probe.onerror = () => {
      if (token !== state.loadToken) return;
      setScrubbing(false);
      updateChrome();
    };
    probe.src = url;
  }

  function scheduleImageLoad(immediate) {
    if (state.imageTimer) {
      clearTimeout(state.imageTimer);
      state.imageTimer = null;
    }
    if (immediate) {
      setScrubbing(false);
      loadSettledImage();
      return;
    }
    setScrubbing(true);
    updateChrome();
    state.imageTimer = setTimeout(() => {
      state.imageTimer = null;
      loadSettledImage();
    }, IMAGE_SETTLE_MS);
  }

  function schedulePositionSave() {
    if (state.positionTimer) clearTimeout(state.positionTimer);
    state.positionTimer = setTimeout(() => {
      state.positionTimer = null;
      const img = current();
      if (!img) return;
      fetch("/api/position", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ index: state.index, name: img.name }),
      }).catch(() => {});
    }, POSITION_SAVE_MS);
  }

  function showImage(idx, opts = {}) {
    if (!state.images.length) {
      state.index = 0;
      el.mainImage.removeAttribute("src");
      state.shownName = null;
      setScrubbing(false);
      updateChrome();
      updateMapHighlight(true);
      return;
    }
    state.index = Math.max(0, Math.min(idx, state.images.length - 1));
    updateChrome();
    updateMapHighlight(!!opts.forcePan);
    schedulePositionSave();

    if (state.spaceHeld || opts.paintMark) {
      setMark(true, { deferTrack: true });
    }

    // Video-like playback for single-step arrows; map-only scrub for jumps/slider.
    const scrub =
      opts.immediate ? false :
      (opts.scrub === true || state.scrubberDragging);
    scheduleImageLoad(!scrub);
  }

  function initMap() {
    state.map = L.map("map", {
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
    });

    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        attribution: "Tiles &copy; Esri",
        maxZoom: 19,
      }
    ).addTo(state.map);

    state.trackLayer = L.layerGroup().addTo(state.map);
    state.currentMarker = L.circleMarker([0, 0], {
      radius: 9,
      color: "#ffffff",
      weight: 2,
      fillColor: "#7ef0ff",
      fillOpacity: 1,
    });
  }

  function rebuildTrack(opts = {}) {
    const fit = !!opts.fit;
    state.trackLayer.clearLayers();
    const pts = [];
    for (const img of state.images) {
      if (img.lat == null || img.lon == null) continue;
      const latlng = [img.lat, img.lon];
      pts.push(latlng);
      const color = img.marked ? "#e5484d" : "#2b7fff";
      const opacity = img.marked ? 0.85 : 0.45;
      L.circleMarker(latlng, {
        radius: img.marked ? 4 : 3,
        color,
        weight: 1,
        fillColor: color,
        fillOpacity: opacity,
        opacity: opacity,
      }).addTo(state.trackLayer);
    }
    if (fit) {
      if (pts.length) {
        state.map.fitBounds(pts, { padding: [24, 24], maxZoom: 17 });
      } else {
        state.map.setView([20.1839, -155.9015], 16);
      }
    }
  }

  function updateMapHighlight(forcePan) {
    const img = current();
    if (!img || img.lat == null || img.lon == null) {
      if (state.map.hasLayer(state.currentMarker)) {
        state.map.removeLayer(state.currentMarker);
      }
      return;
    }
    const latlng = [img.lat, img.lon];
    state.currentMarker.setLatLng(latlng);
    if (!state.map.hasLayer(state.currentMarker)) {
      state.currentMarker.addTo(state.map);
    }
    state.currentMarker.bringToFront();

    const now = performance.now();
    if (forcePan || now - state.lastPan >= MAP_PAN_MS) {
      state.lastPan = now;
      state.map.panTo(latlng, { animate: false });
    }
  }

  async function setMark(marked, opts = {}) {
    const img = current();
    if (!img) return;
    if (img.marked === marked) {
      updateChrome();
      return;
    }
    img.marked = marked;
    updateChrome();
    if (opts.deferTrack) {
      state.trackDirty = true;
    } else {
      rebuildTrack({ fit: false });
      updateMapHighlight(false);
    }
    try {
      await fetch("/api/mark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: img.name, marked }),
      });
    } catch (err) {
      console.error(err);
    }
  }

  function toggleMark() {
    const img = current();
    if (!img) return;
    setMark(!img.marked, { deferTrack: false });
  }

  function flushTrackIfDirty() {
    if (!state.trackDirty) return;
    state.trackDirty = false;
    rebuildTrack({ fit: false });
    updateMapHighlight(false);
  }

  async function deleteMarked() {
    const names = state.images.filter((i) => i.marked).map((i) => i.name);
    if (!names.length) return;
    const ok = window.confirm(
      `Permanently delete ${names.length} marked image(s) from disk?\n\nThis cannot be undone.`
    );
    if (!ok) return;

    el.deleteBtn.disabled = true;
    el.deleteBtn.textContent = "Deleting…";
    el.busyOverlay.hidden = false;
    el.busyTitle.textContent = "Deleting images";
    el.busyMsg.textContent = `Starting delete of ${names.length} files…`;
    el.busyBar.style.width = "0%";

    let pollTimer = setInterval(async () => {
      try {
        const pr = await fetch("/api/delete_progress");
        const p = await pr.json();
        if (!p || !p.total) return;
        const pct = Math.min(100, Math.round((100 * (p.done || 0)) / p.total));
        el.busyBar.style.width = pct + "%";
        el.busyMsg.textContent =
          (p.message || "Working…") +
          (p.errors ? ` (${p.errors} errors)` : "");
      } catch (_) {}
    }, 400);

    try {
      const res = await fetch("/api/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || "Delete failed");
        return;
      }
      if (data.errors && data.errors.length) {
        alert(`Deleted ${data.deleted.length}. Errors:\n` + data.errors.slice(0, 10).join("\n"));
      }
      state.images = data.images || [];
      state.prefetchCache.clear();
      state.shownName = null;
      rebuildTrack({ fit: true });
      showImage(Math.min(state.index, Math.max(0, state.images.length - 1)), {
        forcePan: true,
        immediate: true,
      });
      el.busyMsg.textContent = `Removed ${data.deleted.length} files`;
      el.busyBar.style.width = "100%";
    } catch (err) {
      alert("Delete request failed: " + err);
    } finally {
      clearInterval(pollTimer);
      el.busyOverlay.hidden = true;
      el.deleteBtn.textContent = "Delete all marked";
      updateChrome();
    }
  }

  function onKeyDown(e) {
    if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
    const key = e.key;

    if (key === " ") {
      e.preventDefault();
      if (e.repeat) return;
      state.spaceHeld = true;
      setMark(true, { deferTrack: true });
      return;
    }

    if (key === "ArrowRight") {
      e.preventDefault();
      const step = e.shiftKey ? 10 : 1;
      showImage(state.index + step, { scrub: step > 1 });
    } else if (key === "ArrowLeft") {
      e.preventDefault();
      const step = e.shiftKey ? 10 : 1;
      showImage(state.index - step, { scrub: step > 1 });
    } else if (key === "d" || key === "D" || key === "Delete" || key === "Backspace") {
      e.preventDefault();
      if (!e.repeat) toggleMark();
    } else if (key === "Home") {
      e.preventDefault();
      showImage(0, { forcePan: true });
    } else if (key === "End") {
      e.preventDefault();
      showImage(state.images.length - 1, { forcePan: true });
    }
  }

  function onKeyUp(e) {
    if (e.key === " ") {
      state.spaceHeld = false;
      flushTrackIfDirty();
    }
    // When arrow/shift released after a scrub jump, settle image promptly
    if (e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === "Shift") {
      if (state.scrubbing) scheduleImageLoad(false);
    }
  }

  function onBlur() {
    state.spaceHeld = false;
    flushTrackIfDirty();
    scheduleImageLoad(true);
  }

  async function boot() {
    initMap();
    el.deleteBtn.addEventListener("click", deleteMarked);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);

    const onScrubInput = () => {
      state.scrubberDragging = true;
      const idx = parseInt(el.scrubber.value, 10) || 0;
      showImage(idx, { scrub: true });
    };
    const onScrubEnd = () => {
      state.scrubberDragging = false;
      const idx = parseInt(el.scrubber.value, 10) || 0;
      showImage(idx);
      scheduleImageLoad(true);
      // Return focus to page so arrow keys keep working
      el.scrubber.blur();
    };
    el.scrubber.addEventListener("input", onScrubInput);
    el.scrubber.addEventListener("change", onScrubEnd);
    el.scrubber.addEventListener("pointerup", onScrubEnd);
    el.scrubber.addEventListener("keyup", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        // Let range handle its own steps while focused; sync image settle
        scheduleImageLoad(false);
      }
    });

    const res = await fetch("/api/catalog");
    const data = await res.json();
    state.images = data.images || [];
    rebuildTrack({ fit: true });

    let start = 0;
    const pos = data.position || {};
    if (pos.name) {
      const found = state.images.findIndex((img) => img.name === pos.name);
      if (found >= 0) start = found;
      else if (typeof pos.index === "number") start = pos.index;
    } else if (typeof pos.index === "number") {
      start = pos.index;
    }

    showImage(start, { forcePan: true, immediate: true });
  }

  boot().catch((err) => {
    el.meta.textContent = "Failed to load catalog: " + err;
    console.error(err);
  });
})();
