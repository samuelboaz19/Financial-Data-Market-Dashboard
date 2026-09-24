// app.js
//
// All frontend logic. Talks only to the FastAPI backend defined in
// config.js (API_BASE_URL) - never touches the database directly.
// Kept as plain JS/fetch (no build step) so a frontend problem is
// always just "this file, in this browser" - nothing to compile,
// bundle, or misconfigure.

const state = {
  assets: [],
  selectedSymbol: null,
  selectedRange: "6h",
  chart: null,
};

// --- small utilities -----------------------------------------------------

function symbolToUrlSegment(symbol) {
  // "BTC/USD" -> "BTC-USD" (see backend/routes/market.py for the reverse)
  return symbol.replace("/", "-");
}

function formatPrice(value) {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  const decimals = abs >= 100 ? 2 : abs >= 1 ? 4 : 6;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatVolume(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatTimestamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function formatAge(iso) {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms)) return "—";
  if (ms < 0) return "0s";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body && body.detail) detail = body.detail;
    } catch (_) { /* body wasn't JSON - fall back to statusText */ }
    const err = new Error(detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

// --- status panel ----------------------------------------------------------

function setStatusRow(key, state, valueText) {
  const row = document.querySelector(`.status-row[data-key="${key}"]`);
  if (!row) return;
  const dot = row.querySelector(".status-dot");
  const value = row.querySelector(".status-value");
  if (dot) dot.dataset.state = state;
  if (value) value.textContent = valueText;
}

async function refreshStatus() {
  // API reachability
  try {
    await apiGet("/health");
    setStatusRow("api", "ok", "Connected");
  } catch (err) {
    setStatusRow("api", "error", "Unreachable");
    // If the API itself is unreachable, database/timescaledb checks
    // will fail too - report that plainly instead of hanging on "Checking…".
    setStatusRow("database", "error", "Unknown");
    setStatusRow("timescaledb", "error", "Unknown");
    return;
  }

  // Database connectivity
  try {
    const db = await apiGet("/health/database");
    setStatusRow("database", "ok", `Connected (${db.latency_ms ?? "?"} ms)`);
  } catch (err) {
    setStatusRow("database", "error", err.status ? `Error ${err.status}` : "Unreachable");
  }

  // TimescaleDB extension
  try {
    const ts = await apiGet("/health/timescaledb");
    if (ts.extension_installed) {
      setStatusRow("timescaledb", "ok", `Connected (v${ts.version})`);
    } else {
      setStatusRow("timescaledb", "error", "Extension missing");
    }
  } catch (err) {
    setStatusRow("timescaledb", "error", err.status ? `Error ${err.status}` : "Unreachable");
  }
}

function refreshDataFreshness(latestTimeIso) {
  document.getElementById("status-latest-data").textContent = formatTimestamp(latestTimeIso);
  document.getElementById("status-data-age").textContent = formatAge(latestTimeIso);
}

// --- asset list --------------------------------------------------------

async function loadAssets() {
  const listEl = document.getElementById("asset-list");
  try {
    const assets = await apiGet("/api/assets");
    state.assets = assets;

    if (assets.length === 0) {
      listEl.innerHTML = `<div class="asset-list-error">No assets configured in crypto_assets.</div>`;
      return;
    }

    listEl.innerHTML = "";
    assets.forEach((asset) => {
      const btn = document.createElement("button");
      btn.className = "asset-item";
      btn.dataset.symbol = asset.symbol;
      btn.innerHTML = `
        <span class="asset-symbol">${asset.symbol}</span>
        <span class="asset-name">${asset.name}</span>
      `;
      btn.addEventListener("click", () => selectAsset(asset.symbol));
      listEl.appendChild(btn);
    });

    selectAsset(assets[0].symbol);
  } catch (err) {
    listEl.innerHTML = `<div class="asset-list-error">Failed to load assets: ${err.message}</div>`;
  }
}

function selectAsset(symbol) {
  state.selectedSymbol = symbol;
  document.querySelectorAll(".asset-item").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.symbol === symbol);
  });
  loadQuote(symbol);
  loadChart(symbol, state.selectedRange);
  loadCandles(symbol);
}

// --- quote panel --------------------------------------------------------

