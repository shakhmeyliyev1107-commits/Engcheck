import pytest
from docx import Document as Docx

from engcheck.core.auth import create_user
from engcheck.core.models import KbChunk, KbSource
from engcheck.kb.chunking import chunk_pages
from engcheck.kb.index import bm25_rank, tokenize
from engcheck.kb.service import KbError, add_source, delete_source, prompt_text, reindex, search

from ..ai.fakes import FakeProvider

CORROSION = ("Sulfidation is corrosion of carbon steel resulting from reaction with sulfur compounds in high "
             "temperature environments above 260 °C. Chromium alloys improve resistance.")
AMINE = ("Amine stress corrosion cracking occurs in carbon steel welds exposed to lean amine. "
         "Post weld heat treatment is recommended for all carbon steel piping in amine service.")


@pytest.fixture
def lead(db):
    return create_user(db, "lead", "S3cret-pass", "lead")


@pytest.fixture
def engineer(db):
    return create_user(db, "eng", "S3cret-pass", "engineer")


def test_chunking_overlaps_and_keeps_page_numbers():
    text = " ".join(f"word{i}" for i in range(400))            # ~2800 belgi
    chunks = chunk_pages([(1, text), (2, "short page")], size=900, overlap=150)
    assert [p for p, _ in chunks][-1] == 2 and chunks[-1][1] == "short page"
    first = [c for p, c in chunks if p == 1]
    assert len(first) >= 3 and all(len(c) <= 900 for c in first)
    assert first[0].split()[-1] in first[1]                    # ustma-ust qism
    assert not any(c.startswith(" ") or c.endswith(" ") for c in first)
    assert "word399" in first[-1] and first[0].startswith("word0 ")


def test_chunking_skips_empty_pages():
    assert chunk_pages([(1, "   "), (2, "a b")]) == [(2, "a b")]


def test_tokenize_handles_cyrillic_and_case():
    assert tokenize("Коррозия углеродистой STEEL, 260°C") == ["коррозия", "углеродистой", "steel", "260"]


def test_bm25_ranks_relevant_first_and_drops_zero_scores():
    ranked = bm25_rank("amine cracking", [CORROSION, AMINE, "unrelated text about pumps"])
    assert [i for i, _ in ranked] == [1]


def test_add_text_source_search_and_engineer_sources_need_approval(db, settings, lead, engineer):
    src = add_source(db, settings, engineer, "Amin eslatmasi", "note", text=AMINE)
    assert src.approved is False and db.query(KbChunk).filter_by(source_id=src.id).count() == 1
    assert search(db, "amine cracking") == []                  # tasdiqlanmagan manba qidiruvda yo'q
    src.approved = True
    (hit,) = search(db, "amine cracking")
    assert (hit.source_id, hit.title, hit.page_no) == (src.id, "Amin eslatmasi", 1) and "amine" in hit.excerpt


def test_lead_sources_are_approved_and_status_rules_apply(db, settings, lead):
    old = add_source(db, settings, lead, "API 571 (2011)", "standard", text=CORROSION, standard_code="API RP 571",
                     edition="2011", status="superseded", license_type="licensed")
    gone = add_source(db, settings, lead, "Bekor qilingan", "standard", text=CORROSION + " withdrawn copy",
                      status="withdrawn")
    assert old.approved and old.approved_by == lead.id
    hits = search(db, "sulfidation carbon steel")
    assert [h.source_id for h in hits] == [old.id] and hits[0].status == "superseded"
    assert gone.id not in [h.source_id for h in hits]


def test_licensed_excerpt_is_short_and_never_goes_to_cloud(db, settings, lead):
    long_text = CORROSION + " " + "Further licensed detail. " * 40
    add_source(db, settings, lead, "API 571", "standard", text=long_text, standard_code="API RP 571",
               edition="2020", license_type="licensed")
    add_source(db, settings, lead, "Ichki qo'llanma", "literature", text=CORROSION + " internal note")
    licensed, internal = sorted(search(db, "sulfidation carbon steel", k=5), key=lambda h: h.license_type != "licensed")
    assert len(licensed.excerpt) <= 300 and licensed.excerpt.endswith("…")
    assert prompt_text(licensed, for_cloud=True) is None       # bulutga faqat nomi va sahifasi
    assert prompt_text(licensed, for_cloud=False).startswith("Sulfidation")
    assert prompt_text(internal, for_cloud=True).startswith("Sulfidation")


