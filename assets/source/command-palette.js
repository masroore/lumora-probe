function initialise() {
  const list = document.querySelector('[data-palette-list]');
  const input = document.querySelector('[data-palette-input]');
  if (!list || !input) return;
  let actions = [];
  try { actions = JSON.parse(list.dataset.actions || '[]'); } catch (_) { actions = []; }
  const render = () => {
    const query = input.value.trim().toLowerCase();
    list.replaceChildren(...actions.filter((action) => action.label.toLowerCase().includes(query)).map((action) => {
      const item = document.createElement(action.href ? 'a' : 'button');
      item.setAttribute('role', 'option');
      item.dataset.command = action.name;
      item.textContent = action.label;
      if (action.href) item.href = action.href;
      else {
        item.type = 'button';
        item.addEventListener('click', () => {
          const targets = {
            'toggle-explorer': '[data-panel-toggle="explorer"]',
            'toggle-inspector': '[data-panel-toggle="inspector"]',
          };
          const target = document.querySelector(targets[action.name]);
          if (target) target.click();
        });
      }
      if (action.unavailable_reason) { item.setAttribute('aria-disabled', 'true'); item.title = action.unavailable_reason; }
      return item;
    }));
    input.setAttribute('aria-expanded', String(actions.length > 0));
  };
  input.addEventListener('input', render);
  render();
}
document.addEventListener('DOMContentLoaded', initialise, {once: true});
