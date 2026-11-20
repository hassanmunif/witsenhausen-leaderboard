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
/* The same text without LaTeX, for tooltips and screen readers: \sigma becomes σ, \sqrt{2} becomes √(2). */
var SYMBOLS = { sigma: "σ", gamma: "γ", kappa: "κ", lambda: "λ", mu: "μ", pi: "π", Phi: "Φ", varepsilon: "ε", epsilon: "ε",
  pm: "±", times: "×", cdot: "·", to: "→", approx: "≈", le: "≤", leq: "≤", ge: "≥", geq: "≥", infty: "∞" };
function plain(str) {
  return String(str).replace(/\$/g, "").replace(/\\[,;!: ]/g, " ")
    .replace(/\\sqrt\{([^}]*)\}/g, "√($1)").replace(/\\hat\{([^}]*)\}/g, "$1̂")
    .replace(/\\(?:mathrm|operatorname|text|mathbb)\{([^}]*)\}/g, "$1")
    .replace(/\\([a-zA-Z]+)/g, function (m, w) { return SYMBOLS.hasOwnProperty(w) ? SYMBOLS[w] : w; })
    .replace(/[{}]/g, "").replace(/\s+/g, " ");
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
/* Verified costs: twelve decimals, so rounding stays below the evaluator's error estimate (about 1e-11). */
function fmtCost(c) { return c.toFixed(12); }
/* On the leaderboard: nine decimals at most, so a column of costs is easy to compare (the record rule cannot
   tell apart costs closer than 1e-9). The full value is in each cell's tooltip and in Details. */
function shortCost(c) { return c.toFixed(9); }
function shortPrinted(str) { var m = /\.(\d+)$/.exec(str); return m && m[1].length > 9 ? Number(str).toFixed(9) : str; }
/* An error estimate as plain text, for a tooltip: 3·10⁻¹¹. */
function errPlain(e) {
  var p = (e < 1e-15 ? 1e-15 : e).toExponential(0).split("e"), sup = "⁰¹²³⁴⁵⁶⁷⁸⁹";
  return p[0] + "·10" + String(+p[1]).replace("-", "⁻").replace(/\d/g, function (d) { return sup.charAt(+d); });
}
/* Four significant digits, rounded down: a lower bound is never shown higher than its computed value. */
function fmtBound(v) {
  if (!(v > 0) || !isFinite(v)) return String(v);
  var e = Math.floor(Math.log10(v)) - 3, scale = Math.pow(10, e);
  return (Math.floor(v / scale + 1e-9) * scale).toFixed(Math.max(0, -e));
}
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
/* Claims that still stand: no verified submission reproduces them and none is disputed. */
function openClaims(id) {
  return D.literature.filter(function (r) { return r.setting === id && !r.verified_by && !r.disputed; });
}
function bestClaim(id) {
  return openClaims(id).sort(function (a, b) { return a.reported_cost - b.reported_cost; })[0];
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
  var bestRep = bestClaim(D.benchmark);

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
  mark(rec.result.cost, cssVar("--s2"), "best verified cost " + shortCost(rec.result.cost), 1, "start");
  mark(lin.result.cost, ink2, "best linear " + lin.result.cost.toFixed(2), 0, "end");
  box.append(svg);
  clear("gapcap").append(mt("Its width, $" + (rec.result.cost - lb.best_value).toFixed(4) + "$, measures how far the problem is from solved. The best verified cost is $" +
    (rec.result.cost / lb.best_value).toFixed(2) + "$ times the strongest proven bound tracked here."));

  var claims = clear("claims");
  function claim(color, strong) {
    var key = h("span", { class: "key" }); key.style.background = color;
    var body = h("span", null, h("strong", { text: strong }), " ");
    for (var i = 2; i < arguments.length; i++) add(body, arguments[i]);
    claims.append(h("li", null, key, body));
  }
  claim(cssVar("--s2"), shortCost(rec.result.cost),
    rich(["is the best verified cost, from the ", { href: "leaderboard.html", text: rec.short_name || "record entry" }, " (" + rec.date.slice(0, 4)]),
    rec.ai_assistance ? [", ", h("span", { class: "ai-note", title: "AI-assisted: " + plain(rec.ai_assistance), text: "AI-assisted" })] : null, "), ",
    h("span", { class: "sub" }, tex(errTex(rec.result.error_estimate)), "."));
  /* a claim is shown here only while it beats the verified record; otherwise the table below lists it */
  if (bestRep && bestRep.reported_cost < rec.result.cost) claim(cssVar("--s1"), fmtReported(bestRep),
    rich(["is the best claimed cost, by ", { href: "leaderboard.html", text: andJoin(bestRep.authors) + " (" + bestRep.year + ")" }, ". It has not been verified here yet."]));
  var eq = lb.bounds[lb.best].equation, bname = lb.bounds[lb.best].label.split(",")[0];
  claim(ink, fmtBound(lb.best_value),
    rich(["is the strongest proven lower bound tracked here, the ", { href: "problem.html#eq-" + eq, text: bname + " bound (" + eq + ")" }, "."]));

  controllerPlot(clear("hero-plot"), rec, st.sigma, { height: 370 });
  var hc = clear("hero-cap");
  var lv = (rec.steps.steps || []).filter(function (x) { return x.level > 1e-6; }).slice(0, 2).map(function (x) { return "\\pm" + x.level.toFixed(2); });
  hc.append(h("b", { text: "The record controller at the benchmark." }), mt(" Each step sends a band of initial states to one level" +
    (lv.length ? " ($0, " + lv.join(", ") + ", \\dots$)" : "") +
    ", spaced widely enough to be told apart through unit noise; the slight slope within a step trades a little separation for less control effort. Thin line: $x_1 = x_0$, no control."));
}

