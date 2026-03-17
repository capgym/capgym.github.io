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
  const margin = { top: 20, right: 50, bottom: 40, left: 60 };
  const width = container.clientWidth - margin.left - margin.right;

  // Calculate chart height to fill remaining viewport below the chart container,
  // leaving space for legend (~40px) and section bottom padding (~24px)
  const chartTop = container.getBoundingClientRect().top;
  const reserveBelow = 80; // legend + padding
  const availableHeight = window.innerHeight - chartTop - reserveBelow;
  const chartHeight = Math.max(Math.min(availableHeight, 500), 250);
  const height = chartHeight - margin.top - margin.bottom;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Define defs early (needed for hatch patterns and clip paths)
  const defs = svg.append("defs");

  // Parse dates
  const models = data.models.map(m => ({
    ...m,
    date: new Date(m.releaseDate),
  }));

  // Piecewise X scale: compress sparse early period, expand dense later period
  // Sep 2024 - Jul 2025 (sparse, 2 models) → 20% of width
  // Jul 2025 - Feb 2026 (dense, 10 models) → 80% of width
  const xMin = new Date("2024-08-01");
  const xBreak = new Date("2025-07-01");
  const xMax = new Date("2026-01-15");
  const xBreakPct = 0.20;

  function x(date) {
    const t = date.getTime();
    if (t <= xBreak.getTime()) {
      const pct = (t - xMin.getTime()) / (xBreak.getTime() - xMin.getTime());
      return pct * xBreakPct * width;
    } else {
      const pct = (t - xBreak.getTime()) / (xMax.getTime() - xBreak.getTime());
      return (xBreakPct + pct * (1 - xBreakPct)) * width;
    }
  }
  x.domain = () => [xMin, xMax];

  // Y scale: cap at model range, human baseline shown as off-scale annotation
  const modelMax = d3.max(models, d => d.avgSuccessRate);
  const yMax = Math.ceil(modelMax / 5) * 5 + 10; // round up + padding
  const y = d3.scaleLinear()
    .domain([0, yMax])
    .range([height, 0]);

  // Grid lines
  g.append("g")
    .attr("class", "grid-lines")
    .selectAll("line")
    .data(y.ticks(5))
    .enter()
    .append("line")
    .attr("x1", 0)
    .attr("x2", width)
    .attr("y1", d => y(d))
    .attr("y2", d => y(d))
    .attr("stroke", "#e5e5e5")
    .attr("stroke-width", 0.5);

  // X axis — manual ticks for piecewise scale
  const xTickDates = [
    new Date("2024-09-01"), new Date("2025-01-01"),
    new Date("2025-04-01"), new Date("2025-07-01"),
    new Date("2025-08-01"), new Date("2025-09-01"),
    new Date("2025-10-01"), new Date("2025-11-01"),
    new Date("2025-12-01"), new Date("2026-01-01"),
  ];

  const xAxisG = g.append("g")
    .attr("transform", `translate(0,${height})`);

  // Axis line
  xAxisG.append("line")
    .attr("x1", 0).attr("x2", width)
    .attr("stroke", "#e5e5e5");

  // Year divider lines
  [new Date("2025-01-01"), new Date("2026-01-01")].forEach(d => {
    const tx = x(d);
    if (tx <= 0 || tx >= width) return;

    // Vertical line through full chart
    g.append("line")
      .attr("x1", tx).attr("x2", tx)
      .attr("y1", 0).attr("y2", height)
      .attr("stroke", "#ccc")
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,3");

    // Year label below axis
    xAxisG.append("text")
      .attr("x", tx).attr("y", 34)
      .attr("text-anchor", "middle")
      .attr("fill", "#000").attr("font-size", "12px")
      .attr("font-weight", "700")
      .text(d.getFullYear());
  });

  // Ticks
  xTickDates.forEach(d => {
    const tx = x(d);
    if (tx < 0 || tx > width) return;
    const month = d3.timeFormat("%b")(d);
    const label = month;

    xAxisG.append("line")
      .attr("x1", tx).attr("x2", tx)
      .attr("y1", 0).attr("y2", 5)
      .attr("stroke", "#e5e5e5");

    xAxisG.append("text")
      .attr("x", tx).attr("y", 20)
      .attr("text-anchor", "middle")
      .attr("fill", "#666").attr("font-size", "12px")
      .text(label);
  });

  // Y axis
  const yAxis = d3.axisLeft(y)
    .ticks(5)
    .tickFormat(d => d + "%");

  g.append("g")
    .call(yAxis)
    .call(g => g.select(".domain").attr("stroke", "#e5e5e5"))
    .call(g => g.selectAll(".tick line").attr("stroke", "#e5e5e5"))
    .call(g => g.selectAll(".tick text").attr("fill", "#666").attr("font-size", "12px"));

  // Y axis label
  g.append("text")
    .attr("transform", "rotate(-90)")
    .attr("y", -42)
    .attr("x", -height / 2)
    .attr("text-anchor", "middle")
    .attr("fill", "#666")
    .attr("font-size", "13px")
    .attr("font-weight", "600")
    .text("Avg. Success Rate (%)");

  // Human baseline — off-scale annotation with prominent axis break
  const breakZoneTop = 0;
  const breakZoneBottom = 50;
  const breakZoneMid = breakZoneTop + 16;

  // Diagonal hatch pattern for break zone
  const hatchId = "axis-break-hatch";
  defs.append("pattern")
    .attr("id", hatchId)
    .attr("patternUnits", "userSpaceOnUse")
    .attr("width", 8).attr("height", 8)
    .append("path")
    .attr("d", "M0,8 L8,0")
    .attr("stroke", "#ccc")
    .attr("stroke-width", 1);

  // Break zone background
  g.append("rect")
    .attr("x", 0).attr("y", breakZoneTop)
    .attr("width", width).attr("height", breakZoneBottom - breakZoneTop)
    .attr("fill", `url(#${hatchId})`);

  // Break zone borders (wavy lines)
  function wavyPath(yPos, w) {
    let d = `M0,${yPos}`;
    const step = 10;
    const amp = 3;
    for (let px = 0; px < w; px += step) {
      d += ` l${step / 2},${-amp} l${step / 2},${amp}`;
    }
    return d;
  }
  g.append("path").attr("d", wavyPath(breakZoneTop, width))
    .attr("fill", "none").attr("stroke", "#999").attr("stroke-width", 1.5);
  g.append("path").attr("d", wavyPath(breakZoneBottom, width))
    .attr("fill", "none").attr("stroke", "#999").attr("stroke-width", 1.5);

  // Human baseline dashed line inside break zone
  g.append("line")
    .attr("x1", 0).attr("x2", width)
    .attr("y1", breakZoneMid).attr("y2", breakZoneMid)
    .attr("stroke", "#C0392B")
    .attr("stroke-width", 2)
    .attr("stroke-dasharray", "8,4")
    .attr("opacity", 0.7);

  // Human baseline label with background
  const labelText = `Human Baseline: ${data.humanBaseline.toFixed(1)}%`;
  const labelX = width - 8;
  const labelFontSize = 13;

  // Background rect
  const labelBg = g.append("rect")
    .attr("fill", "#C0392B")
    .attr("rx", 0);

  const labelEl = g.append("text")
    .attr("x", labelX)
    .attr("y", breakZoneMid)
    .attr("text-anchor", "end")
    .attr("dominant-baseline", "central")
    .attr("fill", "#fff")
    .attr("font-size", `${labelFontSize}px`)
    .attr("font-weight", "700")
    .attr("letter-spacing", "0.02em")
    .text(labelText);

  // Size background to text
  const bbox = labelEl.node().getBBox();
  labelBg
    .attr("x", bbox.x - 6)
    .attr("y", bbox.y - 3)
    .attr("width", bbox.width + 12)
    .attr("height", bbox.height + 6);

  // Animate human baseline badge
  if (typeof gsap !== "undefined") {
    gsap.from(labelBg.node(), { scaleX: 0, transformOrigin: "right center", duration: 0.6, delay: 0.8, ease: "power2.out" });
    gsap.from(labelEl.node(), { opacity: 0, duration: 0.4, delay: 1.2, ease: "power2.out" });
  }

  // Frontier AI callout — best model badge, at the level of best model's Y position
  const bestModel = [...models].sort((a, b) => b.avgSuccessRate - a.avgSuccessRate)[0];
  const frontierText = `Frontier AI: ${bestModel.avgSuccessRate.toFixed(1)}%`;
  const frontierColor = "#3B82F6";
  const frontierY = y(bestModel.avgSuccessRate);

  const frontierBg = g.append("rect")
    .attr("fill", frontierColor)
    .attr("rx", 0);

  const frontierEl = g.append("text")
    .attr("x", labelX)
    .attr("y", frontierY)
    .attr("text-anchor", "end")
    .attr("dominant-baseline", "central")
    .attr("fill", "#fff")
    .attr("font-size", `${labelFontSize}px`)
    .attr("font-weight", "700")
    .attr("letter-spacing", "0.02em")
    .text(frontierText);

  const fbbox = frontierEl.node().getBBox();
  frontierBg
    .attr("x", fbbox.x - 6)
    .attr("y", fbbox.y - 3)
    .attr("width", fbbox.width + 12)
    .attr("height", fbbox.height + 6);

  // Animate frontier badge
  if (typeof gsap !== "undefined") {
    gsap.from(frontierBg.node(), { scaleX: 0, transformOrigin: "right center", duration: 0.6, delay: 1.0, ease: "power2.out" });
    gsap.from(frontierEl.node(), { opacity: 0, duration: 0.4, delay: 1.4, ease: "power2.out" });
  }

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
  const NON_SOTA_ALPHA = 0.75;

  // Define clip paths for circular logos
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
    const color = data.companyColors[m.company] || "#666";
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
      .attr("font-size", isSota ? "13px" : "11px")
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

  const html = `
    <div class="tooltip-header" style="color: ${data.companyColors[model.company] || '#333'}">${model.displayName}</div>
    <div class="tooltip-company">${model.company} &middot; ${model.type} &middot; ${model.isClosed ? "Closed" : "Open"} Source</div>
    <div class="tooltip-stat" style="font-weight:700;">
      <span>Avg Success Rate</span>
      <span>${model.avgSuccessRate.toFixed(1)}%</span>
    </div>
  `;

  tooltip.innerHTML = html;
  tooltip.classList.add("visible");
}

