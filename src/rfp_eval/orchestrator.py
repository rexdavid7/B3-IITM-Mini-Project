"""Supplier-by-supplier orchestration and deterministic batch ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping, Sequence
from uuid import uuid4

from .database import DEFAULT_DB, load_criteria, persist_run
from .document_reader import extract_pdf_text
from .scoring import rank_suppliers, validate_criteria
from .validation import validate_assessment


@dataclass(frozen=True)
class SupplierSubmission:
    supplier_name: str
    submission_date: str
    experience_rating: float
    pdf_data: bytes | bytearray | BinaryIO


class BatchEvaluationError(RuntimeError):
    """Raised when the batch cannot be ranked or saved as a coherent run."""


class EvaluationOrchestrator:
    def __init__(self, evaluator: Any, db_path: str | Path = DEFAULT_DB) -> None:
        self.evaluator = evaluator
        self.db_path = Path(db_path)

    def evaluate_one(self, submission: SupplierSubmission, criteria: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Run extraction -> LLM interpretation -> normalization for one proposal."""
        proposal_text = extract_pdf_text(submission.pdf_data)
        raw_assessment = self.evaluator.evaluate(proposal_text, criteria)
        assessment = validate_assessment(
            raw_assessment, criteria, expected_supplier_name=submission.supplier_name
        )
        scores = {item["criterion_id"]: item["score"] for item in assessment["criteria"]}
        return {
            "supplier_name": submission.supplier_name,
            "submission_date": submission.submission_date,
            "experience_rating": submission.experience_rating,
            "scores": scores,
            "assessment": assessment,
        }

    def evaluate_batch(
        self,
        submissions: Sequence[SupplierSubmission],
        *,
        progress_callback: Callable[[int, int, str, str], None] | None = None,
    ) -> dict[str, Any]:
        """Evaluate each proposal, rank successes against the same criteria snapshot, and save one run."""
        if not submissions:
            raise BatchEvaluationError("At least one supplier proposal is required")
        criteria_snapshot = load_criteria(self.db_path, active_only=True)
        try:
            validate_criteria(criteria_snapshot)
        except ValueError as exc:
            raise BatchEvaluationError(f"Active SQLite criteria are invalid: {exc}") from exc

        evaluated: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for index, submission in enumerate(submissions, start=1):
            supplier_name = getattr(submission, "supplier_name", "")
            if progress_callback:
                progress_callback(index - 1, len(submissions), supplier_name, "Evaluating")
            try:
                if not isinstance(submission.supplier_name, str) or not submission.supplier_name.strip():
                    raise ValueError("supplier_name must be a non-empty string")
                try:
                    date.fromisoformat(submission.submission_date)
                except (TypeError, ValueError):
                    raise ValueError("submission_date must be ISO YYYY-MM-DD") from None
                if (
                    isinstance(submission.experience_rating, bool)
                    or not isinstance(submission.experience_rating, (int, float))
                    or not isfinite(submission.experience_rating)
                ):
                    raise ValueError("experience_rating must be a finite number")
                evaluated.append(self.evaluate_one(submission, criteria_snapshot))
            except Exception as exc:
                errors.append({
                    "supplier_name": getattr(submission, "supplier_name", ""),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                })
            finally:
                if progress_callback:
                    progress_callback(index, len(submissions), supplier_name, "Finished")
        if not evaluated:
            return {
                "rfp_run_id": None,
                "status": "FAILED",
                "criteria_snapshot": criteria_snapshot,
                "suppliers": [],
                "errors": errors,
            }

        try:
            ranked = rank_suppliers(evaluated, criteria_snapshot)
            for supplier in ranked:
                assessment = supplier["assessment"]
                weights = {c["criterion_id"]: float(c["weight"]) for c in criteria_snapshot}
                supplier["criterion_results"] = [
                    {
                        **item,
                        "benchmark": supplier["benchmarks"][item["criterion_id"]],
                        "gap": supplier["gaps"][item["criterion_id"]],
                        "relative_performance": supplier["relative_performance"][item["criterion_id"]],
                        "weight": weights[item["criterion_id"]],
                    }
                    for item in assessment["criteria"]
                ]
                supplier["warnings"] = assessment["warnings"]
                supplier["risks"] = assessment["risks"]
                supplier["overall_summary"] = assessment["overall_summary"]
            run_id = uuid4().hex
            status = "COMPLETED_WITH_ERRORS" if errors else "COMPLETED"
            persist_run(
                ranked,
                self.db_path,
                run_id=run_id,
                status=status,
                run_details={"criteria_snapshot": criteria_snapshot, "errors": errors},
            )
        except Exception as exc:
            raise BatchEvaluationError(f"Could not rank or persist evaluation batch: {exc}") from exc
        return {
            "rfp_run_id": run_id,
            "status": status,
            "criteria_snapshot": criteria_snapshot,
            "suppliers": ranked,
            "errors": errors,
        }
