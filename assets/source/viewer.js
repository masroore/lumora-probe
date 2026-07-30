/* Lumora Probe viewer client: renderer state only; no DICOM parsing. */

export function createLumoraImageLoader({ fetchFrame, canvas }) {
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
