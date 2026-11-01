// Charts for the monthly report page.
// All numbers come from /api/report-data; nothing is computed in the browser.

const fmt = (n) => Number(n).toLocaleString("en-US");

const COLORS = [
  "#1f3a5f", "#c0392b", "#1e8449", "#d68910", "#7d3c98",
  "#148f77", "#2e86c1", "#a04000", "#566573", "#b7950b",
];

let pieChart = null;
let lineChart = null;
let barChart = null;

// Chart.js must use a font that can render Persian text
Chart.defaults.font.family = "Tahoma, Vazirmatn, sans-serif";

function renderSummary(totals) {
  document.getElementById("sum-income").textContent = fmt(totals.income);
  document.getElementById("sum-expense").textContent = fmt(totals.expense);
  document.getElementById("sum-balance").textContent = fmt(totals.balance);
}

function renderPie(items) {
  const empty = document.getElementById("pie-empty");
  const canvas = document.getElementById("pie-chart");
  if (pieChart) pieChart.destroy();

  empty.hidden = items.length > 0;
  canvas.hidden = items.length === 0;
  if (items.length === 0) return;

  pieChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: items.map((i) => i.name),
      datasets: [{
        data: items.map((i) => i.total),
        backgroundColor: items.map((_, idx) => COLORS[idx % COLORS.length]),
      }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", rtl: true },
        tooltip: {
          callbacks: { label: (ctx) => ` ${ctx.label}: ${fmt(ctx.parsed)}` },
        },
      },
    },
  });
}

function renderLine(trend) {
  if (lineChart) lineChart.destroy();
  lineChart = new Chart(document.getElementById("line-chart"), {
    type: "line",
    data: {
      labels: trend.map((t) => t.month),
      datasets: [
        {
          label: "درآمد",
          data: trend.map((t) => t.income),
          borderColor: "#1e8449",
          backgroundColor: "#1e8449",
          tension: 0.25,
        },
        {
          label: "هزینه",
          data: trend.map((t) => t.expense),
          borderColor: "#c0392b",
          backgroundColor: "#c0392b",
          tension: 0.25,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { rtl: true } },
      scales: { y: { beginAtZero: true, ticks: { callback: (v) => fmt(v) } } },
    },
  });
}

function renderBar(trend) {
  if (barChart) barChart.destroy();
  barChart = new Chart(document.getElementById("bar-chart"), {
    type: "bar",
    data: {
      labels: trend.map((t) => t.month),
      datasets: [
        { label: "درآمد", data: trend.map((t) => t.income), backgroundColor: "#1e8449" },
        { label: "هزینه", data: trend.map((t) => t.expense), backgroundColor: "#c0392b" },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { rtl: true } },
      scales: { y: { beginAtZero: true, ticks: { callback: (v) => fmt(v) } } },
    },
  });
}

async function loadReport() {
  const year = document.getElementById("year").value;
  const month = document.getElementById("month").value;
  const response = await fetch(`/api/report-data?year=${year}&month=${month}`);
  if (!response.ok) {
    console.error("Failed to load report data", response.status);
    return;
  }
  const data = await response.json();
  renderSummary(data.totals);
  renderPie(data.by_category);
  renderLine(data.trend);
  renderBar(data.trend);
}

document.getElementById("year").addEventListener("change", loadReport);
document.getElementById("month").addEventListener("change", loadReport);
loadReport();
