const STREAM_VERSION = 1;
const KNOWN_PANELS = new Set(['counters', 'status', 'timeline']);
const MAX_RECONNECT_DELAY_MS = 30_000;
const STALE_AFTER_MS = 45_000;

function liveTargets(root = document) {
  const panels = [...root.querySelectorAll('[data-live-panel]')]
    .map((panel) => panel.dataset.livePanel)
    .filter((panel) => KNOWN_PANELS.has(panel));
  return [...new Set(panels)];
}

function currentSubscription(root = document) {
  const view = root.querySelector('[data-live-view]');
  const route = root.querySelector('#workspace-view')?.dataset.routeName || 'workspace';
  return {
    type: 'mount',
    version: STREAM_VERSION,
    page: view?.dataset.livePage || route,
    panels: liveTargets(root),
    topics: ['*'],
  };
}

function stateElement(root = document) {
  return root.querySelector('[data-live-connection-state]') || root.querySelector('#route-announcer');
}

function setState(value, message, root = document) {
  const element = stateElement(root);
  if (element) element.textContent = message;
  const view = root.querySelector('[data-live-view]');
  if (view) view.dataset.liveState = value;
  document.documentElement.dataset.liveState = value;
}

function showDrops(message, root = document) {
  const count = Number.isInteger(message.dropped_count) ? message.dropped_count : 0;
  if (count <= 0) return;
  root.querySelectorAll('[data-live-events-dropped]').forEach((element) => {
    element.textContent = String(Number(element.textContent || 0) + count);
  });
  const evidence = root.querySelector('[data-live-drop-evidence]');
  if (evidence) {
    const sequences = Array.isArray(message.dropped_sequences) ? message.dropped_sequences : [];
    evidence.textContent = sequences.length
      ? `Transport dropped ${count} update${count === 1 ? '' : 's'}; source sequences ${sequences.join(', ')} are evidence of the gap.`
      : `Transport dropped ${count} update${count === 1 ? '' : 's'}; the gap is visible without a causal claim.`;
  }
}

function applyFragment(fragment, root = document) {
  if (!fragment || typeof fragment !== 'object') throw new Error('Malformed live fragment');
  const panel = fragment.panel;
  const target = fragment.target;
  if (!KNOWN_PANELS.has(panel) || target !== `#panel-${panel}`) {
    throw new Error(`Refused unknown live target: ${target || panel || 'missing'}`);
  }
  const currentTargets = [
    ...root.querySelectorAll(`${target}, #panel-${panel}-dock`),
  ];
  if (!currentTargets.length || typeof fragment.html !== 'string') {
    throw new Error(`Refused missing live target: ${target}`);
  }
  const parsed = new DOMParser().parseFromString(fragment.html, 'text/html').body.firstElementChild;
  if (!parsed || parsed.id !== `panel-${panel}`) throw new Error(`Refused malformed ${panel} fragment`);
  currentTargets.forEach((current) => {
    const replacement = parsed.cloneNode(true);
    replacement.id = current.id;
    current.replaceWith(replacement);
  });
}

function createLiveClient({root = document} = {}) {
  let socket = null;
  let retryTimer = null;
  let retryAttempt = 0;
  let listenersReady = false;
  let closed = false;
  let staleTimer = null;

  const send = (message) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
  };

  const mount = () => send(currentSubscription(root));

  const scheduleReconnect = () => {
    if (closed || retryTimer !== null || !navigator.onLine) return;
    const base = Math.min(MAX_RECONNECT_DELAY_MS, 250 * (2 ** retryAttempt));
    retryAttempt += 1;
    const jitter = Math.floor(Math.random() * Math.max(1, base * 0.2));
    retryTimer = window.setTimeout(() => {
      retryTimer = null;
      connect();
    }, Math.min(MAX_RECONNECT_DELAY_MS, base + jitter));
  };

  const connect = () => {
    if (closed || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return;
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${scheme}//${window.location.host}/ws/ui`);
    setState('connecting', 'Connecting to live updates…', root);
    if (staleTimer !== null) window.clearTimeout(staleTimer);
    staleTimer = window.setTimeout(() => {
      setState('stale', 'Live data is stale; waiting for a fresh update.', root);
    }, STALE_AFTER_MS);
    socket.addEventListener('open', () => {
      retryAttempt = 0;
      setState('connected', 'Live updates connected.', root);
      if (staleTimer !== null) window.clearTimeout(staleTimer);
      mount();
    });
    socket.addEventListener('message', (event) => {
      let message;
      try { message = JSON.parse(event.data); } catch (_) {
        setState('error', 'Live update refused: malformed message.', root);
        return;
      }
      if (message.version !== STREAM_VERSION) {
        setState('error', 'Live update refused: unsupported message version.', root);
        return;
      }
      if (message.type === 'ping') {
        send({type: 'pong', version: STREAM_VERSION});
      } else if (message.type === 'mounted') {
        setState('connected', 'Live updates connected.', root);
      } else if (message.type === 'fragments') {
        try {
          (message.fragments || []).forEach((fragment) => applyFragment(fragment, root));
          showDrops(message, root);
          setState('connected', 'Live updates connected.', root);
          if (staleTimer !== null) window.clearTimeout(staleTimer);
          staleTimer = window.setTimeout(() => {
            setState('stale', 'Live data is stale; waiting for a fresh update.', root);
          }, STALE_AFTER_MS);
        } catch (error) {
          setState('error', error instanceof Error ? error.message : 'Live update refused.', root);
        }
      } else if (message.type === 'error') {
        setState('error', message.message || 'Live update refused.', root);
      }
    });
    socket.addEventListener('close', () => {
      socket = null;
      setState('stale', 'Live updates stale; reconnecting…', root);
      scheduleReconnect();
    });
    socket.addEventListener('error', () => setState('disconnected', 'Live updates disconnected.', root));
  };

  const initialise = () => {
    if (listenersReady) return;
    listenersReady = true;
    document.body.addEventListener('htmx:afterSwap', () => window.setTimeout(mount, 0));
    window.addEventListener('online', connect);
    window.addEventListener('offline', () => setState('stale', 'Live updates paused while offline.', root));
    connect();
  };

  return {
    connect,
    mount,
    close() {
      closed = true;
      if (retryTimer !== null) window.clearTimeout(retryTimer);
      if (staleTimer !== null) window.clearTimeout(staleTimer);
      socket?.close(1000, 'page closed');
      socket = null;
    },
    initialise,
  };
}

window.LumoraLiveClient = window.LumoraLiveClient || createLiveClient();
document.addEventListener('DOMContentLoaded', () => window.LumoraLiveClient.initialise(), {once: true});
