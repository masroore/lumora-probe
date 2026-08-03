/* Phase 23 viewer bootstrap. All pixel decoding remains server-side. */

function initialiseViewer(root = document) {
  const surface = root.querySelector("[data-instance-id]");
  if (!surface || !window.LumoraViewer) return null;
  if (surface.dataset.viewerReady === "true") return surface._lumoraViewer;

  const instanceId = surface.dataset.instanceId;
  const captureId = surface.dataset.captureId || null;
  const frameCount = Math.max(1, Number.parseInt(surface.dataset.frameCount || "1", 10));
  const stage = surface.querySelector("[data-viewer-stage]");
  const canvas = surface.querySelector("[data-viewer-canvas]");
  const status = surface.querySelector("[data-viewer-status]");
  const errorBox = surface.querySelector("[data-viewer-error]");
  if (!stage || !canvas) return null;

  const state = { mode: "window-level", dragging: false, x: 0, y: 0 };
  const fetchFrame = (imageId, signal) => {
    const [, id, frame] = imageId.split(":");
    return fetch(`/api/v1/instances/${encodeURIComponent(id)}/frames/${frame}`, { signal });
  };
  const showError = (error) => {
    errorBox.hidden = false;
    errorBox.textContent = `${error.message || "Frame unavailable"} ${error.remediation ? `Remediation: ${error.remediation}` : ""}`;
    status.textContent = "Viewer refused this frame";
  };
  const clearError = () => {
    errorBox.hidden = true;
    errorBox.textContent = "";
  };
  const loader = window.LumoraViewer.createLumoraImageLoader({ fetchFrame, canvas, captureId });
  const controls = window.LumoraViewer.createViewerControls({
    loader,
    viewerPanel: stage,
    fetchFrame,
    frameCount,
    instanceId,
    captureId,
    onFrame: (frame) => {
      clearError();
      status.textContent = `Frame ${frame} of ${frameCount}`;
      surface.querySelector("[data-viewer-frame]").value = String(frame);
      surface.querySelector("[data-viewer-frame-label]").textContent = `Frame ${frame} of ${frameCount}`;
    },
    onError: showError,
  });

  const setMode = (mode) => {
    state.mode = mode;
    surface.querySelector("[data-viewer-pan]").setAttribute("aria-pressed", String(mode === "pan"));
    surface.querySelector("[data-viewer-window-level]").setAttribute("aria-pressed", String(mode === "window-level"));
  };
  const bind = (selector, handler) => surface.querySelector(selector)?.addEventListener("click", handler);
  bind("[data-viewer-previous]", () => controls.showFrame(controls.cineState.currentFrame - 1).catch(() => {}));
  bind("[data-viewer-next]", () => controls.showFrame(controls.cineState.currentFrame + 1).catch(() => {}));
  bind("[data-viewer-zoom-in]", () => loader.zoomIn());
  bind("[data-viewer-zoom-out]", () => loader.zoomOut());
  bind("[data-viewer-pan]", () => setMode("pan"));
  bind("[data-viewer-window-level]", () => setMode("window-level"));
  bind("[data-viewer-invert]", (event) => {
    event.currentTarget.setAttribute("aria-pressed", String(loader.toggleInvert()));
  });
  bind("[data-viewer-reset]", () => {
    loader.reset();
    setMode("window-level");
    surface.querySelector("[data-viewer-invert]").setAttribute("aria-pressed", "false");
  });
  bind("[data-viewer-cine]", (event) => {
    const playing = controls.toggleCine();
    event.currentTarget.setAttribute("aria-pressed", String(playing));
    event.currentTarget.textContent = playing ? "❚❚ Cine" : "▶ Cine";
  });
  bind("[data-viewer-fullscreen]", () => controls.toggleFullscreen());
  surface.querySelector("[data-viewer-frame]")?.addEventListener("change", (event) => {
    const frame = Number.parseInt(event.currentTarget.value, 10);
    controls.showFrame(frame).catch(() => {});
  });

  stage.addEventListener("pointerdown", (event) => {
    state.dragging = true;
    state.x = event.clientX;
    state.y = event.clientY;
    stage.setPointerCapture(event.pointerId);
  });
  stage.addEventListener("pointermove", (event) => {
    if (!state.dragging) return;
    const dx = event.clientX - state.x;
    const dy = event.clientY - state.y;
    state.x = event.clientX;
    state.y = event.clientY;
    if (state.mode === "pan") loader.panBy(dx, dy);
    else loader.setWindowLevel(loader.state.windowCenter + dx * 8, loader.state.windowWidth + dy * 8);
  });
  stage.addEventListener("pointerup", (event) => {
    state.dragging = false;
    stage.releasePointerCapture(event.pointerId);
  });
  const keydown = (event) => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target?.tagName)) return;
    if (event.key === "ArrowLeft") controls.showFrame(controls.cineState.currentFrame - 1).catch(() => {});
    else if (event.key === "ArrowRight") controls.showFrame(controls.cineState.currentFrame + 1).catch(() => {});
    else if (event.key === "+" || event.key === "=") loader.zoomIn();
    else if (event.key === "-") loader.zoomOut();
    else if (event.key.toLowerCase() === "i") loader.toggleInvert();
    else if (event.key === "f") controls.toggleFullscreen();
    else return;
    event.preventDefault();
  };
  stage.addEventListener("keydown", keydown);
  surface.dataset.viewerReady = "true";
  controls.showFrame(0).catch(() => {});
  surface._lumoraViewer = { controls, loader, destroy: () => controls.destroy() };
  return surface._lumoraViewer;
}

document.addEventListener("DOMContentLoaded", () => initialiseViewer());
document.body?.addEventListener("htmx:afterSwap", () => initialiseViewer());
window.LumoraInvestigation = { initialiseViewer };
