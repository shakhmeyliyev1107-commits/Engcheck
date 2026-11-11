"""3D model tahrirlari: tekshirish va yaratilgan qatlam ustiga qo'llash."""
import copy
import math
import unicodedata

from .generator import DEFAULT_SIZE, shape_of

OPS = ("move", "rotate", "resize", "rename", "add_item", "remove_item")
MAX_LABEL, MAX_ID, MAX_COORD, MAX_SIZE, MIN_SIZE = 80, 120, 100_000, 500.0, 0.05
MANUAL_KINDS = tuple(DEFAULT_SIZE)


class EditError(Exception):
    """code: invalid_op | not_applicable | nothing_to_undo | nothing_to_redo | no_layout"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _text(value, limit: int) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(unicodedata.category(c) in ("Cc", "Cf") for c in value)):
        raise EditError("invalid_op")
    return value.strip()


def _number(value, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EditError("invalid_op")
    if isinstance(value, float) and not math.isfinite(value):
        raise EditError("invalid_op")
    if not low <= value <= high:
        raise EditError("invalid_op")
    return round(float(value), 3)


def validate_op(op) -> dict:
    if not isinstance(op, dict) or op.get("op") not in OPS:
        raise EditError("invalid_op")
    kind = op["op"]
    item_id = _text(op.get("id"), MAX_ID)
    if kind == "move":
        return {"op": kind, "id": item_id, "x": _number(op.get("x"), -MAX_COORD, MAX_COORD),
                "y": _number(op.get("y"), -MAX_COORD, MAX_COORD)}
    if kind == "rotate":
        return {"op": kind, "id": item_id, "rot": _number(op.get("rot"), -360, 360) % 360}
    if kind == "resize":
        return {"op": kind, "id": item_id, **{k: _number(op.get(k), MIN_SIZE, MAX_SIZE) for k in ("w", "d", "h")}}
    if kind == "rename":
        return {"op": kind, "id": item_id, "label": _text(op.get("label"), MAX_LABEL)}
    if kind == "add_item":
        if not item_id.startswith("m:") or op.get("kind") not in MANUAL_KINDS:
            raise EditError("invalid_op")   # qo'lda qo'shilgan uskuna hujjatdan olingandek ko'rinmasligi kerak
        return {"op": kind, "id": item_id, "label": _text(op.get("label"), MAX_LABEL), "kind": op["kind"],
                "x": _number(op.get("x"), -MAX_COORD, MAX_COORD), "y": _number(op.get("y"), -MAX_COORD, MAX_COORD)}
    return {"op": kind, "id": item_id}


def apply_one(model: dict, op: dict) -> bool:
    items = {i["id"]: i for i in model["items"]}
    kind, item = op["op"], items.get(op["id"])
    if kind == "add_item":
        if item is not None:
            return False
        w, d, h = DEFAULT_SIZE[op["kind"]]
        model["items"].append({"id": op["id"], "label": op["label"], "kind": op["kind"], "shape": shape_of(op["kind"]),
                               "source": "manual", "x": op["x"], "y": op["y"], "z": 0.0, "rot": 0.0, "w": w, "d": d,
                               "h": h, "position_source": "manual", "size_source": "assumed"})
        return True
    if item is None:
        return False
    if kind == "move":
        if (op["x"], op["y"]) != (item["x"], item["y"]):   # joyida qolgan uskuna "qo'lda" deb belgilanmaydi
            item.update(x=op["x"], y=op["y"], position_source="manual")
    elif kind == "rotate":
        item["rot"] = op["rot"]
    elif kind == "resize":
        if (op["w"], op["d"], op["h"]) != (item["w"], item["d"], item["h"]):
            item.update(w=op["w"], d=op["d"], h=op["h"], size_source="manual")
    elif kind == "rename":
        item.setdefault("original_label", item["label"])
        item["label"] = op["label"]
        item["renamed"] = item["label"] != item["original_label"]
    elif kind == "remove_item":
        model["items"] = [i for i in model["items"] if i["id"] != op["id"]]
    return True


def apply_edits(generated: dict, ops: list[dict]) -> tuple[dict, list[int]]:
    model = copy.deepcopy(generated)
    return model, [i for i, op in enumerate(ops) if not apply_one(model, op)]


def differences(generated: dict, effective: dict) -> list[dict]:
    """Model hujjatlardan nimasi bilan farq qiladi. Taxminiy joy yoki shartli o'lchamni o'zgartirish farq emas."""
    g, e = {i["id"]: i for i in generated["items"]}, {i["id"]: i for i in effective["items"]}
    out = []
    for item_id, item in e.items():
        base = g.get(item_id)
        if base is None:
            out.append({"kind": "item_added", "label": item["label"]})
            continue
        if item["label"] != base["label"]:
            out.append({"kind": "item_renamed", "label": f"{base['label']} → {item['label']}"})
        if base["position_source"] == "document" and (item["x"], item["y"]) != (base["x"], base["y"]):
            out.append({"kind": "position_changed", "label": base["label"]})
        if base["size_source"] in ("document", "partial", "conflict") and (item["w"], item["d"], item["h"]) != (base["w"], base["d"], base["h"]):
            out.append({"kind": "size_changed", "label": base["label"]})
    out += [{"kind": "item_removed", "label": i["label"]} for item_id, i in g.items() if item_id not in e]
    return out
