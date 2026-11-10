import json

import pytest

from engcheck.ai.assist import AssistError, explain_finding, extract_json
from engcheck.ai.base import AiError
from engcheck.ai.registry import Resolution
from engcheck.ai.review import ai_findings
from engcheck.core.auth import create_user
from engcheck.core.models import AuditLog, DocPage, DocType, Finding, FindingAiNote, FindingStatus, KbSource, Rule
from engcheck.kb.service import KbError, add_source, propose_lesson, search
from engcheck.review.engine import run_review

from ..review.factories import EQL, PID, make_doc, make_param
from .fakes import FakeProvider

GUIDE = "Design pressure shall not be less than the maximum operating pressure of the vessel."
LICENSED = "Licensed clause: design pressure of a pressure vessel must exceed operating pressure with margin."


@pytest.fixture
def lead(db):
    return create_user(db, "lead", "S3cret-pass", "lead")


@pytest.fixture
def finding(db, project):
    a, b = make_doc(db, project, PID, "GP-PID-001"), make_doc(db, project, EQL, "GP-EQL-001")
    make_param(db, project, a, "V-101", "design_pressure", "16 barg", 1600.0)
    make_param(db, project, b, "V-101", "design_pressure", "14 barg", 1400.0)
    run = run_review(db, project.id, None)
    return db.query(Finding).filter_by(run_id=run.id).one()


def local(replies):
    p = FakeProvider(replies=replies)
    return Resolution(p, "local"), p


def cloud(replies):
    p = FakeProvider(base_url="https://api.example.com", replies=replies)
    return Resolution(p, "online"), p


@pytest.mark.parametrize("text,expected", [
    ('{"a": 1}', {"a": 1}), ('```json\n{"a": 1}\n```', {"a": 1}), ('Mana javob:\n[{"q": "x"}]\nrahmat', [{"q": "x"}]),
    ('{"a": "qavs } ichida"}', {"a": "qavs } ichida"}), ("JSON yo'q", None), ("", None), ('{"a": ', None),
])
def test_extract_json(text, expected):
    assert extract_json(text) == expected


def test_note_keeps_only_citations_that_were_provided(db, settings, lead, finding):
    src = add_source(db, settings, lead, "Idish qo'llanmasi", "literature", text=GUIDE)
    res, p = local([json.dumps({"explanation": "Farq datasheetda [K1]. Yana [K7] ga qarang.",
                                "citations": ["K1", "K7", "API 510"], "assumptions": ["Datasheet eskirgan bo'lishi mumkin"]})])
    note = explain_finding(db, finding, lead, "uz", res)
    assert note.status == "proposed" and note.ai_mode == "local" and note.provider_name == "soxta"
    assert [c["key"] for c in note.citations] == ["K1"] and note.citations[0]["source_id"] == src.id
    assert "[K7]" not in note.text and "[K1]" in note.text
    assert note.assumptions == ["Datasheet eskirgan bo'lishi mumkin"]
    system, user = p.calls[0]
    assert "V-101" in user and "16 barg" in user and "14 barg" in user and GUIDE in user
    assert "Uzbek" in system
    assert finding.status == FindingStatus.new                       # AI topilma holatini o'zgartirmaydi


def test_note_is_audited_without_text(db, settings, lead, finding):
    res, _ = local([json.dumps({"explanation": "Izoh", "citations": [], "assumptions": []})])
    note = explain_finding(db, finding, lead, "uz", res)
    row = db.query(AuditLog).filter_by(action="ai.note").one()
    assert row.object_id == note.id and row.details == {"finding_id": finding.id, "provider": "soxta", "mode": "local"}