function moveTooltip(event, tooltip, container) {
  if (!tooltip || !container) return;
  const wrapper = container.parentElement;
  const rect = wrapper.getBoundingClientRect();
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
   Highlight Figure 1 — AI vs Human Gap
   Dot strip showing all models vs human baseline
   ========================================== */

async function initHighlightFigure1() {
  const response = await fetch("data/model_data.json");
  const data = await response.json();

  const container = document.getElementById("highlight-fig-1");
  if (!container) return;
  container.innerHTML = "";

  // Filter to 5 frontier models
  const showIds = [
    "google/gemini-3-pro", "anthropic/claude-opus-4-5", "openai/gpt-5.2",
    "openai/gpt-oss-120b", "deepseek-ai/deepseek-v3.1-terminus"
  ];
  const models = showIds
    .map(id => data.models.find(m => m.id === id))
    .filter(Boolean)
    .sort((a, b) => b.avgSuccessRate - a.avgSuccessRate);
  const bestModel = models[0];
  const humanBaseline = data.humanBaseline;

  // Add human as the top row
  const rows = [
    { displayName: "Human", avgSuccessRate: humanBaseline, company: "_human" },
    ...models
  ];

  const labelWidth = 110;
  const pctWidth = 50;
  const margin = { top: 12, right: pctWidth + 10, bottom: 12, left: labelWidth };
  const width = container.clientWidth - margin.left - margin.right;
  const rowH = 28;
  const rowGap = 6;
  const humanGap = 14; // extra gap after human row
  const totalH = rows.length * rowH + (rows.length - 1) * rowGap + humanGap;
  const height = totalH;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", container.clientWidth)
    .attr("height", height + margin.top + margin.bottom);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  const x = d3.scaleLinear().domain([0, 100]).range([0, width]);

  rows.forEach((m, i) => {
    const isHuman = m.company === "_human";
    const yOffset = isHuman ? 0 : humanGap;
    const cy = i * (rowH + rowGap) + rowH / 2 + yOffset;
    const barH = 16;
    const color = isHuman ? "#76b900" : (data.companyColors[m.company] || "#76b900");
    const isBest = !isHuman && m.id === bestModel.id;

    // Bar
    g.append("rect")
      .attr("x", 0)
      .attr("y", cy - barH / 2)
      .attr("width", x(m.avgSuccessRate))
      .attr("height", barH)
      .attr("fill", color)
      .attr("opacity", isHuman ? 0.85 : (isBest ? 0.8 : 0.55))
      .attr("rx", 0);

    // Model name (left of bar)
    g.append("text")
      .attr("x", -10)
      .attr("y", cy)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "central")
      .attr("font-size", isHuman ? "12px" : (isBest ? "12px" : "11px"))
      .attr("font-weight", isHuman || isBest ? "700" : "500")
      .attr("fill", isHuman ? "#76b900" : "#333")
      .text(m.displayName);

    // Percentage (right of bar)
    g.append("text")
      .attr("x", x(m.avgSuccessRate) + 8)
      .attr("y", cy)
      .attr("dominant-baseline", "central")
      .attr("font-size", isHuman ? "13px" : (isBest ? "13px" : "11px"))
      .attr("font-weight", isHuman || isBest ? "800" : "600")
      .attr("fill", isHuman ? "#76b900" : "#333")
      .text(m.avgSuccessRate.toFixed(1) + "%");

    // Separator line after human row
    if (isHuman) {
      g.append("line")
        .attr("x1", -margin.left + 10).attr("x2", width + 40)
        .attr("y1", cy + rowH / 2 + humanGap / 2)
        .attr("y2", cy + rowH / 2 + humanGap / 2)
        .attr("stroke", "#e0e0e0").attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,3");
    }
  });
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
    .attr("font-size", "13px")
    .attr("fill", "#4a4a6a")
    .text(d => d.displayName);

  // X axis
  g.append("g")
    .attr("transform", `translate(0,${height})`)
    .call(d3.axisBottom(x).ticks(4, "~s").tickFormat(d => d >= 1000 ? (d/1000) + "T" : d + "B"))
    .call(g => g.select(".domain").attr("stroke", "#d0d4da"))
    .call(g => g.selectAll(".tick text").attr("fill", "#8888a0").attr("font-size", "12px"));

  g.append("text")
    .attr("x", width / 2)
    .attr("y", height + 35)
    .attr("text-anchor", "middle")
    .attr("fill", "#4a4a6a")
    .attr("font-size", "13px")
    .text("Model Size (approx. params)");

  // Y axis
  g.append("g")
    .call(d3.axisLeft(y).ticks(4).tickFormat(d => d + "%"))
    .call(g => g.select(".domain").remove())
    .call(g => g.selectAll(".tick line").remove())
    .call(g => g.selectAll(".tick text").attr("fill", "#8888a0").attr("font-size", "12px"));
}

