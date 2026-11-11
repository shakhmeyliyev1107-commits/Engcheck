"""Sxemani SVG ga chiqarish (eksport uchun). Fayl ilovadan tashqarida ham to'g'ri o'qilishi kerak:
shartli belgilar va "P&ID o'rnini bosmaydi" izohi faylning o'zida bo'ladi."""
from html import escape

W, H = 150, 64   # tugun o'lchami
STROKE = {"document": "#1c2430", "inferred": "#9a4d00", "manual": "#0f5c8c"}
TEXT = {
    "uz": {"document": "Hujjatdan", "inferred": "Taxminiy: chizmadagi yaqinlik bo‘yicha, yo‘nalishi noma'lum",
           "manual": "Qo‘lda kiritilgan yoki o‘zgartirilgan",
           "note": "Prinsipial sxema hujjatlardan avtomatik qurilgan; u P&ID o‘rnini bosmaydi.",
           "diff": "Hujjatlardan farqlar: {n}", "was": "asli: {label}"},
    "en": {"document": "From documents", "inferred": "Inferred: from proximity on the drawing, direction unknown",
           "manual": "Added manually or modified",
           "note": "Block diagram built automatically from the documents; it does not replace the P&ID.",
           "diff": "Differences from the documents: {n}", "was": "was: {label}"},
    "ru": {"document": "Из документов", "inferred": "Предположительно: по близости на чертеже, направление неизвестно",
           "manual": "Добавлено или изменено вручную",
           "note": "Принципиальная схема построена автоматически по документам; она не заменяет P&ID.",
           "diff": "Отличий от документов: {n}", "was": "было: {label}"},
}


def render_svg(diagram: dict, locale: str = "uz") -> str:
    t = TEXT.get(locale, TEXT["uz"])
    nodes = diagram["nodes"]
    min_x, min_y = min((n["x"] for n in nodes), default=0) - 80, min((n["y"] for n in nodes), default=0) - 80
    max_x = max(max((n["x"] for n in nodes), default=0) + W + 80, min_x + 760)
    body_bottom = max((n["y"] for n in nodes), default=0) + H + 60
    max_y = body_bottom + 130   # pastda shartli belgilar uchun joy
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
        # O'q uchi faqat yo'nalishi hujjatda yoki muhandis tomonidan berilgan ulanishda.
        arrow = ' marker-end="url(#arrow)"' if e.get("directed", e["source"] != "inferred") else ""
        parts.append(f'<line data-source="{escape(e["source"])}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                     f'stroke="{STROKE.get(e["source"], "#1c2430")}" stroke-width="2"{dash}{arrow}/>')
        if e.get("label"):
            parts.append(f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 6}" text-anchor="middle" fill="#5d6877">{escape(e["label"])}</text>')
    for n in nodes:
        radius = 32 if n["kind"] in ("vessel", "column", "tank", "reactor") else 6
        renamed = bool(n.get("renamed"))
        dash = ' stroke-dasharray="4 4"' if n["kind"] == "boundary" or n.get("line_list_only") else ""
        stroke = STROKE["manual"] if renamed else STROKE.get(n["source"], "#1c2430")
        parts.append(f'<rect data-source="{escape(n["source"])}" data-renamed="{"true" if renamed else "false"}" '
                     f'x="{n["x"]}" y="{n["y"]}" width="{W}" height="{H}" rx="{radius}" '
                     f'fill="#f4f5f7" stroke="{stroke}" stroke-width="2"{dash}/>')
        y = n["y"] + H / 2 + (0 if renamed else 5)
        parts.append(f'<text x="{n["x"] + W / 2}" y="{y}" text-anchor="middle" fill="#1c2430">{escape(n["label"])}</text>')
        if renamed:
            parts.append(f'<text x="{n["x"] + W / 2}" y="{y + 16}" text-anchor="middle" fill="#5d6877" font-size="11">'
                         f'({escape(t["was"].format(label=n.get("original_label", "")))})</text>')
    ly = body_bottom + 20
    for i, key in enumerate(("document", "inferred", "manual")):
        dash = ' stroke-dasharray="7 5"' if key == "inferred" else ""
        parts.append(f'<line x1="{min_x + 30}" y1="{ly + i * 22}" x2="{min_x + 70}" y2="{ly + i * 22}" stroke="{STROKE[key]}" stroke-width="3"{dash}/>')
        parts.append(f'<text x="{min_x + 80}" y="{ly + i * 22 + 4}" fill="#1c2430">{escape(t[key])}</text>')
    notes = [t["note"]]
    if diagram.get("differences"):
        notes.append(t["diff"].format(n=len(diagram["differences"])))
    for i, line in enumerate(notes):
        parts.append(f'<text x="{min_x + 30}" y="{ly + 74 + i * 18}" fill="#5d6877">{escape(line)}</text>')
    parts.append("</svg>")
    return "".join(parts)
