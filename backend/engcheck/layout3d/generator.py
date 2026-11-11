"""Hujjatlardan 3D joylashuv modelining yaratilgan qatlamini quradi.

Har uskunada joylashuv va o'lcham manbasi alohida belgilanadi: "document" (hujjatdan),
"assumed" (taxminiy/shartli), "partial" (o'lchamning bir qismi hujjatdan yoki talqin qilingan),
"conflict" (hujjatlar bir-biriga zid; datasheet qiymati olingan).
"""
import math
import re
from collections import defaultdict

from sqlalchemy.orm import Session as Db

from ..core.models import Discipline, DocType, Method, TagClass
from ..diagram.generator import node_kind
from ..review.rules.base import active_docs, doc_label, project_occurrences, project_params

# Turi bo'yicha shartli o'lcham (eni, chuqurligi, balandligi), metrda. Hujjatda o'lcham bo'lmasa ishlatiladi.
DEFAULT_SIZE = {"vessel": (2.0, 2.0, 6.0), "column": (2.5, 2.5, 20.0), "tank": (10.0, 10.0, 8.0),
                "reactor": (3.0, 3.0, 8.0), "exchanger": (6.0, 1.0, 1.0), "pump": (1.5, 0.8, 1.0),
                "compressor": (4.0, 2.5, 2.5), "heater": (5.0, 5.0, 10.0), "generic": (2.0, 2.0, 2.0)}
SHAPE = {"vessel": "cylinder_v", "column": "cylinder_v", "tank": "cylinder_v", "reactor": "cylinder_v",
         "exchanger": "cylinder_h"}
_EQUIPMENT_DOCS = (DocType.PID, DocType.EQUIPMENT_LIST, DocType.DATASHEET)
_SIZE_DOCS = (DocType.DATASHEET, DocType.EQUIPMENT_LIST)   # ustunlik tartibida
_DIM_PARAMS = ("size", "equipment_height", "equipment_length")
_NOMINAL = re.compile(r"\b(dn|nps|ду)\b|\d\s*(\"|in\b|inch)", re.I)
_XY = re.compile(r"^x=(-?\d+(?:\.\d+)?),y=(-?\d+(?:\.\d+)?)$")
MIN_DIM, MAX_DIM = 0.05, 200.0     # metr: bundan tashqaridagi hujjat qiymati ishlatilmaydi
MM_THRESHOLD = 2000.0              # chizma o'lchami bundan katta bo'lsa birlik millimetr deb olinadi
GRID_STEP = 12.0


def shape_of(kind: str) -> str:
    return SHAPE.get(kind, "box")


def _dim(value_mm: float | None) -> float | None:
    if value_mm is None:
        return None
    metres = value_mm / 1000.0
    return round(metres, 3) if MIN_DIM <= metres <= MAX_DIM else None


def _size(kind: str, dims: dict, conflict: bool = False) -> tuple[float, float, float, str]:
    """(w, d, h, manba). Hujjatdagi diametr/balandlik/uzunlik bo'lsa ishlatiladi, yetishmagani shartli.

    Manba "document" faqat ikkala o'lcham ham o'z nomi bilan topilganda qo'yiladi. Balandlik o'rniga uzunlik
    (yoki aksincha) ishlatilgan bo'lsa — bu talqin, shuning uchun "partial"; hujjatlar bir-biriga zid bo'lsa — "conflict".
    """
    w, d, h = DEFAULT_SIZE.get(kind, DEFAULT_SIZE["generic"])
    diameter, height, length = _dim(dims.get("size")), _dim(dims.get("equipment_height")), _dim(dims.get("equipment_length"))
    shape = shape_of(kind)
    if shape == "box":
        return w, d, h, "assumed"   # quti shakli uchun hujjatlardan gabarit olinmaydi
    known, guessed = 0, False
    if shape == "cylinder_v":
        if diameter:
            w = d = diameter; known += 1
        if height or length:
            h = height or length; known += 1; guessed = not height
    else:
        if diameter:
            d = h = diameter; known += 1
        if length or height:
            w = length or height; known += 1; guessed = not length
    if not known:
        return w, d, h, "assumed"
    if conflict:
        return w, d, h, "conflict"
    return w, d, h, "document" if known == 2 and not guessed else "partial"


