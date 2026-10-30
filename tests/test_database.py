import sqlite3

from rfp_eval.database import list_runs, load_criteria, load_run, persist_run, rename_suppliers_in_run, seed_criteria


def test_seed_creates_five_configurable_criteria_and_preserves_edits(tmp_path):
    db = tmp_path / "test.sqlite3"
    seed_criteria(db)
    rows = load_criteria(db)
    assert len(rows) == 5
    assert sum(row["weight"] for row in rows if row["is_active"]) == 100
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE evaluation_criteria SET weight=25, max_score=5, is_active=0 WHERE criterion_id=1")
    seed_criteria(db)
    row = next(row for row in load_criteria(db) if row["criterion_id"] == 1)
    assert (row["weight"], row["max_score"], row["is_active"]) == (25, 5, 0)


def test_active_filter(tmp_path):
    db = tmp_path / "test.sqlite3"
    seed_criteria(db)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE evaluation_criteria SET is_active=0 WHERE criterion_id=1")
    assert len(load_criteria(db, active_only=True)) == 4


def test_persist_and_load_run_details_and_supplier_json(tmp_path):
    db = tmp_path / "test.sqlite3"
    seed_criteria(db)
    result = {
        "supplier_name": "Apex",
        "submission_date": "2026-01-01",
        "experience_rating": 7.0,
        "absolute_score": 8.2,
        "ppi": 100.0,
        "final_rank": 1,
        "criterion_results": [{"criterion_id": 1, "evidence": "Document quote"}],
        "warnings": ["Review evidence"],
    }
    run_id = persist_run(
        [result],
        db,
        run_id="run-test",
        run_details={"criteria_snapshot": [{"criterion_id": 1, "weight": 100}], "errors": []},
    )
    assert list_runs(db)[0]["rfp_run_id"] == run_id
    loaded = load_run(db, run_id)
    assert loaded["details"]["criteria_snapshot"][0]["weight"] == 100
    assert loaded["suppliers"][0]["result"]["criterion_results"][0]["evidence"] == "Document quote"


def test_rename_saved_suppliers_preserves_scores_and_moves_disclaimer_out_of_risks(tmp_path):
    db = tmp_path / "test.sqlite3"
    seed_criteria(db)
    result = {
        "supplier_name": "nexaworks_proposal",
        "submission_date": "2026-10-05",
        "experience_rating": 4.0,
        "absolute_score": 9.999999999999998,
        "ppi": 100.0,
        "final_rank": 1,
        "assessment": {
            "supplier_name": "nexaworks_proposal",
            "warnings": ["LLM supplier_name 'NexaWorks' did not match submitted name; used submitted name."],
            "risks": ["All supplier organizations and claims are fictional synthetic demonstration data."],
        },
        "warnings": ["LLM supplier_name 'NexaWorks' did not match submitted name; used submitted name."],
        "risks": ["All supplier organizations and claims are fictional synthetic demonstration data."],
    }
    run_id = persist_run([result], db, run_id="repair-run")
    rename_suppliers_in_run(db, run_id, {"nexaworks_proposal": "NexaWorks"})
    loaded = load_run(db, run_id)
    row = loaded["suppliers"][0]
    assert row["supplier_name"] == row["result"]["supplier_name"] == "NexaWorks"
    assert row["result"]["assessment"]["supplier_name"] == "NexaWorks"
    assert row["result"]["absolute_score"] == 9.999999999999998
    assert row["result"]["warnings"] == []
    assert row["result"]["risks"] == []
    assert row["result"]["data_provenance"]["synthetic"] is True


def test_initialize_migrates_existing_run_table(tmp_path):
    db = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE rfp_runs (rfp_run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL)")
    assert list_runs(db) == []
    with sqlite3.connect(db) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(rfp_runs)")}
    assert "result_json" in columns
