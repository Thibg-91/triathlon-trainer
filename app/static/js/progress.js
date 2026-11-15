// Graphique de volume hebdomadaire (Chart.js)
(async () => {
  const canvas = document.getElementById("weekly-chart");
  if (!canvas || !window.Chart) return;

  const rows = await fetch("/api/stats/weekly").then((r) => r.json());
  if (!rows.length) return;

  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const label = (iso) => {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
  };

  const bar = (key, name, cssVar) => ({
    type: "bar",
    label: name,
    data: rows.map((r) => r[key]),
    backgroundColor: color(cssVar),
    stack: "done",
    borderRadius: 3,
  });

  Chart.defaults.color = color("--muted");
  Chart.defaults.borderColor = color("--border");

  new Chart(canvas, {
    data: {
      labels: rows.map((r) => label(r.week)),
      datasets: [
        bar("swim", "Natation", "--swim"),
        bar("bike", "Vélo", "--bike"),
        bar("run", "Course", "--run"),
        {
          type: "line",
          label: "Prévu",
          data: rows.map((r) => r.planned || null),
          borderColor: color("--text"),
          borderDash: [5, 4],
          pointRadius: 2,
          tension: 0.25,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: { stacked: true, grid: { display: false } },
        y: { stacked: true, beginAtZero: true, title: { display: true, text: "minutes" } },
      },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
    },
  });
})();
