"""Sxemani SVG ga chiqarish (eksport uchun)."""
from html import escape

W, H = 150, 64   # tugun o'lchami
STROKE = {"document": "#1c2430", "inferred": "#9a4d00", "manual": "#0f5c8c"}


def render_svg(diagram: dict) -> str:
    nodes = diagram["nodes"]
    max_x = max((n["x"] for n in nodes), default=0) + W + 80
    max_y = max((n["y"] for n in nodes), default=0) + H + 80
    min_x, min_y = min((n["x"] for n in nodes), default=0) - 80, min((n["y"] for n in nodes), default=0) - 80
    by_id = {n["id"]: n for n in nodes}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {max_x - min_x} {max_y - min_y}" '
             f'font-family="sans-serif" font-size="13">',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
             'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#5d6877"/></marker></defs>',
             f'<rect x="{min_x}" y="{min_y}" width="{max_x - min_x}" height="{max_y - min_y}" fill="#ffffff"/>']
    for e in diagram["edges"]:
        a, b = by_id.get(e["from"]), by_id.get(e["to"])
        if not a or not b:
            continue
        x1, y1, x2, y2 = a["x"] + W / 2, a["y"] + H / 2, b["x"] + W / 2, b["y"] + H / 2
        dash = ' stroke-dasharray="7 5"' if e["source"] == "inferred" else ""
        parts.append(f'<line data-source="{escape(e["source"])}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                     f'stroke="{STROKE.get(e["source"], "#1c2430")}" stroke-width="2"{dash} marker-end="url(#arrow)"/>')
        if e.get("label"):
            parts.append(f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 6}" text-anchor="middle" fill="#5d6877">{escape(e["label"])}</text>')
    for n in nodes:
        radius = 32 if n["kind"] in ("vessel", "column", "tank", "reactor") else 6
        dash = ' stroke-dasharray="4 4"' if n["kind"] == "boundary" else ""
        parts.append(f'<rect data-source="{escape(n["source"])}" x="{n["x"]}" y="{n["y"]}" width="{W}" height="{H}" rx="{radius}" '
                     f'fill="#f4f5f7" stroke="{STROKE.get(n["source"], "#1c2430")}" stroke-width="2"{dash}/>')
        parts.append(f'<text x="{n["x"] + W / 2}" y="{n["y"] + H / 2 + 5}" text-anchor="middle" fill="#1c2430">{escape(n["label"])}</text>')
    parts.append("</svg>")
    return "".join(parts)
