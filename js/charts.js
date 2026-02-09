/**
 * CaP-X Interactive Charts
 * D3.js visualizations for model performance timeline and highlight figures
 */

/* ==========================================
   Timeline Chart — AI Progress on CaP-X
   ========================================== */

async function initTimelineChart() {
  const response = await fetch("data/model_data.json");
  const data = await response.json();

  const container = document.getElementById("timeline-chart");
  if (!container) return;

  // Clear any existing content
  container.innerHTML = "";

  const tooltip = document.getElementById("timeline-tooltip");

  // Dimensions
  const margin = { top: 30, right: 50, bottom: 50, left: 60 };
  const width = container.clientWidth - margin.left - margin.right;
  const height = 380 - margin.top - margin.bottom;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Parse dates
  const models = data.models.map(m => ({
    ...m,
    date: new Date(m.releaseDate),
  }));

  // Scales
  const xMin = new Date("2024-08-01");
  const xMax = new Date("2026-02-01");
  const x = d3.scaleTime()
    .domain([xMin, xMax])
    .range([0, width]);

  const yMax = Math.max(data.humanBaseline, d3.max(models, d => d.avgSuccessRate)) * 1.15;
  const y = d3.scaleLinear()
    .domain([0, yMax])
    .range([height, 0]);

  // Grid lines
  g.append("g")
    .attr("class", "grid-lines")
    .selectAll("line")
    .data(y.ticks(6))
    .enter()
    .append("line")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", d => y(d))
    .attr("y2", d => y(d))
    .attr("stroke", "#e8eaed")
    .attr("stroke-width", 0.5);

  // X axis
  const xAxis = d3.axisBottom(x)
    .ticks(d3.timeMonth.every(2))
    .tickFormat(d => {
      const month = d3.timeFormat("%b")(d);
      if (d.getMonth() === 0) return `${month}\n${d.getFullYear()}`;
      if (d.getMonth() === 8 && d.getFullYear() === 2024) return `${month}\n${d.getFullYear()}`;
      return month;
    });

  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(xAxis)
    .call(g => g.select(".domain").attr("stroke", "#d0d4da"))
    .call(g => g.selectAll(".tick line").attr("stroke", "#d0d4da"))
    .call(g => g.selectAll(".tick text").attr("fill", "#8888a0").attr("font-size", "11px"));

  // Y axis
  const yAxis = d3.axisLeft(y)
    .ticks(6)
    .tickFormat(d => d + "%");

  g.append("g")
    .call(yAxis)
    .call(g => g.select(".domain").attr("stroke", "#d0d4da"))
    .call(g => g.selectAll(".tick line").attr("stroke", "#d0d4da"))
    .call(g => g.selectAll(".tick text").attr("fill", "#8888a0").attr("font-size", "11px"));

  // Y axis label
  g.append("text")
    .attr("transform", "rotate(-90)")
    .attr("y", -45)
    .attr("x", -height / 2)
    .attr("text-anchor", "middle")
    .attr("fill", "#4a4a6a")
    .attr("font-size", "12px")
    .attr("font-weight", "600")
    .text("Task Success Rate (%)");

  // Human baseline
  g.append("line")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", y(data.humanBaseline))
    .attr("y2", y(data.humanBaseline))
    .attr("stroke", "#C0392B")
    .attr("stroke-width", 2)
    .attr("stroke-dasharray", "8,4")
    .attr("opacity", 0.6);

  g.append("text")
    .attr("x", width - 5)
    .attr("y", y(data.humanBaseline) - 8)
    .attr("text-anchor", "end")
    .attr("fill", "#C0392B")
    .attr("font-size", "11px")
    .attr("font-weight", "700")
    .text(`Human (${data.humanBaseline.toFixed(1)}%)`);

  // Compute SOTA frontier
  const sortedByDate = [...models].sort((a, b) => a.date - b.date);
  const sotaModels = [];
  let currentBest = -1;
  for (const m of sortedByDate) {
    if (m.avgSuccessRate > currentBest) {
      sotaModels.push(m);
      currentBest = m.avgSuccessRate;
    }
  }
  const sotaIds = new Set(sotaModels.map(m => m.id));

  // SOTA frontier line
  if (sotaModels.length > 1) {
    const lineGen = d3.line()
      .x(d => x(d.date))
      .y(d => y(d.avgSuccessRate))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(sotaModels)
      .attr("fill", "none")
      .attr("stroke", "#3B82F6")
      .attr("stroke-width", 2.5)
      .attr("stroke-dasharray", "6,4")
      .attr("opacity", 0.6)
      .attr("d", lineGen);
  }

  // Preload logos
  const logoPromises = {};
  const logoImages = {};
  for (const [company, path] of Object.entries(data.companyLogos)) {
    logoPromises[company] = new Promise((resolve) => {
      const img = new Image();
      img.onload = () => { logoImages[company] = img; resolve(); };
      img.onerror = () => resolve();
      img.src = path;
    });
  }
  await Promise.all(Object.values(logoPromises));

  // Draw model points
  const LOGO_SIZE = 28;
  const NON_SOTA_ALPHA = 0.45;

  // Define clip paths for circular logos
  const defs = svg.append("defs");

  models.forEach((m, i) => {
    defs.append("clipPath")
      .attr("id", `clip-${i}`)
      .append("circle")
      .attr("cx", 0)
      .attr("cy", 0)
      .attr("r", LOGO_SIZE / 2 - 2);
  });

  // Non-SOTA models first (background)
  const nonSota = models.filter(m => !sotaIds.has(m.id));
  const sota = models.filter(m => sotaIds.has(m.id));

  function drawModel(m, i, isSota) {
    const cx = x(m.date);
    const cy = y(m.avgSuccessRate);
    const color = isSota ? (data.companyColors[m.company] || "#666") : "#C0C0C0";
    const size = isSota ? LOGO_SIZE + 4 : LOGO_SIZE;
    const strokeWidth = isSota ? 2.5 : 1.5;
    const alpha = isSota ? 1 : NON_SOTA_ALPHA;

    const group = g.append("g")
      .attr("transform", `translate(${cx},${cy})`)
      .attr("opacity", 0)
      .style("cursor", "pointer");

    // Circle border
    group.append("circle")
      .attr("r", size / 2 + 2)
      .attr("fill", "#fff")
      .attr("stroke", color)
      .attr("stroke-width", strokeWidth)
      .attr("stroke-dasharray", m.isClosed ? "none" : "4,2");

    // Logo image
    if (logoImages[m.company]) {
      const clipId = `clip-model-${m.id.replace(/[\/\.]/g, "-")}`;
      defs.append("clipPath")
        .attr("id", clipId)
        .append("circle")
        .attr("cx", 0)
        .attr("cy", 0)
        .attr("r", size / 2 - 1);

      group.append("image")
        .attr("href", data.companyLogos[m.company])
        .attr("x", -size / 2 + 1)
        .attr("y", -size / 2 + 1)
        .attr("width", size - 2)
        .attr("height", size - 2)
        .attr("clip-path", `url(#${clipId})`)
        .attr("preserveAspectRatio", "xMidYMid slice");
    }

    // Label
    const labelY = isSota ? -(size / 2 + 12) : (size / 2 + 14);
    group.append("text")
      .attr("y", labelY)
      .attr("text-anchor", "middle")
      .attr("fill", color)
      .attr("font-size", isSota ? "11px" : "9px")
      .attr("font-weight", isSota ? "700" : "500")
      .text(m.displayName);

    // Hover interactions
    group
      .on("mouseenter", function (event) {
        d3.select(this).transition().duration(150)
          .attr("transform", `translate(${cx},${cy}) scale(1.15)`);

        showTooltip(event, m, data, tooltip);
      })
      .on("mousemove", function (event) {
        moveTooltip(event, tooltip, container);
      })
      .on("mouseleave", function () {
        d3.select(this).transition().duration(150)
          .attr("transform", `translate(${cx},${cy}) scale(1)`);

        hideTooltip(tooltip);
      });

    // Animate in with GSAP if available
    if (typeof gsap !== "undefined") {
      gsap.to(group.node(), {
        opacity: alpha,
        duration: 0.5,
        delay: 0.3 + i * 0.08,
        ease: "power2.out",
      });
    } else {
      group.attr("opacity", alpha);
    }
  }

  nonSota.forEach((m, i) => drawModel(m, i, false));
  sota.forEach((m, i) => drawModel(m, i + nonSota.length, true));
}

