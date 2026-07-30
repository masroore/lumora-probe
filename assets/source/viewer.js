/* Lumora Probe viewer client: renderer state only; no DICOM parsing. */

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
  const state = { windowCenter: 32768, windowWidth: 65535, zoom: 1, panX: 0, panY: 0, invert: false };

  function setWindowLevel(center, width) {
    state.windowCenter = center;
    state.windowWidth = Math.max(1, width);
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
  }

  async function load(imageId) {
    const response = await fetchFrame(imageId);
    if (!response.ok) throw new Error(`Frame request failed: ${response.status}`);
    const metadata = JSON.parse(response.headers.get("X-Lumora-Frame-Metadata") || "{}");
    const pixels = new Uint16Array(await response.arrayBuffer());
    setWindowLevel(metadata.suggested_window_center ?? 32768, metadata.suggested_window_width ?? 65535);
    render(pixels, metadata.rows, metadata.columns);
    return { imageId, metadata, pixels, render: () => render(pixels, metadata.rows, metadata.columns) };
  }

  return {
    state,
    load,
    setWindowLevel,
    zoomIn: () => { state.zoom = Math.min(20, state.zoom * 1.1); },
    zoomOut: () => { state.zoom = Math.max(0.1, state.zoom / 1.1); },
    toggleInvert: () => { state.invert = !state.invert; },
  };
}

export function registerCornerstoneLoader(cornerstone, loader) {
  if (!cornerstone || typeof cornerstone.registerImageLoader !== "function") return;
  cornerstone.registerImageLoader("lumora", (imageId) => ({ promise: loader.load(imageId) }));
}

export function createViewerControls({ loader, viewerPanel, fetchFrame, frameCount, instanceId }) {
  const cineState = {
    playing: false,
    fps: 10,
    currentFrame: 0,
    animationId: null,
    lastFrameTime: 0,
  };

  function clampFps(fps) {
    return Math.min(60, Math.max(1, Math.round(fps)));
  }

  function setCineFps(fps) {
    cineState.fps = clampFps(fps);
  }

  async function showFrame(frameNumber) {
    const wrapped = ((frameNumber % frameCount) + frameCount) % frameCount;
    cineState.currentFrame = wrapped;
    const imageId = `lumora:${instanceId}:${wrapped}`;
    const image = await loader.load(imageId);
    postImageDisplayed(instanceId, wrapped, captureId);
    return image;
  }

  function startCine() {
    if (cineState.playing || frameCount <= 1) return;
    cineState.playing = true;
    cineState.lastFrameTime = performance.now();
    const intervalMs = 1000 / cineState.fps;

    function tick(now) {
      if (!cineState.playing) return;
      if (now - cineState.lastFrameTime >= intervalMs) {
        cineState.lastFrameTime = now;
        showFrame(cineState.currentFrame + 1).catch(() => {});
      }
      cineState.animationId = requestAnimationFrame(tick);
    }
    cineState.animationId = requestAnimationFrame(tick);
    // T6 will add CineStarted event post-back here; guarded call site:
    // if (window.__lumoraPostClientEvent) window.__lumoraPostClientEvent("CineStarted", {...});
  }

  function stopCine() {
    cineState.playing = false;
    if (cineState.animationId !== null) {
      cancelAnimationFrame(cineState.animationId);
      cineState.animationId = null;
    }
  }

  function toggleCine() {
    if (cineState.playing) {
      stopCine();
    } else {
      startCine();
    }
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

  function handleKeydown(event) {
    if (event.key === "f" || event.key === "F") {
      if (event.target && (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA")) {
        return;
      }
      event.preventDefault();
      toggleFullscreen();
    }
  }

  document.addEventListener("keydown", handleKeydown);

  function destroy() {
    stopCine();
    document.removeEventListener("keydown", handleKeydown);
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
