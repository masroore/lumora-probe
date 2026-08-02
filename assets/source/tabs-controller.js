function selectTab(tab, {updateUrl = true, focus = true} = {}) {
  const tabs = tab.closest('[data-tabs]');
  const name = tab.dataset.tab;
  tabs.querySelectorAll('[role="tab"]').forEach((item) => {
    const selected = item === tab;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
  });
  tabs.querySelectorAll('[role="tabpanel"]').forEach((panel) => { panel.hidden = panel.id !== `panel-${name}`; });
  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set('tab', name);
    history.pushState({}, '', url);
  }
  if (focus) tab.focus();
}

document.addEventListener('click', (event) => {
  const tab = event.target.closest('[data-tab]');
  if (!tab) return;
  event.preventDefault();
  selectTab(tab);
});
document.addEventListener('keydown', (event) => {
  const tab = event.target.closest('[data-tab]');
  if (!tab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const items = [...tab.closest('[role="tablist"]').querySelectorAll('[data-tab]')];
  let index = items.indexOf(tab);
  if (event.key === 'Home') index = 0;
  else if (event.key === 'End') index = items.length - 1;
  else index = (index + (event.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length;
  selectTab(items[index]);
});
window.addEventListener('popstate', () => {
  const name = new URL(window.location.href).searchParams.get('tab');
  const tab = document.querySelector(`[data-tab="${CSS.escape(name || '')}"]`) || document.querySelector('[data-tab]');
  if (tab) selectTab(tab, {updateUrl: false, focus: false});
});
