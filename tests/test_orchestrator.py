import json
import sqlite3
from io import BytesIO
from types import SimpleNamespace

import pymupdf
import pytest

from rfp_eval.database import load_run, seed_criteria
from rfp_eval.gemini_client import GeminiEvaluator
from rfp_eval.orchestrator import EvaluationOrchestrator, SupplierSubmission


def make_pdf(text):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return BytesIO(data)


class MockGeminiClient:
    def __init__(self):
        self.calls = []
        self.models = self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        request = json.loads(kwargs["contents"].split("Evaluate this proposal and return JSON only:\n", 1)[1])
        supplier_name = "Apex Systems" if "Apex" in request["proposal_text"] else "Bright"
        score = 9 if supplier_name.startswith("Apex") else 7
        answer = {
            "supplier_name": supplier_name,
            "criteria": [
                {
                    "criterion_id": criterion["criterion_id"],
                    "score": score,
                    "max_score": criterion["max_score"],
                    "justification": "Mocked assessment",
                    "evidence": "Proposal text",
                }
                for criterion in request["active_criteria"]
            ],
            "risks": [],
            "overall_summary": "Mock only",
        }
        return SimpleNamespace(text=json.dumps(answer))


def test_dynamic_criteria_mocked_end_to_end_and_single_run_persistence(tmp_path):
    db = tmp_path / "evaluation.sqlite3"
    seed_criteria(db)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE evaluation_criteria SET weight=75 WHERE criterion_id=1")
        connection.execute("UPDATE evaluation_criteria SET weight=25 WHERE criterion_id=2")
        connection.execute("UPDATE evaluation_criteria SET is_active=0 WHERE criterion_id > 2")

    fake_client = MockGeminiClient()
    evaluator = GeminiEvaluator(client=fake_client, model="mock-model")
    orchestration = EvaluationOrchestrator(evaluator, db)
    result = orchestration.evaluate_batch([
        SupplierSubmission("Apex Systems", "2026-01-01", 8, make_pdf("Apex proposal detail")),
        SupplierSubmission("Bright", "2026-01-02", 5, make_pdf("Bright proposal detail")),
    ])

    assert result["status"] == "COMPLETED"
    assert result["rfp_run_id"]
    assert len(result["suppliers"]) == 2
    assert result["suppliers"][0]["supplier_name"] == "Apex Systems"
    assert result["suppliers"][0]["assessment"]["supplier_name"] == "Apex Systems"
    assert not any("did not match" in warning for warning in result["suppliers"][0]["warnings"])
    assert result["suppliers"][0]["absolute_score"] == 9
    assert result["suppliers"][1]["absolute_score"] == 7
    assert result["suppliers"][0]["ppi"] == 100
    assert result["suppliers"][1]["ppi"] == pytest.approx(100 * 7 / 9)
    assert [c["criterion_id"] for c in result["criteria_snapshot"]] == [1, 2]
    assert all('"weight": 75.0' in call["contents"] for call in fake_client.calls)

    saved = load_run(db, result["rfp_run_id"])
    assert saved["status"] == "COMPLETED"
    assert len(saved["suppliers"]) == 2
    assert saved["suppliers"][0]["result"]["criterion_results"][0]["evidence"] == "Proposal text"


def test_batch_isolates_supplier_errors_and_persists_successful_subset(tmp_path):
    db = tmp_path / "evaluation.sqlite3"
    seed_criteria(db)
    evaluator = GeminiEvaluator(client=MockGeminiClient(), model="mock-model")
    result = EvaluationOrchestrator(evaluator, db).evaluate_batch([
        SupplierSubmission("Bad PDF", "2026-01-01", 1, b"broken"),
        SupplierSubmission("Apex", "2026-01-02", 8, make_pdf("Apex proposal detail")),
    ])
    assert result["status"] == "COMPLETED_WITH_ERRORS"
    assert len(result["errors"]) == 1
    assert result["errors"][0]["supplier_name"] == "Bad PDF"
    saved = load_run(db, result["rfp_run_id"])
    assert [row["supplier_name"] for row in saved["suppliers"]] == ["Apex"]
    assert saved["suppliers"][0]["result"]["assessment"]["supplier_name"] == "Apex"
    assert saved["details"]["errors"][0]["supplier_name"] == "Bad PDF"
