/* Bench results viewer: runs list, run detail, compare two runs, trends over time. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const esc = Charts.esc, P = Charts.PALETTE;
  const view = $("#view");
  const num = (v, d = 1) => v == null ? "–" : (+v).toFixed(d);
  const cap = s => s[0].toUpperCase() + s.slice(1);

  async function api(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(path + ": " + r.status + " " + (await r.text()).slice(0, 200));
    return r.json();
  }
  const runCache = {};
  async function getRun(id) {
    if (runCache[id]) return runCache[id];
    const d = await api("/api/runs/" + encodeURIComponent(id));
    if ((d.run.status || "complete") === "complete") runCache[id] = d;
    return d;
  }
  const when = s => s ? s.replace("T", " ").slice(0, 16) : "–";

  /* -- metrics ---------------------------------------------------------------- */
  function metricInfo(key) {
    let m;
    const fixed = {
      "response.bw3_mhz": {label: "−3 dB bandwidth", unit: "MHz"}, "response.lowpass_cutoff_mhz": {label: "Low-pass cutoff (−3 dB)", unit: "MHz"}, "response.centre_mhz": {label: "Passband centre", unit: "MHz"},
      "response.passband_dbm": {label: "Passband level (at the analyser)", unit: "dBm"}, "response.ripple_db": {label: "Passband ripple", unit: "dB", better: "lower"},
      "response.reject_low_db": {label: "Rejection below the passband", unit: "dB", better: "higher"},
      "response.reject_high_db": {label: "Rejection above the passband", unit: "dB", better: "higher"}};
    if (fixed[key]) return fixed[key];
    if ((m = key.match(/^spur_map\.(\d+)mA\.(worst|median|best)_dbc$/))) return {label: cap(m[2]) + " close-in spur across the band, " + m[1] + " mA", unit: "dBc", better: "lower"};
    if ((m = key.match(/^wide\.(\d+)mA\.worst_oob_dbc$/))) return {label: "Strongest out-of-band signal, " + m[1] + " mA", unit: "dBc", better: "lower"};
    if ((m = key.match(/^drive\.(\d+)mA\.wanted_dbm$/))) return {label: "Wanted level, " + m[1] + " mA (at the analyser)", unit: "dBm"};
    return {label: key, unit: ""};
  }
  const HEADLINE = ["response.bw3_mhz", "spur_map.8mA.worst_dbc", "wide.8mA.worst_oob_dbc"];

  /* -- shared pieces ------------------------------------------------------------ */
  function chainHtml(setup) {
    const parts = ["Si5351 " + setup.output].concat(setup.chain.map(c => {
      if (c.kind === "attenuator" || c.kind === "cable") return `${c.name || c.kind} ${c.db ?? c.loss_db ?? ""} dB`;
      return (c.name || c.kind) + (c.part ? (c.part === "unknown" ? " (part unknown)" : " (" + c.part + ")") : "");
    }), "analyser");
    return `<div class="chain">${parts.map(p => `<span class="node">${esc(p)}</span>`).join('<span class="arrow">→</span>')}</div>`;
  }
  function badges(h) {
    const st = h.status || "complete";
    return (st !== "complete" ? `<span class="badge ${esc(st)}">${esc(st)}</span> ` : "") + (h.legacy ? '<span class="badge imported">imported</span>' : "");
  }
  const card = (title, inner = "") => { const d = document.createElement("div"); d.className = "card"; d.innerHTML = (title ? `<h2 style="margin-top:0">${esc(title)}</h2>` : "") + inner; return d; };
  const table = (head, rows) => `<table><thead><tr>${head.map(h => `<th class="${h.num ? "num" : ""}">${esc(h.t ?? h)}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => `<td class="${head[i].num ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;

  function conditionsCard(d, title = "Test conditions") {
    const r = d.run, e = r.environment || {}, g = e.git || {}, pico = e.pico || {}, an = e.analyser || {};
    const notes = r.setup.chain.filter(c => c.notes).map(c => `<li><b>${esc(c.name || c.kind)}</b>: ${esc(c.notes)}</li>`).join("");
    return card(title, `${chainHtml(r.setup)}
      ${r.setup.description ? `<p class="muted">${esc(r.setup.description)}</p>` : ""}${notes ? `<ul>${notes}</ul>` : ""}
      ${r.note ? `<p><b>Note:</b> ${esc(r.note)}</p>` : ""}${r.error ? `<p class="bad"><b>Error:</b> ${esc(r.error)}</p>` : ""}
      <dl class="kv"><dt>Started</dt><dd>${esc(when(r.started))}${r.finished ? " – " + esc(when(r.finished)) : ""}</dd>
      <dt>Loss added back (pad)</dt><dd>${num(r.pad_db)} dB</dd>
      <dt>Analyser</dt><dd>${esc(an.model || "?")} ${esc(an.firmware || "")} ${an.hardware ? "· HW " + esc(an.hardware) : ""}${an.attenuation_db != null ? " · attenuation " + an.attenuation_db + " dB" : ""}</dd>
      <dt>Firmware</dt><dd>${esc(g.commit || "?")}${g.dirty ? " (uncommitted changes)" : ""}${pico.micropython ? " · MicroPython " + esc(pico.micropython) : ""}${pico.correction_ppb != null ? " · crystal correction " + pico.correction_ppb + " ppb" : ""}</dd>
      ${e.drift_db != null ? `<dt>Drift during run</dt><dd class="${Math.abs(e.drift_db) > 1 ? "bad" : ""}">${num(e.drift_db, 2)} dB between a reference level at the start and the end</dd>` : ""}</dl>`);
  }

  /* -- per-test renderers ---------------------------------------------------------- */
  const R = {};

  R.response = (box, run, M) => {
    const t = run.tests.response, d = t.data, wk = String(t.params.wanted_order), m = M.response || {};
    box.innerHTML = `<div class="bar"><label><input type="checkbox" id="pad"> add back the ${num(run.pad_db)} dB pad (level leaving the filter)</label></div><div class="chart" id="c"></div><div id="m"></div>`;
    const draw = () => {
      const off = $("#pad", box).checked ? run.pad_db : 0;
      const series = Object.keys(d.orders).map((k, i) => ({name: k === wk ? `wanted (${k}× carrier)` : `${k}× carrier`, width: k === wk ? 2.4 : 1.3, color: k === wk ? P[0] : P[1 + i % 6],
        pts: d.fo_mhz.map((f, j) => [f, d.orders[k].dbm[j] == null ? null : d.orders[k].dbm[j] + off])}));
      Charts.lineChart($("#c", box), {series, xlabel: "wanted output frequency (MHz)", ylabel: "level (dBm)", height: 360,
        vlines: [{x: m.edge_lo_3, label: "−3 dB"}, {x: m.edge_hi_3, label: "−3 dB"}]});
    };
    $("#pad", box).onchange = draw; draw();
    const rows = [3, 10, 20, 30, 40].map(x => [`−${x} dB`, num(m["edge_lo_" + x], 2), num(m["edge_hi_" + x], 2), m["edge_lo_" + x] != null && m["edge_hi_" + x] != null ? num(m["edge_hi_" + x] - m["edge_lo_" + x], 2) : "–"]);
    const oth = Object.entries(m.other_orders || {}).map(([k, v]) => [`${k}× carrier`, num(v.median_dbm), num(v.max_dbm), num(v.worst_dbc_in_passband)]);
    $("#m", box).innerHTML = `<div class="grid2"><div>${table(["Below passband", {t: "Lower edge MHz", num: 1}, {t: "Upper edge MHz", num: 1}, {t: "Width MHz", num: 1}], rows)}
      <p class="muted">${m.lowpass_cutoff_mhz != null ? `Low-pass: −3 dB at ${num(m.lowpass_cutoff_mhz, 2)} MHz · ` : ""}Passband level ${num(m.passband_dbm, 2)} dBm · ripple ${num(m.ripple_db, 2)} dB · centre ${num(m.centre_mhz, 2)} MHz · rejection ${num(m.reject_low_db)} dB below / ${num(m.reject_high_db)} dB above (≥5 MHz outside the −3 dB edges)</p></div>
      <div>${table(["Other orders", {t: "Median dBm", num: 1}, {t: "Max dBm", num: 1}, {t: "Worst dBc in passband", num: 1}], oth)}</div></div>`;
  };

  R.spur_map = (box, run, M) => {
    const d = run.tests.spur_map.data, m = M.spur_map || {};
    const traced = d.series.filter(s => s.trace_dbc && s.trace_dbc.length);
    box.innerHTML = `<div class="bar">${traced.length ? `<label>Heat map for drive <select id="drv">${traced.map(s => `<option value="${s.drive}">${s.drive} mA</option>`).join("")}</select></label>
      <span class="muted">strength of everything within ±${d.window_mhz} MHz of the carrier, in dBc; spurs show as bright streaks</span>` : ""}</div>
      ${traced.length ? '<div class="chart" id="hm"></div>' : ""}<h3>Strongest spur at each frequency</h3><div class="chart" id="ln"></div><div id="tb"></div>`;
    if (traced.length) {
      const hm = () => { const s = traced.find(x => String(x.drive) === $("#drv", box).value);
        Charts.heatmap($("#hm", box), {xs: s.fo_mhz, ys: d.offsets_mhz, z: s.trace_dbc, zmin: -85, zmax: -25, xlabel: "carrier frequency (MHz)", ylabel: "offset from carrier (MHz)", zlabel: "dBc", height: 340}); };
      $("#drv", box).onchange = hm; hm();
    }
    Charts.lineChart($("#ln", box), {series: d.series.map((s, i) => ({name: s.drive + " mA", color: P[i % 8], pts: s.fo_mhz.map((f, j) => [f, (m[String(s.drive)] || {worst_by_fo: []}).worst_by_fo[j] ?? null])})),
      xlabel: "carrier frequency (MHz)", ylabel: "strongest spur (dBc)", height: 280});
    $("#tb", box).innerHTML = table(["Drive", {t: "Worst dBc", num: 1}, {t: "at MHz", num: 1}, {t: "Median dBc", num: 1}, {t: "Best dBc", num: 1}, {t: "at MHz", num: 1}, {t: "Points ≤ −50 dBc", num: 1}],
      Object.entries(m).map(([dr, v]) => [dr + " mA", num(v.worst_dbc), num(v.worst_fo_mhz, 2), num(v.median_dbc), num(v.best_dbc), num(v.best_fo_mhz, 2), `${v.n_better_than_50} of ${v.n_points}`]));
  };

  R.spectrum_close = (box, run, M) => {
    const d = run.tests.spectrum_close.data, m = (M.spectrum_close || {rows: []}).rows;
    const traced = d.configs.some(c => c.trace_dbc);
    box.innerHTML = `${traced ? '<div class="chart" id="c"></div>' : '<p class="muted">This run kept only the spur lists, not the traces.</p>'}<div id="t"></div>`;
    if (traced) Charts.lineChart($("#c", box), {series: d.configs.map((c, i) => ({name: `${c.fo_mhz} MHz ${c.drive} mA`, color: P[i % 8], width: 1.4, pts: d.offsets_mhz.map((o, j) => [o, c.trace_dbc[j]])})),
      xlabel: "offset from the carrier (MHz)", ylabel: "dBc", ylim: [-100, 0], height: 340});
    $("#t", box).innerHTML = table(["Carrier", {t: "Level at analyser dBm", num: 1}, {t: "Strongest spur dBc", num: 1}, {t: "at offset MHz", num: 1}, "All spurs (offset MHz: dBc)"],
      d.configs.map((c, i) => [`${c.fo_mhz} MHz · ${c.drive} mA`, num(c.carrier_dbm), num(m[i] && m[i].worst_dbc), num(m[i] && m[i].worst_offset_mhz, 2),
        c.spurs.slice(0, 6).map(s => `${s[0] > 0 ? "+" : ""}${s[0]}: ${s[1]}`).join(" · ")]));
  };

  const decimate = (xs, ys, n = 2500) => {
    if (xs.length <= n) return xs.map((x, i) => [x, ys[i]]);
    const bin = Math.ceil(xs.length / n), out = [];
    for (let i = 0; i < xs.length; i += bin) { let k = i; for (let j = i; j < Math.min(xs.length, i + bin); j++) if (ys[j] > ys[k]) k = j; out.push([xs[k], ys[k]]); }
    return out;
  };

  R.spectrum_wide = (box, run, M) => {
    const d = run.tests.spectrum_wide.data, m = (M.spectrum_wide || {configs: []}).configs;
    box.innerHTML = `<div class="bar"><label>Configuration <select id="cf">${d.configs.map((c, i) => `<option value="${i}">${c.fo_mhz} MHz · ${c.drive} mA</option>`).join("")}</select></label></div><div class="chart" id="c"></div><div id="t"></div>`;
    const draw = () => {
      const i = +$("#cf", box).value, c = d.configs[i], mm = m[i] || {out_of_band: []};
      const peaks = mm.out_of_band.map(o => [o.freq_mhz, o.dbm, o.order ? `harmonic ${o.order} of the carrier, ${o.dbc} dBc` : `${o.dbc} dBc`]);
      const series = c.freq_mhz ? [{name: "spectrum", color: P[0], width: 1.2, pts: decimate(c.freq_mhz, c.dbm)}] : [{name: "peaks found", color: P[0], kind: "stems", pts: c.peaks.map(p => [p[0], p[1]])}];
      series.push({name: "out-of-band signals", color: P[1], kind: "points", pts: peaks});
      Charts.lineChart($("#c", box), {series, xlabel: "frequency (MHz)", ylabel: "level at analyser (dBm)", height: 340, ylim: [-110, -20], xlim: [0, 800],
        vlines: [{x: c.wanted_hz / 1e6, label: "wanted"}]});
      $("#t", box).innerHTML = `<p class="muted">Floor ${num(mm.floor_dbm)} dBm. Signals within ±${num(mm.exclude_mhz, 1)} MHz of the wanted one are treated as close-in and left out of this list.</p>` +
        table(["Frequency MHz", {t: "Level dBm", num: 1}, {t: "dBc", num: 1}, "Harmonic of carrier", "Checked with extra analyser attenuation"],
          mm.out_of_band.map(o => [num(o.freq_mhz, 3), num(o.dbm), num(o.dbc), o.order ? o.order + "×" : "–",
            o.real === true ? '<span class="good">real signal</span>' : o.real === false ? '<span class="bad">made by the analyser</span>' : '<span class="muted">not checked</span>']));
    };
    $("#cf", box).onchange = draw; draw();
  };

  R.drive_levels = (box, run, M) => {
    const d = run.tests.drive_levels.data, orders = [...new Set(d.rows.flatMap(r => Object.keys(r.lev)))].sort();
    box.innerHTML = `<div class="grid2"><div>${table(["Drive"].concat(orders.map(k => ({t: `${k}× carrier dBm`, num: 1}))), d.rows.map(r => [r.drive + " mA"].concat(orders.map(k => num(r.lev[k], 2)))))}
      <p class="muted">At ${d.fo_mhz} MHz. Levels are as read by the analyser (the pad is not added back).</p></div><div class="chart" id="c"></div></div>`;
    Charts.lineChart($("#c", box), {series: orders.map((k, i) => ({name: k + "× carrier", color: P[i % 8], kind: "points", pts: d.rows.map(r => [r.drive, r.lev[k] ?? null])})), xlabel: "drive (mA)", ylabel: "dBm", height: 240});
  };

  const TITLES = {drive_levels: "Level against drive", response: "Chain response", spur_map: "Spur map", spectrum_close: "Close-in spectra", spectrum_wide: "Wide spectrum"};
  const ORDER = ["drive_levels", "spur_map", "spectrum_close", "spectrum_wide", "response"];

  /* -- views --------------------------------------------------------------------- */
  async function runsView() {
    const runs = await api("/api/runs");
    const outputs = [...new Set(runs.map(r => r.output))];
    view.innerHTML = `<div class="bar"><b>Stored runs</b><label>Output <select id="out"><option value="">all</option>${outputs.map(o => `<option>${esc(o)}</option>`).join("")}</select></label>
      <button class="primary" id="cmp" disabled>Compare selected (pick 2)</button><span class="muted">${runs.length} run(s) in tests-results/</span></div><div class="card" id="tb"></div>`;
    const sel = new Set();
    const draw = () => {
      const f = $("#out").value, rows = runs.filter(r => !f || r.output === f);
      $("#tb").innerHTML = rows.length ? table(["", "Started", "Output", "Test conditions", "Tests", {t: "Headline", num: 0}], rows.map(r =>
        [`<input type="checkbox" data-id="${esc(r.run_id)}" ${sel.has(r.run_id) ? "checked" : ""}>`,
         `<a href="#/run/${encodeURIComponent(r.run_id)}">${esc(when(r.started))}</a> ${badges(r)}`, esc(r.output), esc(r.setup_id) + `<div class="muted">${esc(r.chain)}</div>`,
         r.tests.map(t => `<span class="chip">${esc(t)}</span>`).join(""),
         HEADLINE.filter(k => r.summary[k] != null).map(k => `<div>${esc(metricInfo(k).label)}: <b>${num(r.summary[k])}</b> ${metricInfo(k).unit}</div>`).join("") || "–"])) :
        '<p class="muted">No runs yet. Run <code>python3 tests/bench/run.py --setup &lt;id&gt;</code>.</p>';
      $("#tb").querySelectorAll("input[data-id]").forEach(c => c.onchange = () => { c.checked ? sel.add(c.dataset.id) : sel.delete(c.dataset.id); $("#cmp").disabled = sel.size !== 2; });
    };
    $("#out").onchange = draw; draw();
    $("#cmp").onclick = () => { const [a, b] = [...sel]; location.hash = `#/compare/${encodeURIComponent(a)}/${encodeURIComponent(b)}`; };
  }

  async function runView(id) {
    const d = await getRun(id), run = d.run;
    view.innerHTML = `<div class="bar"><a href="#/">← Runs</a><h2 style="margin:0">${esc(run.output)} · ${esc(run.setup.id)}</h2>${badges({status: run.status, legacy: run.legacy})}<span class="muted">${esc(run.run_id)}</span></div>`;
    view.append(conditionsCard(d));
    const s = Object.entries(d.summary);
    if (s.length) view.append(card("Headline figures", table(["Measurement", {t: "Value", num: 1}, "Unit"], s.map(([k, v]) => [esc(metricInfo(k).label), num(v, 2), esc(metricInfo(k).unit)]))));
    for (const name of ORDER) if (run.tests[name] && run.tests[name].data) {
      const c = card(TITLES[name]); view.append(c);
      const box = document.createElement("div"); c.append(box);
      try { R[name](box, run, d.metrics); } catch (e) { box.innerHTML = `<p class="err">Could not draw this: ${esc(e.message)}</p>`; console.error(e); }
    }
  }

  const label = r => `${when(r.started)} · ${r.output} · ${r.setup_id}${r.legacy ? " (imported)" : ""}`;
  async function compareView(a, b) {
    const runs = await api("/api/runs");
    const opt = sel => runs.map(r => `<option value="${esc(r.run_id)}" ${r.run_id === sel ? "selected" : ""}>${esc(label(r))}</option>`).join("");
    view.innerHTML = `<div class="bar"><b>Compare</b><label>A <select id="a"><option value="">choose…</option>${opt(a)}</select></label><label>B <select id="b"><option value="">choose…</option>${opt(b)}</select></label>
      <span class="muted">Δ = B − A. Green means B is better.</span></div><div id="body"></div>`;
    const go = () => { const x = $("#a").value, y = $("#b").value; if (x && y) location.hash = `#/compare/${encodeURIComponent(x)}/${encodeURIComponent(y)}`; };
    $("#a").onchange = go; $("#b").onchange = go;
    if (!a || !b) { $("#body").innerHTML = '<p class="muted">Pick two runs. Typical uses: the same setup on two days (repeatability), or two different filters on the same output.</p>'; return; }
    const [A, B] = await Promise.all([getRun(a), getRun(b)]);
    const body = $("#body");
    const g2 = document.createElement("div"); g2.className = "grid2"; g2.append(conditionsCard(A, "A"), conditionsCard(B, "B")); body.append(g2);
    const diffs = [];
    for (const n of ORDER) { const ta = A.run.tests[n], tb = B.run.tests[n]; if (!ta || !tb) continue;
      const va = ta.version ?? "imported", vb = tb.version ?? "imported";
      if (va !== vb) diffs.push(`${TITLES[n]}: procedure version ${va} against ${vb}`);
      for (const k of new Set([...Object.keys(ta.params || {}), ...Object.keys(tb.params || {})]))
        if (JSON.stringify((ta.params || {})[k]) !== JSON.stringify((tb.params || {})[k])) diffs.push(`${TITLES[n]}: ${k} is ${esc(JSON.stringify((ta.params || {})[k]) ?? "unset")} in A, ${esc(JSON.stringify((tb.params || {})[k]) ?? "unset")} in B`); }
    const gitA = (A.run.environment.git || {}).commit, gitB = (B.run.environment.git || {}).commit;
    const verdict = diffs.length ?
      `<p class="bad"><b>No: the two runs were not measured the same way.</b> Differences in the figures below may come from the procedure, not the hardware.</p><ul>${diffs.slice(0, 14).map(d => `<li>${d}</li>`).join("")}</ul>${diffs.length > 14 ? `<p class="muted">…and ${diffs.length - 14} more.</p>` : ""}` :
      `<p class="good"><b>Yes:</b> every test has the same procedure version and parameters.</p>`;
    body.append(card("Is this a like-for-like comparison?", verdict + (gitA !== gitB ? `<p class="muted">Firmware commit: A ${esc(gitA || "?")}, B ${esc(gitB || "?")}.</p>` : "")));
    const keys = [...new Set([...Object.keys(A.summary), ...Object.keys(B.summary)])].sort();
    body.append(card("Headline figures", table(["Measurement", {t: "A", num: 1}, {t: "B", num: 1}, {t: "Δ", num: 1}, "Unit"], keys.map(k => {
      const i = metricInfo(k), x = A.summary[k], y = B.summary[k], dl = x != null && y != null ? y - x : null;
      let cls = ""; if (dl != null && Math.abs(dl) >= 0.05 && i.better) cls = (i.better === "lower" ? dl < 0 : dl > 0) ? "good" : "bad";
      return [esc(i.label), num(x, 2), num(y, 2), `<span class="${cls}">${dl == null ? "–" : (dl > 0 ? "+" : "") + dl.toFixed(2)}</span>`, esc(i.unit)];
    }))));
    // overlays
    const both = n => A.run.tests[n] && B.run.tests[n] && A.run.tests[n].data && B.run.tests[n].data;
    if (both("response")) {
      const c = card("Chain response, wanted signal"); body.append(c); const el = document.createElement("div"); el.className = "chart"; c.append(el);
      const ser = (D, nm, col, dash) => { const t = D.run.tests.response, wk = String(t.params.wanted_order); return {name: nm, color: col, dash, width: 2, pts: t.data.fo_mhz.map((f, j) => [f, t.data.orders[wk].dbm[j]])}; };
      Charts.lineChart(el, {series: [ser(A, "A " + A.run.setup.id, P[0], false), ser(B, "B " + B.run.setup.id, P[1], true)], xlabel: "wanted output frequency (MHz)", ylabel: "level at the analyser (dBm)", height: 340});
    }
    if (both("spur_map")) {
      const c = card("Strongest close-in spur across the band"); body.append(c); const el = document.createElement("div"); el.className = "chart"; c.append(el);
      const mk = (D, tag, dash) => D.run.tests.spur_map.data.series.map((s, i) => ({name: `${tag} ${s.drive} mA`, color: P[(tag === "A" ? 0 : 1) + 2 * (i % 3)], dash,
        pts: s.fo_mhz.map((f, j) => [f, (D.metrics.spur_map[String(s.drive)] || {worst_by_fo: []}).worst_by_fo[j] ?? null])}));
      Charts.lineChart(el, {series: [...mk(A, "A", false), ...mk(B, "B", true)], xlabel: "carrier frequency (MHz)", ylabel: "strongest spur (dBc)", height: 300});
      const sa = A.run.tests.spur_map.data, sb = B.run.tests.spur_map.data;
      for (const s of sa.series) { const t = sb.series.find(x => x.drive === s.drive);
        if (t && s.trace_dbc.length && t.trace_dbc.length && s.fo_mhz.length === t.fo_mhz.length && s.fo_mhz.every((f, i) => Math.abs(f - t.fo_mhz[i]) < 1e-6) && sa.offsets_mhz.length === sb.offsets_mhz.length) {
          const h = document.createElement("div"); h.className = "chart"; h.innerHTML = `<h3>Change in the whole close-in spectrum, ${s.drive} mA (B − A)</h3><div></div>`; c.append(h);
          Charts.heatmap(h.lastElementChild, {xs: s.fo_mhz, ys: sa.offsets_mhz, z: s.trace_dbc.map((row, i) => row.map((v, j) => v == null || t.trace_dbc[i][j] == null ? null : t.trace_dbc[i][j] - v)),
            zmin: -15, zmax: 15, palette: "diverging", xlabel: "carrier frequency (MHz)", ylabel: "offset (MHz)", zlabel: "dB (blue: B lower)", height: 300});
        } }
    }
    if (both("spectrum_wide")) {
      const ca = A.run.tests.spectrum_wide.data.configs, cb = B.run.tests.spectrum_wide.data.configs;
      for (const x of ca) { const y = cb.find(z => z.fo_mhz === x.fo_mhz && z.drive === x.drive);
        if (y && x.freq_mhz && y.freq_mhz) { const c = card(`Wide spectrum, ${x.fo_mhz} MHz, ${x.drive} mA`); body.append(c); const el = document.createElement("div"); el.className = "chart"; c.append(el);
          Charts.lineChart(el, {series: [{name: "A", color: P[0], width: 1.2, pts: decimate(x.freq_mhz, x.dbm)}, {name: "B", color: P[1], width: 1.2, dash: true, pts: decimate(y.freq_mhz, y.dbm)}],
            xlabel: "frequency (MHz)", ylabel: "dBm", ylim: [-110, -20], height: 320}); } }
    }
  }

  async function trendsView() {
    const runs = (await api("/api/runs")).filter(r => (r.status || "complete") === "complete");
    const outputs = [...new Set(runs.map(r => r.output))];
    view.innerHTML = `<div class="bar"><b>Trends</b><label>Output <select id="o">${outputs.map(o => `<option>${esc(o)}</option>`).join("")}</select></label><label>Measurement <select id="k"></select></label></div><div class="card"><div class="chart" id="c"></div><div id="t"></div></div>`;
    if (!runs.length) { $("#c").innerHTML = '<p class="muted">No completed runs yet.</p>'; return; }
    const draw = () => {
      const rs = runs.filter(r => r.output === $("#o").value), keys = [...new Set(rs.flatMap(r => Object.keys(r.summary)))].sort();
      const cur = $("#k").value; $("#k").innerHTML = keys.map(k => `<option value="${esc(k)}" ${k === cur ? "selected" : ""}>${esc(metricInfo(k).label)} (${esc(metricInfo(k).unit)})</option>`).join("");
      const k = $("#k").value || keys[0], info = metricInfo(k || ""), bySetup = {};
      for (const r of rs) if (r.summary[k] != null) (bySetup[r.setup_id] = bySetup[r.setup_id] || []).push([Date.parse(r.started), r.summary[k], r.run_id]);
      const series = Object.entries(bySetup).map(([sid, pts], i) => ({name: sid, color: P[i % 8], kind: "line", pts: pts.sort((a, b) => a[0] - b[0])}));
      if (!series.length) { $("#c").innerHTML = '<p class="muted">Nothing recorded for this measurement.</p>'; return; }
      Charts.lineChart($("#c"), {series, xlabel: "run date", ylabel: `${info.label} (${info.unit})`, height: 340, xfmt: v => new Date(v).toISOString().slice(0, 16).replace("T", " "), yfmt: v => +v.toPrecision(5)});
      $("#t").innerHTML = table(["Run", "Test conditions", {t: "Value", num: 1}], rs.filter(r => r.summary[k] != null).map(r => [`<a href="#/run/${encodeURIComponent(r.run_id)}">${esc(when(r.started))}</a> ${badges(r)}`, esc(r.setup_id), num(r.summary[k], 2)]));
    };
    $("#o").onchange = draw; $("#k").onchange = draw; draw();
  }

  /* -- router -------------------------------------------------------------------- */
  async function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
    document.querySelectorAll("nav a").forEach(a => a.classList.toggle("on", a.dataset.r === (parts[0] === "run" || parts[0] === "" ? "runs" : parts[0])));
    try {
      if (parts[0] === "run" && parts[1]) await runView(parts[1]);
      else if (parts[0] === "compare") await compareView(parts[1], parts[2]);
      else if (parts[0] === "trends") await trendsView();
      else await runsView();
    } catch (e) { view.innerHTML = `<p class="err">${esc(e.message)}</p>`; console.error(e); }
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);
  route();
})();