def test_add_docx_file_and_duplicate(db, settings, lead, tmp_path):
    p = tmp_path / "guide.docx"
    d = Docx(); d.add_paragraph(AMINE); d.save(p)
    src = add_source(db, settings, lead, "Qo'llanma", "literature", path=p, filename="guide.docx")
    assert src.sha256 and (settings.data_dir / "kb").is_dir() and search(db, "post weld heat treatment")
    with pytest.raises(KbError) as e:
        add_source(db, settings, lead, "Yana", "literature", path=p, filename="guide.docx")
    assert e.value.code == "duplicate"


def test_add_rejects_empty_unreadable_and_bad_values(db, settings, lead, tmp_path):
    with pytest.raises(KbError) as e:
        add_source(db, settings, lead, "Bo'sh", "note", text="   ")
    assert e.value.code == "empty"
    bad = tmp_path / "x.pdf"; bad.write_bytes(b"%PDF-1.4 broken")
    with pytest.raises(KbError) as e:
        add_source(db, settings, lead, "Buzilgan", "literature", path=bad, filename="x.pdf")
    assert e.value.code == "unreadable"
    with pytest.raises(KbError) as e:
        add_source(db, settings, lead, "x", "poem", text="abc def")
    assert e.value.code == "invalid"
    assert db.query(KbSource).count() == 0


def test_txt_file_in_cp1251_is_read(db, settings, lead, tmp_path):
    p = tmp_path / "gost.txt"
    p.write_bytes("Коррозия углеродистой стали при высокой температуре".encode("cp1251"))
    add_source(db, settings, lead, "ГОСТ", "literature", path=p, filename="gost.txt")
    assert search(db, "коррозия стали")


def test_delete_removes_chunks_and_file(db, settings, lead, tmp_path):
    p = tmp_path / "a.txt"; p.write_text(AMINE)
    src = add_source(db, settings, lead, "A", "note", path=p, filename="a.txt")
    stored = src.stored_path
    delete_source(db, settings, src.id, lead.id)
    assert db.query(KbChunk).count() == 0 and not __import__("pathlib").Path(stored).exists()


def test_hybrid_search_uses_embeddings_when_available(db, settings, lead):
    # So'zlar mos kelmaydi (BM25 topa olmaydi), lekin embedding yaqin.
    a = add_source(db, settings, lead, "A", "note", text="Yuqori haroratda oltingugurt ta'siridagi yemirilish")
    add_source(db, settings, lead, "B", "note", text="Nasos podshipniklarini moylash tartibi")
    vec = lambda t: [1.0, 0.0] if ("yemirilish" in t or "corrosion" in t) else [0.0, 1.0]
    provider = FakeProvider(vectors=vec)
    assert search(db, "sulfidation corrosion", provider=provider) == []         # hali indekslanmagan
    assert reindex(db, provider) == 2
    hits = search(db, "sulfidation corrosion", provider=provider)
    assert hits and hits[0].source_id == a.id


def test_reindex_to_cloud_skips_licensed(db, settings, lead):
    add_source(db, settings, lead, "API", "standard", text=CORROSION, license_type="licensed")
    add_source(db, settings, lead, "Ichki", "note", text=AMINE)
    cloud = FakeProvider(base_url="https://api.example.com", vectors=lambda t: [1.0, 0.0])
    assert reindex(db, cloud) == 1
    assert db.query(KbChunk).filter(KbChunk.embedding.isnot(None)).one().source.license_type == "internal"


def test_search_survives_provider_without_embeddings(db, settings, lead):
    add_source(db, settings, lead, "Ichki", "note", text=AMINE)
    assert search(db, "amine", provider=FakeProvider()) and search(db, "amine", provider=FakeProvider(fail="unreachable"))
