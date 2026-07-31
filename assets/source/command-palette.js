/* Lumora Probe command palette: keyboard-first navigation. */

export function createCommandPalette({ root, onNavigate }) {
  const actions = [
    { id: "open-studies", label: "Open Studies", shortcut: "", run: () => onNavigate("studies") },
    { id: "open-captures", label: "Open Captures", shortcut: "", run: () => onNavigate("captures") },
    { id: "open-search", label: "Open Search", shortcut: "", run: () => onNavigate("search") },
    { id: "focus-viewer", label: "Focus Viewer", shortcut: "", run: () => onNavigate("viewer") },
    { id: "focus-timeline", label: "Focus Timeline", shortcut: "", run: () => onNavigate("timeline") },
    { id: "cycle-theme", label: "Cycle Theme", shortcut: "", run: () => onNavigate("theme") },
  ];

  let open = false;
  let activeIndex = 0;
  let invokingElement = null;

  function render() {
    const overlay = root.querySelector("[data-palette-overlay]");
    if (!overlay) return;
    overlay.hidden = !open;
    const list = overlay.querySelector("[data-palette-list]");
    if (!list) return;
    list.innerHTML = "";
    actions.forEach((action, index) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "palette-item" + (index === activeIndex ? " palette-item--active" : "");
      item.textContent = action.label;
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(index === activeIndex));
      item.addEventListener("click", () => {
        action.run();
        close();
      });
      list.appendChild(item);
    });
  }

  function openPalette() {
    invokingElement = document.activeElement;
    open = true;
    activeIndex = 0;
    render();
    const input = root.querySelector("[data-palette-input]");
    if (input) input.focus();
  }

  function close() {
    open = false;
    render();
    if (invokingElement) invokingElement.focus();
  }

  function handleKeydown(event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "k") {
      event.preventDefault();
      if (open) close();
      else openPalette();
      return;
    }
    if (!open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = (activeIndex + 1) % actions.length;
      render();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = (activeIndex - 1 + actions.length) % actions.length;
      render();
    } else if (event.key === "Enter") {
      event.preventDefault();
      const action = actions[activeIndex];
      if (action) {
        action.run();
        close();
      }
    }
  }

  document.addEventListener("keydown", handleKeydown);

  function destroy() {
    document.removeEventListener("keydown", handleKeydown);
  }

  return { open: openPalette, close, destroy, isOpen: () => open };
}
