const state = {
  page: document.body.dataset.page,
  filtersEnabled: document.body.dataset.filtersEnabled === "true",
  filters: {
    vendedor: [],
    fornecedor: [],
    supervisor: [],
  },
  filterOptions: {
    vendedor: [],
    fornecedor: [],
    supervisor: [],
  },
  charts: {},
};

const endpointByPage = {
  overview: "/api/overview",
  vendedores: "/api/vendedores",
  fornecedores: "/api/fornecedores",
  supervisores: "/api/supervisores",
};

const tableColspanByPage = {
  overview: 9,
  vendedores: 9,
  fornecedores: 8,
  supervisores: 8,
};

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const numberFormatter = new Intl.NumberFormat("pt-BR");
const decimalFormatter = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

document.addEventListener("DOMContentLoaded", () => {
  bindNavigation();

  if (state.filtersEnabled) {
    bindFilterActions();
    loadFiltersAndPage().catch(handleFatalError);
  } else {
    bindUploadForm();
  }
});

function bindNavigation() {
  syncFiltersFromUrl();
  updateNavigationLinks();
}

function bindFilterActions() {
  const clearButton = document.getElementById("clear-button");
  if (!clearButton) return;

  clearButton.addEventListener("click", () => {
    state.filters = {
      vendedor: [],
      fornecedor: [],
      supervisor: [],
    };
    updateUrlWithFilters();
    renderAllFilterOptions();
    updateFilterSummary();
    renderActiveFilters();
    loadCurrentPage().catch(handleFatalError);
  });
}

async function loadFiltersAndPage() {
  const filters = await fetchJson("/api/filters");
  state.filterOptions.vendedor = filters.vendedores || [];
  state.filterOptions.fornecedor = filters.fornecedores || [];
  state.filterOptions.supervisor = filters.supervisores || [];

  normalizeFilters();
  renderAllFilterOptions();
  syncFilterCardState();
  updateFilterSummary();
  renderActiveFilters();
  updateGlobalMeta({
    updated_at: filters.updated_at,
    meses: filters.meses,
    rows: null,
  });

  await loadCurrentPage();
}

function normalizeFilters() {
  Object.keys(state.filters).forEach((key) => {
    const allowed = new Set(state.filterOptions[key]);
    state.filters[key] = state.filters[key].filter((item) => allowed.has(item));
  });
  updateUrlWithFilters();
}

function renderAllFilterOptions() {
  renderFilterOptions("vendedor", state.filterOptions.vendedor);
  renderFilterOptions("fornecedor", state.filterOptions.fornecedor);
  renderFilterOptions("supervisor", state.filterOptions.supervisor);
  syncFilterCardState();
}

function syncFilterCardState() {
  Object.keys(state.filters).forEach((key) => {
    const card = document.querySelector(`[data-filter-card="${key}"]`);
    if (card) {
      card.open = state.filters[key].length > 0;
    }
  });
}

function renderFilterOptions(key, items) {
  const container = document.getElementById(`options-${key}`);
  if (!container) return;

  container.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Sem opcoes";
    container.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const label = document.createElement("label");
    label.className = "filter-option";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = item;
    input.checked = state.filters[key].includes(item);
    input.addEventListener("change", (event) => {
      updateFilterState(key, item, event.target.checked);
      updateUrlWithFilters();
      renderAllFilterOptions();
      updateFilterSummary();
      renderActiveFilters();
      loadCurrentPage().catch(handleFatalError);
    });

    const text = document.createElement("span");
    text.textContent = item;

    label.appendChild(input);
    label.appendChild(text);
    container.appendChild(label);
  });
}

function updateFilterState(key, value, checked) {
  const values = new Set(state.filters[key]);
  if (checked) {
    values.add(value);
  } else {
    values.delete(value);
  }
  state.filters[key] = Array.from(values);
}

function updateFilterSummary() {
  Object.entries(state.filters).forEach(([key, values]) => {
    const summary = document.getElementById(`summary-${key}`);
    if (summary) {
      summary.textContent = values.length ? `${values.length} ativo(s)` : "Todos";
    }
  });
}

