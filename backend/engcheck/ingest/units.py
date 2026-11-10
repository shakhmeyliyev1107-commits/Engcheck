"""Qiymat va birlikni ajratish, SI ga o'girish.

SI birliklar: bosim kPa(g), harorat °C, sarf m³/h, o'lcham mm, quvvat kW.
"""
import re
from dataclasses import dataclass

ATM_KPA = 101.325

PARAM_KIND: dict[str, str] = {
    "design_pressure": "pressure",
    "operating_pressure": "pressure",
    "design_temperature": "temperature",
    "operating_temperature": "temperature",
    "flow_rate": "flow",
    "size": "length",
    "power": "power",
    "material": "text",
    "pipe_class": "text",
    "fluid": "text",
}

SI_UNIT = {"pressure": "kPa(g)", "temperature": "°C", "flow": "m³/h", "length": "mm", "power": "kW"}

# birlik -> (ko'paytuvchi, siljish, taxminiy manometrik)
_PRESSURE = {
    "barg": (100.0, 0.0, False), "bar(g)": (100.0, 0.0, False), "бар(изб)": (100.0, 0.0, False),
    "bar": (100.0, 0.0, True), "бар": (100.0, 0.0, True),
    "bara": (100.0, -ATM_KPA, False), "bar(a)": (100.0, -ATM_KPA, False),
    "psig": (6.894757, 0.0, False), "psi": (6.894757, 0.0, True),
    "psia": (6.894757, -ATM_KPA, False),
    "kpag": (1.0, 0.0, False), "kpa(g)": (1.0, 0.0, False), "kpa": (1.0, 0.0, True),
    "кпа": (1.0, 0.0, True),
    "mpag": (1000.0, 0.0, False), "mpa(g)": (1000.0, 0.0, False), "mpa": (1000.0, 0.0, True),
    "мпа": (1000.0, 0.0, True),
    "kgf/cm2": (98.0665, 0.0, True), "kg/cm2": (98.0665, 0.0, True),
    "kg/cm2g": (98.0665, 0.0, False), "кгс/см2": (98.0665, 0.0, True),
    "атм": (ATM_KPA, 0.0, True), "atm": (ATM_KPA, 0.0, True),
}
_TEMPERATURE = {
    "c": (1.0, 0.0), "degc": (1.0, 0.0), "с": (1.0, 0.0),  # oxirgisi kirill "с"
    "f": (5 / 9, -32 * 5 / 9), "degf": (5 / 9, -32 * 5 / 9),
    "k": (1.0, -273.15),
}
_FLOW = {
    "m3/h": 1.0, "m3/hr": 1.0, "м3/ч": 1.0, "gpm": 0.2271247, "l/s": 3.6, "л/с": 3.6,
    "l/min": 0.06, "л/мин": 0.06,
}
_LENGTH = {"dn": 1.0, "nps": 25.4, "mm": 1.0, "мм": 1.0, "in": 25.4, "inch": 25.4, '"': 25.4, "″": 25.4, "m": 1000.0,
           "м": 1000.0, "cm": 10.0, "см": 10.0}
_POWER = {"kw": 1.0, "квт": 1.0, "w": 0.001, "вт": 0.001, "mw": 1000.0, "мвт": 1000.0,
          "hp": 0.7456999, "л.с.": 0.7354988}

_NUM = r"[+-]?\d[\d\s ]*(?:[.,]\d+)*"
_VALUE_RE = re.compile(rf"^({_NUM})\s*(.*)$")
_RANGE_RE = re.compile(rf"\d\s*(?:/|÷|\.\.\.?|…|\s[-–—]\s|\sto\s)\s*[+-]?\d")
_DN_RE = re.compile(r"^(?:DN|ДУ|Ду)\s*(\d+)$", re.IGNORECASE)
_NPS_RE = re.compile(r"^NPS\s*(\d+(?:[.,]\d+)?)$", re.IGNORECASE)


@dataclass
class Quantity:
    raw: str
    number: float | None
    unit: str | None
    si_value: float | None
    si_unit: str | None
    unit_known: bool
    assumed: bool = False


