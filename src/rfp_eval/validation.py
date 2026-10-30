"""Normalize recoverable LLM response problems and reject ambiguous output."""

from __future__ import annotations

from math import isfinite
import re
from typing import Any, Mapping, Sequence


class LLMValidationError(ValueError):
    """Raised when an LLM assessment cannot be used safely."""


def _valid_text(value: Any) -> bool:
    return isinstance(value, str)


def _supplier_name_key(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    ignored = {"proposal", "response", "supplier", "inc", "incorporated", "llc", "ltd", "limited", "co", "company"}
    return "".join(word for word in words if word not in ignored)


def supplier_names_match(left: str, right: str) -> bool:
    """Match recognizable punctuation/case and generic suffix variants."""
    return bool(_supplier_name_key(left)) and _supplier_name_key(left) == _supplier_name_key(right)


def is_synthetic_disclaimer(value: str) -> bool:
    folded = value.casefold()
    return "synthetic demonstration data" in folded or (
        "fictional" in folded and "not" in folded and ("supplier" in folded or "commercial offer" in folded)
    )


def validate_assessment(
    payload: Mapping[str, Any],
    criteria: Sequence[Mapping[str, Any]],
    *,
    expected_supplier_name: str | None = None,
) -> dict[str, Any]:
    """Return canonical criterion assessments plus explicit normalization warnings.

    Missing criteria and non-numeric scores receive an explicit zero with warnings.
    Numeric out-of-range scores are clipped to the configured maximum with warnings.
    Duplicate IDs are rejected because there is no safe deterministic choice between them.
    """
    if not isinstance(payload, Mapping):
        raise LLMValidationError("LLM response must be a JSON object")
    supplier_name = payload.get("supplier_name")
    if not _valid_text(supplier_name) or not supplier_name.strip():
        if expected_supplier_name:
            supplier_name = expected_supplier_name
            warnings = ["Response omitted supplier_name; used the submitted supplier name."]
        else:
            raise LLMValidationError("LLM response requires a non-empty supplier_name")
    else:
        warnings = []
    canonical_name = expected_supplier_name or supplier_name.strip()
    if (
        expected_supplier_name
        and not supplier_names_match(supplier_name.strip(), expected_supplier_name)
    ):
        warnings.append(f"LLM supplier_name {supplier_name.strip()!r} did not match submitted name; used submitted name.")

    raw_criteria = payload.get("criteria")
    if not isinstance(raw_criteria, list):
        raise LLMValidationError("LLM response field 'criteria' must be an array")
    by_id: dict[int, Mapping[str, Any]] = {}
    for criterion in criteria:
        if bool(criterion.get("is_active", True)):
            cid = criterion.get("criterion_id")
            if isinstance(cid, bool) or not isinstance(cid, int) or cid in by_id:
                raise LLMValidationError("Configured active criterion IDs must be unique integers")
            by_id[cid] = criterion
    if not by_id:
        raise LLMValidationError("At least one active criterion is required")

    seen: dict[int, Mapping[str, Any]] = {}
    for index, item in enumerate(raw_criteria):
        if not isinstance(item, Mapping):
            warnings.append(f"Ignored malformed assessment at index {index}.")
            continue
        cid = item.get("criterion_id")
        if isinstance(cid, str) and cid.isdigit():
            cid = int(cid)
            warnings.append(f"Normalized string criterion_id to integer {cid}.")
        if isinstance(cid, bool) or not isinstance(cid, int):
            warnings.append(f"Ignored assessment at index {index} with invalid criterion_id.")
            continue
        if cid not in by_id:
            warnings.append(f"Ignored unknown or inactive criterion_id {cid}.")
            continue
        if cid in seen:
            raise LLMValidationError(f"Duplicate assessment for criterion_id {cid}")
        seen[cid] = item

    normalized: list[dict[str, Any]] = []
    for cid, criterion in by_id.items():
        maximum = float(criterion["max_score"])
        item = seen.get(cid)
        if item is None:
            score = 0.0
            justification = "No assessment was returned for this active criterion."
            evidence = ""
            warnings.append(f"Missing criterion_id {cid}; assigned score 0 pending human review.")
        else:
            raw_score = item.get("score")
            if isinstance(raw_score, str):
                try:
                    score = float(raw_score.strip())
                    warnings.append(f"Converted string score to a number for criterion_id {cid}.")
                except ValueError:
                    score = 0.0
                    warnings.append(f"Nonnumeric score for criterion_id {cid}; assigned 0 pending human review.")
            elif isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
                score = 0.0
                warnings.append(f"Missing or invalid score for criterion_id {cid}; assigned 0 pending human review.")
            else:
                score = float(raw_score)
            if not isfinite(score):
                score = 0.0
                warnings.append(f"Non-finite score for criterion_id {cid}; assigned 0 pending human review.")
            elif score < 0 or score > maximum:
                original = score
                score = min(maximum, max(0.0, score))
                warnings.append(f"Clipped out-of-range score {original:g} to {score:g} for criterion_id {cid}.")
            llm_max = item.get("max_score")
            if llm_max is None:
                warnings.append(f"Missing LLM max_score for criterion_id {cid}; used configured max_score {maximum:g}.")
            elif llm_max != maximum:
                warnings.append(f"Used configured max_score {maximum:g} instead of LLM max_score for criterion_id {cid}.")
            justification = item.get("justification")
            evidence = item.get("evidence")
            if not _valid_text(justification):
                justification = ""
                warnings.append(f"Missing or invalid justification; used empty string for criterion_id {cid}.")
            if not _valid_text(evidence):
                evidence = ""
                warnings.append(f"Missing or invalid evidence; used empty string for criterion_id {cid}.")
        normalized.append({
            "criterion_id": cid,
            "name": criterion.get("name", f"Criterion {cid}"),
            "weight": float(criterion["weight"]),
            "score": score,
            "max_score": maximum,
            "justification": justification,
            "evidence": evidence,
        })

    risks = payload.get("risks")
    if risks is None:
        risks = []
        warnings.append("Missing risks field; used an empty list.")
    if not isinstance(risks, list) or any(not isinstance(risk, str) for risk in risks):
        risks = []
        warnings.append("Invalid risks field; replaced with an empty list.")
    disclaimer_removed = any(is_synthetic_disclaimer(risk) for risk in risks)
    if disclaimer_removed:
        risks = [risk for risk in risks if not is_synthetic_disclaimer(risk)]
    summary = payload.get("overall_summary")
    if summary is None:
        summary = ""
        warnings.append("Missing overall_summary; used an empty string.")
    if not isinstance(summary, str):
        summary = ""
        warnings.append("Invalid overall_summary; replaced with an empty string.")
    forbidden = {"absolute_score", "weighted_score", "ppi", "rank", "final_rank"} & payload.keys()
    if forbidden:
        warnings.append(f"Ignored LLM-computed ranking fields: {', '.join(sorted(forbidden))}.")
    result = {
        "supplier_name": canonical_name,
        "criteria": normalized,
        "risks": risks,
        "overall_summary": summary,
        "warnings": warnings,
    }
    if disclaimer_removed:
        result["data_provenance"] = {
            "synthetic": True,
            "note": "The proposal identifies its supplier, references, and claims as fictional synthetic demonstration data.",
        }
    return result
