"""Hujjatlardan ajratilgan uskuna va quvurlardan prinsipial sxemaning yaratilgan qatlamini quradi."""
import hashlib
import re
from collections import defaultdict

from sqlalchemy.orm import Session as Db

from ..core.models import DocType, Method, TagClass
from ..ingest.tagging import normalize_tags, tag_prefix
from ..review.rules.base import active_docs, display_value, project_occurrences, project_params
from .layout import layout

KINDS = ("vessel", "pump", "exchanger", "column", "compressor", "tank", "reactor", "heater", "boundary", "generic")
_KIND_BY_PREFIX = {"V": "vessel", "D": "vessel", "P": "pump", "E": "exchanger", "T": "column", "C": "column",
                   "K": "compressor", "TK": "tank", "R": "reactor", "F": "heater", "H": "heater"}
_EQUIPMENT_DOCS = (DocType.PID, DocType.EQUIPMENT_LIST, DocType.DATASHEET)
_XY = re.compile(r"^x=(-?\d+(?:\.\d+)?),y=(-?\d+(?:\.\d+)?)$")
_SHOWN_PARAMS = ("design_pressure", "design_temperature", "material", "power")


def node_kind(tag: str) -> str:
    return _KIND_BY_PREFIX.get(tag_prefix(tag) or "", "generic")


def source_hash(db: Db, project_id: int) -> str:
    """Faol hujjatlar to'plami izi: hujjatlar o'zgarsa, sxema eskirgan hisoblanadi."""
    return hashlib.sha256("|".join(f"{d.id}:{d.sha256}" for d in active_docs(db, project_id)).encode()).hexdigest()


def _equipment_node(tag: str, params: dict | None = None) -> dict:
    return {"id": f"eq:{tag}", "label": tag, "kind": node_kind(tag), "source": "document", "params": params or {}}


def generate(db: Db, project_id: int) -> dict:
    occurrences = project_occurrences(db, project_id)
    params = project_params(db, project_id)
    nodes: dict[str, dict] = {}

    shown = defaultdict(dict)
    for p in params:
        if p.param in _SHOWN_PARAMS and p.param not in shown[p.tag.tag]:
            shown[p.tag.tag][p.param] = display_value(p)
    for o in occurrences:   # uskuna: hujjatning o'z qatori (katak yoki blok atributi), matndagi eslatma emas
        if (o.tag.tag_class == TagClass.equipment and o.method == Method.cell
                and o.document.doc_type in _EQUIPMENT_DOCS):
            nodes.setdefault(f"eq:{o.tag.tag}", _equipment_node(o.tag.tag, shown.get(o.tag.tag)))

    def endpoint(value: str) -> str | None:
        """Quvur uchi: teg bo'lsa uskuna tuguni, aks holda chegara tuguni ("B.L.", "Drain")."""
        value = (value or "").strip()
        if not value:
            return None
        tags = normalize_tags(value)
        if len(tags) == 1:
            if f"eq:{tags[0]}" not in nodes:
                # Uskuna faqat quvurlar ro'yxatida uchraydi (P&ID, uskunalar ro'yxati yoki datasheetda yo'q):
                # yozuv xatosi bo'lishi mumkin, shuning uchun alohida belgilanadi.
                nodes[f"eq:{tags[0]}"] = {**_equipment_node(tags[0], shown.get(tags[0])), "line_list_only": True}
            return f"eq:{tags[0]}"
        label = value[:80]
        nodes.setdefault(f"bd:{label}", {"id": f"bd:{label}", "label": label, "kind": "boundary",
                                         "source": "document", "params": {}})
        return f"bd:{label}"

    ends = defaultdict(dict)
    for p in params:
        if p.param in ("line_from", "line_to") and p.tag.tag_class == TagClass.line:
            ends[p.tag.tag].setdefault(p.param, p.raw_value)
    lines = sorted({o.tag.tag for o in occurrences if o.tag.tag_class == TagClass.line})
    edges, unconnected = [], []
    for line in lines:
        raw_from, raw_to = ends[line].get("line_from", "").strip(), ends[line].get("line_to", "").strip()
        if raw_from or raw_to:
            src, dst = endpoint(raw_from), endpoint(raw_to)
            if src and dst and src != dst:
                edges.append({"id": f"ln:{line}", "from": src, "to": dst, "label": line, "source": "document",
                              "directed": True})
            else:
                # Hujjatda uchlardan biri yozilgan (yoki ikkalasi bir xil): taxmin bilan to'ldirilmaydi va
                # hujjatdagi ma'lumotga zid ulanish chizilmaydi.
                unconnected.append(f"{line} ({raw_from or '?'} → {raw_to or '?'})")
            continue
        inferred = _infer_from_geometry(line, occurrences)
        if inferred:
            a, b = inferred
            # Taxminiy ulanish: chizmadagi yaqinlik bo'yicha. Hujjatda yozilmagan, yo'nalishi noma'lum.
            edges.append({"id": f"ln:{line}", "from": a, "to": b, "label": line, "source": "inferred",
                          "directed": False})
        else:
            unconnected.append(line)
    result_nodes = [nodes[k] for k in sorted(nodes)]
    layout(result_nodes, edges)
    return {"nodes": result_nodes, "edges": sorted(edges, key=lambda e: e["id"]), "unconnected": unconnected}


MAX_REACH = 0.35   # ikkinchi eng yaqin uskunagacha masofa: chizma o'lchamining shu ulushidan oshmasligi kerak
MIN_MARGIN = 1.3   # uchinchi nomzod ikkinchisidan kamida shuncha marta uzoq bo'lishi kerak


def _infer_from_geometry(line: str, occurrences) -> tuple[str, str] | None:
    """P&ID (DXF) da quvur yozuviga eng yaqin ikki uskuna bloki — faqat tanlov aniq bo'lsa.

    Shartlar: varaqda kamida uch uskuna; ikkala nomzod yozuvga yaqin (chizma o'lchamiga nisbatan);
    uchinchi nomzod sezilarli uzoqroq. Aks holda None — quvur "uchi aniqlanmagan" bo'lib qoladi.
    """
    for o in occurrences:
        if o.tag.tag != line or o.document.doc_type != DocType.PID:
            continue
        m = _XY.match(o.location or "")
        if not m:
            continue
        x, y = float(m.group(1)), float(m.group(2))
        blocks = {}
        for e in occurrences:
            em = _XY.match(e.location or "")
            if (e.document_id == o.document_id and em and e.tag.tag_class == TagClass.equipment
                    and e.method == Method.cell and f"eq:{e.tag.tag}"):
                blocks[e.tag.tag] = (float(em.group(1)), float(em.group(2)))
        if len(blocks) < 3:
            continue
        xs, ys = [p[0] for p in blocks.values()], [p[1] for p in blocks.values()]
        extent = ((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2) ** 0.5
        near = sorted((((bx - x) ** 2 + (by - y) ** 2) ** 0.5, tag) for tag, (bx, by) in blocks.items())
        (d1, a), (d2, b), (d3, _) = near[0], near[1], near[2]
        if extent > 0 and d2 <= MAX_REACH * extent and d3 >= MIN_MARGIN * max(d2, 1e-9):
            a, b = sorted((a, b))
            return f"eq:{a}", f"eq:{b}"
    return None