_AMBIGUOUS_RE = re.compile(r"^[+-]?[1-9]\d{0,2},\d{3}$")   # "1,200": 1200 ham, 1.2 ham bo'lishi mumkin
_GROUPED_RE = re.compile(r"^[+-]?\d{1,3}([.,])\d{3}(\1\d{3})+$")
_PLACEHOLDERS = {"N/A", "NA", "TBD", "TBA", "HOLD", "LATER", "VTA", "BY VENDOR", "ATM", "AMB",
                 "AMBIENT", "FV", "-", "–", "—"}


def is_placeholder(text: str) -> bool:
    return (text or "").strip().upper() in _PLACEHOLDERS


def is_unit(param: str, text: str) -> bool:
    """Matn shu parametr turi uchun taniladigan o'lchov birligimi."""
    kind = PARAM_KIND.get(param, "text")
    return kind != "text" and bool((text or "").strip()) and _convert(kind, 1.0, text) is not None


def _clean_value(raw: str) -> str:
    s = raw.replace("−", "-")
    s = re.sub(r"^[–—]\s*(?=\d)", "-", s)
    s = re.sub(r"^[≤≥<>=~≈]+\s*", "", s)
    s = re.sub(r"\([^)]*\)", " ", s)                                # (Note 1)
    s = re.sub(r"\s*/\s*F\.?V\.?\s*$", "", s, flags=re.IGNORECASE)   # "3.5 / FV": to'liq vakuum belgisi
    return s.strip()


def _to_float(text: str) -> float | None:
    s = re.sub(r"[\s ]", "", text)
    if _AMBIGUOUS_RE.match(s):
        return None
    m = _GROUPED_RE.match(s)
    if m:
        s = s.replace(m.group(1), "")
    elif "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.200,5
        else:
            s = s.replace(",", "")                     # 1,200.5
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norm_unit(unit: str) -> str:
    u = unit.strip().lower().replace("³", "3").replace("²", "2").replace("°", "").replace("º", "")
    u = re.sub(r"\s+", "", u)
    return u.rstrip(".") if u not in ("л.с.",) else u


def _convert(kind: str, number: float, unit: str) -> tuple[float, bool] | None:
    """(SI qiymat, taxminiy) yoki birlik tanilmasa None."""
    u = _norm_unit(unit)
    if kind == "pressure" and u in _PRESSURE:
        factor, offset, assumed = _PRESSURE[u]
        return number * factor + offset, assumed
    if kind == "temperature" and u in _TEMPERATURE:
        factor, offset = _TEMPERATURE[u]
        return number * factor + offset, False
    table = {"flow": _FLOW, "length": _LENGTH, "power": _POWER}.get(kind)
    if table and u in table:
        return number * table[u], False
    return None


def parse_quantity(text: str, param: str, unit_hint: str | None = None) -> Quantity:
    raw = (text or "").strip()
    kind = PARAM_KIND.get(param, "text")
    if kind == "text" or not raw:
        return Quantity(raw, None, None, None, None, True)
    si_unit = SI_UNIT[kind]

    if kind == "length":
        m = _DN_RE.match(raw)
        if m:
            return Quantity(raw, float(m.group(1)), "DN", float(m.group(1)), si_unit, True)
        m = _NPS_RE.match(raw)
        if m:
            n = _to_float(m.group(1))
            return Quantity(raw, n, "NPS", n * 25.4, si_unit, True)

    value = _clean_value(raw)
    if _RANGE_RE.search(value):
        # Diapazon bitta songa keltirilmaydi; R007 uni "o'qilmagan qiymat" sifatida ko'rsatadi.
        return Quantity(raw, None, None, None, None, True)
    m = _VALUE_RE.match(value)
    number = _to_float(m.group(1)) if m else None
    if number is None:
        return Quantity(raw, None, None, None, None, True)

    unit = m.group(2).strip() or (unit_hint or "").strip()
    if not unit:
        return Quantity(raw, number, None, None, None, False)
    converted = _convert(kind, number, unit)
    if converted is None:
        return Quantity(raw, number, unit, None, None, False)
    si_value, assumed = converted
    return Quantity(raw, number, unit, round(si_value, 6), si_unit, True, assumed)
