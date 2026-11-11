"""Tahrirlar qatlami: muhandis amallarini tekshirish va yaratilgan qatlam ustiga qo'llash."""
import copy
import math
import unicodedata

from .generator import KINDS

OPS = ("move", "add_node", "remove_node", "rename_node", "add_edge", "remove_edge")
MAX_LABEL, MAX_ID, MAX_COORD = 80, 120, 100_000
MANUAL_KINDS = tuple(k for k in KINDS if k != "boundary")   # chegara tugunlari faqat hujjatdan


def _clean(text: str) -> bool:
    """Boshqaruv va format belgilari yo'q (masalan, matn yo'nalishini teskari qiluvchi U+202E)."""
    return not any(unicodedata.category(c) in ("Cc", "Cf") for c in text)


class EditError(Exception):
    """code: invalid_op | not_applicable | nothing_to_undo | nothing_to_redo | no_diagram"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _id(value) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_ID or not _clean(value):
        raise EditError("invalid_op")
    return value


def _label(value, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > MAX_LABEL or not _clean(value):
        raise EditError("invalid_op")
    if required and not value.strip():
        raise EditError("invalid_op")
    return value.strip()


def _coord(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EditError("invalid_op")
    if isinstance(value, float) and not math.isfinite(value):
        raise EditError("invalid_op")
    if abs(value) > MAX_COORD:   # juda katta butun son ham shu yerda ushlanadi
        raise EditError("invalid_op")
    return round(float(value), 1)


def validate_op(op) -> dict:
    """Amalni tekshirib, tozalangan nusxasini qaytaradi. Noto'g'ri bo'lsa EditError('invalid_op')."""
    if not isinstance(op, dict) or op.get("op") not in OPS:
        raise EditError("invalid_op")
    kind = op["op"]
    if kind == "move":
        return {"op": kind, "id": _id(op.get("id")), "x": _coord(op.get("x")), "y": _coord(op.get("y"))}
    if kind == "add_node":
        node_id = _id(op.get("id"))
        if not node_id.startswith("m:") or op.get("kind") not in MANUAL_KINDS:
            raise EditError("invalid_op")   # qo'lda qo'shilgan element hujjatdan olingandek ko'rinmasligi kerak
        return {"op": kind, "id": node_id, "label": _label(op.get("label")), "kind": op["kind"],
                "x": _coord(op.get("x")), "y": _coord(op.get("y"))}
    if kind == "rename_node":
        return {"op": kind, "id": _id(op.get("id")), "label": _label(op.get("label"))}
    if kind == "add_edge":
        edge_id = _id(op.get("id"))
        if not edge_id.startswith("m:"):
            raise EditError("invalid_op")
        return {"op": kind, "id": edge_id, "from": _id(op.get("from")), "to": _id(op.get("to")),
                "label": _label(op.get("label", ""), required=False)}
    return {"op": kind, "id": _id(op.get("id"))}   # remove_node, remove_edge


def apply_one(diagram: dict, op: dict) -> bool:
    """Bitta amalni qo'llaydi (joyida). Qo'llab bo'lmasa False — sxema o'zgarmaydi."""
    nodes = {n["id"]: n for n in diagram["nodes"]}
    edges = {e["id"]: e for e in diagram["edges"]}
    kind = op["op"]
    if kind == "move":
        if op["id"] not in nodes:
            return False
        nodes[op["id"]].update(x=op["x"], y=op["y"], moved=True)
    elif kind == "add_node":
        if op["id"] in nodes:
            return False
        diagram["nodes"].append({"id": op["id"], "label": op["label"], "kind": op["kind"], "source": "manual",
                                 "params": {}, "x": op["x"], "y": op["y"]})
    elif kind == "remove_node":
        if op["id"] not in nodes:
            return False
        diagram["nodes"] = [n for n in diagram["nodes"] if n["id"] != op["id"]]
        diagram["edges"] = [e for e in diagram["edges"] if op["id"] not in (e["from"], e["to"])]
    elif kind == "rename_node":
        if op["id"] not in nodes:
            return False
        node = nodes[op["id"]]
        node.setdefault("original_label", node["label"])
        node["label"] = op["label"]
        # Hujjatdagi uskuna nomi o'zgartirilgan: endi u hujjatdagidek ko'rinmasligi kerak.
        node["renamed"] = node["label"] != node["original_label"]
    elif kind == "add_edge":
        if op["id"] in edges or op["from"] not in nodes or op["to"] not in nodes or op["from"] == op["to"]:
            return False
        if any((e["from"], e["to"]) == (op["from"], op["to"]) for e in diagram["edges"]):
            return False   # shu yo'nalishdagi ulanish allaqachon bor
        diagram["edges"].append({"id": op["id"], "from": op["from"], "to": op["to"], "label": op["label"],
                                 "source": "manual", "directed": True})
    elif kind == "remove_edge":
        if op["id"] not in edges:
            return False
        diagram["edges"] = [e for e in diagram["edges"] if e["id"] != op["id"]]
    return True


def apply_edits(generated: dict, ops: list[dict]) -> tuple[dict, list[int]]:
    """(ko'rsatiladigan sxema, qo'llanmagan amallar indekslari). Yaratilgan qatlam o'zgarmaydi."""
    diagram = copy.deepcopy(generated)
    skipped = [i for i, op in enumerate(ops) if not apply_one(diagram, op)]
    return diagram, skipped


def differences(generated: dict, effective: dict) -> list[dict]:
    """Sxema hujjatlardan nimasi bilan farq qiladi (ko'chirish farq emas)."""
    g_nodes, e_nodes = {n["id"]: n for n in generated["nodes"]}, {n["id"]: n for n in effective["nodes"]}
    g_edges, e_edges = {e["id"]: e for e in generated["edges"]}, {e["id"]: e for e in effective["edges"]}
    out = []
    for i, n in e_nodes.items():
        if i not in g_nodes:
            out.append({"kind": "node_added", "label": n["label"]})
        elif n["label"] != g_nodes[i]["label"]:
            out.append({"kind": "node_renamed", "label": f"{g_nodes[i]['label']} → {n['label']}"})
    out += [{"kind": "node_removed", "label": n["label"]} for i, n in g_nodes.items() if i not in e_nodes]
    out += [{"kind": "edge_added", "label": e["label"] or f"{e['from']} → {e['to']}"} for i, e in e_edges.items() if i not in g_edges]
    for i, e in g_edges.items():   # tuguni o'chirilgani uchun yo'qolgan qirra alohida sanalmaydi
        if i not in e_edges and e["from"] in e_nodes and e["to"] in e_nodes:
            out.append({"kind": "edge_removed", "label": e["label"]})
    return out