function renderActiveFilters() {
  const container = document.getElementById("active-filters");
  if (!container) return;

  container.innerHTML = "";
  const labels = {
    vendedor: "Vendedor",
    fornecedor: "Fornecedor",
    supervisor: "Supervisor",
  };

  Object.entries(state.filters).forEach(([key, values]) => {
    values.forEach((value) => {
      const chip = document.createElement("div");
      chip.className = "active-filter-chip";

      const text = document.createElement("span");
      text.textContent = `${labels[key]}: ${value}`;

      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "x";
      button.addEventListener("click", () => {
        updateFilterState(key, value, false);
        updateUrlWithFilters();
        renderAllFilterOptions();
        updateFilterSummary();
        renderActiveFilters();
        loadCurrentPage().catch(handleFatalError);
      });

      chip.appendChild(text);
      chip.appendChild(button);
      container.appendChild(chip);
    });
  });
}

function syncFiltersFromUrl() {
  const params = new URLSearchParams(window.location.search);
  state.filters.vendedor = params.getAll("vendedor");
  state.filters.fornecedor = params.getAll("fornecedor");
  state.filters.supervisor = params.getAll("supervisor");
}

function updateUrlWithFilters() {
  const url = new URL(window.location.href);
  url.searchParams.delete("vendedor");
  url.searchParams.delete("fornecedor");
  url.searchParams.delete("supervisor");

  state.filters.vendedor.forEach((value) => url.searchParams.append("vendedor", value));
  state.filters.fornecedor.forEach((value) => url.searchParams.append("fornecedor", value));
  state.filters.supervisor.forEach((value) => url.searchParams.append("supervisor", value));

  const next = `${url.pathname}?${url.searchParams.toString()}`.replace(/\?$/, "");
  window.history.replaceState({}, "", next);
  updateNavigationLinks();
}

function updateNavigationLinks() {
  const params = new URLSearchParams();
  state.filters.vendedor.forEach((value) => params.append("vendedor", value));
  state.filters.fornecedor.forEach((value) => params.append("fornecedor", value));
  state.filters.supervisor.forEach((value) => params.append("supervisor", value));
  const suffix = params.toString() ? `?${params.toString()}` : "";

  document.querySelectorAll("[data-nav-target]").forEach((link) => {
    link.href = `${link.dataset.navTarget}${suffix}`;
  });
}

async function loadCurrentPage() {
  const endpoint = endpointByPage[state.page];
  if (!endpoint) return;

  const query = new URLSearchParams();
  state.filters.vendedor.forEach((value) => query.append("vendedor", value));
  state.filters.fornecedor.forEach((value) => query.append("fornecedor", value));
  state.filters.supervisor.forEach((value) => query.append("supervisor", value));

  const suffix = query.toString() ? `?${query.toString()}` : "";
  const payload = await fetchJson(`${endpoint}${suffix}`);
  updateGlobalMeta(payload.metadata);

  renderKpis(payload.kpis || []);

  if (state.page === "overview") {
    renderOverviewCharts(payload.charts || {});
    renderOverviewTable(payload.table || []);
    return;
  }

  if (state.page === "vendedores") {
    renderVendedoresChart(payload.chart || []);
    renderVendedoresTable(payload.table || []);
    return;
  }

  if (state.page === "fornecedores") {
    renderFornecedoresChart(payload.chart || []);
    renderFornecedoresTable(payload.table || []);
    return;
  }

  if (state.page === "supervisores") {
    renderSupervisoresFornecedorChart(payload.chart || []);
    renderSupervisoresTable(payload.table || []);
  }
}

function updateGlobalMeta(metadata) {
  if (!metadata) return;

  const updated = document.getElementById("sidebar-updated");
  if (updated && metadata.updated_at) {
    updated.textContent = metadata.updated_at;
  }

  const sidebarRows = document.getElementById("sidebar-rows");
  if (sidebarRows && metadata.rows !== null && metadata.rows !== undefined) {
    sidebarRows.textContent = `${numberFormatter.format(metadata.rows)} linhas`;
  }

  const headerMonths = document.getElementById("header-months");
  if (headerMonths && metadata.meses) {
    headerMonths.textContent = metadata.meses.length ? metadata.meses.join(" / ") : "Sem periodo";
  }
}

