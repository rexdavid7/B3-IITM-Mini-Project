"""Streamlit interface for the existing RFP evaluation services."""

from __future__ import annotations

from datetime import date
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Sequence

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rfp_eval import config as _config  # noqa: E402,F401 - loads local settings, if present
from rfp_eval.database import DEFAULT_DB, list_runs, load_criteria, load_run, seed_criteria  # noqa: E402
from rfp_eval.gemini_client import (  # noqa: E402
    GeminiAPIError,
    GeminiConfigurationError,
    GeminiEvaluator,
    is_placeholder_setting,
)
from rfp_eval.orchestrator import (  # noqa: E402
    BatchEvaluationError,
    EvaluationOrchestrator,
    SupplierSubmission,
)


TIE_BREAK_TEXT = (
    "Rank by PPI, highest first; then earlier submission date; then higher historical "
    "experience rating; then supplier name in ascending order. Absolute weighted score "
    "is displayed but does not determine ranking."
)
SYNTHETIC_DATA_PROVENANCE = {
    "synthetic": True,
    "note": "All four supplier proposals, supplier identities, references and associated claims are fictional synthetic demonstration data.",
}
INTERNAL_SYNTHETIC_WARNING = (
    "Excluded the synthetic-data disclaimer from business risks; retained it as provenance metadata."
)


def suggest_supplier_name(filename: str, pdf_bytes: bytes) -> str:
    """Prefer the PDF's declared supplier name, with a readable filename fallback."""
    try:
        import pymupdf

        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            title = (document.metadata or {}).get("title") or ""
        marker = " - Synthetic Proposal"
        if marker.casefold() in title.casefold():
            return title[:title.casefold().index(marker.casefold())].strip()
    except Exception:
        pass
    stem = Path(filename).stem
    for suffix in ("_proposal", "-proposal", " proposal", "_response", "-response", " response"):
        if stem.casefold().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return " ".join(stem.replace("_", " ").replace("-", " ").split()).title()


def build_submissions(
    uploaded_files: Sequence[Any], metadata: Sequence[dict[str, str]]
) -> tuple[list[SupplierSubmission], list[str]]:
    """Validate required per-file metadata and prepare orchestrator inputs."""
    submissions: list[SupplierSubmission] = []
    errors: list[str] = []
    if not uploaded_files:
        return [], ["Upload at least one proposal PDF."]
    if len(uploaded_files) != len(metadata):
        return [], ["Supplier details are incomplete. Refresh the upload list and try again."]
    names: set[str] = set()
    for index, (uploaded, row) in enumerate(zip(uploaded_files, metadata), start=1):
        label = f"Proposal {index} ({uploaded.name})"
        supplier_name = row.get("supplier_name", "").strip()
        submission_date = row.get("submission_date", "").strip()
        experience_text = row.get("experience_rating", "").strip()
        if not supplier_name:
            errors.append(f"{label}: supplier name is required.")
        elif supplier_name.casefold() in names:
            errors.append(f"{label}: supplier names must be unique.")
        else:
            names.add(supplier_name.casefold())
        try:
            parsed_date = date.fromisoformat(submission_date)
            if parsed_date.isoformat() != submission_date:
                raise ValueError
        except ValueError:
            errors.append(f"{label}: enter a valid submission date as YYYY-MM-DD.")
            parsed_date = None
        try:
            experience = float(experience_text)
            if not math.isfinite(experience):
                raise ValueError
        except ValueError:
            errors.append(f"{label}: experience rating must be a finite number.")
            experience = None
        if supplier_name and parsed_date is not None and experience is not None:
            submissions.append(
                SupplierSubmission(
                    supplier_name=supplier_name,
                    submission_date=parsed_date.isoformat(),
                    experience_rating=experience,
                    pdf_data=uploaded.getvalue(),
                )
            )
    return ([], errors) if errors else (submissions, [])


def safe_supplier_error(error_type: str) -> str:
    """Map internal errors to useful UI text without exposing exception details."""
    if error_type == "PDFDocumentError":
        return "PDF is unreadable, empty, or contains no extractable text."
    if error_type in {"GeminiAPIError", "GeminiConfigurationError"}:
        return "Gemini evaluation failed. Check model access, quota, network, and local credentials."
    if error_type == "LLMValidationError":
        return "The model returned an incomplete or invalid assessment. Review the proposal and retry."
    if error_type == "ValueError":
        return "Supplier metadata is invalid. Check the submission date and experience rating."
    return "This supplier could not be evaluated. Check the proposal and retry."


