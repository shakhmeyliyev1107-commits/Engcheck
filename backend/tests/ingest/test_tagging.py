import pytest

from engcheck.core.models import TagClass
from engcheck.ingest.tagging import classify, find_tags, normalize_tag


@pytest.mark.parametrize("raw,canon", [
    ("p-101 a", "P-101A"), ("P101A", "P-101A"), ("P-101A", "P-101A"), ("V-2001", "V-2001"),
    ("pt1001", "PT-1001"), (' 10"-hc-1001-a1a ', '10"-HC-1001-A1A'),
    ("10″-HC-1001-A1A", '10"-HC-1001-A1A'),
    ("hello", None), ("", None), ("12345", None), ("Total", None),
])
def test_normalize_tag(raw, canon):
    assert normalize_tag(raw) == canon


@pytest.mark.parametrize("tag,cls", [
    ("P-101A", TagClass.equipment), ("E-301", TagClass.equipment),
    ("PT-1001", TagClass.instrument), ("FIC-2003", TagClass.instrument),
    ("PSV-1001", TagClass.instrument), ('10"-HC-1001-A1A', TagClass.line),
])
def test_classify(tag, cls):
    assert classify(tag) == cls


def test_find_tags_classes():
    got = dict(find_tags('Pump P-101A feeds 10"-HC-1001-A1A, see PT-1001 and FIC-2003'))
    assert got == {"P-101A": TagClass.equipment, '10"-HC-1001-A1A': TagClass.line,
                   "PT-1001": TagClass.instrument, "FIC-2003": TagClass.instrument}


def test_find_tags_ignores_document_numbers():
    assert find_tags("Ref. P&ID GP-PID-001 Rev A, datasheet GP-DS-V101") == []


def test_find_tags_deduplicates():
    assert find_tags("V-101 and V-101 again") == [("V-101", TagClass.equipment)]


def test_line_number_parts_are_not_separate_tags():
    assert [t for t, _ in find_tags('6"-AM-1004-A1A')] == ['6"-AM-1004-A1A']
