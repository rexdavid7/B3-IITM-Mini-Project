from types import SimpleNamespace
import json

from streamlit.testing.v1 import AppTest

from app import (
    INTERNAL_SYNTHETIC_WARNING,
    SYNTHETIC_DATA_PROVENANCE,
    build_submissions,
    export_payload,
    safe_supplier_error,
    suggest_supplier_name,
)


class Upload:
    def __init__(self, name, data=b"pdf-data"):
        self.name = name
        self.data = data

    def getvalue(self):
        return self.data


def test_build_submissions_accepts_complete_metadata():
    submissions, errors = build_submissions(
        [Upload("Apex.pdf")],
        [{"supplier_name": "Apex", "submission_date": "2026-10-29", "experience_rating": "7.5"}],
    )
    assert errors == []
    assert submissions[0].supplier_name == "Apex"
    assert submissions[0].experience_rating == 7.5


def test_supplier_name_suggestion_uses_document_title_and_humanizes_filename():
    path = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "supplier_proposals" / "nexaworks_proposal.pdf"
    assert suggest_supplier_name(path.name, path.read_bytes()) == "NexaWorks"
    assert suggest_supplier_name("nexaworks_proposal.pdf", b"not a pdf") == "Nexaworks"


def test_build_submissions_reports_missing_invalid_and_duplicate_metadata():
    submissions, errors = build_submissions(
        [Upload("a.pdf"), Upload("b.pdf")],
        [
            {"supplier_name": "Apex", "submission_date": "2026-02-30", "experience_rating": "NaN"},
            {"supplier_name": "apex", "submission_date": "", "experience_rating": ""},
        ],
    )
    assert submissions == []
    assert any("valid submission date" in error for error in errors)
    assert any("finite number" in error for error in errors)
    assert any("unique" in error for error in errors)


def test_safe_error_text_and_run_export_keep_details_without_raw_exception():
    assert "unreadable" in safe_supplier_error("PDFDocumentError")
    run = {
        "rfp_run_id": "run-1",
        "created_at": "2026-10-29T10:00:00+00:00",
        "status": "COMPLETED_WITH_ERRORS",
        "details": {
            "criteria_snapshot": [{"criterion_id": 1, "weight": 100}],
            "errors": [{"supplier_name": "Bad PDF", "error_type": "PDFDocumentError", "message": "private raw detail"}],
        },
        "suppliers": [{"result": {"supplier_name": "Apex", "absolute_score": 9.999999999999998, "ppi": 100.0, "scores": {"1": 9.999999999999998}, "benchmarks": {"1": 9.999999999999998}, "gaps": {"1": -0.000000000000002}, "relative_performance": {"1": 99.99999999999998}, "criterion_results": [{"score": 10.0, "evidence": "evidence"}], "warnings": ["warning"]}}],
    }
    exported = export_payload(run)
    assert exported["suppliers"][0]["criterion_results"][0]["evidence"] == "evidence"
    assert exported["suppliers"][0]["warnings"] == ["warning"]
    assert exported["suppliers"][0]["absolute_score"] == 10.0
    assert exported["suppliers"][0]["scores"]["1"] == 10.0
    assert exported["suppliers"][0]["benchmarks"]["1"] == 10.0
    assert exported["suppliers"][0]["gaps"]["1"] == 0.0
    assert exported["suppliers"][0]["relative_performance"]["1"] == 100.0
    assert "PPI, highest first" in exported["tie_break_rule"]
    assert "private raw detail" not in str(exported)
    assert exported["errors"][0]["message"]


def test_export_rounding_keeps_weighted_ppi_consistent_with_displayed_percentages():
    criteria = [
        {"criterion_id": 1, "weight": 30, "max_score": 10, "is_active": 1},
        {"criterion_id": 2, "weight": 20, "max_score": 10, "is_active": 1},
        {"criterion_id": 3, "weight": 20, "max_score": 10, "is_active": 1},
        {"criterion_id": 4, "weight": 20, "max_score": 10, "is_active": 1},
        {"criterion_id": 5, "weight": 10, "max_score": 10, "is_active": 1},
    ]
    scores = {"1": 5, "2": 6, "3": 7, "4": 3, "5": 3}
    benchmarks = {"1": 9, "2": 8, "3": 9, "4": 8, "5": 7}
    relative = {cid: score / benchmarks[cid] * 100 for cid, score in scores.items()}
    weighted_ppi = sum(relative[str(c["criterion_id"])] * c["weight"] / 100 for c in criteria)
    run = {
        "rfp_run_id": "rounding-run",
        "created_at": "2026-10-29T10:00:00+00:00",
        "status": "COMPLETED",
        "details": {"criteria_snapshot": criteria, "errors": []},
        "suppliers": [{"result": {
            "supplier_name": "BrightPath Tech",
            "scores": scores,
            "absolute_score": 5.0,
            "benchmarks": benchmarks,
            "gaps": {cid: score - benchmarks[cid] for cid, score in scores.items()},
            "relative_performance": relative,
            "ppi": weighted_ppi,
            "criterion_results": [
                {
                    "criterion_id": c["criterion_id"],
                    "score": scores[str(c["criterion_id"])],
                    "max_score": c["max_score"],
                    "weight": c["weight"],
                    "benchmark": benchmarks[str(c["criterion_id"])],
                    "gap": scores[str(c["criterion_id"])] - benchmarks[str(c["criterion_id"])],
                    "relative_performance": relative[str(c["criterion_id"])],
                }
                for c in criteria
            ],
        }}],
    }
    exported = export_payload(run)["suppliers"][0]
    assert exported["ppi"] == round(sum(
        item["relative_performance"] * item["weight"] / 100
        for item in exported["criterion_results"]
    ), 4)
    assert exported["ppi"] == 59.008