def export_payload(run: dict[str, Any]) -> dict[str, Any]:
    details = run.get("details") or {}
    safe_errors = [
        {
            "supplier_name": error.get("supplier_name", ""),
            "error_type": error.get("error_type", "EvaluationError"),
            "message": safe_supplier_error(error.get("error_type", "")),
        }
        for error in details.get("errors", [])
    ]
    def round_export_numbers(value: Any, key: str | None = None) -> Any:
        if isinstance(value, dict):
            if key in {"scores", "benchmarks", "gaps", "relative_performance"}:
                return {
                    child_key: round(float(child), 4)
                    if isinstance(child, (int, float)) and not isinstance(child, bool)
                    else round_export_numbers(child, child_key)
                    for child_key, child in value.items()
                }
            return {child_key: round_export_numbers(child, child_key) for child_key, child in value.items()}
        if isinstance(value, list):
            return [round_export_numbers(child, key) for child in value]
        if key in {"score", "max_score", "weight", "absolute_score", "benchmark", "gap", "relative_performance", "ppi"} and isinstance(value, (int, float)) and not isinstance(value, bool):
            return round(float(value), 4)
        return value

    suppliers = [round_export_numbers(row.get("result", {})) for row in run.get("suppliers", [])]
    for supplier in suppliers:
        # Remove only this obsolete implementation note. Genuine assessment warnings remain.
        supplier["warnings"] = [
            warning for warning in supplier.get("warnings", [])
            if warning != INTERNAL_SYNTHETIC_WARNING
        ]
        assessment = supplier.get("assessment")
        if isinstance(assessment, dict):
            assessment["warnings"] = [
                warning for warning in assessment.get("warnings", [])
                if warning != INTERNAL_SYNTHETIC_WARNING
            ]
    criterion_config = {
        str(item["criterion_id"]): item
        for item in details.get("criteria_snapshot", [])
        if item.get("is_active", True)
    }
    for supplier in suppliers:
        criterion_rows = supplier.get("criterion_results", [])
        if not criterion_rows or any(str(item.get("criterion_id")) not in criterion_config for item in criterion_rows):
            continue
        weighted_score = 0.0
        weighted_ppi = 0.0
        for item in criterion_rows:
            criterion_id = str(item["criterion_id"])
            config = criterion_config[criterion_id]
            score = round(float(item["score"]), 4)
            maximum = round(float(item.get("max_score", config["max_score"])), 4)
            weight = round(float(item.get("weight", config["weight"])), 4)
            benchmark = round(float(item["benchmark"]), 4)
            gap = round(score - benchmark, 4)
            relative = 100.0 if benchmark == 0 else round(score / benchmark * 100, 4)
            item.update({
                "score": score,
                "max_score": maximum,
                "weight": weight,
                "benchmark": benchmark,
                "gap": gap,
                "relative_performance": relative,
            })
            supplier.setdefault("scores", {})[criterion_id] = score
            supplier.setdefault("benchmarks", {})[criterion_id] = benchmark
            supplier.setdefault("gaps", {})[criterion_id] = gap
            supplier.setdefault("relative_performance", {})[criterion_id] = relative
            weighted_score += score / maximum * weight / 100
            weighted_ppi += relative * weight / 100
        supplier["absolute_score"] = round(10 * weighted_score, 4)
        supplier["ppi"] = round(weighted_ppi, 4)

    return {
        "rfp_run_id": run["rfp_run_id"],
        "created_at": run["created_at"],
        "status": run["status"],
        "tie_break_rule": TIE_BREAK_TEXT,
        "criteria_snapshot": details.get("criteria_snapshot", []),
        "data_provenance": dict(SYNTHETIC_DATA_PROVENANCE),
        "errors": safe_errors,
        "suppliers": suppliers,
    }


