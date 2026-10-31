/* Small dependency-free charts: line/points/stems (SVG) and a heatmap (canvas). */
const Charts = (() => {
  const PALETTE = ["#1f6feb", "#d1481f", "#2a9d4b", "#8a4fff", "#c08a00", "#0a8ea0", "#b0267a", "#6b7280"];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function niceTicks(lo, hi, target = 7) {
    const span = hi - lo;
    if (!(span > 0)) return [lo];
    const mag = Math.pow(10, Math.floor(Math.log10(span / target)));
    let step = mag;
    for (const m of [1, 2, 5, 10]) { step = mag * m; if (span / step <= target) break; }
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
    return out;
  }

  function showTip(html, ev) {
    const t = document.getElementById("tip");
    t.innerHTML = html; t.hidden = false;
    const w = t.offsetWidth;
    t.style.left = Math.min(ev.clientX + 14, window.innerWidth - w - 8) + "px";
    t.style.top = (ev.clientY + 14) + "px";
  }
  const hideTip = () => { document.getElementById("tip").hidden = true; };

  /* cfg: {series:[{name,color,pts:[[x,y]],kind:'line'|'points'|'stems',dash,width}], xlabel,ylabel,xlim,ylim,
           vlines:[{x,label}], hlines:[{y,label}], height, xfmt, yfmt} */
  function lineChart(el, cfg) {
    const hidden = new Set();
    const draw = () => {
      const W = Math.max(el.clientWidth, 320), H = cfg.height || 340;
      const m = {l: 62, r: 16, t: 10, b: 44}, iw = W - m.l - m.r, ih = H - m.t - m.b;
      const vis = cfg.series.filter(s => !hidden.has(s.name));
      let xs = [], ys = [];
      for (const s of cfg.series) for (const p of s.pts) if (p[1] != null) { xs.push(p[0]); ys.push(p[1]); }
      let [x0, x1] = cfg.xlim || [Math.min(...xs), Math.max(...xs)];
      let [y0, y1] = cfg.ylim || [Math.min(...ys), Math.max(...ys)];
      if (!isFinite(x0) || x0 === x1) { x0 = (x0 || 0) - 1; x1 = x0 + 2; }
      if (!isFinite(y0) || y0 === y1) { y0 = (y0 || 0) - 1; y1 = y0 + 2; }
      if (!cfg.ylim) { const pad = (y1 - y0) * 0.06; y0 -= pad; y1 += pad; }
      const sx = x => m.l + (x - x0) / (x1 - x0) * iw, sy = y => m.t + (1 - (y - y0) / (y1 - y0)) * ih;
      const xf = cfg.xfmt || (v => +v.toPrecision(7)), yf = cfg.yfmt || (v => +v.toPrecision(6));
      let o = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`;
      for (const t of niceTicks(x0, x1, Math.max(3, iw / 90))) o += `<line class="grid" x1="${sx(t)}" y1="${m.t}" x2="${sx(t)}" y2="${m.t + ih}"/><text class="tick" x="${sx(t)}" y="${m.t + ih + 16}" text-anchor="middle">${esc(xf(t))}</text>`;
      for (const t of niceTicks(y0, y1, Math.max(3, ih / 45))) o += `<line class="grid" x1="${m.l}" y1="${sy(t)}" x2="${m.l + iw}" y2="${sy(t)}"/><text class="tick" x="${m.l - 6}" y="${sy(t) + 4}" text-anchor="end">${esc(yf(t))}</text>`;
      o += `<rect class="frame" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}"/>`;
      for (const v of cfg.vlines || []) if (v.x != null && v.x >= x0 && v.x <= x1)
        o += `<line class="mark" x1="${sx(v.x)}" y1="${m.t}" x2="${sx(v.x)}" y2="${m.t + ih}"/><text class="marklab" transform="rotate(-90 ${sx(v.x) - 3} ${m.t + ih - 6})" x="${sx(v.x) - 3}" y="${m.t + ih - 6}">${esc(v.label || "")}</text>`;
      for (const h of cfg.hlines || []) if (h.y != null && h.y >= y0 && h.y <= y1)
        o += `<line class="mark" x1="${m.l}" y1="${sy(h.y)}" x2="${m.l + iw}" y2="${sy(h.y)}"/><text class="marklab" x="${m.l + iw - 4}" y="${sy(h.y) - 4}" text-anchor="end">${esc(h.label || "")}</text>`;
      for (const s of vis) {
        const col = s.color || PALETTE[cfg.series.indexOf(s) % PALETTE.length], kind = s.kind || "line";
        if (kind === "line") {
          let d = "", pen = false;
          for (const [x, y] of s.pts) { if (y == null) { pen = false; continue; } d += (pen ? "L" : "M") + sx(x).toFixed(1) + " " + sy(Math.max(y0, Math.min(y1, y))).toFixed(1); pen = true; }
          o += `<path d="${d}" fill="none" stroke="${col}" stroke-width="${s.width || 1.8}" ${s.dash ? 'stroke-dasharray="6 4"' : ""}/>`;
        }
        if (kind === "points" || (kind === "line" && s.pts.length <= 120))
          for (const [x, y] of s.pts) if (y != null && x >= x0 && x <= x1) o += `<circle cx="${sx(x).toFixed(1)}" cy="${sy(Math.max(y0, Math.min(y1, y))).toFixed(1)}" r="${kind === "points" ? 3.4 : 2.2}" fill="${col}"/>`;
        if (kind === "stems")
          for (const [x, y] of s.pts) if (y != null && x >= x0 && x <= x1) o += `<line x1="${sx(x)}" y1="${sy(y0)}" x2="${sx(x)}" y2="${sy(y)}" stroke="${col}" stroke-width="2"/><circle cx="${sx(x)}" cy="${sy(y)}" r="3" fill="${col}"/>`;
      }
      o += `<line id="cur" class="cursor" y1="${m.t}" y2="${m.t + ih}" visibility="hidden"/>`;
      o += `<text class="axlab" x="${m.l + iw / 2}" y="${H - 6}" text-anchor="middle">${esc(cfg.xlabel || "")}</text>`;
      o += `<text class="axlab" transform="rotate(-90 14 ${m.t + ih / 2})" x="14" y="${m.t + ih / 2}" text-anchor="middle">${esc(cfg.ylabel || "")}</text></svg>`;
      const legend = cfg.series.length > 1 || cfg.series[0].name ? `<div class="legend">${cfg.series.map((s, i) =>
        `<span class="lg ${hidden.has(s.name) ? "off" : ""}" data-n="${esc(s.name)}"><i style="background:${s.color || PALETTE[i % PALETTE.length]}"></i>${esc(s.name)}</span>`).join("")}</div>` : "";
      el.innerHTML = legend + o;
      el.querySelectorAll(".lg").forEach(n => n.onclick = () => { const k = n.dataset.n; hidden.has(k) ? hidden.delete(k) : hidden.add(k); draw(); });
      const svg = el.querySelector("svg"), cur = svg.querySelector("#cur");
      svg.onmousemove = ev => {
        const r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) * W / r.width;
        if (px < m.l || px > m.l + iw) return hideTip();
        const xv = x0 + (px - m.l) / iw * (x1 - x0);
        const rows = [];
        let bestx = null;
        for (const s of vis) {
          let best = null;
          for (const p of s.pts) if (p[1] != null && (best === null || Math.abs(p[0] - xv) < Math.abs(best[0] - xv))) best = p;
          if (best) { rows.push(`<div><i style="background:${s.color || PALETTE[cfg.series.indexOf(s) % PALETTE.length]}"></i>${esc(s.name)}: <b>${esc(yf(best[1]))}</b> at ${esc(xf(best[0]))}${best[2] ? " " + esc(best[2]) : ""}</div>`); if (bestx === null) bestx = best[0]; }
        }
        if (!rows.length) return hideTip();
        cur.setAttribute("x1", sx(bestx)); cur.setAttribute("x2", sx(bestx)); cur.setAttribute("visibility", "visible");
        showTip(rows.join(""), ev);
      };
      svg.onmouseleave = () => { hideTip(); cur.setAttribute("visibility", "hidden"); };
    };
    draw();
    return {redraw: draw};
  }

  const STOPS = {
    viridis: [[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]],
    diverging: [[33, 102, 172], [146, 197, 222], [247, 247, 247], [244, 165, 130], [178, 24, 43]],
  };
  function colour(t, palette) {
    const stops = STOPS[palette || "viridis"];
    t = Math.max(0, Math.min(1, t)) * (stops.length - 1);
    const i = Math.min(stops.length - 2, Math.floor(t)), f = t - i, a = stops[i], b = stops[i + 1];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  }

  /* cfg: {xs:[..], ys:[..], z:z[xi][yi], zmin,zmax, palette, xlabel,ylabel,zlabel,height,zfmt} */
  function heatmap(el, cfg) {
    const W = Math.max(el.clientWidth, 320), H = cfg.height || 320, m = {l: 62, r: 78, t: 10, b: 44};
    const iw = W - m.l - m.r, ih = H - m.t - m.b, nx = cfg.xs.length, ny = cfg.ys.length;
    el.innerHTML = `<canvas width="${W}" height="${H}" style="width:100%;max-width:${W}px"></canvas>`;
    const cv = el.querySelector("canvas"), ctx = cv.getContext("2d");
    const img = ctx.createImageData(iw, ih), span = cfg.zmax - cfg.zmin;
    const xlo = cfg.xs[0], xhi = cfg.xs[nx - 1], ylo = cfg.ys[0], yhi = cfg.ys[ny - 1];
    const xstep = nx > 1 ? (xhi - xlo) / (nx - 1) : 1;
    for (let py = 0; py < ih; py++) {
      const yi = Math.max(0, Math.min(ny - 1, Math.round((1 - py / (ih - 1)) * (ny - 1))));
      for (let px = 0; px < iw; px++) {
        const xi = Math.max(0, Math.min(nx - 1, Math.floor(px / iw * nx)));
        const v = cfg.z[xi][yi], k = (py * iw + px) * 4;
        const c = v == null ? [128, 128, 128] : colour((v - cfg.zmin) / span, cfg.palette);
        img.data[k] = c[0]; img.data[k + 1] = c[1]; img.data[k + 2] = c[2]; img.data[k + 3] = 255;
      }
    }
    ctx.fillStyle = css("--panel") || "#fff"; ctx.fillRect(0, 0, W, H);
    ctx.putImageData(img, m.l, m.t);
    ctx.fillStyle = css("--fg") || "#222"; ctx.strokeStyle = css("--frame") || "#888"; ctx.font = "12px system-ui,sans-serif";
    ctx.strokeRect(m.l + 0.5, m.t + 0.5, iw, ih);
    ctx.textAlign = "center";
    const xa = xlo - xstep / 2, xb = xhi + xstep / 2;
    for (const t of niceTicks(xa, xb, Math.max(3, iw / 80))) { const x = m.l + (t - xa) / (xb - xa) * iw; ctx.fillText(+t.toPrecision(7), x, m.t + ih + 16); ctx.fillRect(x, m.t + ih, 1, 4); }
    ctx.textAlign = "right";
    for (const t of niceTicks(ylo, yhi, Math.max(3, ih / 45))) { const y = m.t + (1 - (t - ylo) / (yhi - ylo)) * ih; ctx.fillText(+t.toPrecision(6), m.l - 8, y + 4); ctx.fillRect(m.l - 4, y, 4, 1); }
    ctx.textAlign = "center"; ctx.fillText(cfg.xlabel || "", m.l + iw / 2, H - 6);
    ctx.save(); ctx.translate(14, m.t + ih / 2); ctx.rotate(-Math.PI / 2); ctx.fillText(cfg.ylabel || "", 0, 0); ctx.restore();
    const bx = m.l + iw + 16, bw = 14;                     // colour bar
    for (let i = 0; i < ih; i++) { const c = colour(1 - i / (ih - 1), cfg.palette); ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`; ctx.fillRect(bx, m.t + i, bw, 1); }
    ctx.fillStyle = css("--fg") || "#222"; ctx.textAlign = "left";
    const zf = cfg.zfmt || (v => +v.toPrecision(4));
    ctx.fillText(zf(cfg.zmax), bx + bw + 4, m.t + 10); ctx.fillText(zf(cfg.zmin), bx + bw + 4, m.t + ih);
    ctx.save(); ctx.translate(bx + bw + 34, m.t + ih / 2); ctx.rotate(Math.PI / 2); ctx.textAlign = "center"; ctx.fillText(cfg.zlabel || "", 0, 0); ctx.restore();
    cv.onmousemove = ev => {
      const r = cv.getBoundingClientRect(), px = (ev.clientX - r.left) * W / r.width - m.l, py = (ev.clientY - r.top) * H / r.height - m.t;
      if (px < 0 || py < 0 || px >= iw || py >= ih) return hideTip();
      const xi = Math.min(nx - 1, Math.floor(px / iw * nx)), yi = Math.max(0, Math.min(ny - 1, Math.round((1 - py / (ih - 1)) * (ny - 1))));
      const v = cfg.z[xi][yi];
      showTip(`${esc(cfg.xlabel)}: <b>${esc(+cfg.xs[xi].toPrecision(7))}</b><br>${esc(cfg.ylabel)}: <b>${esc(+cfg.ys[yi].toPrecision(5))}</b><br>${esc(cfg.zlabel || "value")}: <b>${v == null ? "n/a" : esc(zf(v))}</b>`, ev);
    };
    cv.onmouseleave = hideTip;
  }

  return {PALETTE, esc, lineChart, heatmap};
})();