/* home: the top of the benchmark leaderboard, ranked exactly as on the leaderboard page, without details */
function renderTop(n) {
  var st = setting(D.benchmark), tb = clear("top-rows");
  var claims = D.literature.filter(function (r) { return r.setting === st.id && !r.verified_by && !r.disputed; });
  var all = ranked(st.entries.map(function (e) { return { cost: e.result.cost, e: e }; })
    .concat(claims.map(function (p) { return { cost: p.reported_cost, p: p }; })), st);
  all.slice(0, n).forEach(function (x) {
    var e = x.e, p = x.p;
    tb.append(h("tr", null,
      h("td", { class: "num", text: String(x.rank) }),
      e ? valueCell(shortCost(e.result.cost), "J(f) = " + fmtCost(e.result.cost) + " ± " + errPlain(e.result.error_estimate))
        : valueCell(shortPrinted(fmtReported(p)), "As printed: " + fmtReported(p)),
      h("td", { class: "evid" }, evidenceTag(e ? "Numerically verified" : "Claimed"),
        e && e.id === st.record_id ? [" ", tagLabel("record", "record", "Record: the first verified entry to reach this cost, under the record rule on the Verification page")] : null),
      h("td", { class: "ctrl", title: plain(e ? e.name : p.method), math: shortLabel(e ? e.name : p.method) }),
      h("td", null, shortAuthors(e ? e.authors || [] : p.authors), aiTag(e ? e.ai_assistance : p.ai_assistance)),
      h("td", { class: "nowrap", text: e ? shownDate(e) : String(p.year) })));
  });
  alignValues(tb);
}

/* ---------- leaderboard: controllers ranked by cost and lower bounds ranked by value, each with an evidence level.
   The address keeps the setting: leaderboard.html#k0.50_s5. ---------- */
var current = null;
/* A paper's cost exactly as printed, without digits the paper did not give. */
function fmtReported(r) { return r.reported_as || String(r.reported_cost); }
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
  ["show-claimed", "show-verified", "show-disputed"].forEach(function (id) { document.getElementById(id).addEventListener("change", renderBoard); });
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
/* An evidence level opens the evidence behind the entry: the controller file of a verified cost, the paper of
   a claimed cost or of a lower bound. Its tooltip says what the level means. */
