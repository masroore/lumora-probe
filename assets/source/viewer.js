/* Lumora Probe viewer client: normalized pixels only; no DICOM parsing. */

function postImageDisplayed(instanceId, frameNumber, captureId) {
  fetch("/api/v1/events/client-asserted", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_name: "ImageDisplayed",
      event_version: 1,
      aggregate_type: "instance",
      aggregate_id: instanceId,
      payload: { instance_id: instanceId, frame_number: frameNumber, capture_id: captureId },
    }),
  }).catch(() => {});
}

export function createLumoraImageLoader({ fetchFrame, canvas, captureId = null }) {
  const context = canvas.getContext("2d", { alpha: false });
  const state = {
    windowCenter: 32768,
    windowWidth: 65535,
    zoom: 1,
    panX: 0,
    panY: 0,
    invert: false,
  };
  let lastImage = null;
  let defaultWindowCenter = state.windowCenter;
  let defaultWindowWidth = state.windowWidth;

  function applyTransform() {
    canvas.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
    canvas.style.transformOrigin = "center center";
  }

  function setWindowLevel(center, width) {
    state.windowCenter = Number.isFinite(center) ? center : state.windowCenter;
    state.windowWidth = Math.max(1, Number.isFinite(width) ? width : state.windowWidth);
    lastImage?.render();
  }

  function render(pixels, rows, columns) {
    canvas.width = columns;
    canvas.height = rows;
    const image = context.createImageData(columns, rows);
    const source = new DataView(pixels.buffer, pixels.byteOffset, pixels.byteLength);
    const half = state.windowWidth / 2;
    const low = state.windowCenter - half;
    const high = state.windowCenter + half;
    for (let index = 0; index < rows * columns; index += 1) {
      const value = source.getUint16(index * 2, true);
      const clipped = Math.min(high, Math.max(low, value));
      const mapped = Math.round(((clipped - low) / Math.max(1, high - low)) * 255);
      const gray = state.invert ? 255 - mapped : mapped;
      const offset = index * 4;
      image.data[offset] = gray;
      image.data[offset + 1] = gray;
      image.data[offset + 2] = gray;
      image.data[offset + 3] = 255;
    }
    context.putImageData(image, 0, 0);
    applyTransform();
  }

  async function load(imageId) {
    const response = await fetchFrame(imageId);
    if (!response.ok) {
      let detail = {};
      try { detail = await response.clone().json(); } catch (_) {}
      const error = new Error(detail.message || `Frame request failed: ${response.status}`);
      error.remediation = detail.remediation || "Verify the capture object and request a supported frame.";
      error.code = detail.code || `HTTP_${response.status}`;
      throw error;
    }
    const metadata = JSON.parse(response.headers.get("X-Lumora-Frame-Metadata") || "{}");
    const pixels = new Uint16Array(await response.arrayBuffer());
    if (!lastImage) {
      defaultWindowCenter = metadata.suggested_window_center ?? defaultWindowCenter;
      defaultWindowWidth = metadata.suggested_window_width ?? defaultWindowWidth;
      state.windowCenter = defaultWindowCenter;
      state.windowWidth = defaultWindowWidth;
    }
    const image = {
      imageId,
      metadata,
      pixels,
      render: () => render(pixels, metadata.rows, metadata.columns),
    };
    lastImage = image;
    image.render();
    return image;
  }

  function reset() {
    state.windowCenter = defaultWindowCenter;
    state.windowWidth = defaultWindowWidth;
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    state.invert = false;
    lastImage?.render();
  }

  return {
    state,
    load,
    setWindowLevel,
    render: () => lastImage?.render(),
    zoomIn: () => { state.zoom = Math.min(20, state.zoom * 1.1); applyTransform(); },
    zoomOut: () => { state.zoom = Math.max(0.1, state.zoom / 1.1); applyTransform(); },
    panBy: (x, y) => { state.panX += x; state.panY += y; applyTransform(); },
    toggleInvert: () => { state.invert = !state.invert; lastImage?.render(); return state.invert; },
    reset,
    captureId,
  };
}

export function registerCornerstoneLoader(cornerstone, loader) {
  if (!cornerstone || typeof cornerstone.registerImageLoader !== "function") return;
  cornerstone.registerImageLoader("lumora", (imageId) => ({ promise: loader.load(imageId) }));
}

export function createViewerControls({
  loader,
  viewerPanel,
  fetchFrame,
  frameCount,
  instanceId,
  captureId = null,
  onFrame = () => {},
  onError = () => {},
}) {
  const cineState = {
    playing: false,
    fps: 10,
    currentFrame: 0,
    animationId: null,
    lastFrameTime: 0,
  };
  let prefetchController = null;

  function clampFrame(frame) {
    if (!Number.isInteger(frame) || frame < 0 || frame >= frameCount) {
      throw Object.assign(new Error("Requested frame is outside the available range."), {
        code: "FRAME_OUT_OF_RANGE",
        remediation: `Choose a frame from 0 through ${frameCount - 1}.`,
      });
    }
    return frame;
  }

  function clampFps(fps) {
    return Math.min(60, Math.max(1, Math.round(fps)));
  }

  function setCineFps(fps) {
    cineState.fps = clampFps(fps);
  }

  async function prefetchAround(frame) {
    prefetchController?.abort();
    prefetchController = new AbortController();
    const signal = prefetchController.signal;
    const requests = [];
    for (let offset = -2; offset <= 2; offset += 1) {
      const candidate = frame + offset;
      if (candidate < 0 || candidate >= frameCount || candidate === frame) continue;
      requests.push(Promise.resolve(fetchFrame(`lumora:${instanceId}:${candidate}`, signal))
        .then((response) => response.ok ? response.arrayBuffer() : null)
        .catch(() => null));
    }
    await Promise.all(requests);
  }

  async function showFrame(frameNumber, { wrap = false } = {}) {
    let frame = frameNumber;
    if (wrap) frame = ((frameNumber % frameCount) + frameCount) % frameCount;
    frame = clampFrame(frame);
    cineState.currentFrame = frame;
    try {
      const image = await loader.load(`lumora:${instanceId}:${frame}`);
      postImageDisplayed(instanceId, frame, captureId);
      onFrame(frame, image.metadata);
      prefetchAround(frame);
      return image;
    } catch (error) {
      onError(error);
      throw error;
    }
  }

  function startCine() {
    if (cineState.playing || frameCount <= 1) return;
    cineState.playing = true;
    cineState.lastFrameTime = performance.now();
    function tick(now) {
      if (!cineState.playing) return;
      if (now - cineState.lastFrameTime >= 1000 / cineState.fps) {
        cineState.lastFrameTime = now;
        showFrame(cineState.currentFrame + 1, { wrap: true }).catch(() => {});
      }
      cineState.animationId = requestAnimationFrame(tick);
    }
    cineState.animationId = requestAnimationFrame(tick);
  }

  function stopCine() {
    cineState.playing = false;
    if (cineState.animationId !== null) {
      cancelAnimationFrame(cineState.animationId);
      cineState.animationId = null;
    }
  }

  function toggleCine() {
    if (cineState.playing) stopCine();
    else startCine();
    return cineState.playing;
  }

  function toggleFullscreen() {
    if (!viewerPanel) return false;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
      return false;
    }
    viewerPanel.requestFullscreen().catch(() => {});
    return true;
  }

  function destroy() {
    stopCine();
    prefetchController?.abort();
  }

  return {
    cineState,
    setCineFps,
    startCine,
    stopCine,
    toggleCine,
    toggleFullscreen,
    showFrame,
    destroy,
  };
}