function showTooltip(event, model, data, tooltip) {
  if (!tooltip) return;

  let html = `
    <div class="tooltip-header" style="color: ${data.companyColors[model.company] || '#333'}">${model.displayName}</div>
    <div class="tooltip-company">${model.company} &middot; ${model.type} &middot; ${model.isClosed ? "Closed" : "Open"} Source</div>
    <div class="tooltip-stat" style="font-weight:600; margin-bottom:0.4rem;">
      <span>Avg Success Rate</span>
      <span>${model.avgSuccessRate.toFixed(1)}%</span>
    </div>
    <hr style="border:none;border-top:1px solid #e8eaed;margin:0.3rem 0;">
  `;

  for (const [task, val] of Object.entries(model.taskSuccessRates)) {
    const displayVal = val !== null ? `${val}%` : "N/A";
    const barWidth = val !== null ? Math.min(val, 100) : 0;
    html += `
      <div class="tooltip-stat">
        <span class="task-name">${task}</span>
        <span class="task-value">${displayVal}</span>
      </div>
    `;
  }

  tooltip.innerHTML = html;
  tooltip.classList.add("visible");
}

function moveTooltip(event, tooltip, container) {
  if (!tooltip || !container) return;
  const rect = container.getBoundingClientRect();
  let left = event.clientX - rect.left + 16;
  let top = event.clientY - rect.top - 10;

  // Keep tooltip within bounds
  if (left + 280 > rect.width) left = event.clientX - rect.left - 290;
  if (top < 0) top = 10;

  tooltip.style.left = left + "px";
  tooltip.style.top = top + "px";
}