var EVIDENCE = {
  "Numerically verified": { cls: "numerical", tip: "Numerically verified: recomputed here from this controller file" },
  "Claimed": { cls: "claimed", tip: "Claimed: printed in this paper, not checked here" },
  "Peer-reviewed": { cls: "peer", tip: "Peer-reviewed: the proof is published; the value is computed here and rounded down" }
};
function evidenceTag(level, href) {
  var ev = EVIDENCE[level] || { cls: "", tip: level };
  return h(href ? "a" : "span", { class: "ev " + ev.cls, href: href || null, rel: href ? "noopener" : null, title: ev.tip, text: level });
}
function tagLabel(text, cls, title, href) {
  return h(href ? "a" : "span", { class: "tag" + (cls ? " " + cls : ""), href: href || null, rel: href ? "noopener" : null, title: title, text: text });
}
/* An entry whose authors say an AI model helped ("ai_assistance" in its file, or in data/literature.json for a
   paper) is tagged after the names; the tooltip and the details say which model and what it did. */
function aiTag(text) { return text ? [" ", tagLabel("AI-assisted", "ai", "AI-assisted: " + plain(text))] : null; }
/* A name links to a page about the person when data/site.json lists one under "people", and otherwise to the
   paper or code the entry comes from. */
function authorLink(names, url) {
  var list = Array.isArray(names) ? names : String(names).split(", "), people = D.site.people || {};
  var href = (list.length === 1 && safeHref(people[list[0]])) || safeHref(url);
  return href ? h("a", { href: href, rel: "noopener", text: shortAuthors(list) }) : shortAuthors(list);
}
/* The table shows a name up to its first comma, bracket or formula; the full name is in the tooltip and in Details. */
function shortLabel(str) {
  var full = String(str), cut = full.search(/,\s| \(| \$/), out = cut > 0 ? full.slice(0, cut) : full;
  return out.split("$").length % 2 ? out : full;
}
/* A value cell. The integer part sits in a box as wide as the widest in its column (see alignValues), so the
   decimal points line up in a left-aligned column: the digits of Latin Modern all have the same width. */
function valueCell(text, title) {
  var i = text.indexOf(".");
  return h("td", { class: "val", title: title || null },
    h("span", { class: "cost" }, h("span", { class: "ip", text: i < 0 ? text : text.slice(0, i) }), i < 0 ? null : h("span", { text: text.slice(i) })));
}
function alignValues(tbody) {
  var w = 1;
  tbody.querySelectorAll(".ip").forEach(function (e) { w = Math.max(w, e.textContent.length); });
  tbody.style.setProperty("--ip", w + "ch");
}
function intervalTex(lo, hi) {
  return (lo === null ? "(-\\infty" : "[" + lo.toFixed(2)) + ",\\ " + (hi === null ? "\\infty" : hi.toFixed(2)) + ")";
}
/* At most 12 steps are listed: for an odd f the steps reaching x0 > 0, and if there are more than 12,
   the 12 most probable, in order of x0. The caption says how many there are. */
function stepsTable(e) {
  var sp = e.steps;
  if (!sp || !sp.steps.length) return null;
  var rows = sp.steps;
  if (sp.odd) rows = rows.filter(function (x) { return x.hi === null || x.hi > 1e-9; });
  if (!rows.length) return null;
  var total = sp.odd ? Math.ceil(sp.n_steps / 2) : sp.n_steps;
  if (rows.length > 12) {
    var cut = rows.map(function (x) { return x.prob; }).sort(function (a, b) { return b - a; })[11];
    rows = rows.filter(function (x) { return x.prob >= cut; }).slice(0, 12);
  }
  var count = rows.length < total ? " The " + rows.length + " most probable of these " + total + " are listed." : "";
  var tb = h("tbody");
  rows.forEach(function (x) {
    tb.append(h("tr", null, h("td", null, tex(intervalTex(x.lo, x.hi))), h("td", { text: x.prob.toFixed(6) }), h("td", { text: num(Math.abs(x.level) < 5e-7 ? 0 : x.level, 4) })));
  });
  return h("div", null,
    h("p", { class: "cap above", math: "Steps of $f$, the maximal intervals without a jump" + (sp.odd ? ". $f$ is odd, so only steps reaching $x_0 > 0$ are listed." : ".") + count }),
    h("table", { class: "mini" }, h("thead", null, h("tr", null, h("th", { math: "$x_0 \\in$" }), h("th", { text: "probability" }), h("th", { math: "$\\mathbb{E}[x_1 \\mid \\text{step}]$" }))), tb));
}
/* A click anywhere on a row opens its details in a row underneath, and a second click closes them. Clicks on
   a link, or while selecting text, are left alone. The arrow at the end of the row is a button, so the
   details can also be opened from the keyboard. */
function withDetails(row, label, build) {
  var open = null;
  var btn = h("button", { class: "rowtoggle", type: "button", "aria-expanded": "false", "aria-label": "Details: " + plain(label), title: "Details" },
    s("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" }, s("path", { d: "M4 6l4 4 4-4" })));
  function toggle() {
    if (open) { open.remove(); open = null; btn.setAttribute("aria-expanded", "false"); row.classList.remove("open"); return; }
    btn.setAttribute("aria-expanded", "true");
    row.classList.add("open");
    var parts = build();
    open = h("tr", { class: "detail" }, h("td", { colspan: row.children.length }, parts.node));
    row.after(open);
    if (parts.after) parts.after();
  }
  btn.addEventListener("click", toggle);
  row.addEventListener("click", function (ev) {
    if (ev.target.closest("a, button") || String(window.getSelection ? window.getSelection() : "")) return;
    toggle();
  });
  row.classList.add("expandable");
  row.append(h("td", { class: "go" }, btn));
  return row;
}
/* A controller taken from a paper (it has a verified_on date) is dated by the paper's year, like a claim;
   a new result by its full date. */
