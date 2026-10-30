"""SQLite schema and criteria access."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .validation import is_synthetic_disclaimer, supplier_names_match

DEFAULT_DB = Path("data/rfp_evaluation.sqlite3")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    weight REAL NOT NULL CHECK (weight >= 0 AND weight <= 100),
    max_score REAL NOT NULL CHECK (max_score > 0),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);
CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS supplier_results (
    rfp_run_id TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id) ON DELETE CASCADE,
    supplier_name TEXT NOT NULL,
    submission_date TEXT NOT NULL,
    experience_rating REAL NOT NULL,
    absolute_score REAL NOT NULL,
    ppi REAL NOT NULL,
    final_rank INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY (rfp_run_id, supplier_name)
);
"""

DEFAULT_CRITERIA = (
    (1, "Technical Capability", "Technical fit, architecture, integrations, and scalability.", 30.0, 10.0, 1),
    (2, "Implementation Plan", "Timeline, milestones, staffing, and delivery feasibility.", 20.0, 10.0, 1),
    (3, "Commercial Value", "Pricing clarity, total cost, assumptions, and value for money.", 20.0, 10.0, 1),
    (4, "Security & Compliance", "Security controls, certifications, privacy, and auditability.", 20.0, 10.0, 1),
    (5, "Support & Experience", "Support model, relevant projects, and references.", 10.0, 10.0, 1),
)


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: str | Path = DEFAULT_DB) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)
        run_columns = {row["name"] for row in connection.execute("PRAGMA table_info(rfp_runs)")}
        if "result_json" not in run_columns:
            connection.execute("ALTER TABLE rfp_runs ADD COLUMN result_json TEXT NOT NULL DEFAULT '{}' ")


def seed_criteria(db_path: str | Path = DEFAULT_DB) -> None:
    """Insert example criteria; preserve any existing user configuration."""
    initialize_database(db_path)
    with connect(db_path) as connection:
        connection.executemany(
            """INSERT OR IGNORE INTO evaluation_criteria
               (criterion_id, name, description, weight, max_score, is_active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            DEFAULT_CRITERIA,
        )


def load_criteria(db_path: str | Path = DEFAULT_DB, *, active_only: bool = False) -> list[dict[str, Any]]:
    initialize_database(db_path)
    query = "SELECT criterion_id, name, description, weight, max_score, is_active FROM evaluation_criteria"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY criterion_id"
    with connect(db_path) as connection:
        return [dict(row) for row in connection.execute(query)]


def persist_run(
    results: list[dict[str, Any]],
    db_path: str | Path = DEFAULT_DB,
    *,
    run_id: str | None = None,
    status: str = "COMPLETED",
    run_details: dict[str, Any] | None = None,
) -> str:
    """Persist a fully ranked batch and all criterion evidence atomically."""
    if not results:
        raise ValueError("Cannot persist an empty evaluation run")
    run_id = run_id or uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as connection:
        with connection:
            connection.execute(
                "INSERT INTO rfp_runs (rfp_run_id, created_at, status, result_json) VALUES (?, ?, ?, ?)",
                (run_id, created_at, status, json.dumps(run_details or {}, ensure_ascii=False, allow_nan=False)),
            )
            connection.executemany(
                """INSERT INTO supplier_results
                   (rfp_run_id, supplier_name, submission_date, experience_rating,
                    absolute_score, ppi, final_rank, result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        run_id,
                        result["supplier_name"],
                        result["submission_date"],
                        result["experience_rating"],
                        result["absolute_score"],
                        result["ppi"],
                        result["final_rank"],
                        json.dumps(result, ensure_ascii=False, allow_nan=False),
                    )
                    for result in results
                ],
            )
    return run_id


