import pytest

from rfp_eval.validation import LLMValidationError, validate_assessment


CRITERIA = [
    {"criterion_id": 1, "name": "Design", "weight": 70, "max_score": 10, "is_active": 1},
    {"criterion_id": 2, "name": "Support", "weight": 30, "max_score": 5, "is_active": 1},
]


def item(cid, score, max_score):
    return {"criterion_id": cid, "score": score, "max_score": max_score, "justification": "Reason", "evidence": "Proposal line"}


def payload(assessments):
    return {"supplier_name": "A", "criteria": assessments, "risks": [], "overall_summary": "Summary"}


def test_valid_structured_output_is_canonicalized():
    result = validate_assessment(payload([item(1, 8, 10), item(2, 4, 5)]), CRITERIA)
    assert [entry["score"] for entry in result["criteria"]] == [8, 4]
    assert result["warnings"] == []


def test_missing_assessment_is_zeroed_with_explicit_warning():
    result = validate_assessment(payload([item(1, 8, 10)]), CRITERIA)
    assert result["criteria"][1]["score"] == 0
    assert any("Missing criterion_id 2" in warning for warning in result["warnings"])


def test_duplicate_criterion_is_rejected():
    with pytest.raises(LLMValidationError, match="Duplicate"):
        validate_assessment(payload([item(1, 8, 10), item(1, 7, 10), item(2, 4, 5)]), CRITERIA)


def test_out_of_range_scores_clipped_with_warning_and_configured_max_used():
    result = validate_assessment(payload([item(1, 12, 100), item(2, -2, 5)]), CRITERIA)
    assert [entry["score"] for entry in result["criteria"]] == [10, 0]
    assert [entry["max_score"] for entry in result["criteria"]] == [10, 5]
    assert any("Clipped out-of-range" in warning for warning in result["warnings"])
    assert any("Used configured max_score" in warning for warning in result["warnings"])


def test_nonnumeric_scores_and_wrong_supplier_name_are_explicit():
    raw = payload([item(1, "not-a-number", 10), item(2, 4, 5)])
    raw["supplier_name"] = "Different"
    result = validate_assessment(raw, CRITERIA, expected_supplier_name="A")
    assert result["supplier_name"] == "A"
    assert result["criteria"][0]["score"] == 0
    assert any("assigned 0" in warning for warning in result["warnings"])
    assert any("did not match" in warning for warning in result["warnings"])


@pytest.mark.parametrize(
    "model_name, submitted_name",
    [
        ("NexaWorks", "nexaworks_proposal"),
        ("APEX SYSTEMS, Inc.", "Apex-Systems"),
        ("BrightPath Tech Proposal", "brightpath_tech"),
    ],
)
def test_recognizable_model_name_variant_keeps_submitted_canonical_name_without_warning(model_name, submitted_name):
    raw = payload([item(1, 8, 10), item(2, 4, 5)])
    raw["supplier_name"] = model_name
    result = validate_assessment(raw, CRITERIA, expected_supplier_name=submitted_name)
    assert result["supplier_name"] == submitted_name
    assert not any("did not match" in warning for warning in result["warnings"])


def test_synthetic_data_disclaimer_is_provenance_not_a_business_risk():
    raw = payload([item(1, 8, 10), item(2, 4, 5)])
    raw["risks"] = [
        "Schedule depends on Banner access.",
        "All supplier organizations and claims are fictional synthetic demonstration data.",
    ]
    result = validate_assessment(raw, CRITERIA)
    assert result["risks"] == ["Schedule depends on Banner access."]
    assert result["data_provenance"]["synthetic"] is True
    assert not any("provenance metadata" in warning for warning in result["warnings"])


def test_ignores_any_llm_calculated_rank_fields():
    raw = payload([item(1, 8, 10), item(2, 4, 5)])
    raw["ppi"] = 1000
    raw["final_rank"] = 1
    result = validate_assessment(raw, CRITERIA)
    assert "ppi" not in result
    assert any("Ignored LLM-computed" in warning for warning in result["warnings"])


def test_missing_explanation_and_summary_fields_are_warned():
    raw = {"supplier_name": "A", "criteria": [
        {"criterion_id": 1, "score": 8}, {"criterion_id": 2, "score": 4}
    ]}
    result = validate_assessment(raw, CRITERIA)
    assert result["criteria"][0]["evidence"] == ""
    assert result["overall_summary"] == ""
    assert any("Missing or invalid evidence" in warning for warning in result["warnings"])
    assert any("Missing risks field" in warning for warning in result["warnings"])
    assert any("Missing overall_summary" in warning for warning in result["warnings"])
