const PREFERENCE_KEY = 'lumora.ui.preferences.v1';
const SAFE_PREFERENCES = new Set(['explorerCollapsed', 'inspectorCollapsed', 'dockExpanded']);

function readPreferences(storage = window.localStorage) {
  try {
    const parsed = JSON.parse(storage.getItem(PREFERENCE_KEY) || '{}');
    if (parsed.version !== 1 || typeof parsed.values !== 'object' || !parsed.values) return {};
    return Object.fromEntries(Object.entries(parsed.values).filter(([key, value]) => SAFE_PREFERENCES.has(key) && typeof value === 'boolean'));
  } catch (_) { return {}; }
}

function writePreference(key, value, storage = window.localStorage) {
  if (!SAFE_PREFERENCES.has(key) || typeof value !== 'boolean') return false;
  try {
    const values = readPreferences(storage);
    values[key] = value;
    storage.setItem(PREFERENCE_KEY, JSON.stringify({version: 1, values}));
    return true;
  } catch (_) { return false; }
}

function activateRoute(root = document) {
  const view = root.querySelector('#workspace-view');
  if (!view) return;
  const route = view.dataset.routeName;
  root.querySelectorAll('[data-route-name]').forEach((link) => {
    if (link.dataset.routeName === route) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  document.title = `${view.dataset.pageTitle} · Lumora Probe`;
  root.querySelector('#route-announcer').textContent = `${view.dataset.pageTitle} loaded`;
}

function initialise() {
  if (document.documentElement.dataset.workspaceController === 'ready') return;
  document.documentElement.dataset.workspaceController = 'ready';
  const frame = document.querySelector('[data-workspace-frame]');
  const preferences = readPreferences();
  for (const [key, value] of Object.entries(preferences)) frame.dataset[key] = String(value);
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-panel-toggle]');
    if (!button) return;
    const panel = button.dataset.panelToggle;
    const key = `${panel}Collapsed`;
    const collapsed = frame.dataset[key] !== 'true';
    frame.dataset[key] = String(collapsed);
    button.setAttribute('aria-expanded', String(!collapsed));
    writePreference(key, collapsed);
  });
  document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.detail.target.id !== 'workspace-view') return;
    activateRoute();
    event.detail.target.focus({preventScroll: true});
  });
  window.addEventListener('popstate', () => activateRoute());
  activateRoute();
}

document.addEventListener('DOMContentLoaded', initialise, {once: true});
export { PREFERENCE_KEY, readPreferences, writePreference };