def _dimensions(params) -> tuple[dict, set]:
    """Uskuna gabaritlari: faqat datasheet va uskunalar ro'yxatidan; datasheet ustun. ({teg: {param: mm}}, zid teglar)."""
    found = defaultdict(lambda: defaultdict(list))
    for p in params:
        if (p.param not in _DIM_PARAMS or p.si_value is None or p.tag.tag_class != TagClass.equipment
                or p.document.doc_type not in _SIZE_DOCS):
            continue
        # "DN 80" — shtutser yoki quvur nominal o'lchami, qobiq diametri emas
        if p.param == "size" and _NOMINAL.search(f"{p.raw_unit or ''} {p.raw_value or ''}"):
            continue
        found[p.tag.tag][p.param].append((_SIZE_DOCS.index(p.document.doc_type), p.id, p.si_value))
    dims, conflicts = defaultdict(dict), set()
    for tag, by_param in found.items():
        for param, values in by_param.items():
            values.sort()
            chosen = values[0][2]
            dims[tag][param] = chosen
            if any(abs(v - chosen) > 0.01 * max(abs(chosen), 1.0) for _, _, v in values[1:]):
                conflicts.add(tag)
    return dims, conflicts


def generate(db: Db, project_id: int) -> dict:
    occurrences = project_occurrences(db, project_id)
    dims, conflicts = _dimensions(project_params(db, project_id))

    civil = [d for d in active_docs(db, project_id) if d.discipline == Discipline.civil]
    placed: dict[str, tuple[float, float]] = {}
    plot = None
    for doc in sorted(civil, key=lambda d: -d.id):   # eng oxirgi yuklangan bosh reja
        coords = {}
        for o in occurrences:
            m = _XY.match(o.location or "")
            if (o.document_id == doc.id and m and o.tag.tag_class == TagClass.equipment and o.method == Method.cell):
                coords.setdefault(o.tag.tag, (float(m.group(1)), float(m.group(2))))
        if coords:
            placed, plot = coords, doc
            break

    tags = {o.tag.tag for o in occurrences
            if o.tag.tag_class == TagClass.equipment and o.method == Method.cell
            and (o.document.doc_type in _EQUIPMENT_DOCS or (plot is not None and o.document_id == plot.id))}

    unit = None
    max_x = min_y = 0.0
    positions: dict[str, tuple[float, float]] = {}
    if placed:
        xs, ys = [p[0] for p in placed.values()], [p[1] for p in placed.values()]
        extent = max(max(xs) - min(xs), max(ys) - min(ys))
        # DXF birligini ishonchli aniqlab bo'lmaydi: bu TAXMIN va modelda aniq ko'rsatiladi.
        unit = "mm" if extent > MM_THRESHOLD else "m"
        factor = 0.001 if unit == "mm" else 1.0
        for tag, (x, y) in placed.items():
            # Chizmaning o'z koordinatalari saqlanadi (siljitilmaydi): bosh reja yangilansa ham qo'lda
            # ko'chirilgan uskunalar hujjatdagilarga nisbatan o'z joyida qoladi.
            positions[tag] = (round(x * factor, 3), round(y * factor, 3))
        max_x, min_y = max(p[0] for p in positions.values()), min(p[1] for p in positions.values())

    loose = sorted(t for t in tags if t not in positions)
    cols = max(1, math.ceil(math.sqrt(len(loose))))
    x0 = max_x + (2 * GRID_STEP if positions else 0.0)   # taxminiy joylashganlar bosh rejadan chetda turadi
    items = []
    for tag in sorted(tags):
        kind = node_kind(tag)
        w, d, h, size_source = _size(kind, dims.get(tag, {}), tag in conflicts)
        if tag in positions:
            (x, y), position_source = positions[tag], "document"
        else:
            k = loose.index(tag)
            x, y, position_source = x0 + (k % cols) * GRID_STEP, min_y + (k // cols) * GRID_STEP, "assumed"
        items.append({"id": f"eq:{tag}", "label": tag, "kind": kind, "shape": shape_of(kind), "source": "document",
                      "x": float(x), "y": float(y), "z": 0.0, "rot": 0.0, "w": w, "d": d, "h": h,
                      "position_source": position_source, "size_source": size_source})
    return {"items": items, "unit_assumed": unit, "plot_plan": doc_label(plot) if plot else None}
