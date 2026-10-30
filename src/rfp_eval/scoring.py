"""Pure Python validation, scoring, peer metrics, PPI, and ranking."""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Any, Mapping, Sequence


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def validate_criteria(criteria: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    active = [criterion for criterion in criteria if bool(criterion.get("is_active", True))]
    if not active:
        raise ValueError("At least one criterion must be active")
    ids: set[Any] = set()
    total = 0.0
    for criterion in active:
        cid = criterion.get("criterion_id")
        if cid is None or cid in ids:
            raise ValueError("Active criteria must have unique criterion_id values")
        ids.add(cid)
        weight = _number(criterion.get("weight"), f"weight for criterion {cid}")
        max_score = _number(criterion.get("max_score"), f"max_score for criterion {cid}")
        if weight <= 0 or weight > 100:
            raise ValueError(f"Active criterion {cid} weight must be greater than 0 and at most 100")
        if max_score <= 0:
            raise ValueError(f"Criterion {cid} max_score must be greater than zero")
        total += weight
    if abs(total - 100.0) > 1e-8:
        raise ValueError(f"Active criterion weights must total 100%; got {total:g}%")
    return active


def _validated_scores(scores: Mapping[Any, Any], active: Sequence[Mapping[str, Any]]) -> dict[Any, float]:
    expected = {c["criterion_id"] for c in active}
    missing = expected - scores.keys()
    if missing:
        raise ValueError(f"Missing scores for active criteria: {sorted(missing, key=str)}")
    result: dict[Any, float] = {}
    by_id = {c["criterion_id"]: c for c in active}
    for cid in expected:
        score = _number(scores[cid], f"score for criterion {cid}")
        maximum = float(by_id[cid]["max_score"])
        if score < 0 or score > maximum:
            raise ValueError(f"Score for criterion {cid} must be between 0 and {maximum:g}")
        result[cid] = score
    return result


def absolute_weighted_score(scores: Mapping[Any, Any], criteria: Sequence[Mapping[str, Any]]) -> float:
    """Return the weighted score on a 0–10 scale, regardless of criterion maxima."""
    active = validate_criteria(criteria)
    valid = _validated_scores(scores, active)
    return 10.0 * sum(
        valid[c["criterion_id"]] / float(c["max_score"]) * float(c["weight"]) / 100
        for c in active
    )


def criterion_benchmarks_and_gaps(
    suppliers: Sequence[Mapping[str, Any]], criteria: Sequence[Mapping[str, Any]]
) -> tuple[dict[Any, float], dict[str, dict[Any, float]]]:
    """Return per-criterion maxima and per-supplier (score - benchmark) gaps."""
    active = validate_criteria(criteria)
    if not suppliers:
        raise ValueError("At least one supplier is required")
    names: set[str] = set()
    parsed: dict[str, dict[Any, float]] = {}
    for supplier in suppliers:
        name = supplier.get("supplier_name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Supplier names must be non-empty and unique")
        names.add(name)
        parsed[name] = _validated_scores(supplier.get("scores", {}), active)
    benchmarks = {
        c["criterion_id"]: max(parsed[name][c["criterion_id"]] for name in parsed)
        for c in active
    }
    gaps = {
        name: {cid: score - benchmarks[cid] for cid, score in supplier_scores.items()}
        for name, supplier_scores in parsed.items()
    }
    return benchmarks, gaps


def relative_performance(score: Any, benchmark: Any) -> float:
    """Return score/benchmark as a percentage; 0/0 is defined as 100%."""
    value = _number(score, "score")
    best = _number(benchmark, "benchmark")
    if value < 0 or best < 0 or value > best:
        raise ValueError("Relative performance requires 0 <= score <= benchmark")
    return 100.0 if best == 0 else value / best * 100.0


def weighted_ppi(scores: Mapping[Any, Any], benchmarks: Mapping[Any, Any], criteria: Sequence[Mapping[str, Any]]) -> float:
    active = validate_criteria(criteria)
    valid = _validated_scores(scores, active)
    missing = {c["criterion_id"] for c in active} - benchmarks.keys()
    if missing:
        raise ValueError(f"Missing benchmarks for active criteria: {sorted(missing, key=str)}")
    return sum(
        relative_performance(valid[c["criterion_id"]], benchmarks[c["criterion_id"]])
        * float(c["weight"]) / 100
        for c in active
    )


def rank_suppliers(
    suppliers: Sequence[Mapping[str, Any]], criteria: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Calculate metrics and return copied supplier records in required rank order."""
    active = validate_criteria(criteria)
    benchmarks, gaps = criterion_benchmarks_and_gaps(suppliers, active)
    ranked: list[dict[str, Any]] = []
    for supplier in suppliers:
        name = supplier["supplier_name"]
        scores = _validated_scores(supplier["scores"], active)
        absolute = absolute_weighted_score(scores, active)
        ppi = weighted_ppi(scores, benchmarks, active)
        submission = supplier.get("submission_date")
        try:
            normalized_date = date.fromisoformat(submission).isoformat()
        except (TypeError, ValueError):
            raise ValueError(f"Supplier {name!r} submission_date must be ISO YYYY-MM-DD") from None
        experience = _number(supplier.get("experience_rating"), f"experience_rating for {name}")
        relative = {c["criterion_id"]: relative_performance(scores[c["criterion_id"]], benchmarks[c["criterion_id"]]) for c in active}
        ranked.append({
            **supplier,
            "scores": scores,
            "absolute_score": absolute,
            "benchmarks": dict(benchmarks),
            "gaps": dict(gaps[name]),
            "relative_performance": relative,
            "ppi": ppi,
            "submission_date": normalized_date,
            "experience_rating": experience,
        })
    # The assignment mandates PPI first; absolute score is displayed but is not a tie-break.
    ranked.sort(key=lambda s: (-s["ppi"], s["submission_date"], -s["experience_rating"], s["supplier_name"].casefold(), s["supplier_name"]))
    for rank, supplier in enumerate(ranked, start=1):
        supplier["final_rank"] = rank
    return ranked
