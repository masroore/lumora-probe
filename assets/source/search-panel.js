/* Lumora Probe Search panel: remote-paginated Tabulator results. */

export function createSearchPanel({ root, fetchResults }) {
  const input = root.querySelector("[data-search-input]");
  const kinds = root.querySelector("[data-search-kinds]");
  const status = root.querySelector("[data-search-status]");
  const tableHost = root.querySelector("[data-search-table]");
  let table = null;
  let debounceTimer = null;
  let requestInFlight = false;
  let reloadQueued = false;

  function selectedKinds() {
    if (!kinds) return "studies,series,instances,events,logs";
    return [...kinds.querySelectorAll("input[type=checkbox]:checked")]
      .map((node) => node.value)
      .join(",");
  }

  async function loadPage(page, size, sorter) {
    const query = (input?.value || "").trim();
    const params = new URLSearchParams({
      q: query,
      kinds: selectedKinds() || "studies",
      page: String(page),
      page_size: String(size),
    });
    const payload = await fetchResults(`/api/v1/search?${params.toString()}`);
    if (status) {
      status.textContent = `${payload.total} result${payload.total === 1 ? "" : "s"}`;
    }
    return {
      data: payload.items || [],
      last_page: Math.max(1, Math.ceil((payload.total || 0) / size)),
    };
  }

  function ensureTable() {
    if (table || !tableHost || typeof window.Tabulator !== "function") {
      return table;
    }
    table = new window.Tabulator(tableHost, {
      layout: "fitColumns",
      height: "18rem",
      placeholder: "No search results",
      reactiveData: false,
      index: "id",
      ajaxURL: "/api/v1/search",
      ajaxRequestFunc: async (_url, _config, params) => {
        requestInFlight = true;
        try {
          const page = params.page || 1;
          const size = params.size || 50;
          return await loadPage(page, size);
        } finally {
          requestInFlight = false;
          if (reloadQueued) {
            reloadQueued = false;
            window.setTimeout(() => {
              if (requestInFlight) {
                reloadQueued = true;
              } else {
                table?.setPage(1);
              }
            }, 0);
          }
        }
      },
      ajaxResponse: (_url, _params, response) => response,
      pagination: true,
      paginationMode: "remote",
      paginationSize: 50,
      paginationSizeSelector: [25, 50, 100],
      columns: [
        { title: "Kind", field: "kind", width: 110 },
        { title: "Label", field: "label", minWidth: 180 },
        { title: "Study", field: "study_uid", minWidth: 160 },
        { title: "Series", field: "series_uid", minWidth: 160 },
        { title: "Event", field: "event_name", width: 140 },
        { title: "Sequence", field: "sequence", width: 100 },
      ],
      rowHeader: false,
      selectableRows: 1,
      keybindings: {
        navUp: true,
        navDown: true,
      },
    });
    tableHost.setAttribute("role", "grid");
    tableHost.setAttribute("aria-label", "Search results");
    return table;
  }

  function scheduleReload() {
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(() => {
      const active = ensureTable();
      if (!active) return;
      if (requestInFlight) {
        reloadQueued = true;
        return;
      }
      active.setPage(1);
    }, 120);
  }

  input?.addEventListener("input", scheduleReload);
  kinds?.addEventListener("change", scheduleReload);
  ensureTable();

  return {
    focus() {
      input?.focus();
    },
    destroy() {
      window.clearTimeout(debounceTimer);
      reloadQueued = false;
      if (table) {
        table.destroy();
        table = null;
      }
    },
  };
}