async function loadQuote(symbol) {
  const asset = state.assets.find((a) => a.symbol === symbol);
  document.getElementById("quote-symbol").textContent = symbol;
  document.getElementById("quote-name").textContent = asset ? asset.name : "";

  try {
    const data = await apiGet(`/api/market/${symbolToUrlSegment(symbol)}/latest`);

    document.getElementById("quote-price").textContent = formatPrice(data.latest_price);
    document.getElementById("quote-time").textContent = formatTimestamp(data.latest_time);
    document.getElementById("quote-volume").textContent = formatVolume(data.latest_volume);
    document.getElementById("quote-prev").textContent = formatPrice(data.previous_price);

    const changeEl = document.getElementById("quote-change");
    if (data.price_change === null || data.price_change === undefined) {
      changeEl.textContent = "No previous tick to compare";
      changeEl.className = "quote-change is-neutral";
    } else {
      const sign = data.price_change >= 0 ? "+" : "";
      const pct = data.percent_change !== null && data.percent_change !== undefined
        ? ` (${sign}${data.percent_change.toFixed(2)}%)`
        : "";
      changeEl.textContent = `${sign}${formatPrice(data.price_change)}${pct}`;
      changeEl.className = `quote-change ${data.price_change >= 0 ? "is-positive" : "is-negative"}`;
    }

    refreshDataFreshness(data.latest_time);
  } catch (err) {
    document.getElementById("quote-price").textContent = "—";
    document.getElementById("quote-change").textContent =
      err.status === 404 ? "No tick data for this symbol" : `Error: ${err.message}`;
    document.getElementById("quote-change").className = "quote-change is-neutral";
  }
}

// --- chart panel ----------------------------------------------------

function ensureChart() {
  if (state.chart) return state.chart;
  const ctx = document.getElementById("price-chart").getContext("2d");
  state.chart = new Chart(ctx, {
    type: "line",
    data: { datasets: [{
      label: "Price",
      data: [],
      borderColor: "#4c8dff",
      backgroundColor: "rgba(76,141,255,0.08)",
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.15,
      fill: true,
    }]},
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "time",
          time: { tooltipFormat: "MMM d, HH:mm:ss" },
          grid: { color: "#1c252d" },
          ticks: { color: "#8b98a5", maxRotation: 0 },
        },
        y: {
          grid: { color: "#1c252d" },
          ticks: { color: "#8b98a5" },
        },
      },
      plugins: {
        legend: { display: false },
      },
    },
  });
  return state.chart;
}

async function loadChart(symbol, range) {
  const emptyEl = document.getElementById("chart-empty");
  const errorEl = document.getElementById("chart-error");
  emptyEl.hidden = true;
  errorEl.hidden = true;

  try {
    const ticks = await apiGet(`/api/market/${symbolToUrlSegment(symbol)}/ticks?range=${range}`);
    const chart = ensureChart();

    if (!ticks.length) {
      chart.data.datasets[0].data = [];
      chart.update();
      emptyEl.hidden = false;
      return;
    }

    chart.data.datasets[0].data = ticks.map((t) => ({ x: t.time, y: t.price }));
    chart.update();
  } catch (err) {
    errorEl.textContent = err.status === 404
      ? "No tick data for this symbol/range."
      : `Failed to load chart: ${err.message}`;
    errorEl.hidden = false;
  }
}

document.getElementById("range-toggle").addEventListener("click", (e) => {
  const btn = e.target.closest(".range-btn");
  if (!btn) return;
  document.querySelectorAll(".range-btn").forEach((b) => b.classList.remove("is-active"));
  btn.classList.add("is-active");
  state.selectedRange = btn.dataset.range;
  if (state.selectedSymbol) loadChart(state.selectedSymbol, state.selectedRange);
});

// --- daily candles ----------------------------------------------------

async function loadCandles(symbol) {
  const body = document.getElementById("candle-body");
  body.innerHTML = `<tr><td colspan="7" class="table-loading">Loading candles…</td></tr>`;

  try {
    const candles = await apiGet(`/api/market/${symbolToUrlSegment(symbol)}/daily?days=14`);

    if (!candles.length) {
      body.innerHTML = `<tr><td colspan="7" class="table-empty">No daily candles yet for this symbol. The continuous aggregate may not have refreshed, or there isn't 1 day of data yet.</td></tr>`;
      return;
    }

    body.innerHTML = candles
      .slice()
      .reverse()
      .map((c) => `
        <tr>
          <td>${new Date(c.bucket).toLocaleDateString()}</td>
          <td>${c.symbol}</td>
          <td class="num">${formatPrice(c.open)}</td>
          <td class="num">${formatPrice(c.high)}</td>
          <td class="num">${formatPrice(c.low)}</td>
          <td class="num">${formatPrice(c.close)}</td>
          <td class="num">${formatVolume(c.day_volume)}</td>
        </tr>
      `).join("");
  } catch (err) {
    const message = err.status === 404
      ? "No daily candle data for this symbol."
      : `Failed to load candles: ${err.message}`;
    body.innerHTML = `<tr><td colspan="7" class="table-error">${message}</td></tr>`;
  }
}

// --- boot ----------------------------------------------------------

loadAssets();
refreshStatus();
setInterval(refreshStatus, 15000);
