(() => {
  const status = (message, error = false) => {
    document.querySelectorAll('[data-workflow-status]').forEach((element) => {
      element.textContent = message;
      element.dataset.state = error ? 'error' : 'ok';
    });
  };

  const askConfirmation = (message) => new Promise((resolve) => {
    const dialog = document.querySelector('#workflow-confirmation');
    const text = document.querySelector('#workflow-confirmation-message');
    if (!dialog || typeof dialog.showModal !== 'function') {
      resolve(window.confirm(message));
      return;
    }
    text.textContent = message;
    const finish = (value) => {
      dialog.close();
      resolve(value);
    };
    dialog.querySelector('[data-workflow-confirm]')?.addEventListener('click', () => finish(true), { once: true });
    dialog.querySelector('[data-workflow-confirm-cancel]')?.addEventListener('click', () => finish(false), { once: true });
    dialog.addEventListener('cancel', () => finish(false), { once: true });
    dialog.showModal();
  });

  const jsonRequest = async (url, method, body) => {
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || 'Request refused';
      throw new Error(message);
    }
    return payload;
  };

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.submitting === 'true') {
      event.preventDefault();
      return;
    }
    if (form.matches('[data-replay-form]')) {
      event.preventDefault();
      form.dataset.submitting = 'true';
      const submit = form.querySelector('button[type="submit"]');
      if (submit) submit.disabled = true;
      const values = new FormData(form);
      const dryRun = values.get('dry_run') === 'on';
      const mode = String(values.get('mode') || 'event');
      const request = {
        mode,
        capture_id: String(values.get('capture_id') || ''),
        fidelity: String(values.get('fidelity') || 'events'),
        speed: Number(values.get('speed') || 1),
        dry_run: dryRun,
        target_confirmed: values.get('target_confirmed') === 'on',
      };
      if (mode === 'protocol') {
        request.target = {
          host: String(values.get('target_host') || ''),
          port: Number(values.get('target_port') || 0),
        };
      }
      try {
        const preflight = await jsonRequest('/api/v1/replays/preflight', 'POST', request);
        if (!preflight.eligible) {
          throw new Error([...(preflight.reasons || []), ...(preflight.remediation || [])].join(' '));
        }
        if (!dryRun && !(await askConfirmation('Start protocol replay to the explicitly confirmed target?'))) {
          throw new Error('Replay creation cancelled before writing.');
        }
        const created = await jsonRequest('/api/v1/replays', 'POST', request);
        status(`Replay started: ${created.operation_id || created.operation?.operation_id || 'operation'}`);
        if (created.operation_id) window.location.assign(`/replay/${created.operation_id}`);
      } catch (error) {
        status(error.message || 'Replay request failed.', true);
      } finally {
        delete form.dataset.submitting;
        if (submit) submit.disabled = false;
      }
    } else if (form.matches('[data-settings-form]')) {
      event.preventDefault();
      form.dataset.submitting = 'true';
      const submit = form.querySelector('button[type="submit"]');
      if (submit) submit.disabled = true;
      const values = Object.fromEntries(new FormData(form).entries());
      try {
        const result = await jsonRequest('/api/v1/settings', 'PATCH', values);
        status(`${result.items?.length || 0} settings loaded after update.`);
      } catch (error) {
        status(error.message || 'Settings update refused.', true);
      } finally {
        delete form.dataset.submitting;
        if (submit) submit.disabled = false;
      }
    } else if (form.matches('[data-report-form]')) {
      event.preventDefault();
      form.dataset.submitting = 'true';
      const submit = form.querySelector('button[type="submit"]');
      if (submit) submit.disabled = true;
      const format = String(new FormData(form).get('format') || 'html');
      try {
        const result = await jsonRequest(form.action, 'POST', { format });
        status(`Report generation started: ${result.operation_id}`);
        if (result.operation_id) window.location.assign(`/reports/${result.operation_id}`);
      } catch (error) {
        status(error.message || 'Report generation refused.', true);
      } finally {
        delete form.dataset.submitting;
        if (submit) submit.disabled = false;
      }
    }
  });

  document.addEventListener('click', async (event) => {
    const cancel = event.target.closest('[data-cancel-operation]');
    if (cancel) {
      cancel.disabled = true;
      try {
        await jsonRequest(`/api/v1/operations/${encodeURIComponent(cancel.dataset.cancelOperation)}/cancel`, 'POST');
        status('Cooperative cancellation requested.');
      } catch (error) {
        cancel.disabled = false;
        status(error.message || 'Cancellation refused.', true);
      }
      return;
    }
    const toggle = event.target.closest('[data-plugin-toggle]');
    if (toggle) {
      const enabled = toggle.dataset.pluginEnabled === 'true';
      const action = enabled ? 'disable' : 'enable';
      if (!(await askConfirmation(`${action === 'enable' ? 'Enable' : 'Disable'} this trusted plugin? A restart is required.`))) return;
      toggle.disabled = true;
      try {
        const result = await jsonRequest(
          `/api/v1/plugins/${encodeURIComponent(toggle.dataset.pluginId)}/${action}`,
          'POST',
        );
        toggle.dataset.pluginEnabled = String(!enabled);
        toggle.textContent = enabled ? 'Enable' : 'Disable';
        status(`${action === 'enable' ? 'Enabled' : 'Disabled'} for the next restart.`);
        if (result.restart_required !== true) status('Provider did not confirm restart impact.', true);
      } catch (error) {
        status(error.message || 'Plugin mutation refused.', true);
      } finally {
        toggle.disabled = false;
      }
    }
  });
})();
