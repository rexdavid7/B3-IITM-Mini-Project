# Agentic RFP Evaluation and Supplier Ranking

Classroom mini-project. It includes a Streamlit procurement dashboard, configurable SQLite criteria, deterministic scoring and ranking, PDF extraction, Gemini proposal evaluation, response validation, batch orchestration, persistence, and tests.

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Put these settings in a project-root `.env` file for local development, or set them in the process environment:

```text
GEMINI_API_KEY=your-real-key
GEMINI_MODEL=model-id-selected-in-ai-studio
```

The project loads `.env` via `python-dotenv` with `override=False`, so values already set by the execution environment take precedence. `.env` is listed in `.gitignore`; never commit it. Run `python scripts/gemini_smoke_test.py` to make one minimal request when both settings are present and the key is not a recognizable placeholder. The command does not display the key.

Choose the model ID from Google AI Studio's model picker and check that it is enabled for the API key/account. Google AI Studio's **Get code** panel also shows the ID for the selected model. Model availability and quota can vary, so this project has no assumed default. `GEMINI_MODEL` may be changed without editing the code.

Seed the criteria and run tests:

```powershell
python scripts/seed_database.py
python -m pytest
streamlit run app.py
```

The local app opens at `http://localhost:8501`. On first start it creates the SQLite schema and inserts the five defaults without overwriting existing criteria settings. Supplier metadata validation errors appear only after clicking **Evaluate supplier batch**. The app reads Gemini credentials from Streamlit secrets first, then the environment (including the project `.env` loaded for local development). It never displays credentials.

## Structure

- `src/rfp_eval/scoring.py`: validation and deterministic formulas
- `src/rfp_eval/database.py`: SQLite schema, criteria access, and run persistence
- `src/rfp_eval/document_reader.py`: strict text extraction from uploaded PDFs
- `src/rfp_eval/gemini_client.py`: official Google Gen AI SDK client
- `src/rfp_eval/config.py`: safe project-local `.env` loading
- `src/rfp_eval/validation.py`: LLM schema checks, normalization, and warnings
- `src/rfp_eval/orchestrator.py`: supplier evaluation, batch ranking, and persistence
- `app.py`: Streamlit presentation only; delegates extraction, evaluation, scoring and persistence to the service modules
- `scripts/gemini_smoke_test.py`: one minimal API connectivity check; prints no secrets
- `scripts/seed_database.py`: initializes the database and inserts five defaults without overwriting configuration
- `scripts/generate_supplier_proposals.py`: regenerates the four synthetic proposal PDFs
- `tests/`: deterministic, PDF, validation, persistence, and mocked Gemini tests

## Evaluation flow

`EvaluationOrchestrator.evaluate_batch()` snapshots active criteria from SQLite, then processes each supplier independently: extract PDF text, request a Gemini JSON assessment, normalize and validate it, and prepare a scorecard. It benchmarks and ranks successful proposals as one batch and saves them under one run ID. Supplier-specific failures are returned under `errors`; an all-failed batch is not saved. Persisted supplier results contain criterion-level scores, weights, benchmarks, gaps, relative performance, evidence, justifications, risks, warnings, absolute score, PPI, and rank.

The Streamlit app displays active criteria, collects multiple proposal PDFs and supplier metadata, reports per-supplier failures without exposing raw exception details, and shows saved run leaderboards, scorecards, warnings, tie-break rules, and complete JSON downloads. Run-level details preserve failed supplier information for incomplete batches. Legacy SQLite databases are upgraded to add the run-details JSON column when initialized.

## Formulas

Weights are percentage points (30 means 30%) and active weights must total 100. Absolute weighted score is `10 * sum((score / max_score) * weight / 100)`, on a 0–10 scale. Criterion benchmark is the highest observed score; gap is `supplier score - benchmark`. Relative performance is `score / benchmark * 100`; when both are zero, it is defined as 100%. PPI is the active-weighted average of criterion relative-performance percentages (0–100).

Ranking order (assignment-mandated): PPI descending, earlier ISO submission date, higher historical experience rating, and supplier name ascending. Absolute weighted score is displayed but is not a ranking key.

Missing criterion assessments and nonnumeric scores are assigned zero only with explicit warnings; numeric out-of-range scores are clipped with warnings. Duplicate criterion IDs are rejected as ambiguous. A human should review warnings and evidence before relying on a supplier ranking.

The evaluation prompt scores requirement coverage, evidence quality, feasibility, and material gaps. It tells the model not to reward proposal length, to distinguish claims from substantiating evidence, and to reserve 10/10 for comprehensive coverage with credible evidence and no material unresolved gaps. All four demonstration proposals, supplier identities, references and associated claims are fictional synthetic data; the application labels this at the run level in results and JSON exports. The synthetic-data disclaimer is not a supplier risk or validation warning. JSON exports round calculated display values to four decimal places after the unrounded metrics have determined rank.

## Smoke test limitations

Automated tests mock Gemini responses and do not make paid requests. The smoke-test script makes one small real API request only when a nonempty API key and model are configured; it reports success or a sanitized diagnostic, never the key. A successful smoke test confirms connectivity and model access at that moment; it does not validate proposal-scoring quality or guarantee future quota/availability.

## Synthetic proposal set

`data/supplier_proposals/` contains four synthetic responses to the same Morrowfield University graduate-admissions procurement scenario. Regenerate them with `python scripts/generate_supplier_proposals.py`. The test metadata to enter in the Streamlit uploader is:

| PDF | Supplier name | Submission date | Experience rating |
| --- | --- | --- | ---: |
| `apex_systems_proposal.pdf` | Apex Systems | 2026-10-20 | 8 |
| `brightpath_tech_proposal.pdf` | BrightPath Tech | 2026-10-21 | 3 |
| `nexaworks_proposal.pdf` | NexaWorks | 2026-10-22 | 7 |
| `orbit_digital_proposal.pdf` | Orbit Digital | 2026-10-23 | 9 |

Experience ratings are relative numeric demonstration metadata; higher indicates more relevant experience. The application accepts any finite numeric value and does not define a rating range, so use one consistent scale across suppliers. Required-field and format errors appear after clicking **Evaluate supplier batch**, not while entering supplier details.

`data/rfp_run_fd1151d1f93b4edf9206c847315b98d0_corrected.json` is a corrected export of a completed historical run. Supplier labels and provenance were corrected from the submitted proposal documents; its LLM scores were preserved, not rescored.

`data/rfp_run_b2cb741cf63d4cd0ae5cdb8fed8c6d62_verified.json` is a presentation-rounded export of the next completed run, generated from its persisted SQLite result. It retains the run's supplier metadata and ranks.
