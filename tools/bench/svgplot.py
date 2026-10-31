"""Tiny dependency-free SVG line/point charts for bench reports."""

_COLOURS = ("#1f6feb", "#d1481f", "#2a9d4b", "#8a4fff", "#555555")


def _nice_ticks(lo, hi, target=8):
    span = hi - lo
    raw = span / target
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 10 ** (-1 if raw >= 0.1 else -2)
    for m in (1, 2, 5, 10):
        step = mag * m
        if span / step <= target:
            break
    first = int(lo / step) * step
    ticks, v = [], first
    while v <= hi + 1e-9:
        if v >= lo - 1e-9:
            ticks.append(round(v, 6))
        v += step
    return ticks


def chart(path, series, title, xlabel, ylabel, xlim, ylim, vlines=(), hlines=(), notes=(),
          width=900, height=480, points_only=False):
    """series: list of (label, [(x, y), ...]). vlines/hlines: (value, label) pairs."""
    ml, mr, mt, mb = 70, 20, 40, 55
    pw, ph = width - ml - mr, height - mt - mb
    x0, x1 = xlim
    y0, y1 = ylim

    def sx(x):
        return ml + (x - x0) / (x1 - x0) * pw

    def sy(y):
        return mt + (1 - (y - y0) / (y1 - y0)) * ph

    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
         'font-family="system-ui,sans-serif" font-size="12">' % (width, height, width, height),
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         '<text x="%d" y="22" font-size="15" font-weight="600" fill="#111">%s</text>' % (ml, title)]
    for t in _nice_ticks(x0, x1):
        o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#e3e3e3"/>' % (sx(t), mt, sx(t), mt + ph))
        o.append('<text x="%.1f" y="%d" text-anchor="middle" fill="#444">%g</text>' % (sx(t), mt + ph + 16, t))
    for t in _nice_ticks(y0, y1):
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e3e3e3"/>' % (ml, sy(t), ml + pw, sy(t)))
        o.append('<text x="%d" y="%.1f" text-anchor="end" fill="#444">%g</text>' % (ml - 6, sy(t) + 4, t))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#888"/>' % (ml, mt, pw, ph))
    for v, lab in vlines:
        if x0 <= v <= x1:
            o.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#b36b00" stroke-dasharray="5 4"/>' % (sx(v), mt, sx(v), mt + ph))
            o.append('<text x="%.1f" y="%d" fill="#b36b00" font-size="11" transform="rotate(-90 %.1f %d)">%s</text>' % (sx(v) - 3, mt + ph - 6, sx(v) - 3, mt + ph - 6, lab))
    for v, lab in hlines:
        if y0 <= v <= y1:
            o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#b36b00" stroke-dasharray="5 4"/>' % (ml, sy(v), ml + pw, sy(v)))
            o.append('<text x="%d" y="%.1f" fill="#b36b00" font-size="11" text-anchor="end">%s</text>' % (ml + pw - 4, sy(v) - 4, lab))
    for i, (label, pts) in enumerate(series):
        col = _COLOURS[i % len(_COLOURS)]
        pts = [(x, y) for x, y in pts if x0 <= x <= x1]
        if not points_only and len(pts) > 1:
            d = " ".join("%.1f,%.1f" % (sx(x), min(max(sy(y), mt), mt + ph)) for x, y in pts)
            o.append('<polyline fill="none" stroke="%s" stroke-width="1.8" points="%s"/>' % (col, d))
        for x, y in pts:
            o.append('<circle cx="%.1f" cy="%.1f" r="2.6" fill="%s"/>' % (sx(x), min(max(sy(y), mt), mt + ph), col))
        o.append('<rect x="%d" y="%d" width="12" height="12" fill="%s"/>' % (ml + 10, mt + 8 + i * 18, col))
        o.append('<text x="%d" y="%d" fill="#222">%s</text>' % (ml + 28, mt + 18 + i * 18, label))
    for j, (x, y, text) in enumerate(notes):
        o.append('<text x="%.1f" y="%.1f" fill="#222" font-size="11">%s</text>' % (sx(x), sy(y), text))
    o.append('<text x="%d" y="%d" text-anchor="middle" fill="#222">%s</text>' % (ml + pw // 2, height - 12, xlabel))
    o.append('<text x="16" y="%d" text-anchor="middle" fill="#222" transform="rotate(-90 16 %d)">%s</text>' % (mt + ph // 2, mt + ph // 2, ylabel))
    o.append("</svg>")
    open(path, "w").write("\n".join(o))