/* ==========================================
   Highlight Figure 2 — CaP-Agent0 vs VLAs on LIBERO-PRO
   Data from Table 2 in the paper
   ========================================== */

function initHighlightFigure2VLA() {
  const container = document.getElementById("highlight-fig-2");
  if (!container) return;
  container.innerHTML = "";

  /* Data from Table 2: LIBERO-PRO (averaged across 30 tasks)
     Each suite has Pos (position perturbation) and Task (instruction perturbation) averages.
     Values are success rates as percentages. */
  const suites = [
    { name: "libero-object",  pi05_pos: 17, pi05_task: 1,  agent_pos: 22, agent_task: 18 },
    { name: "libero-goal",    pi05_pos: 0,  pi05_task: 38, agent_pos: 26, agent_task: 17 },
    { name: "libero-spatial", pi05_pos: 20, pi05_task: 1,  agent_pos: 12, agent_task: 14 },
  ];

  const suiteData = suites.map(s => ({
    name: s.name,
    pi05: Math.round((s.pi05_pos + s.pi05_task) / 2),
    agent: Math.round((s.agent_pos + s.agent_task) / 2),
  }));

  const overallAvg = {
    openVLA: 0,
    pi0: 0,
    pi05: Math.round(suites.reduce((a, s) => a + (s.pi05_pos + s.pi05_task) / 2, 0) / suites.length),
    agent: Math.round(suites.reduce((a, s) => a + (s.agent_pos + s.agent_task) / 2, 0) / suites.length),
  };

  const methods = [
    { key: "openVLA", label: "OpenVLA",    color: "#d0d0d0" },
    { key: "pi0",     label: "\u03C0\u2080",         color: "#c0c0c0" },
    { key: "pi05",    label: "\u03C0\u2080.\u2085",       color: "#888" },
    { key: "agent",   label: "CaP-Agent0", color: "#76b900" },
  ];

  /* ---- SVG setup ---- */
  const totalH = 290;
  const margin = { top: 36, right: 20, bottom: 36, left: 20 };
  const cw = container.clientWidth;
  const width = cw - margin.left - margin.right;
  const height = totalH - margin.top - margin.bottom;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", cw)
    .attr("height", totalH);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  /* ---- Layout: left (overall avg) | divider | right (per-suite) ---- */
  const labelColW = 80;                       // fixed label column
  const leftBarArea = width * 0.32;            // bar area for left panel
  const leftW = labelColW + leftBarArea;
  const dividerX = leftW + 14;
  const rightX = dividerX + 14;
  const rightW = width - rightX;

  /* ============ LEFT PANEL: Overall averages ============ */
  const leftG = g.append("g");

  const barH = 24;
  const barGap = 6;
  // Extra gap between trained group (3 bars) and training-free (1 bar)
  const groupSepExtra = 14;
  const trainedBlockH = 3 * barH + 2 * barGap;
  const totalBlockH = trainedBlockH + groupSepExtra + barH;
  const startY = (height - totalBlockH) / 2;

  // Section heading
  leftG.append("text")
    .attr("x", labelColW + leftBarArea / 2).attr("y", startY - 16)
    .attr("text-anchor", "middle")
    .attr("font-size", "10px").attr("font-weight", "700")
    .attr("fill", "#444").attr("letter-spacing", "0.8px")
    .text("OVERALL AVERAGE");

  // Category labels
  leftG.append("text")
    .attr("x", labelColW - 8).attr("y", startY - 4)
    .attr("text-anchor", "end")
    .attr("font-size", "8px").attr("font-weight", "700")
    .attr("fill", "#aaa").attr("letter-spacing", "0.6px")
    .text("TRAINED ON LIBERO");

  leftG.append("text")
    .attr("x", labelColW - 8).attr("y", startY + trainedBlockH + groupSepExtra - 4)
    .attr("text-anchor", "end")
    .attr("font-size", "8px").attr("font-weight", "700")
    .attr("fill", "#76b900").attr("letter-spacing", "0.6px")
    .text("TRAINING-FREE");

  const xScale = d3.scaleLinear().domain([0, 25]).range([0, leftBarArea]);

  methods.forEach((m, i) => {
    const isAgent = m.key === "agent";
    const by = i < 3
      ? startY + i * (barH + barGap)
      : startY + trainedBlockH + groupSepExtra;
    const val = overallAvg[m.key];

    // Method label — right-aligned to fixed column
    leftG.append("text")
      .attr("x", labelColW - 8).attr("y", by + barH / 2)
      .attr("text-anchor", "end").attr("dominant-baseline", "central")
      .attr("font-size", "11px").attr("font-weight", isAgent ? "700" : "600")
      .attr("fill", isAgent ? "#4a7a00" : "#666")
      .text(m.label);

    // Bar (all bars start at the same x)
    const barX = labelColW;
    if (val === 0) {
      leftG.append("rect")
        .attr("x", barX).attr("y", by)
        .attr("width", 2).attr("height", barH)
        .attr("fill", m.color);
      leftG.append("text")
        .attr("x", barX + 10).attr("y", by + barH / 2)
        .attr("dominant-baseline", "central")
        .attr("font-size", "11px").attr("font-weight", "700")
        .attr("fill", "#ccc")
        .text("0%");
    } else {
      leftG.append("rect")
        .attr("x", barX).attr("y", by)
        .attr("width", xScale(val)).attr("height", barH)
        .attr("fill", m.color);
      leftG.append("text")
        .attr("x", barX + xScale(val) + 6).attr("y", by + barH / 2)
        .attr("dominant-baseline", "central")
        .attr("font-size", "11px").attr("font-weight", "700")
        .attr("fill", isAgent ? "#4a7a00" : "#555")
        .text(val + "%");
    }
  });

  /* ---- Separator between trained group and CaP-Agent0 ---- */
  leftG.append("line")
    .attr("x1", labelColW).attr("x2", labelColW + leftBarArea)
    .attr("y1", startY + trainedBlockH + groupSepExtra / 2)
    .attr("y2", startY + trainedBlockH + groupSepExtra / 2)
    .attr("stroke", "#e8e8e8").attr("stroke-width", 1)
    .attr("stroke-dasharray", "4,3");

  /* ---- Vertical divider ---- */
  g.append("line")
    .attr("x1", dividerX).attr("x2", dividerX)
    .attr("y1", startY - 20).attr("y2", startY + totalBlockH + 16)
    .attr("stroke", "#e0e0e0").attr("stroke-width", 1);

  /* ============ RIGHT PANEL: Per-suite breakdown ============ */
  const rightG = g.append("g").attr("transform", `translate(${rightX}, 0)`);

  // Heading
  rightG.append("text")
    .attr("x", rightW / 2).attr("y", startY - 16)
    .attr("text-anchor", "middle")
    .attr("font-size", "10px").attr("font-weight", "700")
    .attr("fill", "#444").attr("letter-spacing", "0.8px")
    .text("BY TASK SUITE");

  // Chart area for vertical grouped bars
  const chartTop = startY + 4;
  const chartBottom = startY + totalBlockH - 4;
  const chartH = chartBottom - chartTop;

  const yAxisLabelW = 28;                      // space for "25%" etc.
  const chartLeft = yAxisLabelW;
  const chartRight = rightW - 4;
  const chartInnerW = chartRight - chartLeft;

  const suiteNames = suiteData.map(s => s.name);
  const xSuite = d3.scaleBand()
    .domain(suiteNames).range([chartLeft, chartRight]).paddingInner(0.3).paddingOuter(0.1);

  const yMax = 25;
  const yScale = d3.scaleLinear().domain([0, yMax]).range([chartBottom, chartTop]);

  // Y-axis grid lines + labels
  [0, 5, 10, 15, 20, 25].forEach(v => {
    rightG.append("line")
      .attr("x1", chartLeft).attr("x2", chartRight)
      .attr("y1", yScale(v)).attr("y2", yScale(v))
      .attr("stroke", v === 0 ? "#d0d0d0" : "#f0f0f0")
      .attr("stroke-width", v === 0 ? 0.8 : 0.5);
    if (v > 0) {
      rightG.append("text")
        .attr("x", chartLeft - 4).attr("y", yScale(v))
        .attr("text-anchor", "end").attr("dominant-baseline", "central")
        .attr("font-size", "9px").attr("fill", "#bbb")
        .text(v + "%");
    }
  });

  // Legend (top-right of chart area)
  const legendItems = [
    { label: "\u03C0\u2080.\u2085", color: "#888" },
    { label: "CaP-Agent0", color: "#76b900" },
  ];
  const legendG = rightG.append("g")
    .attr("transform", `translate(${chartRight - 120}, ${chartTop - 16})`);
  legendItems.forEach((item, i) => {
    const lx = i * 68;
    legendG.append("rect")
      .attr("x", lx).attr("y", 0).attr("width", 10).attr("height", 10)
      .attr("fill", item.color);
    legendG.append("text")
      .attr("x", lx + 14).attr("y", 9)
      .attr("font-size", "9px").attr("font-weight", "600").attr("fill", "#555")
      .text(item.label);
  });

  // Bars per suite
  const barMethods = [
    { key: "pi05",  color: "#888" },
    { key: "agent", color: "#76b900" },
  ];
  const bw = xSuite.bandwidth() / (barMethods.length + 0.4);

  suiteData.forEach(suite => {
    const sx = xSuite(suite.name);

    barMethods.forEach((m, mi) => {
      const val = suite[m.key];
      const bx = sx + mi * bw + bw * 0.15;
      const w = bw * 0.85;

      rightG.append("rect")
        .attr("x", bx).attr("y", yScale(val))
        .attr("width", w).attr("height", yScale(0) - yScale(val))
        .attr("fill", m.color);

      // Value label on top
      if (val > 0) {
        rightG.append("text")
          .attr("x", bx + w / 2).attr("y", yScale(val) - 4)
          .attr("text-anchor", "middle")
          .attr("font-size", "9px").attr("font-weight", "700")
          .attr("fill", m.key === "agent" ? "#4a7a00" : "#666")
          .text(val + "%");
      }
    });

    // Suite label below baseline
    const shortName = suite.name.replace("libero-", "");
    rightG.append("text")
      .attr("x", sx + xSuite.bandwidth() / 2)
      .attr("y", chartBottom + 14)
      .attr("text-anchor", "middle")
      .attr("font-size", "10px").attr("font-weight", "600").attr("fill", "#555")
      .text(shortName);
  });

  // Footnote below right panel
  rightG.append("text")
    .attr("x", chartLeft + chartInnerW / 2)
    .attr("y", chartBottom + 30)
    .attr("text-anchor", "middle")
    .attr("font-size", "8px").attr("fill", "#bbb").attr("font-style", "italic")
    .text("OpenVLA and \u03C0\u2080 score 0% on all suites (omitted)");
}