def _streamlit_secret(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
    except Exception:
        return None
    return str(value).strip() if value else None


def _gemini_settings() -> tuple[str | None, str | None]:
    api_key = _streamlit_secret("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = _streamlit_secret("GEMINI_MODEL") or os.getenv("GEMINI_MODEL")
    if is_placeholder_setting(api_key):
        api_key = None
    if is_placeholder_setting(model):
        model = None
    return api_key, model


def _render_criteria() -> list[dict[str, Any]]:
    st.subheader("Evaluation criteria")
    try:
        seed_criteria(DEFAULT_DB)
        criteria = load_criteria(DEFAULT_DB, active_only=True)
    except Exception:
        st.error("Could not load evaluation criteria from SQLite.")
        return []
    if not criteria:
        st.warning("No active criteria were found. Run `python scripts/seed_database.py` to initialize the example criteria.")
        return []
    st.dataframe(
        [
            {
                "Criterion": item["name"],
                "Description": item["description"],
                "Weight": f'{item["weight"]:g}%',
                "Maximum score": f'{item["max_score"]:g}',
            }
            for item in criteria
        ],
        hide_index=True,
        use_container_width=True,
    )
    return criteria


def _collect_supplier_input() -> tuple[list[Any], list[dict[str, str]]] | None:
    st.subheader("Supplier proposals")
    uploaded_files = st.file_uploader(
        "Upload one or more supplier RFP response PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="Text-based PDFs are required; scanned image-only proposals are not OCR processed.",
    )
    if not uploaded_files:
        st.info("Upload proposal PDFs to enter supplier details.")
        return None

    metadata: list[dict[str, str]] = []
    for index, uploaded in enumerate(uploaded_files):
        with st.expander(f"Supplier {index + 1}: {uploaded.name}", expanded=True):
            col_name, col_date, col_experience = st.columns([1.4, 1, 1])
            supplier_name = col_name.text_input(
                "Supplier name *",
                value=suggest_supplier_name(uploaded.name, uploaded.getvalue()),
                key=f"supplier_name_{index}_{uploaded.name}",
            )
            submission_date = col_date.text_input(
                "Submission date *",
                placeholder="YYYY-MM-DD",
                key=f"submission_date_{index}_{uploaded.name}",
            )
            experience_rating = col_experience.text_input(
                "Historical experience rating *",
                placeholder="Numeric rating",
                help="Use one consistent numeric scale for every supplier; higher values mean stronger relevant experience.",
                key=f"experience_rating_{index}_{uploaded.name}",
            )
            metadata.append({
                "supplier_name": supplier_name,
                "submission_date": submission_date,
                "experience_rating": experience_rating,
            })

    return uploaded_files, metadata


def _run_evaluation(submissions: list[SupplierSubmission]) -> None:
    api_key, model = _gemini_settings()
    if not api_key:
        st.error("Gemini API key is not configured. Set GEMINI_API_KEY in Streamlit secrets or the environment.")
        return
    if not model:
        st.error("Gemini model is not configured. Set GEMINI_MODEL in Streamlit secrets or the environment.")
        return

    try:
        evaluator = GeminiEvaluator(api_key=api_key, model=model)
    except GeminiConfigurationError:
        st.error("Could not configure Gemini. Verify the local SDK setup and model settings.")
        return

    progress = st.progress(0, text="Preparing batch…")
    current_status = st.empty()

    def report_progress(completed: int, total: int, supplier_name: str, phase: str) -> None:
        progress.progress(min(completed / total, 1.0), text=f"Evaluated {completed} of {total} suppliers")
        if phase == "Evaluating":
            current_status.info(f"Evaluating {supplier_name}…")
        else:
            current_status.success(f"Finished {supplier_name}")

    try:
        result = EvaluationOrchestrator(evaluator, DEFAULT_DB).evaluate_batch(
            submissions, progress_callback=report_progress
        )
        st.session_state["last_run_id"] = result.get("rfp_run_id")
        if result["status"] == "FAILED":
            st.error("No supplier could be evaluated, so no run was saved.")
            for error in result.get("errors", []):
                st.warning(f'{error.get("supplier_name", "Supplier")}: {safe_supplier_error(error.get("error_type", ""))}')
        elif result["status"] == "COMPLETED_WITH_ERRORS":
            st.warning("The run completed with supplier errors. Successful suppliers were ranked and saved.")
        else:
            st.success("Evaluation completed and the ranked run was saved.")
    except BatchEvaluationError:
        st.error("The evaluation batch could not be ranked or saved. Check SQLite access and try again.")
    except GeminiAPIError:
        st.error("Gemini could not complete this evaluation. Check model access, quota, network, and credentials.")
    except Exception:
        st.error("An unexpected evaluation error occurred. Review the local terminal logs and retry.")
    finally:
        evaluator.close()


def _render_scorecards(run: dict[str, Any]) -> None:
    st.subheader("Detailed scorecards")
    for result in export_payload(run)["suppliers"]:
        name = result.get("supplier_name", "Supplier")
        with st.expander(f'Rank {result.get("final_rank", "—")} · {name}'):
            st.write(result.get("overall_summary", "No overall summary provided."))
            criterion_rows = result.get("criterion_results", [])
            st.dataframe(
                [
                    {
                        "Criterion": item.get("name", ""),
                        "Score": item.get("score"),
                        "Maximum": item.get("max_score"),
                        "Weight": item.get("weight"),
                        "Benchmark": item.get("benchmark"),
                        "Gap": item.get("gap"),
                        "Relative %": item.get("relative_performance"),
                    }
                    for item in criterion_rows
                ],
                hide_index=True,
                use_container_width=True,
            )
            for item in criterion_rows:
                with st.expander(item.get("name", f'Criterion {item.get("criterion_id", "")}')):
                    st.markdown(f'**Evidence**\n\n{item.get("evidence") or "No supporting evidence returned."}')
                    st.markdown(f'**Justification**\n\n{item.get("justification") or "No justification returned."}')
            if result.get("risks"):
                st.markdown("**Risks**")
                for risk in result["risks"]:
                    st.markdown(f"- {risk}")
            warnings = result.get("warnings", [])
            if warnings:
                st.markdown("**Validation warnings**")
                for warning in warnings:
                    st.warning(warning)


def _render_run(run: dict[str, Any]) -> None:
    export = export_payload(run)
    suppliers = export["suppliers"]
    st.subheader("Leaderboard")
    if suppliers:
        first = suppliers[0]
        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("Recommended supplier", first.get("supplier_name", "—"))
        metric2.metric("Top weighted score", f'{first.get("absolute_score", 0):.2f} / 10')
        metric3.metric("Top PPI", f'{first.get("ppi", 0):.2f}%')
        st.dataframe(
            [
                {
                    "Rank": item.get("final_rank"),
                    "Supplier": item.get("supplier_name"),
                    "Absolute score / 10": item.get("absolute_score"),
                    "PPI %": item.get("ppi"),
                    "Submission date": item.get("submission_date"),
                    "Experience rating": item.get("experience_rating"),
                }
                for item in suppliers
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("This run has no successful supplier evaluations.")

    st.subheader("Run details")
    st.code(export["rfp_run_id"], language=None)
    st.write(f'**Status:** {export["status"]}')
    st.caption(export["data_provenance"]["note"])
    st.info(TIE_BREAK_TEXT)
    for error in export["errors"]:
        st.warning(f'{error["supplier_name"]}: {error["message"]}')
    all_warnings = [
        (supplier.get("supplier_name", "Supplier"), warning)
        for supplier in suppliers
        for warning in supplier.get("warnings", [])
    ]
    if all_warnings:
        with st.expander(f"Validation warnings ({len(all_warnings)})", expanded=False):
            for supplier_name, warning in all_warnings:
                st.warning(f"{supplier_name}: {warning}")

    _render_scorecards(run)
    st.download_button(
        "Download complete run as JSON",
        data=json.dumps(export, ensure_ascii=False, indent=2, allow_nan=False),
        file_name=f'rfp_run_{export["rfp_run_id"]}.json',
        mime="application/json",
        use_container_width=True,
    )


def main() -> None:
    st.set_page_config(page_title="Supplier RFP Evaluation", page_icon="📊", layout="wide")
    st.title("Supplier RFP Evaluation")
    st.caption("Evidence-based proposal review with deterministic peer scoring and ranking")

    criteria = _render_criteria()
    st.divider()
    supplier_input = _collect_supplier_input()
    uploaded_files, metadata = supplier_input if supplier_input is not None else ([], [])
    if st.button(
        "Evaluate supplier batch",
        type="primary",
        disabled=not uploaded_files or not criteria,
        use_container_width=True,
    ):
        submissions, errors = build_submissions(uploaded_files, metadata)
        if errors:
            for error in errors:
                st.error(error)
        else:
            _run_evaluation(submissions)

    st.divider()
    st.subheader("Evaluation history")
    try:
        runs = list_runs(DEFAULT_DB)
    except Exception:
        st.error("Could not load evaluation history from SQLite.")
        return
    if not runs:
        st.info("Completed runs will appear here.")
        return
    last_run_id = st.session_state.get("last_run_id")
    run_ids = [run["rfp_run_id"] for run in runs]
    default_index = run_ids.index(last_run_id) if last_run_id in run_ids else 0
    selected_id = st.selectbox(
        "Select a saved run",
        options=run_ids,
        index=default_index,
        format_func=lambda run_id: next(
            f'{run["created_at"][:19]} · {run["status"]} · {run_id[:8]}'
            for run in runs
            if run["rfp_run_id"] == run_id
        ),
    )
    try:
        selected_run = load_run(DEFAULT_DB, selected_id)
    except Exception:
        st.error("The selected run could not be loaded from SQLite.")
        return
    if selected_run:
        _render_run(selected_run)


if __name__ == "__main__":
    main()