def test_export_removes_only_internal_warning_adds_run_provenance_and_preserves_results():
    result = {
        "supplier_name": "NexaWorks",
        "absolute_score": 8.6,
        "ppi": 100.0,
        "final_rank": 1,
        "warnings": [INTERNAL_SYNTHETIC_WARNING, "Review delivery timeline."],
        "assessment": {"warnings": [INTERNAL_SYNTHETIC_WARNING, "Review delivery timeline."]},
        "criterion_results": [{"criterion_id": 1, "score": 8.6, "benchmark": 8.6, "gap": 0.0, "relative_performance": 100.0}],
    }
    run = {
        "rfp_run_id": "53c1cd28921c44cdbb6de0f8dabbc5fc",
        "created_at": "2026-10-30T00:00:00+00:00",
        "status": "COMPLETED",
        "details": {"criteria_snapshot": [], "errors": []},
        "suppliers": [{"result": result}],
    }
    original = json.loads(json.dumps(result))
    exported = export_payload(run)
    serialized = json.dumps(exported, allow_nan=False)
    round_trip = json.loads(serialized)
    clean = round_trip["suppliers"][0]

    assert round_trip["data_provenance"] == SYNTHETIC_DATA_PROVENANCE
    assert INTERNAL_SYNTHETIC_WARNING not in serialized
    assert clean["warnings"] == ["Review delivery timeline."]
    assert clean["assessment"]["warnings"] == ["Review delivery timeline."]
    assert clean["absolute_score"] == original["absolute_score"]
    assert clean["ppi"] == original["ppi"]
    assert clean["final_rank"] == original["final_rank"]
    assert clean["criterion_results"] == original["criterion_results"]


def test_cleaned_historical_run_export_is_valid_and_keeps_all_four_ranked_results():
    path = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / "rfp_run_53c1cd28921c44cdbb6de0f8dabbc5fc_cleaned.json"
    exported = json.loads(path.read_text(encoding="utf-8"))
    assert exported["rfp_run_id"] == "53c1cd28921c44cdbb6de0f8dabbc5fc"
    assert exported["status"] == "COMPLETED"
    assert exported["errors"] == []
    assert [(row["supplier_name"], row["final_rank"]) for row in exported["suppliers"]] == [
        ("NexaWorks", 1),
        ("Apex Systems", 2),
        ("Orbit Digital", 3),
        ("BrightPath Tech", 4),
    ]
    assert [(row["absolute_score"], row["ppi"]) for row in exported["suppliers"]] == [
        (8.6, 100.0),
        (8.2, 95.5556),
        (6.2, 72.4603),
        (5.1, 58.7699),
    ]
    assert exported["data_provenance"]["synthetic"] is True
    assert INTERNAL_SYNTHETIC_WARNING not in path.read_text(encoding="utf-8")


def test_streamlit_app_renders_without_exception():
    app_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app_path)).run(timeout=20)
    assert not at.exception
    assert any("Supplier RFP Evaluation" in item.value for item in at.title)


def test_missing_metadata_errors_wait_until_evaluate_is_clicked():
    app_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "app.py"
    pdf_path = app_path.parent / "data" / "supplier_proposals" / "apex_systems_proposal.pdf"
    at = AppTest.from_file(str(app_path)).run(timeout=20)
    at.file_uploader[0].set_value((pdf_path.name, pdf_path.read_bytes(), "application/pdf")).run(timeout=20)

    assert not at.exception
    assert len(at.error) == 0
    assert at.text_input[0].value == "Apex Systems"

    at.button[0].click().run(timeout=20)
    assert any("valid submission date" in error.value for error in at.error)
    assert any("finite number" in error.value for error in at.error)
