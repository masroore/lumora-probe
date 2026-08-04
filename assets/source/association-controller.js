function associationDialog() {
  return document.querySelector('#association-dialog');
}

function setAssociationState(dialog, message, error = false) {
  const status = dialog.querySelector('[data-association-dialog-status]');
  status.textContent = message;
  status.dataset.state = error ? 'error' : 'loading';
  status.hidden = false;
  dialog.querySelector('[data-association-dialog-details]').hidden = true;
}

function formatTimestamp(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  }).format(date);
}

function closeAssociationDialog() {
  const dialog = associationDialog();
  if (!dialog) return;
  if (dialog.open) dialog.close();
  dialog.querySelector('[data-association-dialog-status]').hidden = false;
  dialog.querySelector('[data-association-dialog-details]').hidden = true;
  dialog._returnFocus?.focus();
  dialog._returnFocus = null;
}

function showAssociation(dialog, record) {
  const fields = ['association_id', 'status', 'calling_ae', 'called_ae', 'started_at', 'completed_at'];
  fields.forEach((field) => {
    const value = record[field];
    dialog.querySelector(`[data-association-field="${field}"]`).textContent =
      field === 'started_at' || field === 'completed_at'
        ? formatTimestamp(value)
        : value === null || value === undefined || value === '' ? '—' : String(value);
  });
  dialog.querySelector('[data-association-dialog-status]').hidden = true;
  dialog.querySelector('[data-association-dialog-details]').hidden = false;
}

async function openAssociationDialog(link) {
  const dialog = associationDialog();
  if (!dialog) return;
  dialog._returnFocus = document.activeElement;
  if (!dialog.open) dialog.showModal();
  setAssociationState(dialog, 'Loading association details…');
  dialog.querySelector('[data-association-dialog-close]').focus();
  try {
    const response = await fetch(link.href, { headers: { Accept: 'application/json' } });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || payload.detail || 'Association details unavailable.');
    }
    showAssociation(dialog, payload);
  } catch (error) {
    setAssociationState(
      dialog,
      error instanceof Error ? error.message : 'Association details unavailable.',
      true,
    );
  }
}

document.addEventListener('click', (event) => {
  const link = event.target.closest('[data-association-link]');
  if (link) {
    event.preventDefault();
    void openAssociationDialog(link);
    return;
  }
  if (event.target.closest('[data-association-dialog-close]') || event.target === associationDialog()) {
    closeAssociationDialog();
  }
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && associationDialog()?.open) closeAssociationDialog();
});