def test_licensed_text_is_withheld_from_cloud_but_sent_to_local(db, settings, lead, finding):
    add_source(db, settings, lead, "ASME VIII", "standard", text=LICENSED, standard_code="ASME BPVC VIII-1",
               edition="2023", license_type="licensed")
    reply = json.dumps({"explanation": "x [K1]", "citations": ["K1"], "assumptions": []})
    res, p = cloud([reply])
    note = explain_finding(db, finding, lead, "en", res)
    assert LICENSED not in p.calls[0][1] and "ASME BPVC VIII-1" in p.calls[0][1] and "2023" in p.calls[0][1]
    assert note.citations[0]["standard_code"] == "ASME BPVC VIII-1" and len(note.citations[0]["excerpt"]) <= 300
    res, p = local([reply])
    explain_finding(db, finding, lead, "en", res)
    assert LICENSED in p.calls[0][1]


def test_superseded_source_is_flagged_in_prompt_and_citation(db, settings, lead, finding):
    add_source(db, settings, lead, "Eski nashr", "standard", text=GUIDE, standard_code="X-1", edition="2001",
               status="superseded")
    res, p = local([json.dumps({"explanation": "x [K1]", "citations": ["K1"], "assumptions": []})])
    note = explain_finding(db, finding, lead, "uz", res)
    assert "superseded" in p.calls[0][1] and note.citations[0]["status"] == "superseded"


@pytest.mark.parametrize("reply", ["Bu JSON emas", json.dumps({"citations": []}), json.dumps({"explanation": "  "}),
                                   json.dumps(["ro'yxat"])])
def test_unusable_reply_is_an_error_not_a_note(db, lead, finding, reply):
    res, _ = local([reply])
    with pytest.raises(AssistError) as e:
        explain_finding(db, finding, lead, "uz", res)
    assert e.value.code == "bad_response" and db.query(FindingAiNote).count() == 0


def test_no_provider_and_provider_failure(db, lead, finding):
    with pytest.raises(AssistError) as e:
        explain_finding(db, finding, lead, "uz", Resolution(None, "none", "cloud_not_allowed"))
    assert e.value.code == "cloud_not_allowed"
    with pytest.raises(AssistError) as e:
        explain_finding(db, finding, lead, "uz", Resolution(FakeProvider(replies=[AiError("auth")]), "local"))
    assert e.value.code == "auth"


# ---------- AI tekshiruv ----------
@pytest.fixture
def doc_with_text(db, project):
    d = make_doc(db, project, DocType.OTHER, "GP-NOTE-001")   # qoidalarga ta'sir qilmaydigan hujjat turi
    db.add(DocPage(document_id=d.id, page_no=1, text="Pump P-101A  discharge has no check valve.\nV-101 PSV set at 20 barg."))
    db.flush()
    return d


def test_ai_findings_require_verbatim_quote(db, project, doc_with_text):
    reply = json.dumps([
        {"quote": "P-101A discharge has no check valve", "issue": "Teskari klapan yo'q", "recommendation": "Qo'shing", "severity": "major"},
        {"quote": "PSV set at 25 barg", "issue": "Uydirma iqtibos", "recommendation": "-", "severity": "critical"},
        {"quote": "ok", "issue": "Juda qisqa iqtibos", "recommendation": "-", "severity": "minor"},
        {"issue": "Iqtibossiz"}, "satr",
    ])
    drafts, stats, error = ai_findings(db, project.id, FakeProvider(replies=[reply]), "uz")
    assert error is None and len(drafts) == 1
    assert stats == {"pages_reviewed": 1, "pages_skipped": 0, "pages_failed": 0, "pages_truncated": 0, "rejected": 4}
    d = drafts[0]
    assert d.rule_code == "AI01" and d.tag_text == "P-101A" and d.description_key == "ai_text"
    assert d.confidence == "low" and d.severity == "major"
    assert d.evidence[0].document_id == doc_with_text.id and d.evidence[0].page_no == 1


