// Столбцы по дням, сложенные по тональности. Негатив у основания: его важнее всего сравнивать.
(function () {
  const days = JSON.parse(document.getElementById("days-data").textContent);
  const canvas = document.getElementById("by-day");
  const SERIES = [
    ["negative", "Негатив"],
    ["neutral", "Нейтрально"],
    ["positive", "Позитив"],
    ["unrated", "Без оценки"],
  ];
  const fmtDay = (iso) => {
    const [, m, d] = iso.split("-");
    return `${d}.${m}`;
  };
  let chart;

  function render() {
    const css = getComputedStyle(document.documentElement);
    const v = (name) => css.getPropertyValue(name).trim();
    const surface = v("--pico-card-background-color") || v("--pico-background-color");
    const text = v("--pico-muted-color");
    const grid = v("--chart-grid");

    const datasets = SERIES.map(([key, label]) => {
      const color = v(`--s-${key}`);
      const unrated = key === "unrated";
      return {
        label,
        data: days.map((d) => d[key]),
        // «Без оценки» — только контур, чтобы не спорить с нейтральным серым
        backgroundColor: unrated ? "transparent" : color,
        borderColor: unrated ? color : surface,
        borderWidth: unrated ? 1.5 : { top: 2 },
        borderRadius: 4,
        borderSkipped: "bottom",
        maxBarThickness: 28,
      };
    }).filter((ds) => ds.data.some((n) => n > 0));

    chart?.destroy();
    chart = new Chart(canvas, {
      type: "bar",
      data: { labels: days.map((d) => fmtDay(d.day)), datasets },
      options: {
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false }, // легенда в HTML над графиком
          tooltip: {
            callbacks: {
              footer: (items) => `Всего: ${items.reduce((s, i) => s + i.parsed.y, 0)}`,
            },
          },
        },
        scales: {
          x: { stacked: true, grid: { display: false }, ticks: { color: text, maxRotation: 0, autoSkipPadding: 12 } },
          y: { stacked: true, beginAtZero: true, grid: { color: grid }, border: { display: false },
               ticks: { color: text, precision: 0 } },
        },
      },
    });
  }

  render();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
})();