def rename_suppliers_in_run(
    db_path: str | Path,
    run_id: str,
    name_map: dict[str, str],
) -> None:
    """Correct supplier labels in one saved run without changing its evaluation metrics."""
    if not name_map:
        return
    if any(not old.strip() or not new.strip() for old, new in name_map.items()):
        raise ValueError("Supplier rename values must be non-empty")
    if len({name.casefold() for name in name_map.values()}) != len(name_map):
        raise ValueError("Supplier rename targets must be unique")

    initialize_database(db_path)
    with connect(db_path) as connection:
        with connection:
            run = connection.execute(
                "SELECT result_json FROM rfp_runs WHERE rfp_run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise ValueError(f"Unknown RFP run: {run_id}")
            rows = connection.execute(
                "SELECT supplier_name, result_json FROM supplier_results WHERE rfp_run_id = ?",
                (run_id,),
            ).fetchall()
            existing = {row["supplier_name"] for row in rows}
            absent = set(name_map) - existing
            if absent:
                raise ValueError(f"Supplier names not present in run: {sorted(absent)}")
            unchanged = existing - set(name_map)
            if {name.casefold() for name in name_map.values()} & {name.casefold() for name in unchanged}:
                raise ValueError("A supplier rename target conflicts with an existing run supplier")

            for row in rows:
                old_name = row["supplier_name"]
                new_name = name_map.get(old_name, old_name)
                result = json.loads(row["result_json"])
                result["supplier_name"] = new_name
                assessment = result.get("assessment")
                if isinstance(assessment, dict):
                    assessment["supplier_name"] = new_name

                containers = [result]
                if isinstance(assessment, dict):
                    containers.append(assessment)
                disclaimer_removed = False
                for container in containers:
                    warnings = container.get("warnings", [])
                    container["warnings"] = [
                        warning for warning in warnings
                        if not (
                            warning.startswith("LLM supplier_name '")
                            and " did not match submitted name;" in warning
                            and supplier_names_match(warning.split("'", 2)[1], new_name)
                        )
                    ]
                    risks = container.get("risks", [])
                    if isinstance(risks, list):
                        disclaimer_removed |= any(is_synthetic_disclaimer(risk) for risk in risks)
                        container["risks"] = [risk for risk in risks if not is_synthetic_disclaimer(risk)]
                if isinstance(assessment, dict):
                    assessment["warnings"] = result.get("warnings", assessment.get("warnings", []))
                    assessment["risks"] = result.get("risks", assessment.get("risks", []))
                if disclaimer_removed:
                    result["data_provenance"] = {
                        "synthetic": True,
                        "note": "The proposal identifies its supplier, references, and claims as fictional synthetic demonstration data.",
                    }

                connection.execute(
                    "UPDATE supplier_results SET supplier_name = ?, result_json = ? "
                    "WHERE rfp_run_id = ? AND supplier_name = ?",
                    (new_name, json.dumps(result, ensure_ascii=False, allow_nan=False), run_id, old_name),
                )

            details = json.loads(run["result_json"] or "{}")
            for error in details.get("errors", []):
                if error.get("supplier_name") in name_map:
                    error["supplier_name"] = name_map[error["supplier_name"]]
            connection.execute(
                "UPDATE rfp_runs SET result_json = ? WHERE rfp_run_id = ?",
                (json.dumps(details, ensure_ascii=False, allow_nan=False), run_id),
            )


def list_runs(db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    """Return recent persisted run metadata for the UI's run selector."""
    initialize_database(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT rfp_run_id, created_at, status FROM rfp_runs ORDER BY created_at DESC, rfp_run_id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def load_run(db_path: str | Path, run_id: str) -> dict[str, Any] | None:
    """Load a persisted run and its complete supplier/criterion result payloads."""
    initialize_database(db_path)
    with connect(db_path) as connection:
        run = connection.execute("SELECT * FROM rfp_runs WHERE rfp_run_id = ?", (run_id,)).fetchone()
        if run is None:
            return None
        suppliers = connection.execute(
            "SELECT * FROM supplier_results WHERE rfp_run_id = ? ORDER BY final_rank", (run_id,)
        ).fetchall()
    run_data = dict(run)
    try:
        details = json.loads(run_data.get("result_json") or "{}")
    except json.JSONDecodeError:
        details = {}
    return {
        **run_data,
        "details": details,
        "suppliers": [
            {**dict(row), "result": json.loads(row["result_json"])} for row in suppliers
        ],
    }
