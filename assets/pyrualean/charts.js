// Interactive figures of the PyRUA-Lean post. Each <figure class="pa-chart"> carries its data as
// JSON (<script type="application/json" class="pa-spec">); this file draws it at the column's
// width, redraws on resize, and adds tooltips (hover, tap, keyboard focus), a crosshair, metric
// switches and the episode replay of Figure 1. No dependencies. The exact numbers are in the
// tooltips, which open on hover, on tap and on keyboard focus.
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const CODE = 'var(--pa-code)', TOOL = 'var(--pa-tool)';
  // The site's root, read off this script's own URL, so that a root-relative asset path in a spec
  // ("/assets/...") also works when the site is served under a base path such as /Agentic-Robot.
  const SELF = (document.currentScript && document.currentScript.src) || '';
  const SITE_ROOT = SELF.replace(/\/assets\/pyrualean\/charts\.js(?:[?#].*)?$/, '');
  const siteUrl = path => (path.startsWith('/') && SITE_ROOT !== SELF ? SITE_ROOT + path : path);

  const svgEl = (tag, attrs, parent) => {
    const node = document.createElementNS(NS, tag);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    if (parent) parent.appendChild(node);
    return node;
  };
  const htmlEl = (tag, cls, text, parent) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  };
  const linear = (d0, d1, r0, r1) => v => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
  const logScale = (d0, d1, r0, r1) => {
    const a = Math.log(d0), b = Math.log(d1);
    return v => r0 + ((Math.log(v) - a) / (b - a)) * (r1 - r0);
  };
  const times = (v, digits = 1) => `${v.toFixed(digits)}×`;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const kTokens = v => (v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : `${Math.round(v / 1e3)}k`);
  const fmtTok = v => (v >= 1e6 ? `${+(v / 1e6).toFixed(2)}M` : v >= 1e3 ? `${Math.round(v / 1e3)}k` : `${v}`);
  const fmtUsd = v => `$${v.toFixed(2)}`;
  // A round step that splits [0, max] into about `count` intervals.
  const niceStep = (max, count) => {
    const raw = max / count, p = 10 ** Math.floor(Math.log10(raw));
    return [1, 2, 2.5, 5, 10].map(k => k * p).find(v => v >= raw * 0.999);
  };
  const steps = (max, step) => {
    const out = [];
    for (let t = 0; t <= max * 1.0001; t += step) out.push(+t.toFixed(9));
    return out;
  };
  // Dashed arrow from (x1, y1) to (x2, y2), stopping `gap` px short of both ends.
  const dashedArrow = (parent, x1, y1, x2, y2, gap = 0) => {
    const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
    const sx = x1 + ux * gap, sy = y1 + uy * gap, ex = x2 - ux * gap, ey = y2 - uy * gap;
    const bx = ex - ux * 8, by = ey - uy * 8, px = -uy * 4, py = ux * 4;
    svgEl('line', { x1: sx, y1: sy, x2: bx, y2: by, stroke: '#4d5249', 'stroke-width': 1.6, 'stroke-dasharray': '5 4' }, parent);
    svgEl('path', { d: `M${ex},${ey} L${bx + px},${by + py} L${bx - px},${by - py} Z`, fill: '#4d5249' }, parent);
    return { mx: (sx + bx) / 2, my: (sy + by) / 2 };
  };

  // Text with a halo in the surface colour, so labels stay legible over lines and washes.
  const label = (parent, x, y, text, opts = {}) => {
    const node = svgEl('text', {
      x, y, 'font-size': opts.size || 12, fill: opts.fill || 'var(--ink)',
      'text-anchor': opts.anchor || 'start', 'dominant-baseline': opts.baseline || 'middle',
      'font-weight': opts.weight || 400,
    }, parent);
    if (opts.halo !== false) {
      node.setAttribute('stroke', opts.haloColor || 'var(--pa-surface)');
      node.setAttribute('stroke-width', 4);
      node.setAttribute('stroke-linejoin', 'round');
      node.setAttribute('paint-order', 'stroke');
    }
    if (opts.transform) node.setAttribute('transform', opts.transform);
    node.textContent = text;
    return node;
  };
  // Shift a laid-out text node so it stays within [lo, hi] horizontally.
  const keepInside = (node, lo, hi) => {
    const box = node.getBBox();
    const shift = box.x < lo ? lo - box.x : box.x + box.width > hi ? hi - box.x - box.width : 0;
    if (shift) node.setAttribute('x', Number(node.getAttribute('x')) + shift);
    return node;
  };
  // Direct label beside a mark: side is left, right, above (over the interval) or below.
  const sideLabel = (svg, p, cx, cy, top, width, opts) => {
    const at = {
      left: [cx - 12, cy, 'end'], right: [cx + 12, cy, 'start'],
      above: [cx, top - 12, 'middle'], below: [cx + 8, cy + 18, 'end'],
    }[p.labelSide || 'right'];
    return keepInside(label(svg, at[0], at[1], p.label, { ...opts, anchor: at[2] }), 2, width - 2);
  };

  // Marker shapes: circle (LIBERO-PRO), square (RoboTwin 2.0), triangle (RoboCasa365 atomic), diamond
  // (RoboCasa365 composite); filled unless `filled` is false.
  const marker = (parent, shape, x, y, size, filled) => {
    const attrs = filled
      ? { fill: CODE, stroke: 'var(--pa-surface)', 'stroke-width': 2 }
      : { fill: 'var(--pa-surface)', stroke: CODE, 'stroke-width': 1.7, 'stroke-opacity': 0.8 };
    const r = size / 2;
    if (shape === 'square') {
      return svgEl('rect', { x: x - r * 0.9, y: y - r * 0.9, width: r * 1.8, height: r * 1.8, rx: 1.5, ...attrs }, parent);
    }
    if (shape === 'diamond') {
      const h = r * 1.25;
      return svgEl('path', { d: `M${x},${y - h} L${x + h},${y} L${x},${y + h} L${x - h},${y} Z`, 'stroke-linejoin': 'round', ...attrs }, parent);
    }
    if (shape === 'triangle') {
      const h = r * 1.15;
      return svgEl('path', { d: `M${x},${y - h} L${x + h},${y + h * 0.8} L${x - h},${y + h * 0.8} Z`, 'stroke-linejoin': 'round', ...attrs }, parent);
    }
    return svgEl('circle', { cx: x, cy: y, r, ...attrs }, parent);
  };

  class Tip {
    constructor(host) {
      this.host = host;
      this.el = htmlEl('div', 'pa-tip', null, host);
      this.el.hidden = true;
      this.el.setAttribute('role', 'status');
    }
    show(x, y, build) {
      const el = this.el;
      el.textContent = '';
      build(el);
      el.hidden = false;
      const width = this.host.clientWidth;
      const tw = el.offsetWidth, th = el.offsetHeight;
      let left = x + 16;
      if (left + tw > width) left = x - tw - 16;
      if (left < 0) left = clamp(x - tw / 2, 0, Math.max(0, width - tw));
      let top = y - th - 14;
      if (top < -8) top = y + 18;
      el.style.left = `${left}px`;
      el.style.top = `${top}px`;
    }
    hide() {
      this.el.hidden = true;
    }
  }
  const tipTitle = (el, title, sub) => {
    htmlEl('div', 'pa-tip-title', title, el);
    if (sub) htmlEl('div', 'pa-tip-sub', sub, el);
  };
  const tipValue = (el, value, what) => {
    htmlEl('div', 'pa-tip-value', value, el);
    if (what) htmlEl('div', 'pa-tip-value-label', what, el);
  };
  const tipRows = (el, rows) => {
    for (const [key, value] of rows || []) {
      const row = htmlEl('div', 'pa-tip-row', null, el);
      htmlEl('span', null, key, row);
      htmlEl('span', null, value, row);
    }
  };
  // A focusable, hoverable mark: the group is the hit target (at least 26 px across).
  const interactive = (group, tip, cx, cy, build, aria) => {
    group.setAttribute('class', 'pa-mark');
    group.setAttribute('tabindex', '0');
    group.setAttribute('role', 'button');
    group.setAttribute('aria-label', aria);
    const on = () => {
      group.classList.add('pa-hot');
      tip.show(cx, cy, build);
    };
    const off = () => {
      group.classList.remove('pa-hot');
      tip.hide();
    };
    group.addEventListener('pointerenter', on);
    group.addEventListener('pointerleave', off);
    group.addEventListener('focus', on);
    group.addEventListener('blur', off);
    group.addEventListener('click', event => {
      event.stopPropagation();
      on();
    });
    group.addEventListener('keydown', event => {
      if (event.key === 'Escape') off();
    });
  };

  const newSvg = (plot, width, height, title) => {
    const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': title });
    plot.insertBefore(svg, plot.firstChild);
    return svg;
  };
  const gridY = (svg, ticks, y, x0, x1, fmt, opts = {}) => {
    for (const t of ticks) {
      const yy = y(t);
      svgEl('line', { x1: x0, x2: x1, y1: yy, y2: yy, stroke: opts.strong && opts.strong(t) ? 'var(--pa-axis)' : 'var(--pa-grid)', 'stroke-width': 1 }, svg);
      if (opts.labels !== false) label(svg, x0 - 8, yy, fmt(t), { size: 11, fill: 'var(--muted)', anchor: 'end', halo: false });
    }
  };
  const axisX = (svg, ticks, x, y0, x0, x1, fmt, opts = {}) => {
    svgEl('line', { x1: x0, x2: x1, y1: y0, y2: y0, stroke: 'var(--pa-axis)', 'stroke-width': 1 }, svg);
    for (const t of ticks) {
      const xx = x(t);
      svgEl('line', { x1: xx, x2: xx, y1: y0, y2: y0 + 4, stroke: 'var(--pa-axis)', 'stroke-width': 1 }, svg);
      label(svg, xx, y0 + 16, fmt(t), { size: 11, fill: 'var(--muted)', anchor: 'middle', halo: false });
    }
    if (opts.title) label(svg, (x0 + x1) / 2, y0 + 38, opts.title, { size: 12, fill: 'var(--muted)', anchor: 'middle', halo: false });
  };

  // -- Figure 2: SR per benchmark, both agents, and the difference in points -----------------------
  // Columns from 0 to 100% (bars start at zero), RPent then PyRUA-Lean in each pair, the difference
  // in a pill above the pair. A narrow screen has too little room for the names under columns, so
  // there the same chart lies on its side.
  const bar = (parent, x0, y0, x1, y1, end, fill) => { // a bar with its data end rounded (4 px)
    const r = Math.min(4, Math.abs(x1 - x0) / 2, Math.abs(y1 - y0) / 2);
    const d = end === 'top'
      ? `M${x0},${y1} V${y0 + r} Q${x0},${y0} ${x0 + r},${y0} H${x1 - r} Q${x1},${y0} ${x1},${y0 + r} V${y1} Z`
      : `M${x0},${y0} H${x1 - r} Q${x1},${y0} ${x1},${y0 + r} V${y1 - r} Q${x1},${y1} ${x1 - r},${y1} H${x0} Z`;
    return svgEl('path', { d, fill }, parent);
  };
  const pill = (parent, cx, cy, r, narrow) => {
    const d = r.cells.rate - r.rpent.rate, pw = narrow ? 58 : 66, ph = 20;
    svgEl('rect', { x: cx - pw / 2, y: cy - ph / 2, width: pw, height: ph, rx: ph / 2, fill: 'var(--pa-code-wash-strong)' }, parent);
    label(parent, cx, cy, `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} pts`, { size: 11.5, weight: 600, anchor: 'middle', halo: false, fill: 'var(--pa-code-ink)' });
  };
  const drawSuccess = (plot, spec, state, tip) => {
    const width = plot.clientWidth;
    const narrow = width < 520;
    const build = r => el => {
      const d = r.cells.rate - r.rpent.rate;
      tipTitle(el, r.name, r.sub);
      tipValue(el, `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(1)} points`, 'SR, PyRUA-Lean − RPent');
      tipRows(el, [['SR, PyRUA-Lean · code', `${r.cells.rate.toFixed(1)}%`],
        ['SR, RPent · tool calling', `${r.rpent.rate.toFixed(1)}%`],
        ...(r.at100 ? [['SR with 100 LLM calls', `PyRUA-Lean ${r.at100.cells.toFixed(1)}% · RPent ${r.at100.rpent.toFixed(1)}%`]] : [])]);
    };
    const aria = r => `${r.name}: PyRUA-Lean ${r.cells.rate.toFixed(1)} percent, RPent ${r.rpent.rate.toFixed(1)} percent`;
    if (narrow) {
      const rowH = 70, m = { l: 0, r: 8, t: 8, b: 44 };
      const height = m.t + spec.rows.length * rowH + m.b;
      const svg = newSvg(plot, width, height, spec.title);
      const x0 = m.l, x1 = width - m.r - 44; // room for the value at a bar's end
      const x = linear(0, 100, x0, x1);
      for (const t of [0, 25, 50, 75, 100]) {
        svgEl('line', { x1: x(t), x2: x(t), y1: m.t, y2: height - m.b, stroke: t ? 'var(--pa-grid)' : 'var(--pa-axis)', 'stroke-width': 1 }, svg);
        label(svg, x(t), height - m.b + 15, `${t}%`, { size: 11, fill: 'var(--muted)', anchor: t ? (t === 100 ? 'end' : 'middle') : 'start', halo: false });
      }
      label(svg, (x0 + x1) / 2, height - 8, 'SR (success rate)', { size: 12, fill: 'var(--muted)', anchor: 'middle', halo: false });
      spec.rows.forEach((r, i) => {
        const top = m.t + i * rowH;
        const g = svgEl('g', {}, svg);
        svgEl('rect', { class: 'pa-ring pa-row', x: 0, y: top + 1, width, height: rowH - 2, rx: 3, fill: 'transparent', stroke: 'none' }, g);
        label(g, 0, top + 12, r.name, { size: 12.5, weight: 600, halo: false });
        pill(g, width - 34, top + 12, r, true);
        [['rpent', TOOL, top + 24], ['cells', CODE, top + 40]].forEach(([arm, colour, by]) => {
          bar(g, x0, by, x(r[arm].rate), by + 13, 'right', colour);
          label(g, x(r[arm].rate) + 6, by + 7, `${r[arm].rate.toFixed(1)}%`, { size: 11, weight: arm === 'cells' ? 700 : 400, fill: arm === 'cells' ? 'var(--ink)' : 'var(--muted)', halo: false });
        });
        interactive(g, tip, x(r.cells.rate), top + 40, build(r), aria(r));
      });
      return;
    }
    const m = { l: 58, r: 8, t: 52, b: 56 };
    const height = 380;
    const svg = newSvg(plot, width, height, spec.title);
    const x0 = m.l, x1 = width - m.r, y0 = m.t, y1 = height - m.b;
    const y = linear(0, 100, y1, y0);
    for (const t of [0, 20, 40, 60, 80, 100]) {
      svgEl('line', { x1: x0, x2: x1, y1: y(t), y2: y(t), stroke: t ? 'var(--pa-grid)' : 'var(--pa-axis)', 'stroke-width': 1 }, svg);
      label(svg, x0 - 8, y(t), `${t}%`, { size: 11, fill: 'var(--muted)', anchor: 'end', halo: false });
    }
    label(svg, 14, (y0 + y1) / 2, 'SR (success rate)', { size: 12, fill: 'var(--muted)', anchor: 'middle', halo: false, transform: `rotate(-90 14 ${(y0 + y1) / 2})` });
    const gw = (x1 - x0) / spec.rows.length, bw = clamp(gw * 0.24, 16, 46), gap = 2;
    spec.rows.forEach((r, i) => {
      const cx = x0 + gw * (i + 0.5);
      const g = svgEl('g', {}, svg);
      svgEl('rect', { class: 'pa-ring pa-row', x: x0 + gw * i + 6, y: 4, width: gw - 12, height: height - 8, rx: 4, fill: 'transparent', stroke: 'none' }, g);
      [['rpent', TOOL, cx - gap / 2 - bw], ['cells', CODE, cx + gap / 2]].forEach(([arm, colour, bx]) => {
        const v = r[arm].rate;
        bar(g, bx, y(v), bx + bw, y1, 'top', colour);
        label(g, bx + bw / 2, y(v) - 9, `${v.toFixed(1)}%`, { size: 11.5, anchor: 'middle', weight: arm === 'cells' ? 700 : 400, fill: arm === 'cells' ? 'var(--ink)' : 'var(--muted)', halo: false });
      });
      pill(g, cx, y(Math.max(r.cells.rate, r.rpent.rate)) - 34, r, false);
      label(g, cx, y1 + 19, r.name, { size: 12.5, weight: 600, anchor: 'middle', halo: false });
      label(g, cx, y1 + 36, r.sub, { size: 11, fill: 'var(--muted)', anchor: 'middle', halo: false });
      interactive(g, tip, cx, y(Math.max(r.cells.rate, r.rpent.rate)), build(r), aria(r));
    });
  };

  // -- Figure 3: a solved episode, both arms, all benchmarks in one chart --------------------------
  // Log scales on both axes (so the six points spread out and an arrow's length is its factor):
  // RPent and PyRUA-Lean at their mean model requests and prompt tokens (or dollars at list price)
  // on the cells both arms solved, and a dashed arrow from tool calling to PyRUA-Lean.
  const logTicks = (lo, hi, candidates) => candidates.filter(t => t >= lo * 0.999 && t <= hi * 1.001);
  const drawEpisode = (plot, spec, state, tip) => {
    const width = plot.clientWidth;
    const narrow = width < 560;
    const metric = spec.metrics.find(k => k.key === state.mode);
    const height = narrow ? clamp(Math.round(width * 1.15), 340, 460) : clamp(Math.round(width * 0.62), 380, 500);
    const m = { l: 54, r: 16, t: 30, b: 50 };
    const svg = newSvg(plot, width, height, spec.title);
    const ps = spec.panels;
    const reqs = ps.flatMap(p => [p.req.rpent, p.req.cells]);
    const vals = ps.flatMap(p => [p.y[metric.key].rpent, p.y[metric.key].cells]);
    const xlo = Math.min(...reqs) / 1.35, xhi = Math.max(...reqs) * 1.3;
    const ylo = Math.min(...vals) / 1.5, yhi = Math.max(...vals) * 1.9;
    const x = logScale(xlo, xhi, m.l, width - m.r), y = logScale(ylo, yhi, height - m.b, m.t);
    const yCand = metric.fmt === 'usd' ? [0.1, 0.2, 0.3, 0.5, 1, 2, 3, 5, 10] : [3e4, 5e4, 1e5, 2e5, 3e5, 5e5, 1e6, 2e6, 3e6, 5e6];
    const fmtY = metric.fmt === 'usd' ? v => `$${v < 1 ? v.toFixed(1) : v}` : fmtTok;
    gridY(svg, logTicks(ylo, yhi, yCand), y, m.l, width - m.r, fmtY);
    axisX(svg, logTicks(xlo, xhi, [2, 3, 4, 5, 7, 10, 15, 20, 30, 50]), x, height - m.b, m.l, width - m.r, t => `${t}`,
      { title: narrow ? `${spec.xShort} (log)` : `${spec.xLabel} (log scale)` });
    label(svg, m.l - 44, 11, narrow ? `${metric.short} (log)` : `${metric.axis} (log scale)`, { size: 12, fill: 'var(--muted)', halo: false });
    const fmtV = metric.fmt === 'usd' ? fmtUsd : fmtTok;
    // arrows first, then points, then labels on top
    const geo = ps.map(p => ({ p, rx: x(p.req.rpent), ry: y(p.y[metric.key].rpent), cx: x(p.req.cells), cy: y(p.y[metric.key].cells) }));
    for (const g of geo) dashedArrow(svg, g.rx, g.ry, g.cx, g.cy, 10);
    const labels = [];
    for (const { p, rx, ry, cx, cy } of geo) {
      const f = p.factor[metric.key];
      for (const [arm, px, py, colour, name] of [['rpent', rx, ry, TOOL, 'RPent · tool calling'], ['cells', cx, cy, CODE, 'PyRUA-Lean · code']]) {
        const g = svgEl('g', {}, svg);
        svgEl('circle', { class: 'pa-ring', cx: px, cy: py, r: 13, fill: 'transparent', stroke: 'none' }, g);
        const mk = marker(g, p.shape, px, py, 13, true);
        mk.setAttribute('fill', colour);
        const v = p.y[metric.key][arm];
        interactive(g, tip, px, py, el => {
          tipTitle(el, name, `${p.title} · mean of a solved episode`);
          tipValue(el, metric.fmt === 'usd' ? fmtUsd(v) : fmtTok(v), metric.fmt === 'usd' ? 'dollars at GPT-6 Astra list price' : 'token consumption (prompt tokens)');
          tipRows(el, [['LLM calls', p.req[arm].toFixed(1)], ['Token consumption', fmtTok(p.y.tokens[arm])],
            ['Dollars, list price', fmtUsd(p.y.usd[arm])], ['RPent ÷ PyRUA-Lean', `${f.toFixed(2)}×`]]);
        }, `${p.title}, ${name}: ${p.req[arm].toFixed(1)} LLM calls, ${fmtV(v)}`);
      }
      // The benchmark's label sits at the tail of its arrow, one line each: the benchmark, the two
      // values and the factor (on a narrow screen the benchmark, broken before its last word when
      // long, and the factor).
      const cut = p.title.lastIndexOf(' ');
      const titleLines = narrow
        ? (p.title.length > 12 && cut > 0 ? [p.title.slice(0, cut), p.title.slice(cut + 1)] : [p.title])
        : p.titleLines || [p.title];
      const lines = [
        ...titleLines.map(t => [t, { size: narrow ? 11.5 : 13, weight: 600 }]),
        ...(narrow ? [] : [[`${fmtV(p.y[metric.key].rpent)} → ${fmtV(p.y[metric.key].cells)}`, { size: 12, fill: 'var(--muted)' }]]),
        [`${f.toFixed(1)}× ${narrow ? metric.whatShort : metric.what}`, { size: narrow ? 11 : 12, weight: 700, fill: 'var(--pa-code-ink)' }],
      ];
      labels.push({ p, rx, ry, lines });
    }
    // Place each label block at the first spot around its arrow's tail that stays inside the plot and
    // clear of every arrow, marker and label already placed; the benchmark's preferred side goes first.
    const dots = geo.flatMap(g => [[g.rx, g.ry], [g.cx, g.cy]]);
    const segs = geo.map(g => [g.rx, g.ry, g.cx, g.cy]);
    const placed = [];
    const segHits = ([x1, y1, x2, y2], r) => { // Liang-Barsky: does the segment enter the rectangle?
      let t0 = 0, t1 = 1;
      const dx = x2 - x1, dy = y2 - y1;
      for (const [pp, q] of [[-dx, x1 - r.x0], [dx, r.x1 - x1], [-dy, y1 - r.y0], [dy, r.y1 - y1]]) {
        if (pp === 0) { if (q < 0) return false; continue; }
        const t = q / pp;
        if (pp < 0) { if (t > t1) return false; t0 = Math.max(t0, t); } else { if (t < t0) return false; t1 = Math.min(t1, t); }
      }
      return t0 <= t1;
    };
    const blocked = r => r.x0 < m.l + 2 || r.x1 > width - 2 || r.y0 < m.t - 6 || r.y1 > height - m.b - 2
      || dots.some(([dx, dy]) => dx > r.x0 - 9 && dx < r.x1 + 9 && dy > r.y0 - 9 && dy < r.y1 + 9)
      || segs.some(s => segHits(s, r))
      || placed.some(q => r.x0 < q.x1 && r.x1 > q.x0 && r.y0 < q.y1 && r.y1 > q.y0);
    const spots = (px, py, h, d) => ({ // [anchor, x, centre of the first line] for a block h tall (first to last line)
      right: ['start', px + 13 + d, py - h / 2], left: ['end', px - 13 - d, py - h / 2],
      above: ['end', px + 8, py - 20 - d - h], aboveRight: ['start', px - 8, py - 20 - d - h],
      aboveLeft: ['end', px - 12 - d, py - 12 - d - h], rightUp: ['start', px + 13 + d, py - 8 - h],
      below: ['start', px + 10 + d, py + 20 + d], under: ['start', px - 6, py + 22 + d],
      underEnd: ['end', px + 8, py + 22 + d],
      rightDown: ['start', px + 13 + d, py + 8], belowLeft: ['end', px - 10 - d, py + 20 + d],
    });
    const ORDER = ['right', 'above', 'below', 'rightUp', 'rightDown', 'under', 'underEnd', 'aboveRight', 'aboveLeft', 'left', 'belowLeft'];
    const lh = narrow ? 14 : 16;
    const box = nodes => {
      const bs = nodes.map(nd => nd.getBBox());
      return { x0: Math.min(...bs.map(b => b.x)) - 2, x1: Math.max(...bs.map(b => b.x + b.width)) + 2,
        y0: Math.min(...bs.map(b => b.y)) - 1, y1: Math.max(...bs.map(b => b.y + b.height)) + 1 };
    };
    // One greedy pass in the given order; returns the text nodes and how many labels found no clear spot.
    const pass = order => {
      placed.length = 0;
      const all = [];
      let misses = 0;
      const missed = [];
      for (const item of order) {
        const { p, rx, ry, lines } = item;
        const h = (lines.length - 1) * lh;
        const prefer = (narrow && p.labelSideNarrow) || p.labelSide;
        const tries = [0, 18, 36, 60, 90].flatMap(d => [prefer, ...ORDER.filter(k => k !== prefer)].map(k => [k, d]));
        const draw = ([anchor, lx, top]) => lines.map(([text, o], i) => label(svg, lx, top + i * lh, text, { ...o, anchor }));
        let nodes = null;
        for (const [k, d] of tries) {
          const trial = draw(spots(rx, ry, h, d)[k] || spots(rx, ry, h, d).right);
          if (!blocked(box(trial))) { nodes = trial; break; }
          trial.forEach(nd => nd.remove());
        }
        if (!nodes) { // nothing is clear: the preferred side, kept inside the plot
          misses += 1;
          missed.push(item);
          nodes = draw(spots(rx, ry, h, 0)[prefer] || spots(rx, ry, h, 0).right);
          const b = box(nodes);
          const shift = b.x0 < m.l + 2 ? m.l + 2 - b.x0 : b.x1 > width - 2 ? width - 2 - b.x1 : 0;
          if (shift) nodes.forEach(nd => nd.setAttribute('x', Number(nd.getAttribute('x')) + shift));
        }
        placed.push(box(nodes));
        all.push(...nodes);
      }
      return { all, misses, missed };
    };
    // The benchmarks' own order first. If a label found no clear spot, place the missed labels first,
    // then try the other orders; the first order that places every label cleanly (or the best) is kept.
    const first = pass(labels);
    if (first.misses) {
      first.all.forEach(nd => nd.remove());
      const permute = (rest, head = []) => (rest.length
        ? rest.flatMap((q, i) => permute([...rest.slice(0, i), ...rest.slice(i + 1)], [...head, q])) : [head]);
      const candidates = [[...first.missed, ...labels.filter(q => !first.missed.includes(q))], ...permute(labels)];
      let bestOrder = labels, bestMisses = first.misses;
      for (const order of candidates) {
        const trial = pass(order);
        trial.all.forEach(nd => nd.remove());
        if (trial.misses < bestMisses) { bestOrder = order; bestMisses = trial.misses; }
        if (!trial.misses) break;
      }
      pass(bestOrder);
    }
  };

  // -- Figure: success under a budget (small multiples, crosshair) --------------------------------
  const drawCurves = (plot, spec, state, tip) => {
    const width = plot.clientWidth;
    const mode = spec.modes.find(k => k.key === state.mode);
    const cols = width >= 640 ? (spec.panels.length > 3 ? 2 : spec.panels.length) : 1;
    const gap = 44, m = { l: 58, r: 40, t: 30, b: 50 };
    const pw = (width - m.l - (cols - 1) * gap - m.r) / cols;
    const ph = cols === 1 ? 170 : 200;
    const rows = Math.ceil(spec.panels.length / cols);
    const rowGap = rows > 1 ? 64 : 0;
    const height = m.t + rows * ph + (rows - 1) * rowGap + m.b;
    const svg = newSvg(plot, width, height, spec.title);
    const xs = mode.x;
    const xmax = mode.max;
    const logX = mode.scale === 'log';
    const fmtX = mode.fmt === 'tok' ? fmtTok : mode.fmt === 'M' ? t => (t ? `${t}M` : '0') : t => `${t}`;
    const panels = [];
    spec.panels.forEach((panel, i) => {
      const col = i % cols, row = Math.floor(i / cols);
      const x0 = m.l + col * (pw + gap), x1 = x0 + pw;
      const y0 = m.t + row * (ph + rowGap), y1 = y0 + ph;
      // counted in LLM calls, a panel's axis ends at its benchmark's own call budget: no episode counts past it
      const pmax = mode.budget && panel.budget ? Math.min(panel.budget, xmax) : xmax;
      const x = logX ? logScale(mode.min, pmax, x0, x1) : linear(0, pmax, x0, x1);
      const y = linear(0, 100, y1, y0);
      label(svg, x0, y0 - 16, panel.title, { size: 13, weight: 600, halo: false });
      gridY(svg, [0, 25, 50, 75, 100], y, x0, x1, t => `${t}%`, { labels: col === 0, strong: t => t === 0 });
      if (col === 0) label(svg, 12, (y0 + y1) / 2, 'SR (success rate)', { size: 12, fill: 'var(--muted)', anchor: 'middle', halo: false, transform: `rotate(-90 12 ${(y0 + y1) / 2})` });
      const ticks = mode.ticks.filter(t => t <= pmax);
      if (ticks[ticks.length - 1] !== pmax && pmax !== xmax) ticks.push(pmax);
      axisX(svg, ticks, x, y1, x0, x1, fmtX);
      if (i === spec.panels.length - 1) {
        // one axis title for all panels, centred under the last row
        label(svg, width / 2, y1 + 38, cols === 1 ? mode.short : mode.xLabel, { size: 12, fill: 'var(--muted)', anchor: 'middle', halo: false });
      }
      // the benchmark's own LLM-call budget (40, or 100 on the composite tasks), where the axis reaches it
      const budget = mode.budget && panel.budget;
      if (budget && budget <= pmax) {
        const bx = x(budget);
        svgEl('line', { x1: bx, x2: bx, y1: y0, y2: y1, stroke: 'var(--pa-faint)', 'stroke-width': 1, 'stroke-dasharray': '2 3' }, svg);
        label(svg, bx - 4, y1 - 9, 'budget', { size: 10, fill: 'var(--muted)', anchor: 'end', halo: false });
      }
      const pct = arm => panel.y[mode.key][arm].map(v => (100 * v) / panel.n);
      const code = pct('cells'), tool = pct('rpent');
      const last = xs.reduce((k, v, j) => (v <= pmax ? j : k), 0);  // the panel's last grid point
      // Drawn: a monotone fit through every exact point (budget, cells solved within it), over the
      // exact step curve in a faint line; the crosshair reads the exact counts.
      const fx = (panel.fine && panel.fine[mode.key]) || mode.fine || xs;
      const sm = panel.smooth ? panel.smooth[mode.key] : { cells: code, rpent: tool };
      let d = '';
      fx.forEach((v, j) => { d += `${j ? 'L' : 'M'}${x(v)},${y(sm.cells[j])}`; });
      for (let j = fx.length - 1; j >= 0; j--) d += `L${x(fx[j])},${y(sm.rpent[j])}`;
      svgEl('path', { d: `${d}Z`, fill: CODE, 'fill-opacity': 0.12, stroke: 'none' }, svg);
      for (const [arm, values] of [['rpent', tool], ['cells', code]]) {
        const s = spec.series.find(k => k.key === arm);
        let step = `M${x(xs[0])},${y(values[0])}`;
        for (let j = 1; j <= last; j++) step += `H${x(xs[j])}V${y(values[j])}`;
        svgEl('path', { d: step, fill: 'none', stroke: s.color, 'stroke-width': 1, 'stroke-opacity': 0.35 }, svg);
      }
      if (panel.final) {
        for (const arm of ['rpent', 'cells']) {
          const s = spec.series.find(k => k.key === arm), yy = y(panel.final[arm]);
          svgEl('line', { x1: x0, x2: x1, y1: yy, y2: yy, stroke: s.color, 'stroke-width': 1, 'stroke-dasharray': '1.5 3', 'stroke-opacity': 0.9 }, svg);
        }
        const [hi, lo] = panel.final.cells >= panel.final.rpent ? ['cells', 'rpent'] : ['rpent', 'cells'];
        const close = Math.abs(y(panel.final.cells) - y(panel.final.rpent)) < 13;
        for (const arm of [hi, lo]) {
          const yy = y(panel.final[arm]) + (close ? (arm === hi ? -6 : 6) : 0);
          label(svg, x1 + 4, yy, `${panel.final[arm].toFixed(1)}%`, {
            size: 10.5, weight: 600, anchor: 'start', halo: false, fill: arm === 'cells' ? 'var(--pa-code-ink)' : 'var(--pa-tool-ink)' });
        }
      }
      for (const [arm, values] of [['rpent', sm.rpent], ['cells', sm.cells]]) {
        const s = spec.series.find(k => k.key === arm);
        const path = fx.map((v, j) => `${j ? 'L' : 'M'}${x(v)},${y(values[j])}`).join('');
        svgEl('path', { d: path, fill: 'none', stroke: s.color, 'stroke-width': 2.4, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
      }
      panels.push({ panel, x, y, x0, x1, y0, y1, code, tool, last });
    });
    const hair = panels.map(({ y0, y1 }) => {
      const g = svgEl('g', { visibility: 'hidden', 'pointer-events': 'none' }, svg);
      const line = svgEl('line', { y1: y0, y2: y1, stroke: 'var(--ink)', 'stroke-width': 1, 'stroke-opacity': 0.55 }, g);
      const dots = ['rpent', 'cells'].map(arm => svgEl('circle', { r: 4.5, fill: spec.series.find(k => k.key === arm).color, stroke: 'var(--pa-surface)', 'stroke-width': 2 }, g));
      return { g, line, dots };
    });
    let active = null;
    const at = (index, pi) => {
      active = index;
      panels.forEach((p, k) => {
        const h = hair[k], xx = p.x(xs[index]);
        if (index > p.last) { h.g.setAttribute('visibility', 'hidden'); return; }  // past this panel's budget
        h.g.setAttribute('visibility', 'visible');
        h.line.setAttribute('x1', xx);
        h.line.setAttribute('x2', xx);
        h.dots[0].setAttribute('cx', xx); h.dots[0].setAttribute('cy', p.y(p.tool[index]));
        h.dots[1].setAttribute('cx', xx); h.dots[1].setAttribute('cy', p.y(p.code[index]));
      });
      const p = panels[pi];
      const where = mode.fmt === 'tok' ? `${fmtTok(xs[index])} tokens` : `${xs[index]} LLM calls`;
      tip.show(p.x(xs[index]), p.y(Math.max(p.code[index], p.tool[index])), el => {
        tipTitle(el, p.panel.title, `Within ${where} per episode`);
        for (const arm of ['cells', 'rpent']) {
          const s = spec.series.find(k => k.key === arm);
          const count = p.panel.y[mode.key][arm][index];
          const row = htmlEl('div', 'pa-tip-series', null, el);
          const key = htmlEl('i', null, null, row);
          key.style.background = s.color;
          htmlEl('b', null, `${Math.round((100 * count) / p.panel.n)}%`, row);
          htmlEl('span', null, s.label, row);
        }
      });
    };
    const clear = () => {
      active = null;
      hair.forEach(h => h.g.setAttribute('visibility', 'hidden'));
      tip.hide();
    };
    panels.forEach((p, pi) => {
      const overlay = svgEl('rect', { class: 'pa-overlay', x: p.x0, y: p.y0, width: p.x1 - p.x0, height: p.y1 - p.y0, fill: 'transparent', tabindex: 0, role: 'slider', 'aria-label': `${p.panel.title}: move along the budget with the arrow keys` }, svg);
      const pick = event => {
        const box = svg.getBoundingClientRect();
        const px = ((event.clientX - box.left) / box.width) * width;
        let best = 0, bestD = Infinity;
        xs.forEach((xv, j) => {
          const d = Math.abs(p.x(xv) - px);
          if (j <= p.last && d < bestD) { bestD = d; best = j; }
        });
        at(best, pi);
      };
      overlay.addEventListener('pointermove', pick);
      overlay.addEventListener('pointerdown', pick);
      overlay.addEventListener('pointerleave', clear);
      overlay.addEventListener('focus', () => at(Math.min(active ?? Math.floor(p.last / 4), p.last), pi));
      overlay.addEventListener('blur', clear);
      overlay.addEventListener('keydown', event => {
        const step = event.shiftKey ? 5 : 1;
        if (event.key === 'ArrowRight') at(Math.min(p.last, (active ?? 0) + step), pi);
        else if (event.key === 'ArrowLeft') at(Math.max(0, (active ?? 0) - step), pi);
        else if (event.key === 'Escape') clear();
        else return;
        event.preventDefault();
      });
    });
    // The budget each arm needs to solve as many cells as tool calling finally does: a dashed arrow
    // from where RPent's curve levels off to where PyRUA-Lean's reaches the same height.
    panels.forEach(p => {
      const r = p.panel.reach && p.panel.reach[mode.key];
      if (!r) return;
      const yy = p.y(r.level), xa = p.x(r.cells), xb = p.x(r.rpent);
      const g = svgEl('g', {}, svg);
      svgEl('rect', { x: xa - 6, y: yy - 24, width: xb - xa + 12, height: 32, fill: 'transparent' }, g);
      dashedArrow(g, xb, yy, xa, yy, 1);
      svgEl('circle', { cx: xb, cy: yy, r: 3.5, fill: TOOL, stroke: 'var(--pa-surface)', 'stroke-width': 1.5 }, g);
      keepInside(label(g, xa - 6, yy - 11, `${r.ratio.toFixed(1)}× ${mode.what}`, { size: 11.5, weight: 700, anchor: 'end', fill: 'var(--pa-code-ink)' }), p.x0 + 2, p.x1 - 2);
      const f = mode.fmt === 'tok' ? v => `${fmtTok(v)} tokens` : v => `${v} LLM calls`;
      interactive(g, tip, (xa + xb) / 2, yy, el => {
        tipTitle(el, p.panel.title, `To solve ${r.level.toFixed(1)}% of the cells, all that tool calling solves`);
        tipValue(el, `${r.ratio.toFixed(1)}× ${mode.what}`, 'for PyRUA-Lean');
        tipRows(el, [['RPent · tool calling', f(r.rpent)], ['PyRUA-Lean · code', f(r.cells)]]);
      }, `${p.panel.title}: PyRUA-Lean reaches tool calling's final success with ${r.ratio.toFixed(1)} times ${mode.what}`);
    });
  };

  // -- Figure 5: fewer LLM calls x smaller calls (log-log, lines of equal token factor) ------------
  // Both axes share one log scale, so x * y = constant is a straight line at 45 degrees through the
  // grid corners (1, N), (2, N/2), ...; each label runs along its line, on the upper-left stretch.
  const drawDecomp = (plot, spec, state, tip) => {
    const width = plot.clientWidth;
    const narrow = width < 520;
    const side = clamp(width - (narrow ? 58 : 110), 220, 400);
    const m = { l: narrow ? 44 : Math.max(56, (width - side) / 2), t: 38, b: 58 };
    const height = m.t + side + m.b;
    const svg = newSvg(plot, width, height, spec.title);
    const [lo, hi] = spec.domain;
    const x = logScale(lo, hi, m.l, m.l + side);
    const y = logScale(lo, hi, m.t + side, m.t);
    // washes: above the 1x line code consumes fewer tokens overall, below it tool calling
    const pts = (list) => list.map(([a, b]) => `${x(a)},${y(b)}`).join(' ');
    svgEl('polygon', { points: pts([[lo, 1 / lo], [lo, hi], [hi, hi], [hi, lo], [1 / lo, lo]]), fill: 'var(--pa-code-wash)' }, svg);
    svgEl('polygon', { points: pts([[lo, lo], [lo, 1 / lo], [1 / lo, lo]]), fill: 'var(--pa-tool-wash)' }, svg);
    for (const t of spec.ticks) {
      svgEl('line', { x1: x(t), x2: x(t), y1: m.t, y2: m.t + side, stroke: 'var(--pa-grid)', 'stroke-width': 1 }, svg);
      svgEl('line', { x1: m.l, x2: m.l + side, y1: y(t), y2: y(t), stroke: 'var(--pa-grid)', 'stroke-width': 1 }, svg);
      const ly = label(svg, m.l - 8, y(t), `${t}×`, { size: 11, fill: 'var(--muted)', anchor: 'end', halo: false });
      const lx = label(svg, x(t), m.t + side + 16, `${t}×`, { size: 11, fill: 'var(--muted)', anchor: 'middle', halo: false });
      Object.assign(ly.dataset, { tick: t, axis: 'y', px: y(t) });
      Object.assign(lx.dataset, { tick: t, axis: 'x', px: x(t) });
    }
    for (const total of spec.totals) {
      const a = Math.max(lo, total / hi), b = Math.min(hi, total / lo);
      if (a >= b) continue;
      const line = svgEl('line', { x1: x(a), y1: y(total / a), x2: x(b), y2: y(total / b), stroke: total === 1 ? 'var(--pa-faint)' : 'var(--pa-axis)', 'stroke-width': total === 1 ? 1.3 : 1 }, svg);
      line.dataset.total = total;
      const t = Math.exp(Math.log(a) + 0.1 * (Math.log(b) - Math.log(a)));
      const lx = x(t), ly = y(total / t);
      label(svg, lx, ly, `${total}× total`, { size: 10, fill: 'var(--muted)', anchor: 'start', baseline: 'auto', transform: `rotate(45 ${lx} ${ly}) translate(0 -4)` });
    }
    keepInside(label(svg, m.l, m.t + side + 38, narrow ? spec.xShort : spec.xLabel, { size: 12, fill: 'var(--muted)', halo: false }), 2, width - 2);
    keepInside(label(svg, m.l - 40, 14, narrow ? spec.yShort : spec.yLabel, { size: 12, fill: 'var(--muted)', halo: false }), 2, width - 2);
    for (const p of spec.points) {
      const cx = x(p.x), cy = y(p.y);
      const g = svgEl('g', {}, svg);
      Object.assign(g.dataset, { point: p.id, cx, cy });
      svgEl('circle', { class: 'pa-ring', cx, cy, r: 13, fill: 'transparent', stroke: 'none' }, g);
      marker(g, p.shape, cx, cy, 13, true);
      sideLabel(svg, p, cx, cy, cy - 4, width, { size: 13, weight: 600 });
      const build = el => {
        tipTitle(el, p.title, 'task instances both agents solved');
        tipValue(el, `${times(p.x, 2)} × ${times(p.y, 2)} = ${times(p.total, 2)}`, 'fewer LLM calls × smaller calls = token factor');
        tipRows(el, p.rows);
      };
      interactive(g, tip, cx, cy, build, `${p.title}: ${times(p.x, 2)} fewer LLM calls times ${times(p.y, 2)} smaller calls, ${times(p.total, 2)} fewer tokens`);
    }
  };

  // -- Figure 6: the ablation, one dot per setting (the ratio, log scale) ----------------------------
  const drawForest = (plot, spec, state, tip) => {
    const width = plot.clientWidth;
    const metric = spec.metrics.find(k => k.key === state.mode);
    const narrow = width < 480;
    const labelW = narrow ? 0 : clamp(Math.round(width * 0.36), 118, 220);
    const valueW = 52;
    const rowH = narrow ? 44 : 30, headH = 30;
    const m = { t: 26, b: 44 };
    const lines = [];
    for (const group of spec.groups) {
      lines.push({ head: group.title });
      for (const row of group.rows) lines.push({ row, group });
    }
    const height = m.t + lines.reduce((h, l) => h + (l.head ? headH : rowH), 0) + m.b;
    const svg = newSvg(plot, width, height, spec.title);
    const x0 = narrow ? 14 : labelW + 10, x1 = width - valueW - 8;
    const x = logScale(spec.domain[0], spec.domain[1], x0, x1);
    const plotBottom = height - m.b;
    svgEl('rect', { x: x(1), y: m.t - 6, width: x1 - x(1), height: plotBottom - m.t + 6, fill: 'var(--pa-code-wash)' }, svg);
    svgEl('rect', { x: x0, y: m.t - 6, width: x(1) - x0, height: plotBottom - m.t + 6, fill: 'var(--pa-tool-wash)' }, svg);
    for (const t of spec.ticks) {
      svgEl('line', { x1: x(t), x2: x(t), y1: m.t - 6, y2: plotBottom, stroke: t === 1 ? 'var(--pa-faint)' : 'var(--pa-grid)', 'stroke-width': 1 }, svg);
      label(svg, x(t), plotBottom + 16, `${t}×`, { size: 11, fill: 'var(--muted)', anchor: 'middle', halo: false });
    }
    label(svg, x(1) + 6, m.t - 14, 'PyRUA-Lean cheaper →', { size: 10, fill: 'var(--pa-code-ink)', weight: 600, halo: false });
    keepInside(label(svg, x0, plotBottom + 36, narrow ? metric.short : metric.axis, { size: 12, fill: 'var(--muted)', halo: false }), 2, width - 2);
    let top = m.t;
    for (const line of lines) {
      if (line.head) {
        label(svg, 0, top + headH / 2 + 3, line.head, { size: 13, weight: 600, halo: false });
        top += headH;
        continue;
      }
      const r = line.row;
      const v = r.values[state.mode];
      const cy = narrow ? top + 30 : top + rowH / 2;
      const g = svgEl('g', {}, svg);
      svgEl('rect', { class: 'pa-ring pa-row', x: 0, y: top + 2, width, height: rowH - 4, rx: 2, fill: 'transparent', stroke: 'none' }, g);
      label(g, 12, narrow ? top + 12 : cy, r.setting, { size: 12, fill: r.baseline ? 'var(--ink)' : 'var(--muted)', weight: r.baseline ? 600 : 400, halo: false });
      svgEl('line', { x1: x(1), x2: x(v), y1: cy, y2: cy, stroke: v > 1 ? CODE : TOOL, 'stroke-width': 1.6, 'stroke-opacity': 0.45 }, g);
      svgEl('circle', { cx: x(v), cy, r: 5.5, fill: v > 1 ? CODE : TOOL, stroke: 'var(--pa-surface)', 'stroke-width': 2 }, g);
      label(g, width - 4, cy, times(v, 2), { size: 12, anchor: 'end', halo: false, weight: 600 });
      const build = el => {
        tipTitle(el, line.group.title, r.setting + (r.baseline ? ' (main comparison)' : ''));
        tipValue(el, times(v, 2), metric.what);
        tipRows(el, r.rows);
      };
      interactive(g, tip, x(v), cy, build, `${line.group.title}, ${r.setting}: ${times(v, 2)} ${metric.what}`);
      top += rowH;
    }
  };

  // -- Figure 1: one real episode, replayed request by request on both arms --------------------------
  const drawReplay = (plot, spec, state) => {
    if (plot.querySelector('.pa-replay')) return; // the replay is responsive by CSS; build it once
    const root = htmlEl('div', 'pa-replay', null, plot);
    const base = siteUrl(spec.assets);
    // Which cameras to show: the spec names them (RoboTwin and RoboCasa differ from LIBERO). Without
    // them (Figure 1's LIBERO episode) the agent view is large, the wrist camera small, and a tool
    // result's three images are the policy view (the agent view at 256 px), the agent view and the wrist.
    const cams = spec.cameras || {};
    const MAIN = cams.main || 'agentview', INSET = cams.inset === undefined ? 'wrist' : cams.inset;
    const LIBERO_TITLES = { policy: 'policy view, 256 px', agentview: 'agent view, 1024 px', wrist: 'wrist camera, 1024 px' };
    const camName = cam => (cams.labels && cams.labels[cam]) || { agentview: 'agent view', wrist: 'wrist camera' }[cam] || cam.replace(/_/g, ' ');
    const camTitle = cam => (spec.cameras ? camName(cam) : LIBERO_TITLES[cam] || camName(cam));
    // LIBERO's policy view is the agent view mirrored at 256 px; its frame stands in for it
    const SAME_FRAME = { policy: 'agentview', agentview_policy: 'agentview' };
    const frame = (view, cam) => (view && view[SAME_FRAME[cam] || cam]) || null;
    const arms = [
      { key: 'rpent', name: 'RPent', kind: 'tool calling', cls: 'pa-lane-tool', data: spec.rpent },
      { key: 'cells', name: 'PyRUA-Lean', kind: 'python(code) over robo.*', cls: 'pa-lane-code', data: spec.cells },
    ];
    const maxCum = Math.max(...arms.map(a => a.data.requests[a.data.requests.length - 1].cum));
    const N = Math.max(...arms.map(a => a.data.requests.length));
    const lanes = htmlEl('div', 'pa-rp-lanes', null, root);
    for (const arm of arms) {
      const lane = htmlEl('section', `pa-lane ${arm.cls}`, null, lanes);
      const head = htmlEl('header', 'pa-lane-head', null, lane);
      htmlEl('span', 'pa-lane-dot', null, head);
      htmlEl('b', null, arm.name, head);
      htmlEl('span', 'pa-lane-kind', arm.kind, head);
      const view = htmlEl('div', 'pa-view', null, lane);
      arm.main = htmlEl('img', 'pa-view-main', null, view);
      arm.main.alt = `${arm.name}: the ${camName(MAIN)}`;
      arm.main.loading = 'lazy';
      arm.wrist = htmlEl('img', 'pa-view-wrist', null, view);
      arm.wrist.alt = INSET ? `${arm.name}: the ${camName(INSET)}` : '';
      arm.wrist.loading = 'lazy';
      arm.wrist.hidden = !INSET;
      arm.badge = htmlEl('span', 'pa-solved', '✓ task solved', view);
      arm.strip = htmlEl('div', 'pa-strip', null, lane);
      arm.cells = arm.data.requests.map((r, i) => {
        const b = htmlEl('button', 'pa-strip-cell', null, arm.strip);
        b.type = 'button';
        b.title = `LLM call ${i + 1}`;
        b.setAttribute('aria-label', `${arm.name}, LLM call ${i + 1}`);
        if (r.images) b.classList.add('pa-has-images');
        b.addEventListener('click', () => go(i + 1));
        return b;
      });
      const meter = htmlEl('div', 'pa-meter', null, lane);
      arm.fill = htmlEl('div', 'pa-meter-fill', null, meter);
      arm.meterText = htmlEl('div', 'pa-meter-text', null, lane);
      arm.step = htmlEl('div', 'pa-step', null, lane);
      arm.step.setAttribute('aria-live', 'polite');
      arm.lane = lane;
    }
    // two linked charts under the lanes: prompt tokens so far, and the size of each request
    const curveBox = htmlEl('div', 'pa-rp-curves', null, root);
    const curveLegend = htmlEl('div', 'pa-legend pa-rp-legend', null, curveBox);
    for (const [cls, text] of [['pa-key-tool', 'RPent · tool calling'], ['pa-key-code', 'PyRUA-Lean · code'],
      ['pa-key-solved', 'task solved (the benchmark\'s success check fired)']]) {
      const key = htmlEl('span', `pa-key ${cls}`, null, curveLegend);
      htmlEl('i', null, null, key);
      key.appendChild(document.createTextNode(text));
    }
    const curveTip = new Tip(curveBox);
    const series = arms.map(arm => {
      const cum = arm.data.requests.map(r => r.cum);
      return { arm, cum, per: cum.map((v, j) => v - (j ? cum[j - 1] : 0)) };
    });
    let curveState = null;
    const drawCurves = () => {
      const old = curveBox.querySelector('svg');
      if (old) old.remove();
      const width = curveBox.clientWidth;
      if (!width) return;
      const m = { l: 48, r: 48, t: 26, b: 50 };
      const pw = width - m.l - m.r;
      const ph = width >= 560 ? 170 : 150;
      const height = ph + m.t + m.b;
      const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': 'Token consumption so far, both agents' });
      curveBox.insertBefore(svg, curveLegend.nextSibling);
      const panels = [
        { key: 'cum', title: 'Token consumption so far', max: Math.max(...series.map(q => q.cum[q.cum.length - 1])) },
      ].map(panel => {
        const x0 = m.l, x1 = x0 + pw;
        const y0 = m.t, y1 = y0 + ph;
        const x = linear(0, N, x0, x1);
        const top = panel.max * 1.08;
        const y = linear(0, top, y1, y0);
        label(svg, x0, y0 - 14, panel.title, { size: 12, weight: 600, halo: false });
        // round ticks for any episode length (Appendix A replays episodes of up to 100 LLM calls)
        const ticks = steps(top, niceStep(panel.max, 6));
        gridY(svg, ticks, y, x0, x1, t => (t ? fmtTok(t) : '0'), { strong: t => t === 0 });
        axisX(svg, steps(N, niceStep(N, 6)), x, y1, x0, x1, t => `${t}`, { title: 'LLM call' });
        const ends = [];
        for (const q of series) {
          const values = q[panel.key];
          const colour = q.arm.key === 'rpent' ? TOOL : CODE;
          const d = values.map((v, j) => `${j ? 'L' : 'M'}${x(j + 1)},${y(v)}`).join('');
          svgEl('path', { d: panel.key === 'cum' ? `M${x(0)},${y(0)}L${d.slice(1)}` : d, fill: 'none', stroke: colour, 'stroke-width': 2.2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
          values.forEach((v, j) => svgEl('circle', { cx: x(j + 1), cy: y(v), r: 2.2, fill: colour }, svg));
          const solved = q.arm.data.solved_at;
          if (solved) {
            const sx = x(solved), sy = y(values[solved - 1]);
            svgEl('circle', { cx: sx, cy: sy, r: 6, fill: 'none', stroke: 'var(--pa-good)', 'stroke-width': 1.6 }, svg);
          }
          const last = values.length;
          ends.push({ x: x(last) + 7, y: y(values[last - 1]), text: kTokens(values[last - 1]) });
        }
        // each curve's last value at its end; two ends close together are pushed apart
        if (ends.length === 2 && Math.abs(ends[0].x - ends[1].x) < 44 && Math.abs(ends[0].y - ends[1].y) < 13) {
          const [hi, lo] = ends[0].y <= ends[1].y ? ends : [ends[1], ends[0]];
          const mid = (hi.y + lo.y) / 2;
          hi.y = mid - 6.5;
          lo.y = mid + 6.5;
        }
        for (const e of ends) label(svg, e.x, e.y, e.text, { size: 11, weight: 600 });
        const hair = svgEl('line', { y1: y0, y2: y1, stroke: 'var(--ink)', 'stroke-width': 1, 'stroke-opacity': 0.45 }, svg);
        const dots = series.map(q => svgEl('circle', { r: 5, fill: q.arm.key === 'rpent' ? TOOL : CODE, stroke: 'var(--pa-surface)', 'stroke-width': 2 }, svg));
        const overlay = svgEl('rect', { class: 'pa-overlay', x: x0, y: y0, width: x1 - x0, height: y1 - y0, fill: 'transparent' }, svg);
        const nearest = event => {
          const box = svg.getBoundingClientRect();
          const px = ((event.clientX - box.left) / box.width) * width;
          return clamp(Math.round(((px - x0) / (x1 - x0)) * N), 1, N);
        };
        overlay.addEventListener('pointermove', event => {
          const k = nearest(event);
          curveTip.show(x(k), y0 + 10, el => {
            tipTitle(el, `LLM call ${k}`, panel.title);
            for (const q of series) {
              const j = Math.min(k, q.cum.length) - 1;
              const row = htmlEl('div', 'pa-tip-series', null, el);
              const key = htmlEl('i', null, null, row);
              key.style.background = q.arm.key === 'rpent' ? 'var(--pa-tool)' : 'var(--pa-code)';
              htmlEl('b', null, kTokens(q.cum[j]), row);
              const solved = q.arm.data.solved_at;
              const note = solved && k >= solved ? ` (solved at LLM call ${solved})` : '';
              // the size of the call itself, which the running total's slope shows
              htmlEl('span', null, k > q.cum.length ? `${q.arm.name} (finished)` : `${q.arm.name}, ${kTokens(q.per[j])} in this call${note}`, row);
            }
          });
        });
        overlay.addEventListener('pointerleave', () => curveTip.hide());
        overlay.addEventListener('click', event => { stop(); go(nearest(event)); });
        return { panel, x, y, hair, dots };
      });
      curveState = panels;
      if (typeof i === 'number') placeCurves(i);
    };
    const placeCurves = k => {
      if (!curveState) return;
      for (const pn of curveState) {
        pn.hair.setAttribute('x1', pn.x(k));
        pn.hair.setAttribute('x2', pn.x(k));
        series.forEach((q, n) => {
          const j = Math.min(k, q.cum.length);
          pn.dots[n].setAttribute('cx', pn.x(j));
          pn.dots[n].setAttribute('cy', pn.y(q[pn.panel.key][j - 1]));
        });
      }
    };
    const controls = htmlEl('div', 'pa-rp-controls', null, root);
    const play = htmlEl('button', 'pa-rp-play', '▶ Play', controls);
    play.type = 'button';
    const prev = htmlEl('button', 'pa-rp-step', '‹', controls);
    prev.type = 'button';
    prev.setAttribute('aria-label', 'previous LLM call');
    const next = htmlEl('button', 'pa-rp-step', '›', controls);
    next.type = 'button';
    next.setAttribute('aria-label', 'next LLM call');
    const range = htmlEl('input', 'pa-rp-range', null, controls);
    Object.assign(range, { type: 'range', min: 1, max: N, value: 1 });
    range.setAttribute('aria-label', 'LLM call');
    const where = htmlEl('span', 'pa-rp-where', null, controls);

    const chip = (parent, text, cls) => htmlEl('span', `pa-chip ${cls || ''}`, text, parent);
    const thumbs = (parent, view, which) => {
      const row = htmlEl('span', 'pa-thumbs', null, parent);
      for (const cam of which) {
        const file = frame(view, cam);
        if (!file) continue;
        const img = htmlEl('img', null, null, row);
        img.loading = 'lazy';
        img.src = `${base}/${file}`;
        img.alt = camName(cam);
        img.title = camTitle(cam);
      }
      return row;
    };
    const renderTool = (arm, r) => {
      const box = arm.step;
      box.textContent = '';
      htmlEl('div', 'pa-step-k', `LLM call ${r.k} of ${arm.data.requests.length}`, box);
      const calls = htmlEl('div', 'pa-calls', null, box);
      const groups = [];
      for (const c of r.calls) {
        const last = groups[groups.length - 1];
        if (last && last.tool === c.tool) last.n += 1;
        else groups.push({ tool: c.tool, args: c.args, n: 1 });
      }
      if (!groups.length) chip(calls, 'final message', 'pa-chip-muted');
      for (const gr of groups) chip(calls, gr.n > 1 ? `${gr.tool} × ${gr.n}` : `${gr.tool}(${gr.args})`);
      const back = htmlEl('div', 'pa-returned', null, box);
      if (r.images) {
        htmlEl('span', null, `returned text + ${r.images} images`, back);
        thumbs(back, r.view, r.returned || ['policy', 'agentview', 'wrist']);
      } else {
        htmlEl('span', null, r.calls.length ? 'returned text' : '', back);
      }
      if (r.note) htmlEl('div', 'pa-note', `“${r.note}”`, box);
    };
    // Long code and output are shown in full, in boxes that scroll (with a fade and a hint while
    // more is below), so the lanes keep a fixed size.
    const scrollBox = (parent, cls, text) => {
      const wrap = htmlEl('div', 'pa-scrollbox', null, parent);
      const pre = htmlEl('pre', cls, text, wrap);
      htmlEl('span', 'pa-scroll-hint', 'scroll ↓', wrap);
      const update = () => wrap.classList.toggle('pa-more', pre.scrollHeight - pre.clientHeight - pre.scrollTop > 2);
      pre.addEventListener('scroll', update, { passive: true });
      update();
      return pre;
    };
    const renderCode = (arm, r) => {
      const box = arm.step;
      box.textContent = '';
      htmlEl('div', 'pa-step-k', `LLM call ${r.k} of ${arm.data.requests.length}`, box);
      if (r.tool === 'python' || r.tool === 'exec') {
        scrollBox(box, 'pa-code', r.code);
        const back = htmlEl('div', 'pa-returned', null, box);
        const printed = (r.stdout || '').replace(/\n+$/, '');
        // a cell that raised returns the error (its last line) after anything it printed
        const what = r.exception ? (printed ? 'what it printed and an error' : 'an error') : 'what it printed';
        htmlEl('span', null, r.images ? `returned ${what} + ${r.images} image${r.images > 1 ? 's' : ''} it asked for` : `returned ${what}`, back);
        if (r.images) thumbs(back, r.view, r.shown && r.shown.length ? r.shown : [MAIN]);
        const out = [printed, r.exception].filter(Boolean).join('\n');
        if (out) scrollBox(box, 'pa-stdout', out);
      } else {
        const calls = htmlEl('div', 'pa-calls', null, box);
        chip(calls, r.tool === 'message' ? 'final message' : r.code, r.tool === 'message' ? 'pa-chip-muted' : '');
      }
    };
    let i = 1, timer = null;
    const go = k => {
      placeCurves(clamp(k, 1, N));
      i = clamp(k, 1, N);
      range.value = i;
      where.textContent = `LLM call ${i}`;
      for (const arm of arms) {
        const reqs = arm.data.requests;
        const j = Math.min(i, reqs.length);
        const r = reqs[j - 1];
        // a call without a frame of its own keeps the last one shown
        const main = frame(r.view, MAIN), inset = INSET && frame(r.view, INSET);
        if (main) arm.main.src = `${base}/${main}`;
        if (inset) arm.wrist.src = `${base}/${inset}`;
        arm.badge.hidden = !arm.data.solved_at || j < arm.data.solved_at;  // an arm that never solved it has none
        arm.cells.forEach((b, n) => {
          b.classList.toggle('pa-past', n < j - 1);
          b.classList.toggle('pa-now', n === j - 1);
        });
        if (arm.key === 'rpent') renderTool(arm, r);
        else renderCode(arm, r);
        if (i > reqs.length) htmlEl('div', 'pa-done', `Finished after ${reqs.length} LLM calls.`, arm.step);
        arm.fill.style.width = `${(100 * r.cum) / maxCum}%`;
        const images = reqs.slice(0, j).reduce((s, q) => s + (q.images || 0), 0);
        arm.meterText.textContent = `${kTokens(r.cum)} tokens · ${images} images so far`;
      }
    };
    // Each step panel takes the height of its tallest request, so the figure does not jump while
    // stepping (the meters sit above the panels, so they line up whatever the panels hold).
    const fitSteps = () => {
      for (const arm of arms) {
        arm.step.style.minHeight = '0px';
        let h = 0;
        for (const r of arm.data.requests) {
          if (arm.key === 'rpent') renderTool(arm, r);
          else renderCode(arm, r);
          h = Math.max(h, arm.step.offsetHeight);
        }
        htmlEl('div', 'pa-done', 'Finished.', arm.step);
        arm.step.style.minHeight = `${Math.max(h, arm.step.offsetHeight)}px`;
      }
    };
    const stop = () => {
      clearInterval(timer);
      timer = null;
      play.textContent = '▶ Play';
    };
    root.paStop = stop; // a gallery stops the replay it replaces
    play.addEventListener('click', () => {
      if (timer) return stop();
      if (i >= N) go(1);
      play.textContent = '❚❚ Pause';
      timer = setInterval(() => (i >= N ? stop() : go(i + 1)), 1300);
    });
    prev.addEventListener('click', () => { stop(); go(i - 1); });
    next.addEventListener('click', () => { stop(); go(i + 1); });
    range.addEventListener('input', () => { stop(); go(Number(range.value)); });
    new ResizeObserver(() => drawCurves()).observe(curveBox);
    let lanesWidth = 0;
    new ResizeObserver(() => {
      if (Math.abs(lanes.clientWidth - lanesWidth) < 1) return;
      lanesWidth = lanes.clientWidth;
      fitSteps();
      go(i);
    }).observe(lanes);
    drawCurves();
    fitSteps();
    go(1);
    void state;
  };

  // -- Appendix A: more episodes, replayed one at a time ------------------------------------------------
  // The spec lists the episodes by benchmark and task; each one's data (the replay schema of Figure 1) is
  // fetched when chosen.
  const drawGallery = (plot, spec) => {
    if (plot.querySelector('.pa-gallery')) return; // built once; the replay inside is responsive
    const root = htmlEl('div', 'pa-gallery', null, plot);
    const bar = htmlEl('div', 'pa-gallery-bar', null, root);
    const picker = (text, cls) => {
      const wrap = htmlEl('span', `pa-gallery-pick ${cls}`, null, bar);
      const name = htmlEl('label', 'pa-gallery-label', text, wrap);
      const select = htmlEl('select', 'pa-gallery-select', null, wrap);
      select.id = `pa-gallery-${Math.random().toString(36).slice(2, 8)}`;
      name.htmlFor = select.id;
      return select;
    };
    const benchSelect = picker('Benchmark', 'pa-gallery-bench');
    const taskSelect = picker('Task', 'pa-gallery-task-pick');
    const benchmarks = [...new Set(spec.episodes.map(e => e.benchmark))];
    for (const b of benchmarks) htmlEl('option', null, b, benchSelect).value = b;
    const fillTasks = b => {
      taskSelect.textContent = '';
      spec.episodes.forEach((e, i) => {
        if (e.benchmark === b) htmlEl('option', null, e.task, taskSelect).value = String(i);
      });
    };
    const info = htmlEl('div', 'pa-gallery-info', null, root);
    info.setAttribute('aria-live', 'polite');
    const stage = htmlEl('div', 'pa-gallery-stage', null, root);
    const loaded = {};
    let latest = 0;
    const outcome = (a, who) => {
      const reqs = a.requests, at = a.solved_at, last = reqs[reqs.length - 1];
      return at ? `${who} solved it in LLM call ${at} of ${reqs.length}, ${kTokens(reqs[at - 1].cum)} tokens in`
        : `${who} did not solve it: ${reqs.length} LLM calls, ${kTokens(last.cum)} tokens`;
    };
    const show = async i => {
      const e = spec.episodes[i], mine = ++latest;
      info.textContent = 'Loading the episode…';
      try {
        loaded[e.slug] = loaded[e.slug] || fetch(siteUrl(`${spec.assets}/${e.slug}/demo.json`)).then(r => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        });
        const demo = await loaded[e.slug];
        if (mine !== latest) return; // another episode was chosen meanwhile
        const old = stage.querySelector('.pa-replay');
        if (old && old.paStop) old.paStop();
        stage.textContent = '';
        info.textContent = '';
        const task = htmlEl('div', 'pa-gallery-task', null, info);
        htmlEl('b', null, 'Task', task);
        task.appendChild(document.createTextNode(` “${demo.task}”`));
        htmlEl('div', 'pa-gallery-sum', `${outcome(demo.rpent, 'Tool calling')}; ${outcome(demo.cells, 'PyRUA-Lean')}.`, info);
        drawReplay(stage, { type: 'replay', title: `${e.benchmark}: ${e.task}`, assets: `${spec.assets}/${e.slug}/frames`,
          task: demo.task, cell: demo.cell, rpent: demo.rpent, cells: demo.cells, cameras: demo.cameras });
      } catch (err) {
        delete loaded[e.slug];
        if (mine === latest) info.textContent = `This episode could not be loaded (${err.message}).`;
      }
    };
    benchSelect.addEventListener('change', () => {
      fillTasks(benchSelect.value);
      show(Number(taskSelect.value));
    });
    taskSelect.addEventListener('change', () => show(Number(taskSelect.value)));
    fillTasks(benchmarks[0]);
    show(Number(taskSelect.value));
  };

  const DRAW = { success: drawSuccess, episode: drawEpisode, curves: drawCurves, decomp: drawDecomp, forest: drawForest, replay: drawReplay, gallery: drawGallery };

  const mount = figure => {
    const spec = JSON.parse(figure.querySelector('script.pa-spec').textContent);
    const plot = figure.querySelector('.pa-plot');
    const buttons = [...figure.querySelectorAll('.pa-controls button')];
    const state = { mode: (buttons.find(b => b.getAttribute('aria-pressed') === 'true') || {}).dataset?.mode || spec.mode };
    const tip = new Tip(plot);
    const draw = () => {
      const old = plot.querySelector(':scope > svg');
      if (old) old.remove();
      tip.hide();
      DRAW[spec.type](plot, spec, state, tip);
    };
    buttons.forEach(button => button.addEventListener('click', () => {
      state.mode = button.dataset.mode;
      buttons.forEach(b => b.setAttribute('aria-pressed', String(b === button)));
      draw();
    }));
    figure.classList.add('pa-live');
    let lastWidth = 0;
    new ResizeObserver(() => {
      const w = plot.clientWidth;
      if (Math.abs(w - lastWidth) > 1) {
        lastWidth = w;
        draw();
      }
    }).observe(plot);
    document.addEventListener('pointerdown', event => {
      if (!plot.contains(event.target)) tip.hide();
    });
  };

  const start = () => document.querySelectorAll('figure.pa-chart').forEach(mount);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