function renderKpis(items) {
  const container = document.getElementById("kpi-grid");
  if (!container) return;

  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = '<div class="panel empty-state">Sem dados</div>';
    return;
  }

  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = "kpi-card";

    const icon = document.createElement("div");
    icon.className = "kpi-icon";
    icon.appendChild(createKpiIcon(item.icon));

    const body = document.createElement("div");
    body.className = "kpi-body";

    const label = document.createElement("span");
    label.textContent = item.label;

    const value = document.createElement("strong");
    value.textContent = formatValue(item.value, item.kind);

    body.appendChild(label);
    body.appendChild(value);

    if (item.detail) {
      const detail = document.createElement("small");
      detail.textContent = item.detail;
      body.appendChild(detail);
    }

    article.appendChild(icon);
    article.appendChild(body);
    container.appendChild(article);
  });
}

function createKpiIcon(type) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", "28");
  svg.setAttribute("height", "28");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");

  const icons = {
    sales: ["M4 18h16", "M7 14l3-3 3 2 4-5", "M17 8h3v3"],
    target: ["M12 3v3", "M12 18v3", "M3 12h3", "M18 12h3", "M12 8a4 4 0 100 8 4 4 0 000-8z"],
    performance: ["M5 16l4-4 3 2 6-6", "M16 8h4v4", "M4 20h16"],
    users: ["M8 11a3 3 0 100-6 3 3 0 000 6z", "M16 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z", "M3 20a5 5 0 0110 0", "M13 20a4 4 0 018 0"],
    supplier: ["M4 20h16", "M6 20V8l6-4 6 4v12", "M9 12h.01", "M15 12h.01", "M9 16h.01", "M15 16h.01"],
    supervisor: ["M12 4a3 3 0 100 6 3 3 0 000-6z", "M5 20a7 7 0 0114 0", "M18 8l1.5 1.5L22 7"],
  };

  (icons[type] || icons.sales).forEach((definition) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", definition);
    svg.appendChild(path);
  });

  return svg;
}

function renderOverviewCharts(charts) {
  rebuildChart("supervisores", document.getElementById("chart-supervisores"), {
    type: "doughnut",
    data: {
      labels: (charts.supervisores || []).map((item) => item.supervisor),
      datasets: [
        {
          data: (charts.supervisores || []).map((item) => item.vendido),
          backgroundColor: ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"],
          borderWidth: 0,
        },
      ],
    },
    options: doughnutOptions(),
  });

  rebuildChart("status", document.getElementById("chart-status"), {
    type: "polarArea",
    data: {
      labels: (charts.status || []).map((item) => item.faixa),
      datasets: [
        {
          data: (charts.status || []).map((item) => item.quantidade),
          backgroundColor: [
            "rgba(71, 85, 105, 0.9)",
            "rgba(96, 165, 250, 0.8)",
            "rgba(59, 130, 246, 0.85)",
            "rgba(37, 99, 235, 0.92)",
          ],
          borderWidth: 0,
        },
      ],
    },
    options: polarOptions(),
  });
}

function renderVendedoresChart(items) {
  rebuildChart("vendedores", document.getElementById("chart-vendedores"), {
    type: "bar",
    data: {
      labels: items.map((item) => item.vendedor),
      datasets: [
        {
          label: "Vendido",
          data: items.map((item) => item.vendido),
          backgroundColor: items.map((_, index) => `rgba(59, 130, 246, ${Math.max(0.35, 0.9 - index * 0.04)})`),
          borderRadius: 10,
        },
      ],
    },
    options: horizontalCurrencyBarOptions("Vendido"),
  });
}

function renderFornecedoresChart(items) {
  rebuildChart("fornecedores", document.getElementById("chart-fornecedores"), {
    type: "bar",
    data: {
      labels: items.map((item) => item.fornecedor),
      datasets: [
        {
          label: "Meta",
          data: items.map((item) => item.meta),
          backgroundColor: "rgba(96, 165, 250, 0.32)",
          borderRadius: 8,
        },
        {
          label: "Vendido",
          data: items.map((item) => item.vendido),
          backgroundColor: "rgba(37, 99, 235, 0.9)",
          borderRadius: 8,
        },
      ],
    },
    options: verticalCurrencyBarOptions(),
  });
}

function renderSupervisoresFornecedorChart(items) {
  rebuildChart("supervisor-fornecedores", document.getElementById("chart-supervisor-fornecedores"), {
    type: "bar",
    data: {
      labels: items.map((item) => `${item.supervisor} â€¢ ${item.fornecedor}`),
      datasets: [
        {
          label: "Vendido",
          data: items.map((item) => item.vendido),
          backgroundColor: items.map((_, index) => `rgba(37, 99, 235, ${Math.max(0.3, 0.92 - index * 0.03)})`),
          borderRadius: 10,
        },
      ],
    },
    options: horizontalCurrencyBarOptions("Vendido"),
  });
}

