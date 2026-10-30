from pathlib import Path

import pymupdf
import pytest

from rfp_eval.document_reader import extract_pdf_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_DIR = PROJECT_ROOT / "data" / "supplier_proposals"

PROPOSALS = {
    "apex_systems_proposal.pdf": ("Apex Systems", "idempotency key", "20-week"),
    "brightpath_tech_proposal.pdf": ("BrightPath Tech", "13 months", "12-week"),
    "nexaworks_proposal.pdf": ("NexaWorks", "15-minute", "22-week"),
    "orbit_digital_proposal.pdf": ("Orbit Digital", "nine fictional", "18-week"),
}

REQUIRED_SECTIONS = (
    "1. Executive summary",
    "2. Understanding of the university's requirements",
    "3. Proposed solution, architecture, and integrations",
    "4. Implementation plan, timeline, staffing, and responsibilities",
    "5. Commercial proposal",
    "6. Security, compliance, privacy, auditability, and risk",
    "7. Support arrangements, experience, references, and limitations",
)


@pytest.mark.parametrize("filename, expected", PROPOSALS.items())
def test_synthetic_proposal_has_readable_pages_and_expected_supplier_profile(filename, expected):
    path = PROPOSAL_DIR / filename
    assert path.is_file(), f"Missing generated sample: {path}"

    pdf_bytes = path.read_bytes()
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
        assert 2 <= pdf.page_count <= 4
        assert all(page.get_text("text").strip() for page in pdf)

    text = extract_pdf_text(pdf_bytes)
    folded = text.casefold()
    assert len(text) > 5_000
    assert "synthetic demonstration data" in folded
    assert "morrowfield university" in folded
    assert "18,000 applications per year" in text
    assert all(section.casefold() in folded for section in REQUIRED_SECTIONS)
    assert all(phrase.casefold() in folded for phrase in expected)
    assert "three-year total cost of ownership" in folded
    assert ".invalid" in folded


def test_all_proposals_share_one_common_procurement_request():
    extracted = {
        filename: extract_pdf_text((PROPOSAL_DIR / filename).read_bytes())
        for filename in PROPOSALS
    }
    common_requirements = (
        "18,000 applications per year",
        "11 academic divisions",
        "1,200 concurrent portal users",
        "54,000 applicant records",
        "400,000 documents",
        "Ellucian Banner",
        "Microsoft Entra ID",
        "Exchange Online",
        "Box",
        "30 April 2027",
        "seven-year audit-retention plan",
        "three-year total cost of ownership",
    )
    for filename, text in extracted.items():
        normalized = " ".join(text.split()).casefold()
        for requirement in common_requirements:
            assert requirement.casefold() in normalized, (filename, requirement)