function hideTooltip(tooltip) {
  if (!tooltip) return;
  tooltip.classList.remove("visible");
}

/* ==========================================
   Highlight Figure 1 — Task Success Rates
   Bar chart of frontier models across tasks
   ========================================== */

async function initHighlightFigure1() {
  const response = await fetch("data/model_data.json");
  const data = await response.json();

  const container = document.getElementById("highlight-fig-1");
  if (!container) return;
  container.innerHTML = "";

  // Pick top 5 models by avgSuccessRate
  const topModels = [...data.models]
    .sort((a, b) => b.avgSuccessRate - a.avgSuccessRate)
    .slice(0, 5);

  const margin = { top: 20, right: 20, bottom: 60, left: 50 };
  const width = container.clientWidth - margin.left - margin.right;
  const height = 220 - margin.top - margin.bottom;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x0 = d3.scaleBand()
    .domain(topModels.map(m => m.displayName))
    .range([0, width])
    .padding(0.3);

  const y = d3.scaleLinear()
    .domain([0, Math.max(40, d3.max(topModels, d => d.avgSuccessRate) * 1.2)])
    .range([height, 0]);

  // Grid
  g.selectAll(".grid-line")
    .data(y.ticks(4))
    .enter()
    .append("line")
    .attr("x1", 0).attr("x2", width)
    .attr("y1", d => y(d)).attr("y2", d => y(d))
    .attr("stroke", "#e8eaed").attr("stroke-width", 0.5);

  // Bars
  g.selectAll(".bar")
    .data(topModels)
    .enter()
    .append("rect")
    .attr("x", d => x0(d.displayName))
    .attr("y", d => y(d.avgSuccessRate))
    .attr("width", x0.bandwidth())
    .attr("height", d => height - y(d.avgSuccessRate))
    .attr("fill", d => data.companyColors[d.company] || "#76b900")
    .attr("rx", 4)
    .attr("opacity", 0.85);

  // Bar labels
  g.selectAll(".bar-label")
    .data(topModels)
    .enter()
    .append("text")
    .attr("x", d => x0(d.displayName) + x0.bandwidth() / 2)
    .attr("y", d => y(d.avgSuccessRate) - 5)
    .attr("text-anchor", "middle")
    .attr("font-size", "10px")
    .attr("font-weight", "600")
    .attr("fill", "#4a4a6a")
    .text(d => d.avgSuccessRate.toFixed(1) + "%");

  // X axis
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x0))
    .call(g => g.select(".domain").attr("stroke", "#d0d4da"))
    .call(g => g.selectAll(".tick line").remove())
    .call(g => g.selectAll(".tick text")
      .attr("fill", "#4a4a6a")
      .attr("font-size", "10px")
      .attr("transform", "rotate(-25)")
      .attr("text-anchor", "end"));

  // Y axis
  g.append("g")
    .call(d3.axisLeft(y).ticks(4).tickFormat(d => d + "%"))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll(".tick line").remove())
    .call(g => g.selectAll(".tick text").attr("fill", "#8888a0").attr("font-size", "10px"));
}

