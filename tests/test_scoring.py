import pytest

from rfp_eval.scoring import (
    absolute_weighted_score,
    criterion_benchmarks_and_gaps,
    rank_suppliers,
    relative_performance,
    weighted_ppi,
)


CRITERIA = [
    {"criterion_id": 1, "name": "A", "weight": 30, "max_score": 10, "is_active": 1},
    {"criterion_id": 2, "name": "B", "weight": 70, "max_score": 20, "is_active": 1},
]


def test_absolute_weighted_score_normalizes_maximums():
    assert absolute_weighted_score({1: 8, 2: 10}, CRITERIA) == pytest.approx(5.9)


def test_implementation_guide_example_is_7_80():
    criteria = [
        {"criterion_id": 1, "weight": 30, "max_score": 10},
        {"criterion_id": 2, "weight": 20, "max_score": 10},
        {"criterion_id": 3, "weight": 20, "max_score": 10},
        {"criterion_id": 4, "weight": 20, "max_score": 10},
        {"criterion_id": 5, "weight": 10, "max_score": 10},
    ]
    assert absolute_weighted_score({1: 8, 2: 7, 3: 9, 4: 8, 5: 6}, criteria) == pytest.approx(7.8)


def test_inactive_criteria_do_not_affect_weights_or_scores():
    criteria = CRITERIA + [{"criterion_id": 3, "weight": 90, "max_score": 10, "is_active": 0}]
    assert absolute_weighted_score({1: 10, 2: 20}, criteria) == pytest.approx(10)


@pytest.mark.parametrize("criteria", [[], [{"criterion_id": 1, "weight": 60, "max_score": 10}], [{"criterion_id": 1, "weight": 0, "max_score": 10}, {"criterion_id": 2, "weight": 100, "max_score": 10}]])
def test_invalid_active_weights_rejected(criteria):
    with pytest.raises(ValueError, match="weight|active"):
        absolute_weighted_score({}, criteria)


@pytest.mark.parametrize("scores", [{1: -1, 2: 10}, {1: 11, 2: 10}, {1: float("nan"), 2: 10}, {1: 1}])
def test_bad_scores_rejected(scores):
    with pytest.raises(ValueError):
        absolute_weighted_score(scores, CRITERIA)


def test_benchmarks_gaps_and_weighted_ppi():
    suppliers = [{"supplier_name": "A", "scores": {1: 10, 2: 10}}, {"supplier_name": "B", "scores": {1: 5, 2: 20}}]
    benchmarks, gaps = criterion_benchmarks_and_gaps(suppliers, CRITERIA)
    assert benchmarks == {1: 10, 2: 20}
    assert gaps["A"] == {1: 0, 2: -10}
    assert gaps["B"] == {1: -5, 2: 0}
    assert weighted_ppi(suppliers[0]["scores"], benchmarks, CRITERIA) == pytest.approx(65)


def test_zero_benchmark_is_safe():
    assert relative_performance(0, 0) == 100
    assert weighted_ppi({1: 0, 2: 0}, {1: 0, 2: 0}, CRITERIA) == 100
    with pytest.raises(ValueError):
        relative_performance(1, 0)


def test_ranking_uses_ppi_then_date_experience_and_name_not_absolute_score():
    criteria = [
        {"criterion_id": 1, "weight": 50, "max_score": 10, "is_active": 1},
        {"criterion_id": 2, "weight": 50, "max_score": 10, "is_active": 1},
    ]
    suppliers = [
        {"supplier_name": "PPI Winner", "submission_date": "2026-12-01", "experience_rating": 1, "scores": {1: 8, 2: 1}},
        {"supplier_name": "Absolute Winner", "submission_date": "2026-01-01", "experience_rating": 99, "scores": {1: 10, 2: 0.5}},
        {"supplier_name": "Low Absolute Early", "submission_date": "2026-01-01", "experience_rating": 1, "scores": {1: 0, 2: 1}},
        {"supplier_name": "High Absolute Later", "submission_date": "2026-01-02", "experience_rating": 99, "scores": {1: 10, 2: 0}},
        {"supplier_name": "Zulu", "submission_date": "2026-01-03", "experience_rating": 9, "scores": {1: 4, 2: 0.5}},
        {"supplier_name": "Echo", "submission_date": "2026-01-03", "experience_rating": 9, "scores": {1: 4, 2: 0.5}},
        {"supplier_name": "Bravo", "submission_date": "2026-01-03", "experience_rating": 10, "scores": {1: 4, 2: 0.5}},
    ]
    result = rank_suppliers(suppliers, criteria)
    assert [s["supplier_name"] for s in result] == [
        "PPI Winner", "Absolute Winner", "Low Absolute Early", "High Absolute Later",
        "Bravo", "Echo", "Zulu",
    ]
    assert result[0]["ppi"] > result[1]["ppi"]
    assert result[0]["absolute_score"] < result[1]["absolute_score"]
    assert result[2]["ppi"] == result[3]["ppi"]
    assert result[2]["absolute_score"] < result[3]["absolute_score"]
    assert result[4]["ppi"] == result[5]["ppi"] == result[6]["ppi"]
    assert result[4]["absolute_score"] == result[5]["absolute_score"] == result[6]["absolute_score"]
    assert [s["final_rank"] for s in result] == list(range(1, len(suppliers) + 1))


def test_ppi_breaks_tie_when_absolute_scores_are_equal():
    criteria = [{"criterion_id": 1, "weight": 50, "max_score": 10, "is_active": 1}, {"criterion_id": 2, "weight": 50, "max_score": 10, "is_active": 1}]
    suppliers = [
        {"supplier_name": "Alpha", "submission_date": "2026-01-01", "experience_rating": 5, "scores": {1: 10, 2: 0}},
        {"supplier_name": "Beta", "submission_date": "2026-02-01", "experience_rating": 5, "scores": {1: 5, 2: 5}},
    ]
    result = rank_suppliers(suppliers, criteria)
    assert result[0]["absolute_score"] == result[1]["absolute_score"]
    assert result[0]["supplier_name"] == "Beta"


def test_rank_validates_dates_and_experience():
    supplier = {"supplier_name": "A", "submission_date": "not-a-date", "experience_rating": 1, "scores": {1: 1}}
    with pytest.raises(ValueError, match="submission_date"):
        rank_suppliers([supplier], [{"criterion_id": 1, "weight": 100, "max_score": 10}])