function shownDate(e) { return e.verified_on ? e.date.slice(0, 4) : e.date; }
function verifiedRow(e, rank, st, paper) {
  var r = e.result, label = shortLabel(e.name);
  var row = h("tr", { class: "verified" },
    h("td", { class: "num", text: String(rank) }),
    valueCell(shortCost(r.cost), "J(f) = " + fmtCost(r.cost) + " ± " + errPlain(r.error_estimate)),
    h("td", { class: "evid" }, evidenceTag("Numerically verified", repoHref(e.file) || e.file),
      e.id === st.record_id ? [" ", tagLabel("record", "record", "Record: the first verified entry to reach this cost, under the record rule on the Verification page")] : null),
    h("td", { class: "ctrl", title: plain(e.name), math: label }),
    h("td", null, authorLink(e.authors || [], e.source && e.source.url), aiTag(e.ai_assistance)),
    h("td", { class: "nowrap", text: shownDate(e) }));
  return withDetails(row, label, function () {
    var c1 = h("div", { class: "chartbox" }), c2 = h("div", { class: "chartbox" });
    var kv = h("dl", { class: "kv" },
      h("dt", { text: "Controller" }), h("dd", { math: e.name }),
      e.method ? [h("dt", { text: "Method" }), h("dd", { math: e.method })] : null,
      h("dt", { text: "Authors" }), h("dd", { text: (e.authors || []).join(", ") }),
      e.ai_assistance ? [h("dt", { text: "AI assistance" }), h("dd", { math: e.ai_assistance })] : null,
      e.ported_by ? [h("dt", { text: "Controller file by" }), h("dd", { text: e.ported_by })] : null,
      e.verified_on ? [h("dt", { text: "Verified here" }), h("dd", { text: e.verified_on })] : null,
      paper ? [h("dt", { text: "Paper" }), h("dd", null, linkOrText(paper.title, paper.url), ". " + paper.venue + "."),
        h("dt", { text: "Cost as printed" }), h("dd", { text: fmtReported(paper) }),
        paper.notes ? [h("dt", { text: "On the printed cost" }), h("dd", { math: paper.notes })] : null] : null,
      h("dt", null, "Cost ", tex("J(f)")), h("dd", { text: fmtCost(r.cost) }),
      h("dt", { text: "Error estimate" }), h("dd", null, tex(errTex(r.error_estimate))),
      h("dt", null, "First-stage cost ", tex("k^2\\,\\mathbb{E}[u_1^2]")), h("dd", { text: r.stage1.toFixed(9) }),
      h("dt", null, "Estimation error ", tex("\\mathbb{E}[x_2^2]")), h("dd", { text: r.mmse.toFixed(9) }),
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
  var label = shortLabel(p.method), printed = fmtReported(p);
  var row = h("tr", { class: p.disputed ? "claimed disputed" : "claimed" },
    h("td", { class: "num", text: String(rank) }),
    valueCell(shortPrinted(printed), "As printed: " + printed),
    h("td", { class: "evid" }, evidenceTag("Claimed", safeHref(p.url)),
      p.disputed ? [" ", tagLabel("disputed", null, "Disputed: there is evidence that the printed cost is not the cost of the paper’s controller", safeHref(p.disputed.note))] : null),
    h("td", { class: "ctrl", title: plain(p.method), math: label }),
    h("td", null, authorLink(p.authors, p.url), aiTag(p.ai_assistance)),
    h("td", { class: "nowrap", text: String(p.year) }));
  return withDetails(row, label, function () {
    return { node: h("dl", { class: "kv" },
      h("dt", { text: "Method" }), h("dd", { math: p.method }),
      h("dt", { text: "Authors" }), h("dd", { text: p.authors }),
      p.ai_assistance ? [h("dt", { text: "AI assistance" }), h("dd", { math: p.ai_assistance })] : null,
      h("dt", { text: "Paper" }), h("dd", null, linkOrText(p.title, p.url), ". " + p.venue + "."),
      h("dt", { text: "Shape of the controller" }), h("dd", { math: p.structure }),
      h("dt", { text: "Cost as printed" }), h("dd", { text: p.reported_as }),
      p.disputed ? [h("dt", { text: "Disputed" }), h("dd", null, mt(p.disputed.reason), " (" + p.disputed.date + ")"),
        p.disputed.note ? [h("dt", { text: "Note and scripts" }), h("dd", null, linkOrText(p.disputed.note, p.disputed.note))] : null] : null,
      p.notes ? [h("dt", { text: "Notes" }), h("dd", { math: p.notes })] : null) };
  });
}
/* Rows in rank order, each with its rank label. Verified costs that the record rule cannot tell apart
   (within its tolerance plus both error estimates) share a rank, shown as "=1", and so do equal claimed
   costs. In a tie the record holder comes first, then the earlier entry. scripts/score_all.py ranks the
   verified entries the same way. renderBoard ranks every verified entry and every claim that is not
   disputed, before the tick boxes hide any, so hiding an evidence level never changes a rank. */
function ranked(rows, st) {
  var tol = D.record_rule.tolerance;
  function tied(a, b) {
    if (a.e && b.e) return Math.abs(a.cost - b.cost) <= tol + a.e.result.error_estimate + b.e.result.error_estimate;
    return !a.e && !b.e && a.cost === b.cost;
  }
  function first(x) { return x.e && x.e.id === st.record_id ? 0 : 1; }
  function when(x) { return x.e ? x.e.date : String(x.p.year); }
  var groups = [];
  rows.slice().sort(function (a, b) { return (a.cost - b.cost) || ((a.e ? 0 : 1) - (b.e ? 0 : 1)); }).forEach(function (x) {
    var g = groups.filter(function (g) { return tied(g[0], x); })[0];
    if (g) g.push(x); else groups.push([x]);
  });
  var out = [];
  groups.forEach(function (g) {
    g.sort(function (a, b) { return (first(a) - first(b)) || (when(a) < when(b) ? -1 : when(a) > when(b) ? 1 : 0) || (a.cost - b.cost); });
    var label = (g.length > 1 ? "=" : "") + (out.length + 1);
    g.forEach(function (x) { x.rank = label; out.push(x); });
  });
  return out;
}
function renderBoard() {
  var st = setting(current), rec = recordOf(st), lbs = st.lower_bounds;
  var papers = D.literature.filter(function (r) { return r.setting === st.id; });
  var claims = papers.filter(function (r) { return !r.verified_by && !r.disputed; });
  var disputed = papers.filter(function (r) { return !r.verified_by && r.disputed; });
  var paperOf = {};
  papers.forEach(function (r) { if (r.verified_by) paperOf[r.verified_by] = r; });
  var best = bestClaim(st.id);
  /* a setting can have no verified entry yet (tests/test_data.py keeps the published ones from it) */
  add(clear("scorebar"), [
    h("span", { title: rec ? "J(f) = " + fmtCost(rec.result.cost) + " ± " + errPlain(rec.result.error_estimate) : null },
      "Best verified ", h("b", { text: rec ? shortCost(rec.result.cost) : "none yet" })),
    best ? h("span", { title: "As printed: " + fmtReported(best) }, "Best claimed ", h("b", { text: shortPrinted(fmtReported(best)) })) : null,
    h("span", null, "Best lower bound ", h("b", { text: fmtBound(lbs.best_value) })),
    /* the gap: how many times the best verified cost exceeds the best lower bound (as on the home page) */
    rec ? h("span", { title: "The best verified cost is " + (rec.result.cost / lbs.best_value).toFixed(2) + " times the best lower bound; they differ by " + (rec.result.cost - lbs.best_value).toFixed(4) },
      "Gap ", h("b", { text: (rec.result.cost / lbs.best_value).toFixed(2) + "×" })) : null]);

  /* Disputed claims are hidden unless their box is ticked; the box says how many there are. */
  document.getElementById("n-disputed").textContent = String(disputed.length);
  document.getElementById("disputed-toggle").hidden = !disputed.length;
  var showClaimed = document.getElementById("show-claimed").checked, showVerified = document.getElementById("show-verified").checked;
  var showDisputed = document.getElementById("show-disputed").checked;
  var all = ranked(st.entries.map(function (e) { return { cost: e.result.cost, e: e }; })
    .concat(claims.map(function (p) { return { cost: p.reported_cost, p: p }; })), st);
  /* A disputed claim is not ranked: it sits where its printed cost would put it, with a dash for its rank. */
  disputed.forEach(function (p) {
    var i = 0;
    while (i < all.length && all[i].cost <= p.reported_cost) i++;
    all.splice(i, 0, { cost: p.reported_cost, p: p, rank: "–" });
  });
  var rows = all.filter(function (x) { return x.e ? showVerified : x.p.disputed ? showDisputed : showClaimed; });
  var tb = clear("board-rows");
  if (!rows.length) tb.append(h("tr", null, h("td", { colspan: 7, class: "empty", text: "Tick an evidence level to show entries." })));
  rows.forEach(function (x) { tb.append(x.e ? verifiedRow(x.e, x.rank, st, paperOf[x.e.id]) : claimedRow(x.p, x.rank)); });
  alignValues(tb);

  var lb = clear("bound-rows"), bs = lbs.bounds;
  Object.keys(bs).sort(function (a, b) { return bs[b].value - bs[a].value; }).forEach(function (k, i) {
    var b = bs[k];
    lb.append(h("tr", null,
      h("td", { class: "num", text: String(i + 1) }),
      valueCell(fmtBound(b.value_rounded_down), "Rounded down from " + b.value.toPrecision(10)),
      h("td", null, evidenceTag(b.evidence, safeHref(b.source))),
      h("td", null, b.label + " ", h("a", { href: "problem.html#eq-" + b.equation, text: "(" + b.equation + ")" })),
      h("td", null, linkOrText(shortAuthors(b.authors), b.source)),
      h("td", { text: String(b.year) })));
  });
  alignValues(lb);
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
  /* reference lines, such as the strongest proven lower bound: dashed, labelled at the right */
  (o.refs || []).forEach(function (r) {
    if (!(r.y >= o.y[0] && r.y <= o.y[1])) return;
    svg.append(s("line", { class: "refline", x1: m.l, x2: m.l + iw, y1: Y(r.y), y2: Y(r.y) }));
    svg.append(s("text", { class: "lbl", x: m.l + iw - 4, y: Y(r.y) - 6, "text-anchor": "end", text: r.label }));
  });
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
    var color = p.kind === "verified" ? cssVar("--s2") : cssVar("--s1"), ring = p.kind === "disputed";
    var kind = { reported: "claimed", disputed: "claimed, disputed", verified: "numerically verified" }[p.kind];
    var pos = W >= 420 ? o.label(p) : null;
    if (pos) {
      var right = pos.charAt(1) === "r", above = pos.charAt(0) === "a";
      svg.append(s("text", { class: "lbl", x: X(p.x) + (right ? 11 : -11), y: Y(p.y) + (above ? -8 : 18), "text-anchor": right ? "start" : "end", text: p.short }));
    }
    var g = s("g", { class: "pt", tabindex: 0, "aria-label": plain(p.label) + ", " + p.year + ": " + p.value + " (" + kind + ")" });
    g.append(s("circle", { class: "hit", cx: X(p.x), cy: Y(p.y), r: 12 }));
    g.append(s("circle", { class: ring ? "dot ring" : "dot", cx: X(p.x), cy: Y(p.y), r: 4.5, fill: ring ? cssVar("--page") : color }));
    function show() {
      tip.textContent = "";
      var row = h("div", { class: "row" }); var k = h("i"); k.style.background = color;
      row.append(k, h("span", { class: "v", text: p.value }), h("span", { class: "l", text: kind }));
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
    refs: [{ y: st.lower_bounds.best_value, label: "proven lower bound " + fmtBound(st.lower_bounds.best_value) }],
    label: function (p) { return p.kind === "reported" && p.year === 1968 ? "ar" : null; } });
  var place = { "mehmetoglu-2014": "bl", "tseng-tang-2017": "br" };
  historyChart(clear("hist-zoom"), HIST, { x: [2000, yNow + 2], y: [0.16685, 0.16740], xTicks: [2000, 2005, 2010, 2015, 2020, 2025],
    aria: "Benchmark costs since 2001 between 0.16685 and 0.16740",
    label: function (p) { return p.kind !== "verified" ? (place[p.id] || "ar") : (p.id === st.record_id ? "al" : null); } });
}
function renderHistory() {
  var st = setting(D.benchmark);
  D.literature.filter(function (r) { return r.setting === D.benchmark; }).forEach(function (r) {
    /* a disputed claim is drawn as a ring at its printed cost, and the line of best claimed costs skips it */
    HIST.push({ kind: r.disputed ? "disputed" : "reported", id: r.id, x: r.year, y: r.reported_cost, year: r.year, value: fmtReported(r),
      label: r.authors, short: (r.short || r.authors) + (r.disputed ? ", disputed" : ""), note: r.disputed ? r.disputed.reason : r.method });
  });
  /* a verified dot sits at the year of the result it recomputes, just right of the paper's own claim */
  st.entries.forEach(function (e) {
    var yr = +e.date.slice(0, 4);
    HIST.push({ kind: "verified", id: e.id, x: yr + 0.25, y: e.result.cost, year: yr, value: fmtCost(e.result.cost), label: e.name, short: e.short_name || "verified here",
      note: (e.authors || []).join(", ") + (e.ai_assistance ? ", AI-assisted" : "") + (e.verified_on ? "; verified here on " + e.verified_on.replace(/-/g, "\u2011") : "") });
  });
  var lg = clear("hist-legend");
  var keys = [["--s1", "Claimed"], ["--s2", "Numerically verified"]];
  if (HIST.some(function (p) { return p.kind === "disputed"; })) keys.splice(1, 0, ["ring", "Claimed, disputed"]);
  keys.forEach(function (x) {
    var k = h("span", { class: x[0] === "ring" ? "key ring" : "key" });
    if (x[0] !== "ring") k.style.background = "var(" + x[0] + ")";
    lg.append(h("span", null, k, x[1]));
  });
  renderHistoryCharts();
}

/* ---------- theory and contribute ---------- */
/* "used here as (7)" in a claim refers to an equation on the problem page: the number becomes a link */
function claimParts(text) {
  var parts = [], re = /(used here as (?:bound )?)\((\d{1,2})\)/g, last = 0, m;
  while ((m = re.exec(text))) {
    parts.push(text.slice(last, m.index + m[1].length), { href: "problem.html#eq-" + m[2], text: "(" + m[2] + ")" });
    last = m.index + m[0].length;
  }
  parts.push(text.slice(last));
  return parts;
}
function renderTheory() {
  var ul = clear("theorylist");
  D.theory.forEach(function (t) {
    ul.append(h("li", null,
      h("span", { text: String(t.year) }),
      h("div", null, h("div", null, rich(claimParts(t.claim))),
        h("div", { class: "cite" }, t.authors + ", ", linkOrText(t.title, t.url), (/[.?!]$/.test(t.title) ? " " : ". ") + t.venue + ".")),
      h("div", { class: "kind" }, h("div", { text: t.kind }), h("span", { class: "ev " + (t.evidence === "Peer-reviewed" ? "peer" : "preprint"), text: t.evidence }))));
  });
}
function renderContribute() {
  document.getElementById("example").textContent = D.example;
  var promptBox = document.getElementById("prompt"), btn = document.getElementById("copy-prompt");
  if (promptBox && btn && D.agent_prompt) {  /* shown only when data/site.json has "show_agent_prompt": true */
    promptBox.textContent = D.agent_prompt;
    btn.addEventListener("click", function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(D.agent_prompt).then(function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy prompt"; }, 1600); });
    });
  }
  var st = setting(D.benchmark), rec = recordOf(st), bestRep = bestClaim(D.benchmark);
  var first = ["A verified cost below the benchmark record, $" + shortCost(rec.result.cost) + "$, by the margin of the ", { href: "verification.html#record-rule", text: "record rule" }, "."];
  if (bestRep && bestRep.reported_cost < rec.result.cost) first.push(" In particular, a controller file that reproduces the $" + fmtReported(bestRep) + "$ claimed by " +
    andJoin(bestRep.authors) + " would settle whether that value or the verified record is the better one.");
  var ul = clear("targets");
  [
    first,
    ["A proven lower bound above $" + fmtBound(st.lower_bounds.best_value) + "$ at the benchmark. Bounds are added by pull request to ", h("code", { text: "witsenhausen/bounds.py" }), ", with a reference or a proof."],
    ["A controller file that reproduces one of the ", { href: "leaderboard.html", text: "claimed costs on the leaderboard" }, ", or a check showing that a printed cost is wrong, which marks the claim as disputed."],
    ["A new result about the optimum for the ", { href: "theory.html", text: "theory log" }, ", or a correction to an entry."]
  ].forEach(function (parts) { ul.append(h("li", null, rich(parts))); });
}

/* ---------- start ---------- */
var redraw = null, recolor = null;  /* redraw: after a resize; recolor: after the theme changes */
if (D) {
  if (PAGE === "index") { renderHero(); renderTop(5); redraw = recolor = renderHero; }
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
/* ---------- light and dark: the button in the top bar. The site starts light; a reader's choice is kept in
   localStorage ("wl-theme") and applied by the <head> before the page is drawn. ---------- */
function themeNow() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
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
}

/* An address that points inside a closed <details> (verification.html#eq-12, where the formulas are folded
   away) opens it, so the target can be shown. */
function openFolded() {
  var id = decodeURIComponent(location.hash.slice(1)), target = id && document.getElementById(id);
  var box = target && target.closest ? target.closest("details") : null;
  if (box && !box.open) { box.open = true; target.scrollIntoView(); }
}
openFolded();
window.addEventListener("hashchange", openFolded);

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