/* ==========================================
   Highlight Figure 3 — CaP-RL Post-Training
   Data from Table 4 in the paper
   ========================================== */

function initHighlightFigure3() {
  const container = document.getElementById("highlight-fig-3");
  if (!container) return;
  container.innerHTML = "";

  /* Table 4 data: Impact of RL Post-Training in Sim and Real */
  const simTasks = [
    { name: "Cube Lift",  human: 93, base: 25, rl: 80 },
    { name: "Cube Stack", human: 73, base: 4,  rl: 44 },
    { name: "Spill Wipe", human: 100, base: 30, rl: 93 },
  ];
  const realTasks = [
    { name: "Cube Lift",  human: 92, base: 24, rl: 84 },
    { name: "Cube Stack", human: 84, base: 12, rl: 76 },
  ];

  const methods = [
    { key: "base", label: "Base (7B)",  color: "#d0d0d0" },
    { key: "rl",   label: "w/ CaP-RL",  color: "#76b900" },
    { key: "human", label: "Human",      color: "#8c9bab" },
  ];

  /* ---- SVG setup ---- */
  const totalH = 290;
  const margin = { top: 36, right: 16, bottom: 30, left: 20 };
  const cw = container.clientWidth;
  const width = cw - margin.left - margin.right;
  const height = totalH - margin.top - margin.bottom;

  const svg = d3.select(container)
    .append("svg")
    .attr("width", cw)
    .attr("height", totalH);

  const g = svg.append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  /* ---- Layout: left (sim) | divider | right (real) ---- */
  const dividerGap = 28;
  const leftW = (width - dividerGap) * 0.58;
  const rightX = leftW + dividerGap;
  const rightW = width - rightX;

  /* ---- Shared legend at top ---- */
  const legendG = g.append("g").attr("transform", `translate(${width / 2 - 120}, -20)`);
  methods.forEach((m, i) => {
    const lx = i * 82;
    legendG.append("rect")
      .attr("x", lx).attr("y", 0).attr("width", 10).attr("height", 10)
      .attr("fill", m.color).attr("opacity", m.key === "base" ? 0.6 : 1);
    legendG.append("text")
      .attr("x", lx + 14).attr("y", 9)
      .attr("font-size", "10px").attr("font-weight", "600").attr("fill", "#555")
      .text(m.label);
  });

  /* ---- Helper: draw a grouped bar panel ---- */
  function drawPanel(parentG, tasks, panelW, title, subtitle) {
    const yAxisW = 30;
    const chartLeft = yAxisW;
    const chartRight = panelW - 4;
    const chartInnerW = chartRight - chartLeft;
    const chartTop = 16;
    const chartBottom = height - 16;

    // Title
    parentG.append("text")
      .attr("x", chartLeft + chartInnerW / 2).attr("y", 4)
      .attr("text-anchor", "middle")
      .attr("font-size", "11px").attr("font-weight", "700")
      .attr("fill", "#333").attr("letter-spacing", "0.5px")
      .text(title);

    if (subtitle) {
      parentG.append("text")
        .attr("x", chartLeft + chartInnerW / 2).attr("y", 16)
        .attr("text-anchor", "middle")
        .attr("font-size", "8px").attr("font-weight", "600")
        .attr("fill", "#999")
        .text(subtitle);
    }

    const yScale = d3.scaleLinear().domain([0, 100]).range([chartBottom, chartTop + 10]);
    const xBand = d3.scaleBand()
      .domain(tasks.map(t => t.name))
      .range([chartLeft, chartRight])
      .paddingInner(0.2).paddingOuter(0.08);

    // Y grid
    [25, 50, 75, 100].forEach(v => {
      parentG.append("line")
        .attr("x1", chartLeft).attr("x2", chartRight)
        .attr("y1", yScale(v)).attr("y2", yScale(v))
        .attr("stroke", "#f0f0f0").attr("stroke-width", 0.5);
      parentG.append("text")
        .attr("x", chartLeft - 4).attr("y", yScale(v))
        .attr("text-anchor", "end").attr("dominant-baseline", "central")
        .attr("font-size", "9px").attr("fill", "#bbb")
        .text(v + "%");
    });

    // Baseline at 0
    parentG.append("line")
      .attr("x1", chartLeft).attr("x2", chartRight)
      .attr("y1", yScale(0)).attr("y2", yScale(0))
      .attr("stroke", "#d0d0d0").attr("stroke-width", 0.8);

    // Bars
    const nMethods = methods.length;
    tasks.forEach(task => {
      const tx = xBand(task.name);
      const bw = xBand.bandwidth() / (nMethods + 0.4);

      methods.forEach((m, mi) => {
        const val = task[m.key];
        const bx = tx + mi * bw + bw * 0.15;
        const w = bw * 0.8;

        parentG.append("rect")
          .attr("x", bx).attr("y", yScale(val))
          .attr("width", w).attr("height", yScale(0) - yScale(val))
          .attr("fill", m.color)
          .attr("opacity", m.key === "base" ? 0.6 : 1);

        // Value on top
        parentG.append("text")
          .attr("x", bx + w / 2).attr("y", yScale(val) - 3)
          .attr("text-anchor", "middle")
          .attr("font-size", "9px").attr("font-weight", "700")
          .attr("fill", m.key === "rl" ? "#4a7a00" : m.key === "human" ? "#7a8999" : "#aaa")
          .text(val + "%");
      });

      // Task label
      const shortName = task.name.replace("Cube ", "").replace("Spill ", "");
      parentG.append("text")
        .attr("x", tx + xBand.bandwidth() / 2)
        .attr("y", chartBottom + 12)
        .attr("text-anchor", "middle")
        .attr("font-size", "10px").attr("font-weight", "600").attr("fill", "#555")
        .text(task.name);
    });
  }

  /* ---- Left panel: Simulation ---- */
  const leftG = g.append("g");
  drawPanel(leftG, simTasks, leftW, "SIMULATION", "(N = 100 trials)");

  /* ---- Vertical divider ---- */
  g.append("line")
    .attr("x1", leftW + dividerGap / 2).attr("x2", leftW + dividerGap / 2)
    .attr("y1", 0).attr("y2", height)
    .attr("stroke", "#e0e0e0").attr("stroke-width", 1);

  /* ---- Right panel: Real World ---- */
  const rightG = g.append("g").attr("transform", `translate(${rightX}, 0)`);
  drawPanel(rightG, realTasks, rightW, "REAL WORLD", "(N = 25 trials)");
}

/* ==========================================
   Initialize all charts
   ========================================== */

function initAllCharts() {
  initTimelineChart();
  initHighlightFigure1();
  initHighlightFigure2VLA();
  initHighlightFigure3();
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
