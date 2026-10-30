# Agentic RFP Evaluation and Supplier Ranking

An IIT Madras / IIT Pravartak classroom mini-project demonstrating an agentic workflow for evaluating multiple supplier proposals against configurable procurement criteria.

The application combines PDF extraction, Gemini-powered proposal assessment, structured response validation, deterministic scoring, peer benchmarking, PPI-based ranking, SQLite persistence, and an interactive Streamlit dashboard.

## Live Application

- **Application:** Streamlit deployment
- **Source code:** [GitHub – B3-IITM-Mini-Project](https://github.com/rexdavid7/B3-IITM-Mini-Project)
- **LLM provider:** Google Gemini (Google Gen AI SDK)
- **Frontend:** Streamlit
- **Database:** SQLite

## Features

- **Configurable evaluation criteria:** Five weighted procurement criteria stored in SQLite.
- **Multiple PDF uploads:** Evaluate multiple supplier proposals in one batch.
- **AI-powered assessment:** Gemini evaluates each proposal against the active criteria.
- **Structured response validation:** Validates model responses, normalizes results, and identifies missing or invalid assessments.
- **Deterministic scoring:** Calculates weighted scores, criterion benchmarks, performance gaps, relative performance, and PPI.
- **Supplier ranking:** Ranks suppliers using the assignment-mandated PPI-first tie-breaking rules.
- **Evaluation history:** Persists completed runs and supplier results in SQLite.
- **Interactive dashboard:** Displays leaderboards, supplier scorecards, supporting evidence, justifications, risks, and warnings.
- **JSON export:** Downloads the complete evaluation run, including criteria, metadata, scores, assessments, and provenance.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| Frontend | Streamlit |
| LLM | Google Gemini |
| LLM integration | Google Gen AI SDK |
| PDF extraction | pypdf |
| Database | SQLite |
| Data validation | Python validation and normalization |
| Configuration | python-dotenv |
| Testing | pytest, Streamlit AppTest |

## Local Setup

### 1. Clone the repository

```powershell
git clone https://github.com/rexdavid7/B3-IITM-Mini-Project.git
cd B3-IITM-Mini-Project
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure Gemini API credentials

Create a `.env` file in the project root:

```text
GEMINI_API_KEY=your-real-api-key
GEMINI_MODEL=model-id-selected-in-ai-studio
```

Obtain an API key through [Google AI Studio](https://aistudio.google.com/).

Choose an available model ID from Google AI Studio and configure it through `GEMINI_MODEL`.

The application uses `python-dotenv` with `override=False`, allowing existing environment variables to take precedence over `.env` values.

**Security:** Never commit `.env`, API keys, or Streamlit secrets to GitHub. These files are excluded through `.gitignore`.

### 5. Initialize the database and verify API connectivity

```powershell
python scripts/seed_database.py
python scripts/gemini_smoke_test.py
```

The smoke test makes one minimal Gemini API request and reports a sanitized success or failure message without displaying credentials.

### 6. Run the application

```powershell
python -m pytest
streamlit run app.py
```

The application opens at:

`http://localhost:8501`

On first start, the application initializes the SQLite schema and inserts the five default evaluation criteria without overwriting existing configurations.

## Evaluation Criteria

The application uses five configurable criteria stored in SQLite.

| Criterion | Description | Weight | Maximum Score |
|---|---|---:|---:|
| Technical Capability | Technical fit, architecture, integrations, and scalability. | 30% | 10 |
| Implementation Plan | Timeline, milestones, staffing, and delivery feasibility. | 20% | 10 |
| Commercial Value | Pricing clarity, total cost, assumptions, and value for money. | 20% | 10 |
| Security & Compliance | Security controls, certifications, privacy, and auditability. | 20% | 10 |
| Support & Experience | Support model, relevant projects, and references. | 10% | 10 |
| **Total** | | **100%** | |

Criteria can be configured through the application's database-backed evaluation criteria functionality.

## Agentic Evaluation Workflow

The evaluation workflow is orchestrated through `EvaluationOrchestrator.evaluate_batch()`.

1. **Criteria retrieval:** Loads the currently active evaluation criteria from SQLite and snapshots them for the batch.
2. **Document extraction:** Extracts proposal text from each uploaded supplier PDF.
3. **AI assessment:** Sends the extracted proposal content and evaluation criteria to Gemini for structured assessment.
4. **Response validation:** Validates the returned JSON structure, criterion IDs, supplier identity, and score values. Normalizes acceptable model variations and generates warnings for missing or invalid information.
5. **Score calculation:** Calculates deterministic weighted scores and criterion-level performance metrics.
6. **Peer benchmarking:** Compares each supplier against the highest observed score for every criterion across the batch.
7. **Supplier ranking:** Calculates PPI and applies the assignment-mandated ranking rules.
8. **Persistence:** Saves successful supplier assessments, evaluation metadata, and run details to SQLite under a unique run ID.
9. **Presentation and export:** Displays results through Streamlit and provides a downloadable JSON representation of the complete run.

Supplier-specific failures are recorded under `errors`. A failed supplier does not prevent other suppliers from being evaluated. An entirely failed batch is not saved as a completed run.

## Scoring Methodology

### Absolute Weighted Score

The absolute weighted score is calculated on a scale of 0–10.

`Absolute Score = 10 × Σ[(Criterion Score / Maximum Score) × (Weight / 100)]`

### Criterion Benchmark

The benchmark for each criterion is the highest observed score among the evaluated suppliers.

`Benchmark = Highest Supplier Score for the Criterion`

### Performance Gap

`Gap = Supplier Score − Criterion Benchmark`

A negative value indicates that the supplier scored below the best-performing supplier for that criterion.

### Relative Performance

`Relative Performance = (Supplier Score / Criterion Benchmark) × 100`

When both supplier score and benchmark are zero, relative performance is defined as 100%.

### Proposal Performance Index (PPI)

PPI represents the weighted average of each supplier's relative performance across all active criteria.

`PPI = Σ[(Relative Performance × Criterion Weight) / 100]`

PPI is expressed as a percentage from 0 to 100.

### Ranking Rules

The assignment-mandated ranking order is:

1. Higher PPI.
2. Earlier submission date.
3. Higher historical experience rating.
4. Supplier name in ascending alphabetical order.

**Important:** Absolute weighted score is displayed for reference but does not determine supplier ranking.

The ranking calculations use unrounded values. Exported display metrics are rounded to four decimal places.

## Latest Demonstration Run

The following results are from the completed evaluation run generated on October 30, 2026.

**Run ID:** `bf08c5a0356846fe833e5a17229c65bc`

**Status:** COMPLETED

**Suppliers evaluated:** 4

**Evaluation errors:** 0

### Leaderboard

| Rank | Supplier | Absolute Score / 10 | PPI |
|---:|---|---:|---:|
| 1 | NexaWorks | 8.60 | 100.0000 |
| 2 | Apex Systems | 7.40 | 86.0714 |
| 3 | Orbit Digital | 6.30 | 73.8889 |
| 4 | BrightPath Tech | 5.00 | 57.3413 |

### Supplier Metadata

The following metadata was used in the completed demonstration run.

| Supplier | Submission Date | Experience Rating |
|---|---|---:|
| NexaWorks | 2026-10-03 | 4 |
| Apex Systems | 2026-10-05 | 4 |
| Orbit Digital | 2026-10-15 | 5 |
| BrightPath Tech | 2026-09-21 | 5 |

Experience ratings are numeric demonstration metadata. The application accepts finite numeric values and does not enforce a predefined rating scale. A consistent scale should be used when comparing suppliers.

### Evaluation Observations

- **NexaWorks:** Strongest overall proposal, with comprehensive technical architecture, detailed implementation planning, transparent commercial pricing, and a well-defined support model. Security claims and fictional references require independent verification.
- **Apex Systems:** Architecture-focused proposal with detailed integration design and strong commercial clarity. Its shorter implementation timeline and on-call after-hours support are identified as limitations.
- **Orbit Digital:** Offers competitive commercial pricing and an 18-week implementation plan. Technical integration details and long-term audit-retention procedures require further clarification.
- **BrightPath Tech:** Lowest quoted three-year cost and fastest implementation schedule. However, it has significant security, compliance, integration, and support limitations.

All supplier proposals, supplier identities, references, and associated claims are fictional synthetic demonstration data. The results demonstrate the evaluation workflow and must not be interpreted as real supplier assessments.

## Response Validation and Error Handling

The validation layer handles:

- Malformed or incomplete JSON responses.
- Missing criterion assessments.
- Duplicate criterion IDs.
- Invalid supplier identities.
- Nonnumeric scores.
- Scores outside configured ranges.
- Recognizable supplier name variations.
- Supplier-specific processing failures.

Missing criterion assessments and nonnumeric scores are assigned zero only with explicit warnings. Numeric out-of-range scores are clipped with warnings.

Validation warnings and supplier risks are maintained separately. The synthetic-data disclaimer is recorded as run-level provenance rather than a supplier risk or validation warning.

Human review of evidence, warnings, and supplier risks is recommended before relying on the resulting ranking.

## Project Structure

```text
B3-IITM-Mini-Project/
│
├── app.py
├── requirements.txt
├── pyproject.toml
├── README.md
├── .gitignore
├── .gitattributes
│
├── data/
│   ├── supplier_proposals/
│   │   ├── apex_systems_proposal.pdf
│   │   ├── brightpath_tech_proposal.pdf
│   │   ├── nexaworks_proposal.pdf
│   │   └── orbit_digital_proposal.pdf
│   │
│   └── rfp_run_53c1cd28921c44cdbb6de0f8dabbc5fc_cleaned.json
│
├── scripts/
│   ├── gemini_smoke_test.py
│   ├── generate_supplier_proposals.py
│   └── seed_database.py
│
├── src/
│   └── rfp_eval/
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       ├── document_reader.py
│       ├── gemini_client.py
│       ├── orchestrator.py
│       ├── scoring.py
│       └── validation.py
│
└── tests/
    ├── conftest.py
    ├── test_app.py
    ├── test_config.py
    ├── test_database.py
    ├── test_document_reader.py
    ├── test_gemini_client.py
    ├── test_orchestrator.py
    ├── test_scoring.py
    ├── test_supplier_proposals.py
    └── test_validation.py
```

## Testing

The project includes automated tests covering:

- Configuration and environment-variable handling.
- PDF text extraction.
- Gemini client integration using mocked responses.
- Structured response validation and normalization.
- Deterministic scoring and PPI calculations.
- Ranking and tie-breaking rules.
- Batch orchestration.
- SQLite persistence and retrieval.
- Streamlit application behaviour.
- Synthetic supplier proposal generation.

Run the complete test suite:

```powershell
python -m pytest
```

The automated tests mock Gemini responses and do not make paid API requests. The separate smoke test performs a real API connectivity check.

## Streamlit Cloud Deployment

The application can be deployed using [Streamlit Community Cloud](https://share.streamlit.io/).

Deployment procedure:

1. Push the project repository to GitHub.
2. Sign in to Streamlit Community Cloud using GitHub.
3. Select **Create app**.
4. Select the `B3-IITM-Mini-Project` repository.
5. Select the `main` branch.
6. Set `app.py` as the application entry point.
7. Configure the application secrets.

Add the following to the Streamlit Cloud Secrets configuration:

```toml
GEMINI_API_KEY = "your-real-api-key"
GEMINI_MODEL = "model-id-selected-in-ai-studio"
```

8. Deploy the application.

The application reads credentials from Streamlit secrets first, followed by environment variables.

**Database limitation:** The application uses SQLite for local persistence. Streamlit Community Cloud does not guarantee persistence of local application files across restarts or redeployments. SQLite is suitable for the classroom demonstration, but a production deployment requiring durable evaluation history should use an external persistent database.

## Limitations

- Gemini-generated assessments depend on the quality and completeness of extracted PDF text.
- LLM assessments can contain interpretation errors and require human review.
- API availability, model access, and usage quotas depend on the Google AI Studio account and selected model.
- Automated tests use mocked LLM responses and do not independently establish assessment quality.
- Supplier benchmarking is relative to the suppliers in the same evaluation batch.
- Synthetic demonstration proposals and associated claims are fictional.
- SQLite persistence on Streamlit Community Cloud is not guaranteed.

## Disclaimer

This project was developed as an academic mini-project to demonstrate agentic workflows, LLM integration, document processing, deterministic evaluation, and supplier ranking.

All demonstration supplier identities, proposals, references, and associated claims are fictional. The application is a demonstration of an AI-assisted procurement evaluation workflow and is not a substitute for formal procurement due diligence or human decision-making.