function renderOverviewTable(rows) {
  const tbody = document.getElementById("details-body");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!rows.length) {
    renderEmptyRow(tbody);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    addCell(tr, row.vendedor);
    addCell(tr, row.supervisor);
    addCell(tr, row.fornecedor);
    addCell(tr, currencyFormatter.format(row.meta || 0));
    addCell(tr, currencyFormatter.format(row.vendido || 0));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_meta || 0)));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_real || 0)));
    addPercentCell(tr, row.positivacao, false);
    addPercentCell(tr, row.atingimento, true);
    tbody.appendChild(tr);
  });
}

function renderVendedoresTable(rows) {
  const tbody = document.getElementById("details-body");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!rows.length) {
    renderEmptyRow(tbody);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    addCell(tr, row.vendedor);
    addCell(tr, row.supervisor);
    addCell(tr, row.fornecedor);
    addCell(tr, currencyFormatter.format(row.meta || 0));
    addCell(tr, currencyFormatter.format(row.vendido || 0));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_meta || 0)));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_real || 0)));
    addPercentCell(tr, row.positivacao, false);
    addPercentCell(tr, row.atingimento, true);
    tbody.appendChild(tr);
  });
}

function renderFornecedoresTable(rows) {
  const tbody = document.getElementById("details-body");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!rows.length) {
    renderEmptyRow(tbody);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    addCell(tr, row.fornecedor);
    addCell(tr, currencyFormatter.format(row.meta || 0));
    addCell(tr, currencyFormatter.format(row.vendido || 0));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_meta || 0)));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_real || 0)));
    addPercentCell(tr, row.positivacao, false);
    addPercentCell(tr, row.atingimento, true);
    addCell(tr, numberFormatter.format(Math.round(row.volume || 0)));
    tbody.appendChild(tr);
  });
}

function renderSupervisoresTable(rows) {
  const tbody = document.getElementById("details-body");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!rows.length) {
    renderEmptyRow(tbody);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    addCell(tr, row.supervisor);
    addCell(tr, row.fornecedor);
    addCell(tr, currencyFormatter.format(row.meta || 0));
    addCell(tr, currencyFormatter.format(row.vendido || 0));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_meta || 0)));
    addCell(tr, numberFormatter.format(Math.round(row.positivado_real || 0)));
    addPercentCell(tr, row.positivacao, false);
    addPercentCell(tr, row.atingimento, true);
    tbody.appendChild(tr);
  });
}

function addCell(row, value) {
  const td = document.createElement("td");
  td.textContent = value ?? "-";
  row.appendChild(td);
}

function addPercentCell(row, value, colored) {
  const td = document.createElement("td");
  if (colored) {
    const pill = document.createElement("span");
    pill.className = `pill ${classifyAttainment(value)}`;
    pill.textContent = `${decimalFormatter.format(value || 0)}%`;
    td.appendChild(pill);
  } else {
    td.textContent = `${decimalFormatter.format(value || 0)}%`;
  }
  row.appendChild(td);
}

function renderEmptyRow(tbody) {
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = tableColspanByPage[state.page] || 8;
  td.className = "empty-state";
  td.textContent = "Sem dados";
  tr.appendChild(td);
  tbody.appendChild(tr);
}

function bindUploadForm() {
  const form = document.getElementById("upload-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const feedback = document.getElementById("upload-feedback");
    const button = document.getElementById("upload-button");
    const formData = new FormData(form);

    button.disabled = true;
    feedback.textContent = "Processando...";
    feedback.classList.remove("is-error");

    try {
      const response = await fetch("/api/base/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let detail = "Falha ao atualizar a base.";
        try {
          const err = await response.json();
          detail = err.detail || detail;
        } catch {
          // resposta nao era JSON
        }
        throw new Error(detail);
      }

      const payload = await response.json();

      feedback.textContent = payload.message;
      updateUploadStatus(payload);
    } catch (error) {
      feedback.textContent = error.message;
      feedback.classList.add("is-error");
    } finally {
      button.disabled = false;
    }
  });
}