def test_run_review_with_ai_marks_source_and_mode(db, project, doc_with_text):
    reply = json.dumps([{"quote": "V-101 PSV set at 20 barg", "issue": "PSV bosimi tekshirilsin",
                         "recommendation": "Loyiha bosimi bilan solishtiring", "severity": "weird"}])
    run = run_review(db, project.id, None, resolution=Resolution(FakeProvider(replies=[reply]), "local"), locale="uz")
    (f,) = db.query(Finding).filter_by(run_id=run.id).all()
    assert (run.ai_mode, run.ai_provider) == ("local", "soxta")
    assert (f.source_type, f.confidence, f.severity, f.rule.code, f.status) == ("ai", "low", "minor", "AI01", "new")
    assert f.description == "PSV bosimi tekshirilsin" and "V-101 PSV set at 20 barg" in f.rationale
    assert "AI" in f.rationale


def test_provider_dying_mid_review_keeps_rule_findings(db, project, finding, doc_with_text):
    run = run_review(db, project.id, None, resolution=Resolution(FakeProvider(replies=[AiError("unreachable")]), "online"))
    assert [f.rule.code for f in db.query(Finding).filter_by(run_id=run.id)] == ["R001"]
    assert run.errors == [{"rule": "AI01", "error": "unreachable"}] and run.ai_mode == "online"


def test_unavailable_ai_is_recorded_with_reason(db, project, finding):
    run = run_review(db, project.id, None, resolution=Resolution(None, "none", "cloud_not_allowed"))
    assert (run.ai_mode, run.ai_provider, run.ai_note) == ("none", None, "cloud_not_allowed")


def test_disabled_ai_rule_skips_ai(db, project, doc_with_text):
    run_review(db, project.id, None)
    db.query(Rule).filter_by(code="AI01").one().enabled = False
    db.flush()
    p = FakeProvider(replies=["[]"])
    run = run_review(db, project.id, None, resolution=Resolution(p, "local"))
    assert p.calls == [] and run.ai_mode == "none" and run.ai_note == "rule_disabled"


def test_large_documents_are_capped_and_counted(db, project):
    d = make_doc(db, project, PID, "GP-PID-009")
    for n in range(1, 46):
        db.add(DocPage(document_id=d.id, page_no=n, text=f"page {n} text " + "x" * 50))
    db.add(DocPage(document_id=d.id, page_no=99, text="   "))
    db.flush()
    p = FakeProvider(replies=["[]"] * 60)
    _, stats, _ = ai_findings(db, project.id, p, "uz")
    assert stats["pages_reviewed"] == 40 and stats["pages_skipped"] == 5 and len(p.calls) == 40


def test_bad_json_page_is_counted_not_fatal(db, project, doc_with_text):
    drafts, stats, _ = ai_findings(db, project.id, FakeProvider(replies=["uzr, bilmayman"]), "uz")
    assert drafts == [] and stats["pages_failed"] == 1


# ---------- Nazoratli o'rganish ----------
def test_lesson_needs_a_decided_finding_and_lead_approval(db, settings, lead, finding):
    with pytest.raises(KbError):
        propose_lesson(db, settings, finding, lead)               # hali qaror qilinmagan
    finding.status = FindingStatus.confirmed
    src = propose_lesson(db, settings, finding, lead, "V-101: datasheet P&ID dan orqada qolgan; datasheet Rev B da tuzatildi.")
    assert (src.kind, src.approved, src.origin_finding_id) == ("lesson", False, finding.id)
    assert search(db, "datasheet orqada qolgan") == []            # tasdiqlanmaguncha qidiruvda yo'q
    src.approved = True
    assert search(db, "datasheet orqada qolgan")[0].kind == "lesson"
    assert db.query(KbSource).count() == 1


def test_lesson_default_text_states_facts_and_decision(db, settings, lead, finding):
    finding.status = FindingStatus.rejected
    src = propose_lesson(db, settings, finding, lead)
    text = src.chunks[0].text
    assert "V-101" in text and "16 barg" in text and "rejected" in text