/* ==========================================
   Highlight Figure 2 — Model Size vs Performance
   (Abstraction analysis: smaller models catch up)
   ========================================== */

async function initHighlightFigure2() {
  const container = document.getElementById("highlight-fig-4");
  if (!container) return;
  container.innerHTML = "";

  const response = await fetch("data/model_data.json");
  const data = await response.json();

  // Approximate model sizes (for visualization)
  const modelSizes = {
    "GPT-5.2": 1800, "GPT-5.1": 1500, "Gemini 3 Pro": 1200,
    "Opus 4.5": 1000, "o1": 900, "o4-mini": 200,
    "Haiku 4.5": 150, "GPT-OSS-120B": 120, "GPT-OSS-20B": 20,
    "Qwen3-235B": 235, "Kimi K2": 235, "DeepSeek 3.1": 600,
  };

  const modelsWithSize = data.models
    .filter(m => modelSizes[m.displayName])
    .map(m => ({ ...m, size: modelSizes[m.displayName] }));

  const margin = { top: 20, right: 20, bottom: 40, left: 50 };
  const width = container.clientWidth - margin.left - margin.right;
  const height = 220 - margin.top - margin.bottom;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLog()
    .domain([10, 2000])
    .range([0, width]);

  const y = d3.scaleLinear()
    .domain([0, d3.max(modelsWithSize, d => d.avgSuccessRate) * 1.2])
    .range([height, 0]);

  // Grid
  g.selectAll(".grid-line")
    .data(y.ticks(4))
    .enter()
    .append("line")
    .attr("x1", 0).attr("x2", width)
    .attr("y1", d => y(d)).attr("y2", d => y(d))
    .attr("stroke", "#e8eaed").attr("stroke-width", 0.5);

  // Scatter points
  g.selectAll(".point")
    .data(modelsWithSize)
    .enter()
    .append("circle")
    .attr("cx", d => x(d.size))
    .attr("cy", d => y(d.avgSuccessRate))
    .attr("r", 6)
    .attr("fill", d => data.companyColors[d.company] || "#76b900")
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5)
    .attr("opacity", 0.85);

  // Labels
  g.selectAll(".point-label")
    .data(modelsWithSize)
    .enter()
    .append("text")
    .attr("x", d => x(d.size))
    .attr("y", d => y(d.avgSuccessRate) - 10)
    .attr("text-anchor", "middle")
    .attr("font-size", "8px")
    .attr("fill", "#4a4a6a")
    .text(d => d.displayName);

  // X axis
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x).ticks(4, "~s").tickFormat(d => d >= 1000 ? (d/1000) + "T" : d + "B"))
    .call(g => g.select(".domain").attr("stroke", "#d0d4da"))
    .call(g => g.selectAll(".tick text").attr("fill", "#8888a0").attr("font-size", "10px"));

  g.append("text")
    .attr("x", width / 2)
    .attr("y", height + 35)
    .attr("text-anchor", "middle")
    .attr("fill", "#4a4a6a")
    .attr("font-size", "11px")
    .text("Model Size (approx. params)");

  // Y axis
  g.append("g")
    .call(d3.axisLeft(y).ticks(4).tickFormat(d => d + "%"))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll(".tick line").remove())
    .call(g => g.selectAll(".tick text").attr("fill", "#8888a0").attr("font-size", "10px"));
}

/* ==========================================
   Initialize all charts
   ========================================== */

function initAllCharts() {
  initTimelineChart();
  initHighlightFigure1();
  initHighlightFigure2();
}

// Resize handler
let resizeTimeout;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(() => {
    initAllCharts();
  }, 250);
});