function updateUploadStatus(payload) {
  const updated = document.getElementById("status-updated");
  const rows = document.getElementById("status-rows");
  const meta = document.getElementById("status-meta");
  const vendido = document.getElementById("status-vendido");
  const sidebarUpdated = document.getElementById("sidebar-updated");
  const sidebarRows = document.getElementById("sidebar-rows");
  const headerMonths = document.getElementById("header-months");

  if (updated) updated.textContent = payload.updated_at;
  if (rows) rows.textContent = numberFormatter.format(payload.row_count || payload.rows_generated || 0);
  if (meta) meta.textContent = numberFormatter.format(payload.meta_files || payload.meta_uploaded || 0);
  if (vendido) vendido.textContent = numberFormatter.format(payload.vendido_files || payload.vendido_uploaded || 0);
  if (sidebarUpdated) sidebarUpdated.textContent = payload.updated_at;
  if (sidebarRows) sidebarRows.textContent = `${numberFormatter.format(payload.row_count || payload.rows_generated || 0)} linhas`;
  if (headerMonths) {
    headerMonths.textContent = (payload.months || []).length ? payload.months.join(" / ") : "Sem periodo";
  }
}

function rebuildChart(key, canvas, config) {
  if (!canvas) return;
  if (state.charts[key]) {
    state.charts[key].destroy();
  }
  state.charts[key] = new Chart(canvas, config);
}

function verticalCurrencyBarOptions() {
  return {
    maintainAspectRatio: false,
    responsive: true,
    plugins: {
      legend: {
        labels: {
          color: "#e8f0ff",
          usePointStyle: true,
          pointStyle: "circle",
          font: { family: "Plus Jakarta Sans" },
        },
      },
      tooltip: {
        callbacks: {
          label(context) {
            return `${context.dataset.label}: ${currencyFormatter.format(context.raw || 0)}`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: "#8ea4c8",
          font: { family: "Plus Jakarta Sans" },
        },
      },
      y: {
        grid: { color: "rgba(148, 184, 255, 0.12)" },
        ticks: {
          color: "#8ea4c8",
          font: { family: "Plus Jakarta Sans" },
          callback(value) {
            return currencyFormatter.format(Number(value)).replace("R$", "").trim();
          },
        },
      },
    },
  };
}

function horizontalCurrencyBarOptions(label) {
  return {
    maintainAspectRatio: false,
    responsive: true,
    indexAxis: "y",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label(context) {
            return `${label}: ${currencyFormatter.format(context.raw || 0)}`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: { color: "rgba(148, 184, 255, 0.12)" },
        ticks: {
          color: "#8ea4c8",
          font: { family: "Plus Jakarta Sans" },
          callback(value) {
            return currencyFormatter.format(Number(value)).replace("R$", "").trim();
          },
        },
      },
      y: {
        grid: { display: false },
        ticks: {
          color: "#dbe7ff",
          font: { family: "Plus Jakarta Sans" },
        },
      },
    },
  };
}

function doughnutOptions() {
  return {
    maintainAspectRatio: false,
    cutout: "68%",
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          color: "#e8f0ff",
          usePointStyle: true,
          pointStyle: "circle",
          padding: 16,
          font: { family: "Plus Jakarta Sans" },
        },
      },
    },
  };
}

function polarOptions() {
  return {
    maintainAspectRatio: false,
    scales: {
      r: {
        grid: { color: "rgba(148, 184, 255, 0.12)" },
        ticks: { display: false },
        pointLabels: {
          color: "#e8f0ff",
          font: { family: "Plus Jakarta Sans" },
        },
      },
    },
    plugins: {
      legend: {
        position: "bottom",
        labels: {
          color: "#e8f0ff",
          usePointStyle: true,
          pointStyle: "circle",
          padding: 16,
          font: { family: "Plus Jakarta Sans" },
        },
      },
    },
  };
}

function classifyAttainment(value) {
  if (value >= 100) return "good";
  if (value >= 70) return "warn";
  return "low";
}

function formatValue(value, kind) {
  if (kind === "currency") return currencyFormatter.format(value || 0);
  if (kind === "percent") return `${decimalFormatter.format(value || 0)}%`;
  return numberFormatter.format(Math.round(value || 0));
}

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || `Falha ao carregar ${url}`);
  }
  return payload;
}

function handleFatalError(error) {
  console.error(error);
  const tbody = document.getElementById("details-body");
  if (tbody) {
    renderEmptyRow(tbody);
  }
}
