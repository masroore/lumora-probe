let returnFocus = null;
function openDialog(dialog) {
  returnFocus = document.activeElement;
  dialog.hidden = false;
  dialog.querySelector('input,button,[href]')?.focus();
}
function closeDialog(dialog) {
  dialog.hidden = true;
  returnFocus?.focus();
}
document.addEventListener('click', (event) => {
  const opener = event.target.closest('[data-command-palette]');
  if (opener) openDialog(document.querySelector('#command-palette'));
  const closer = event.target.closest('[data-dialog-close]');
  if (closer) closeDialog(closer.closest('[role="dialog"]'));
});
document.addEventListener('keydown', (event) => {
  const dialog = document.querySelector('[role="dialog"]:not([hidden])');
  if (event.key === 'Escape' && dialog) closeDialog(dialog);
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    openDialog(document.querySelector('#command-palette'));
  }
});
