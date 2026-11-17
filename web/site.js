/* Witsenhausen leaderboard: maths rendering and the data-driven parts of each page
   (copied to site/assets/site.js). Every page loads this file. Pages with charts or
   tables also load assets/data.js first, which defines window.WL; <body data-page>
   says which page this is. */
(function () {
"use strict";
var D = window.WL || null;
var PAGE = document.body.getAttribute("data-page") || "";
var SVGNS = "http://www.w3.org/2000/svg";
var HAS_KATEX = typeof window.katex !== "undefined";

/* Links into the old single-page site (index.html#leaderboard) go to the page that now holds the section. */
var MOVED = { problem: 1, leaderboard: 1, verification: 1, history: 1, theory: 1, contribute: 1 };
if (PAGE === "index" && MOVED.hasOwnProperty(location.hash.slice(1))) {
  location.replace(location.hash.slice(1) + ".html");
  return;
}

/* ---------- maths: static \( \) and \[ \] via auto-render, data strings via $...$ ---------- */
if (HAS_KATEX && typeof window.renderMathInElement === "function") {
  window.renderMathInElement(document.body, {
    delimiters: [{ left: "\\[", right: "\\]", display: true }, { left: "\\(", right: "\\)", display: false }],
    throwOnError: false
  });
}
function tex(src, display) {
  var sp = document.createElement("span");
  if (HAS_KATEX) {
    try { window.katex.render(src, sp, { throwOnError: false, displayMode: !!display }); return sp; } catch (e) { /* fall through */ }
  }
  sp.textContent = src;
  return sp;
}
/* Text that may contain inline LaTeX between dollar signs (names and notes come from data files). */
function mt(str) {
  var frag = document.createDocumentFragment();
  String(str).split("$").forEach(function (seg, i) {
    if (i % 2) frag.append(tex(seg)); else if (seg) frag.append(document.createTextNode(seg.replace(/(\w)'(\w)/g, "$1’$2")));
  });
  return frag;
}
/* Mixed content: strings may hold $...$ maths, {href, text} objects become links. */
function rich(parts) {
  var frag = document.createDocumentFragment();
  parts.forEach(function (p) {
    if (p === null || p === undefined) return;
    if (typeof p === "string") frag.append(mt(p));
    else if (p instanceof Node) frag.append(p);
    else frag.append(h("a", { href: p.href, math: p.text }));
  });
  return frag;
}
function plain(str) {
  return String(str).replace(/\$/g, "").replace(/\\[,;!: ]/g, " ").replace(/\\(?:mathrm|operatorname|text)\{([^}]*)\}/g, "$1")
    .replace(/\\([a-zA-Z]+)/g, "$1").replace(/[{}]/g, "").replace(/\s+/g, " ");
}

/* ---------- DOM helpers (text always goes in as text nodes) ---------- */
function h(tag, attrs) {
  var e = document.createElement(tag);
  setAttrs(e, attrs);
  for (var i = 2; i < arguments.length; i++) add(e, arguments[i]);
  return e;
}
function s(tag, attrs) {
  var e = document.createElementNS(SVGNS, tag);
  setAttrs(e, attrs);
  for (var i = 2; i < arguments.length; i++) add(e, arguments[i]);
  return e;
}
function setAttrs(e, attrs) {
  if (!attrs) return;
  Object.keys(attrs).forEach(function (k) {
    var v = attrs[k];
    if (v === null || v === undefined || v === false) return;
    if (k === "text") e.textContent = v;
    else if (k === "math") e.append(mt(v));
    else if (k === "class") e.setAttribute("class", v);
    else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  });
}
function add(e, kid) {
  if (kid === null || kid === undefined || kid === false) return;
  if (Array.isArray(kid)) { kid.forEach(function (k) { add(e, k); }); return; }
  e.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
}
function clear(id) { var e = document.getElementById(id); e.textContent = ""; return e; }
function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

/* ---------- formatting ---------- */
function fmtCost(c) { return c.toFixed(9); }
function fmtBound(v) { return v.toPrecision(4); }
function errTex(e) {
  var p = (e < 1e-15 ? 1e-15 : e).toExponential(0).split("e");
  return "\\pm\\," + p[0] + "\\times 10^{" + (+p[1]) + "}";
}
function num(v, d) { return v.toFixed(d).replace("-", "−"); }
function settingTex(st) { return "k = " + st.k + ",\\ \\sigma = " + st.sigma; }
function andJoin(names) {
  var parts = String(names).split(", ");
  return parts.length < 2 ? parts[0] : parts.slice(0, -1).join(", ") + " and " + parts[parts.length - 1];
}
function repoConfigured() { var r = D.site.repo_url || ""; return /^https?:\/\//.test(r) && r.indexOf("YOUR-GITHUB-USERNAME") < 0; }
function repoHref(path) { return repoConfigured() ? D.site.repo_url.replace(/\/$/, "") + "/blob/" + (D.site.branch || "main") + "/" + path : null; }
function safeHref(u) {
  if (!u) return null;
  if (/^https?:\/\//i.test(u)) return u;
  if (/^[\w.\-\/]+$/.test(u)) return repoHref(u);
  return null;
}
function linkOrText(label, url) {
  var href = safeHref(url);
  return href ? h("a", { href: href, rel: "noopener", math: label }) : h("span", { math: label });
}
function setting(id) { return D.settings.filter(function (x) { return x.id === id; })[0]; }
function entry(st, id) { return st.entries.filter(function (e) { return e.id === id; })[0]; }
function recordOf(st) { return entry(st, st.record_id); }
function bestReported() {
  return D.literature.filter(function (r) { return r.setting === D.benchmark; })
    .sort(function (a, b) { return a.reported_cost - b.reported_cost; })[0];
}
function niceTicks(lo, hi, n) {
  var span = hi - lo, step = Math.pow(10, Math.floor(Math.log10(span / n)));
  var err = (span / n) / step;
  if (err >= 7.5) step *= 10; else if (err >= 3.5) step *= 5; else if (err >= 1.5) step *= 2;
  var out = [], t = Math.ceil(lo / step - 1e-9) * step;
  for (; t <= hi + step * 1e-9; t += step) out.push(+t.toPrecision(12));
  return { ticks: out, step: step };
}
function tickLabel(t, step) { return num(t, Math.max(0, -Math.floor(Math.log10(step) + 1e-9))); }
function fitWidth(box, w) {
  var bw = box.getBoundingClientRect().width;
  return Math.round(bw > 0 ? Math.min(w, Math.max(280, bw)) : w);
}

/* ---------- line plot with crosshair readout ---------- */
function linePlot(box, o) {
  var W0 = o.width || 540, H0 = o.height || 330, m = { t: 8, r: 12, b: 26, l: 40 };
  var W = fitWidth(box, W0), H = Math.round(H0 * Math.max(0.82, W / W0));
  var iw = W - m.l - m.r, ih = H - m.t - m.b;
  var X = function (x) { return m.l + (x - o.x[0]) / (o.x[1] - o.x[0]) * iw; };
  var Y = function (y) { return m.t + ih - (y - o.y[0]) / (o.y[1] - o.y[0]) * ih; };
  var plot = h("div", { class: "plot" });
  if (o.yLabel) box.append(h("p", { class: "ylab", math: o.yLabel }));
  box.append(plot);
  if (o.xLabel) box.append(h("p", { class: "xlab", math: o.xLabel }));
  var svg = s("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": o.aria || "" });
  var xt = niceTicks(o.x[0], o.x[1], o.xTicks || 6), yt = niceTicks(o.y[0], o.y[1], o.yTicks || 6);
  var grid = s("g", { class: "grid" });
  yt.ticks.forEach(function (t) { grid.append(s("line", { x1: m.l, x2: m.l + iw, y1: Y(t), y2: Y(t) })); });
  svg.append(grid);
  var ax = s("g", { class: "axis" });
  ax.append(s("line", { x1: m.l, x2: m.l + iw, y1: m.t + ih, y2: m.t + ih }));
  xt.ticks.forEach(function (t) { ax.append(s("text", { x: X(t), y: m.t + ih + 18, "text-anchor": "middle", text: tickLabel(t, xt.step) })); });
  yt.ticks.forEach(function (t) { ax.append(s("text", { x: m.l - 7, y: Y(t) + 4.5, "text-anchor": "end", text: tickLabel(t, yt.step) })); });
  svg.append(ax);
  var clipId = "c" + Math.random().toString(36).slice(2);
  svg.append(s("clipPath", { id: clipId }, s("rect", { x: m.l, y: m.t, width: iw, height: ih })));
  var layer = s("g", { "clip-path": "url(#" + clipId + ")" });
  (o.layers || []).forEach(function (L) {
    var d = "";
    if (L.segments) {
      var last = null;
      L.segments.forEach(function (sg) {
        var p0 = X(sg[0]).toFixed(2) + "," + Y(sg[1]).toFixed(2), p1 = X(sg[2]).toFixed(2) + "," + Y(sg[3]).toFixed(2);
        if (last && Math.abs(last[0] - sg[0]) < 1e-9 && Math.abs(last[1] - sg[1]) < 1e-9) d += "L" + p1;
        else d += "M" + p0 + "L" + p1;
        last = [sg[2], sg[3]];
      });
    } else if (L.points) {
      L.points.forEach(function (p, i) { d += (i ? "L" : "M") + X(p[0]).toFixed(2) + "," + Y(p[1]).toFixed(2); });
    }
    var path = s("path", { d: d, class: L.ref ? "ref" : "series" });
    if (!L.ref) path.style.stroke = L.color;
    layer.append(path);
  });
  svg.append(layer);
  plot.append(svg);
  if (!o.readout) return;
  var tip = h("div", { class: "tip", role: "status" });
  plot.append(tip);
  var xh = s("line", { class: "xhair", y1: m.t, y2: m.t + ih, x1: -10, x2: -10, visibility: "hidden" });
  var dots = s("g");
  svg.append(xh, dots);
  var hit = s("rect", { class: "hit", x: m.l, y: m.t, width: iw, height: ih, tabindex: 0, "aria-label": (o.aria || "") + ". Use the left and right arrow keys to read values." });
  svg.append(hit);
  var cur = (o.x[0] + o.x[1]) / 2;
  function show(xv) {
    cur = Math.max(o.x[0], Math.min(o.x[1], xv));
    var rows = o.readout(cur);
    xh.setAttribute("x1", X(cur)); xh.setAttribute("x2", X(cur)); xh.setAttribute("visibility", "visible");
    while (dots.firstChild) dots.removeChild(dots.firstChild);
    tip.textContent = "";
    rows.forEach(function (r) {
      if (r.y !== undefined && r.color) dots.append(s("circle", { class: "dot", cx: X(cur), cy: Y(r.y), r: 4, fill: r.color }));
      var row = h("div", { class: "row" });
      if (r.color) { var k = h("i"); k.style.background = r.color; row.append(k); }
      row.append(h("span", { class: "v", text: r.value }), h("span", { class: "l", math: r.label }));
      tip.append(row);
    });
    var bw = plot.getBoundingClientRect().width, scale = bw / W, px = X(cur) * scale, tw = tip.offsetWidth;
    tip.style.left = (px + 14 + tw > bw ? Math.max(0, px - 14 - tw) : px + 14) + "px";
    tip.style.top = (m.t * scale + 4) + "px";
    tip.classList.add("on");
  }
  function hide() { xh.setAttribute("visibility", "hidden"); tip.classList.remove("on"); while (dots.firstChild) dots.removeChild(dots.firstChild); }
  hit.addEventListener("pointermove", function (ev) {
    var r = svg.getBoundingClientRect();
    show(o.x[0] + ((ev.clientX - r.left) * W / r.width - m.l) / iw * (o.x[1] - o.x[0]));
  });
  hit.addEventListener("pointerleave", hide);
  hit.addEventListener("blur", hide);
  hit.addEventListener("focus", function () { show(cur); });
  hit.addEventListener("keydown", function (ev) {
    var step = (o.x[1] - o.x[0]) / 100;
    if (ev.key === "ArrowRight") { show(cur + step); ev.preventDefault(); }
    if (ev.key === "ArrowLeft") { show(cur - step); ev.preventDefault(); }
  });
}
function interp(xs, ys, x) {
  if (x <= xs[0]) return ys[0];
  for (var i = 1; i < xs.length; i++) if (x <= xs[i]) {
    var t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    return ys[i - 1] + t * (ys[i] - ys[i - 1]);
  }
  return ys[ys.length - 1];
}
function segmentsOf(plot, xmin, xmax) {
  if (plot.segments) return plot.segments.filter(function (sg) { return sg[2] >= xmin && sg[0] <= xmax; });
  var out = [];
  for (var i = 0; i + 1 < plot.x.length; i++) out.push([plot.x[i], plot.f[i], plot.x[i + 1], plot.f[i + 1]]);
  return out;
}
function fAt(plot, x) {
  var sg = plot.segments;
  if (sg) for (var i = 0; i < sg.length; i++) if (x >= sg[i][0] && x <= sg[i][2]) {
    var t = (x - sg[i][0]) / ((sg[i][2] - sg[i][0]) || 1);
    return sg[i][1] + t * (sg[i][3] - sg[i][1]);
  }
  return interp(plot.x, plot.f, x);
}
function controllerPlot(box, e, sigma, opts) {
  opts = opts || {};
  var L = 6 * sigma, p = e.plot, col = cssVar("--s2");
  var ylo = Math.min(-L, Math.min.apply(null, p.f)), yhi = Math.max(L, Math.max.apply(null, p.f));
  linePlot(box, {
    height: opts.height || 350, x: [-L, L], y: [ylo, yhi],
    xLabel: "initial state $x_0$", yLabel: "$x_1 = f(x_0)$",
    aria: "First controller, " + plain(e.name) + ": x1 = f(x0) for x0 between " + (-L) + " and " + L,
    layers: [{ ref: true, points: [[-L, -L], [L, L]] }, { segments: segmentsOf(p, -L, L), color: col }],
    readout: function (x) {
      var fx = fAt(p, x);
      return [{ value: num(fx, 3), label: "$= x_1$ at $x_0 = " + x.toFixed(2) + "$", y: fx, color: col },
              { value: num(fx - x, 3), label: "$= u_1 = x_1 - x_0$" }];
    }
  });
}
function secondControllerPlot(box, e, sigma, opts) {
  opts = opts || {};
  var p = e.plot, col = cssVar("--s2"), lo = p.y[0], hi = p.y[p.y.length - 1];
  var glo = Math.min.apply(null, p.g), ghi = Math.max.apply(null, p.g);
  linePlot(box, {
    height: opts.height || 300, x: [lo, hi], y: [Math.min(glo, lo), Math.max(ghi, hi)],
    xLabel: "observation $y = x_1 + w$", yLabel: "$u_2 = g_f(y)$",
    aria: "Optimal second controller for " + plain(e.name),
    layers: [{ ref: true, points: [[lo, lo], [hi, hi]] }, { points: p.y.map(function (y, i) { return [y, p.g[i]]; }), color: col }],
    readout: function (y) {
      var g = interp(p.y, p.g, y);
      return [{ value: num(g, 3), label: "$= g_f(y)$ at $y = " + y.toFixed(2) + "$", y: g, color: col }];
    }
  });
}

/* ---------- home: the gap, the headline numbers and the record controller ---------- */
function renderHero() {
  var st = setting(D.benchmark), rec = recordOf(st), lb = st.lower_bounds, lin = entry(st, "affine-optimal");
  var bestRep = bestReported();

  var box = clear("gap");
  var W = fitWidth(box, 540), H = 110, m = { l: 12, r: 12 };
  var X = function (v) { return m.l + v * (W - m.l - m.r); };
  var svg = s("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, role: "img",
    "aria-label": "Number line from 0 to 1. The optimal benchmark cost lies between the proven lower bound " + fmtBound(lb.best_value) + " and the best verified cost " + fmtCost(rec.result.cost) + ". The best linear controller costs " + lin.result.cost.toFixed(2) + "." });
  var yb = 78, ink = cssVar("--ink"), ink2 = cssVar("--ink-2");
  svg.append(s("rect", { x: X(lb.best_value), y: yb - 12, width: X(rec.result.cost) - X(lb.best_value), height: 24, fill: cssVar("--wash") }));
  var ax = s("g", { class: "axis" });
  ax.append(s("line", { x1: X(0), x2: X(1), y1: yb, y2: yb }));
  [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
    ax.append(s("line", { x1: X(t), x2: X(t), y1: yb, y2: yb + 5 }));
    ax.append(s("text", { x: X(t), y: yb + 22, "text-anchor": t === 0 ? "start" : t === 1 ? "end" : "middle", text: t.toFixed(2) }));
  });
  svg.append(ax);
  function mark(v, color, label, row, anchor) {
    var ty = row === 0 ? 14 : 36;
    svg.append(s("line", { x1: X(v), x2: X(v), y1: ty + 5, y2: yb, stroke: ink2, "stroke-width": 1, "shape-rendering": "crispEdges" }));
    svg.append(s("circle", { cx: X(v), cy: yb, r: 5, fill: color, class: "dot" }));
    svg.append(s("text", { class: "lbl", x: X(v) + (anchor === "end" ? 4 : -4), y: ty, "text-anchor": anchor, text: label }));
  }
  mark(lb.best_value, ink, "proven lower bound " + fmtBound(lb.best_value), 0, "start");
  mark(rec.result.cost, cssVar("--s2"), "best verified cost " + rec.result.cost.toFixed(5), 1, "start");
  mark(lin.result.cost, ink2, "best linear " + lin.result.cost.toFixed(2), 0, "end");
  box.append(svg);
  clear("gapcap").append(mt("Its width, $" + (rec.result.cost - lb.best_value).toFixed(4) + "$, measures how far the problem is from solved. The best verified cost is $" +
    (rec.result.cost / lb.best_value).toFixed(2) + "$ times the best proven bound."));

  var claims = clear("claims");
  function claim(color, strong) {
    var key = h("span", { class: "key" }); key.style.background = color;
    var body = h("span", null, h("strong", { text: strong }), " ");
    for (var i = 2; i < arguments.length; i++) add(body, arguments[i]);
    claims.append(h("li", null, key, body));
  }
  claim(cssVar("--s2"), fmtCost(rec.result.cost),
    rich(["is the best verified cost, from the ", { href: "leaderboard.html", text: rec.short_name || "record entry" }, " (" + rec.date.slice(0, 4) + "), "]),
    h("span", { class: "sub" }, tex(errTex(rec.result.error_estimate)), "."));
  if (bestRep) claim(cssVar("--s1"), fmtReported(bestRep),
    rich(["is the best claimed cost, by ", { href: "leaderboard.html", text: andJoin(bestRep.authors) + " (" + bestRep.year + ")" }, ". It has not been verified here yet."]));
  var eq = lb.bounds[lb.best].equation;
  claim(ink, fmtBound(lb.best_value),
    rich(["is the best proven lower bound, ", { href: "problem.html#eq-" + eq, text: "equation (" + eq + ")" }, " in Section 1."]));

  controllerPlot(clear("hero-plot"), rec, st.sigma, { height: 370 });
  var hc = clear("hero-cap");
  var lv = (rec.steps.steps || []).filter(function (x) { return x.level > 1e-6; }).slice(0, 3).map(function (x) { return "\\pm" + x.level.toFixed(2); });
  hc.append(h("b", { text: "Figure 1." }), mt(" The record controller at the benchmark: " + rec.name.replace(/^./, function (c) { return c.toLowerCase(); }) +
    ". Each step sends a band of initial states to one signalling level" + (lv.length ? " (here $0, " + lv.join(", ") + ", \\dots$)" : "") +
    ". The levels are far enough apart to be told apart through unit noise, and the slight slope within a step trades some of that separation for less control effort. Thin line: $x_1 = x_0$, no control."));
}

/* ---------- leaderboard: controllers ranked by cost and lower bounds ranked by value, each with an evidence level.
   The address keeps the setting: leaderboard.html#k0.50_s5. ---------- */
var current = null;
function fmtReported(r) { return Number(r.reported_cost).toFixed(9); }
function settingFromHash() {
  var id = decodeURIComponent(location.hash.slice(1));
  return id && setting(id) ? id : null;
}
function initLeaderboard() {
  current = settingFromHash() || D.benchmark;
  var sel = clear("setting");
  D.settings.forEach(function (st) {
    sel.append(h("option", { value: st.id, text: (st.id === D.benchmark ? "Benchmark, " : "") + "k = " + st.k + ", σ = " + st.sigma }));
  });
  sel.value = current;
  sel.addEventListener("change", function () { selectSetting(sel.value); });
  ["show-claimed", "show-verified"].forEach(function (id) { document.getElementById(id).addEventListener("change", renderBoard); });
  renderBoard();
  window.addEventListener("hashchange", function () {
    var id = settingFromHash();
    if (id && id !== current) { sel.value = id; selectSetting(id); }
  });
}
function selectSetting(id) {
  current = id;
  try { history.replaceState(null, "", "#" + id); } catch (e) { /* some browsers refuse this for files opened from disk */ }
  renderBoard();
}
/* "A, B" stays as it is; three or more authors become "A et al." (the full list is in Details). */
function shortAuthors(list) {
  var names = Array.isArray(list) ? list : String(list).split(", ");
  return names.length > 2 ? names[0] + " et al." : names.join(", ");
}
function evidenceTag(level) {
  var cls = { "Claimed": "claimed", "Numerically verified": "numerical", "Peer-reviewed": "peer" }[level] || "";
  return h("span", { class: "ev " + cls, text: level });
}
function intervalTex(lo, hi) {
  return (lo === null ? "(-\\infty" : "[" + lo.toFixed(2)) + ",\\ " + (hi === null ? "\\infty" : hi.toFixed(2)) + ")";
}
function stepsTable(e) {
  var sp = e.steps;
  if (!sp || !sp.steps.length) return null;
  var rows = sp.steps;
  if (sp.odd) rows = rows.filter(function (x) { return x.hi === null || x.hi > 1e-9; });
  rows = rows.slice(0, 12);
  var tb = h("tbody");
  rows.forEach(function (x) {
    tb.append(h("tr", null, h("td", null, tex(intervalTex(x.lo, x.hi))), h("td", { text: x.prob.toFixed(6) }), h("td", { text: num(Math.abs(x.level) < 5e-7 ? 0 : x.level, 4) })));
  });
  return h("div", null,
    h("p", { class: "cap above", math: "Steps of $f$, the maximal intervals without a jump" + (sp.odd ? ". $f$ is odd, so only steps reaching $x_0 > 0$ are listed." : ".") }),
    h("table", { class: "mini" }, h("thead", null, h("tr", null, h("th", { math: "$x_0 \\in$" }), h("th", { text: "probability" }), h("th", { math: "$\\mathbb{E}[x_1 \\mid \\text{step}]$" }))), tb));
}
/* A "Details" button in the row's last cell; the details open in a row underneath. */
function withDetails(row, btn, build) {
  var open = null;
  btn.addEventListener("click", function () {
    if (open) { open.remove(); open = null; btn.setAttribute("aria-expanded", "false"); return; }
    btn.setAttribute("aria-expanded", "true");
    var parts = build();
    open = h("tr", { class: "detail" }, h("td", { colspan: 9 }, parts.node));
    row.after(open);
    if (parts.after) parts.after();
  });
  return row;
}
function verifiedRow(e, rank, st, paper) {
  var r = e.result, btn = h("button", { class: "btn", "aria-expanded": "false", text: "Details" });
  var row = h("tr", null,
    h("td", { class: "num", text: String(rank) }),
    h("td", { class: "num" }, h("span", { class: "cost", text: fmtCost(r.cost) })),
    h("td", null, evidenceTag("Numerically verified")),
    h("td", { math: e.name }),
    h("td", { text: shortAuthors(e.authors || []) }),
    h("td", { class: "nowrap", text: e.date }),
    h("td", { class: "num", text: r.stage1.toFixed(6) }),
    h("td", { class: "num", text: r.mmse.toFixed(6) }),
    h("td", null, btn));
  return withDetails(row, btn, function () {
    var c1 = h("div", { class: "chartbox" }), c2 = h("div", { class: "chartbox" });
    var kv = h("dl", { class: "kv" },
      e.method ? [h("dt", { text: "Method" }), h("dd", { math: e.method })] : null,
      paper ? [h("dt", { text: "Paper" }), h("dd", null, linkOrText(paper.title, paper.url), ". " + paper.venue + ".")] : null,
      h("dt", { text: "Error estimate" }), h("dd", null, tex(errTex(r.error_estimate))),
      h("dt", { text: "Pieces" }), h("dd", { text: String(r.n_pieces) }),
      h("dt", { text: "Controller file" }), h("dd", null, h("a", { href: e.file, download: true, text: e.file })),
      h("dt", { text: "SHA-256" }), h("dd", null, h("code", { text: e.sha256.slice(0, 20) + "…" })),
      h("dt", null, tex("\\mathbb{E}[u_1^2]")), h("dd", { text: r.power.toFixed(9) }),
      h("dt", null, tex("\\mathbb{E}[x_1^2]")), h("dd", { text: r.second_moment.toFixed(9) }),
      h("dt", { text: "Evaluation" }), h("dd", { text: "evaluator v" + r.evaluator_version + ", " + r.n_nodes.toLocaleString("en-US") + " quadrature nodes, " + e.eval_seconds + " s" }),
      e.source && e.source.url ? [h("dt", { text: "Source" }), h("dd", null, linkOrText(e.source.url, e.source.url))] : null,
      e.notes ? [h("dt", { text: "Notes" }), h("dd", { math: e.notes })] : null);
    return {
      node: h("div", { class: "detailgrid" }, c1, c2, kv, stepsTable(e)),
      after: function () { controllerPlot(c1, e, st.sigma, { height: 290 }); secondControllerPlot(c2, e, st.sigma, { height: 290 }); }
    };
  });
}
function claimedRow(p, rank) {
  var btn = h("button", { class: "btn", "aria-expanded": "false", text: "Details" });
  var row = h("tr", null,
    h("td", { class: "num", text: String(rank) }),
    h("td", { class: "num" }, h("span", { class: "cost", text: fmtReported(p) })),
    h("td", null, evidenceTag("Claimed")),
    h("td", { math: p.method }),
    h("td", { text: shortAuthors(p.authors) }),
    h("td", { class: "nowrap", text: String(p.year) }),
    h("td", { class: "num", text: "–" }),
    h("td", { class: "num", text: "–" }),
    h("td", null, btn));
  return withDetails(row, btn, function () {
    return { node: h("dl", { class: "kv" },
      h("dt", { text: "Authors" }), h("dd", { text: p.authors }),
      h("dt", { text: "Paper" }), h("dd", null, linkOrText(p.title, p.url), ". " + p.venue + "."),
      h("dt", { text: "Shape of the controller" }), h("dd", { math: p.structure }),
      h("dt", { text: "Cost as printed" }), h("dd", { text: p.reported_as }),
      p.notes ? [h("dt", { text: "Notes" }), h("dd", { math: p.notes })] : null) };
  });
}
function renderBoard() {
  var st = setting(current), rec = recordOf(st), lbs = st.lower_bounds;
  var papers = D.literature.filter(function (r) { return r.setting === st.id; });
  var claims = papers.filter(function (r) { return !r.verified_by; });
  var paperOf = {};
  papers.forEach(function (r) { if (r.verified_by) paperOf[r.verified_by] = r; });
  var bestClaim = claims.slice().sort(function (a, b) { return a.reported_cost - b.reported_cost; })[0];
  add(clear("scorebar"), [h("span", null, "Best verified ", h("b", { text: fmtCost(rec.result.cost) })),
    bestClaim ? h("span", null, "Best claimed ", h("b", { text: fmtReported(bestClaim) })) : null,
    h("span", null, "Best lower bound ", h("b", { text: fmtBound(lbs.best_value) }))]);

  var showClaimed = document.getElementById("show-claimed").checked, showVerified = document.getElementById("show-verified").checked;
  var rows = (showVerified ? st.entries.map(function (e) { return { cost: e.result.cost, e: e }; }) : [])
    .concat(showClaimed ? claims.map(function (p) { return { cost: p.reported_cost, p: p }; }) : [])
    .sort(function (a, b) { return (a.cost - b.cost) || ((a.e ? 0 : 1) - (b.e ? 0 : 1)); });
  var tb = clear("board-rows");
  if (!rows.length) tb.append(h("tr", null, h("td", { colspan: 9, class: "empty", text: "Tick an evidence level to show entries." })));
  rows.forEach(function (x, i) { tb.append(x.e ? verifiedRow(x.e, i + 1, st, paperOf[x.e.id]) : claimedRow(x.p, i + 1)); });

  var lb = clear("bound-rows"), bs = lbs.bounds;
  Object.keys(bs).sort(function (a, b) { return bs[b].value - bs[a].value; }).forEach(function (k, i) {
    var b = bs[k];
    lb.append(h("tr", null,
      h("td", { class: "num", text: String(i + 1) }),
      h("td", { class: "num" }, h("span", { class: "cost", text: fmtBound(b.value_rounded_down) })),
      h("td", null, evidenceTag(b.evidence)),
      h("td", null, b.label + " ", h("a", { href: "problem.html#eq-" + b.equation, text: "(" + b.equation + ")" })),
      h("td", null, linkOrText(shortAuthors(b.authors), b.source)),
      h("td", { text: String(b.year) })));
  });
}

/* ---------- history ---------- */
function historyChart(box, pts, o) {
  var W = fitWidth(box, 540), H = Math.round(320 * Math.max(0.85, W / 540)), m = { t: 12, r: 14, b: 26, l: 52 };
  var iw = W - m.l - m.r, ih = H - m.t - m.b;
  var X = function (x) { return m.l + (x - o.x[0]) / (o.x[1] - o.x[0]) * iw; };
  var Y = function (y) { return m.t + ih - (y - o.y[0]) / (o.y[1] - o.y[0]) * ih; };
  var plot = h("div", { class: "plot" });
  box.append(h("p", { class: "ylab", math: "cost $J$" }), plot, h("p", { class: "xlab", text: "year" }));
  var svg = s("svg", { class: "chart", viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": o.aria });
  var yt = niceTicks(o.y[0], o.y[1], 5);
  var grid = s("g", { class: "grid" });
  yt.ticks.forEach(function (t) { grid.append(s("line", { x1: m.l, x2: m.l + iw, y1: Y(t), y2: Y(t) })); });
  svg.append(grid);
  var ax = s("g", { class: "axis" });
  ax.append(s("line", { x1: m.l, x2: m.l + iw, y1: m.t + ih, y2: m.t + ih }));
  o.xTicks.forEach(function (t) { ax.append(s("text", { x: X(t), y: m.t + ih + 18, "text-anchor": "middle", text: String(t) })); });
  yt.ticks.forEach(function (t) { ax.append(s("text", { x: m.l - 7, y: Y(t) + 4.5, "text-anchor": "end", text: tickLabel(t, yt.step) })); });
  svg.append(ax);
  var rep = pts.filter(function (p) { return p.kind === "reported"; }).sort(function (a, b) { return a.x - b.x || b.y - a.y; });
  var best = Infinity, d = "", started = false;
  rep.forEach(function (p) {
    if (p.y < best) {
      if (started) d += "L" + X(p.x).toFixed(1) + "," + Y(Math.min(best, o.y[1])).toFixed(1);
      best = p.y;
      d += (started ? "L" : "M") + X(p.x).toFixed(1) + "," + Y(Math.min(best, o.y[1])).toFixed(1);
      started = true;
    }
  });
  if (started) d += "L" + X(o.x[1]).toFixed(1) + "," + Y(best).toFixed(1);
  var clipId = "hc" + Math.random().toString(36).slice(2);
  svg.append(s("clipPath", { id: clipId }, s("rect", { x: m.l, y: m.t - 6, width: iw, height: ih + 12 })));
  var path = s("path", { d: d, class: "series", "clip-path": "url(#" + clipId + ")" });
  path.style.stroke = cssVar("--s1");
  svg.append(path);
  var tip = h("div", { class: "tip", role: "status" });
  plot.append(svg, tip);
  pts.filter(function (p) { return p.y >= o.y[0] && p.y <= o.y[1] && p.x >= o.x[0] && p.x <= o.x[1]; }).forEach(function (p) {
    var color = p.kind === "reported" ? cssVar("--s1") : cssVar("--s2");
    var pos = W >= 420 ? o.label(p) : null;
    if (pos) {
      var right = pos.charAt(1) === "r", above = pos.charAt(0) === "a";
      svg.append(s("text", { class: "lbl", x: X(p.x) + (right ? 11 : -11), y: Y(p.y) + (above ? -8 : 18), "text-anchor": right ? "start" : "end", text: p.short }));
    }
    var g = s("g", { class: "pt", tabindex: 0, "aria-label": plain(p.label) + ", " + p.year + ": " + p.value + (p.kind === "reported" ? " (claimed)" : " (numerically verified)") });
    g.append(s("circle", { class: "hit", cx: X(p.x), cy: Y(p.y), r: 12 }));
    g.append(s("circle", { class: "dot", cx: X(p.x), cy: Y(p.y), r: 4.5, fill: color }));
    function show() {
      tip.textContent = "";
      var row = h("div", { class: "row" }); var k = h("i"); k.style.background = color;
      row.append(k, h("span", { class: "v", text: p.value }), h("span", { class: "l", text: p.kind === "reported" ? "claimed" : "numerically verified" }));
      tip.append(row, h("div", { class: "l", math: p.label + " (" + p.year + ")" }));
      if (p.note) tip.append(h("div", { class: "l", math: p.note }));
      var bw = plot.getBoundingClientRect().width, sc = bw / W, px = X(p.x) * sc, tw = tip.offsetWidth, th = tip.offsetHeight;
      tip.style.left = (px + 14 + tw > bw ? Math.max(0, px - 14 - tw) : px + 14) + "px";
      tip.style.top = Math.max(0, Math.min(Y(p.y) * sc - th / 2, H * sc - th)) + "px";
      tip.classList.add("on");
    }
    function hide() { tip.classList.remove("on"); }
    g.addEventListener("pointerenter", show); g.addEventListener("pointerleave", hide);
    g.addEventListener("focus", show); g.addEventListener("blur", hide);
    svg.append(g);
  });
}
var HIST = [];
function renderHistoryCharts() {
  var yNow = new Date().getFullYear(), st = setting(D.benchmark);
  historyChart(clear("hist-all"), HIST, { x: [1964, yNow + 2], y: [0, 1], xTicks: [1970, 1980, 1990, 2000, 2010, 2020],
    aria: "Benchmark costs by year from 1968, claimed and numerically verified",
    label: function (p) { return p.kind === "reported" && p.year === 1968 ? "ar" : null; } });
  var place = { "mehmetoglu-2014": "bl", "tseng-tang-2017": "br" };
  historyChart(clear("hist-zoom"), HIST, { x: [2000, yNow + 2], y: [0.16685, 0.16740], xTicks: [2000, 2005, 2010, 2015, 2020, 2025],
    aria: "Benchmark costs since 2001 between 0.16685 and 0.16740",
    label: function (p) { return p.kind === "reported" ? (place[p.id] || "ar") : (p.id === st.record_id ? "al" : null); } });
}
function renderHistory() {
  var st = setting(D.benchmark);
  D.literature.filter(function (r) { return r.setting === D.benchmark; }).forEach(function (r) {
    HIST.push({ kind: "reported", id: r.id, x: r.year, y: r.reported_cost, year: r.year, value: fmtReported(r), label: r.authors, short: r.short || r.authors, note: r.method });
  });
  st.entries.forEach(function (e) {
    var yr = +e.date.slice(0, 4);
    HIST.push({ kind: "verified", id: e.id, x: yr + 0.25, y: e.result.cost, year: yr, value: fmtCost(e.result.cost), label: e.name, short: "verified here", note: (e.authors || []).join(", ") });
  });
  var lg = clear("hist-legend");
  [["--s1", "Claimed"], ["--s2", "Numerically verified"]].forEach(function (x) {
    var k = h("span", { class: "key" }); k.style.background = "var(" + x[0] + ")";
    lg.append(h("span", null, k, x[1]));
  });
  renderHistoryCharts();
}

/* ---------- theory and contribute ---------- */
function renderTheory() {
  var ul = clear("theorylist");
  D.theory.forEach(function (t) {
    ul.append(h("li", null,
      h("span", { text: String(t.year) }),
      h("div", null, h("div", { math: t.claim }),
        h("div", { class: "cite" }, t.authors + ", ", linkOrText(t.title, t.url), (/[.?!]$/.test(t.title) ? " " : ". ") + t.venue + ".")),
      h("div", { class: "kind" }, h("div", { text: t.kind }), h("span", { class: "tag", text: t.evidence }))));
  });
}
function renderContribute() {
  document.getElementById("example").textContent = D.example;
  document.getElementById("prompt").textContent = D.agent_prompt;
  var btn = document.getElementById("copy-prompt");
  btn.addEventListener("click", function () {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(D.agent_prompt).then(function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy prompt"; }, 1600); });
  });
  var st = setting(D.benchmark), rec = recordOf(st), bestRep = bestReported();
  var ul = clear("targets");
  [
    ["A verified cost below $" + rec.result.cost.toFixed(7) + "$ at the benchmark. In particular, a controller file that reproduces the $" + fmtReported(bestRep) + "$ claimed by " +
      andJoin(bestRep.authors) + " would settle whether that value or the verified record is the better one."],
    ["A proven lower bound above $" + fmtBound(st.lower_bounds.best_value) + "$ at the benchmark. Bounds are added by pull request to ", h("code", { text: "witsenhausen/bounds.py" }), ", with a reference or a proof."],
    ["A controller file that reproduces one of the ", { href: "leaderboard.html", text: "claimed costs on the leaderboard" }, "."],
    ["A new result about the optimum for the ", { href: "theory.html", text: "log in Section 5" }, ", or a correction to an entry."]
  ].forEach(function (parts) { ul.append(h("li", null, rich(parts))); });
}

/* ---------- start ---------- */
var redraw = null, recolor = null;  /* redraw: after a resize; recolor: after the theme changes */
if (D) {
  if (PAGE === "index") { renderHero(); redraw = recolor = renderHero; }
  else if (PAGE === "leaderboard") { initLeaderboard(); recolor = renderBoard; }
  else if (PAGE === "history") { renderHistory(); redraw = recolor = renderHistoryCharts; }
  else if (PAGE === "theory") renderTheory();
  else if (PAGE === "contribute") renderContribute();
}
if (redraw) {
  var lastW = window.innerWidth, timer = null;
  window.addEventListener("resize", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { if (Math.abs(window.innerWidth - lastW) >= 40) { lastW = window.innerWidth; redraw(); } }, 200);
  });
}
/* ---------- light and dark: the button in the top bar. The choice is kept in localStorage ("wl-theme");
   until the reader picks one, the system setting decides. The <head> applies a saved choice before drawing. ---------- */
function themeNow() {
  var t = document.documentElement.getAttribute("data-theme");
  if (t === "dark" || t === "light") return t;
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function showThemeButton(btn) {
  var next = themeNow() === "dark" ? "light" : "dark", svg = btn.querySelector("svg");
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  if (next === "dark") svg.append(s("path", { d: "M13.2 10.4A5.6 5.6 0 0 1 5.6 2.8a5.6 5.6 0 1 0 7.6 7.6z", fill: "currentColor" }));
  else svg.append(s("circle", { cx: 8, cy: 8, r: 3, fill: "currentColor" }),
    s("path", { d: "M8 1.2v1.8M8 13v1.8M1.2 8H3M13 8h1.8M3.2 3.2l1.3 1.3M11.5 11.5l1.3 1.3M3.2 12.8l1.3-1.3M11.5 4.5l1.3-1.3",
      fill: "none", stroke: "currentColor", "stroke-width": 1.4, "stroke-linecap": "round" }));
  btn.setAttribute("aria-label", "Switch to " + next + " mode");
}
var themeBtn = document.getElementById("theme");
if (themeBtn) {
  showThemeButton(themeBtn);
  themeBtn.addEventListener("click", function () {
    var next = themeNow() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("wl-theme", next); } catch (e) { /* storage off: the choice lasts for this page only */ }
    showThemeButton(themeBtn);
    if (recolor) recolor();  /* charts were drawn with the old colours */
  });
  if (window.matchMedia) {
    var system = window.matchMedia("(prefers-color-scheme: dark)");
    var onSystem = function () { if (!document.documentElement.getAttribute("data-theme")) { showThemeButton(themeBtn); if (recolor) recolor(); } };
    if (system.addEventListener) system.addEventListener("change", onSystem); else if (system.addListener) system.addListener(onSystem);
  }
}

/* Fonts and maths change line heights after the browser has jumped to an #anchor
   (problem.html#eq-6); on a fresh visit, put the target back at the top of the window. */
window.addEventListener("load", function () {
  var nav = window.performance && performance.getEntriesByType ? performance.getEntriesByType("navigation")[0] : null;
  if (nav && nav.type !== "navigate") return;
  var id = decodeURIComponent(location.hash.slice(1)), target = id && document.getElementById(id);
  if (!target) return;
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () {
    var root = document.documentElement, behaviour = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    target.scrollIntoView();
    root.style.scrollBehavior = behaviour;
  });
});
})();
