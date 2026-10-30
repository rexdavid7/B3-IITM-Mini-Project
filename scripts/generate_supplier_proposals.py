"""Generate the four fictional, comparable PDF proposals used for demonstrations."""

from __future__ import annotations

from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "supplier_proposals"
NAVY = colors.HexColor("#17324D")
TEAL = colors.HexColor("#087E8B")
INK = colors.HexColor("#263746")
MUTED = colors.HexColor("#637381")
PALE = colors.HexColor("#EAF2F5")
RULE = colors.HexColor("#D8E1E6")

RFP = (
    "Morrowfield University is a fictional public university seeking a secure cloud service for "
    "graduate admissions case management. The same scope applies to every response: 18,000 "
    "applications per year across 11 academic divisions; 55 staff users; peak loads near 1,200 "
    "concurrent portal users; migration of three prior cycles (up to 54,000 applicant records and "
    "approximately 400,000 documents); and a production launch target of 30 April 2027 after a "
    "26-week delivery window beginning 2 November 2026. Required interfaces are Ellucian Banner "
    "student information, Microsoft Entra ID, Exchange Online, and Box. Deliverables include an "
    "applicant portal, configurable review queues, document checklist, decision notifications, "
    "role-based staff workspace, reports, migration, training, and cutover support. The security "
    "baseline asks for TLS 1.2 or stronger, AES-256 encryption at rest, MFA/SSO, least-privilege "
    "access, auditable decisions, a seven-year audit-retention plan, US data residency, annual "
    "independent penetration testing, and incident notice within 24 hours. The university requests "
    "a three-year total cost of ownership, stated assumptions, and a support plan."
)


PROPOSALS = [
    {
        "name": "Apex Systems",
        "filename": "apex_systems_proposal.pdf",
        "label": "Architecture-forward proposal | Higher cost | 20-week schedule",
        "summary": (
            "Apex proposes a single-tenant, managed admissions workspace with a relational case "
            "store, object storage for documents, and asynchronous integration workers. The design "
            "is intended to absorb the stated 1,200-user peak while separating applicant traffic "
            "from staff review queues. The offer prices all four named interfaces and three-cycle "
            "migration in the implementation fee."
        ),
        "understanding": (
            "Apex interprets the seven-year audit requirement as an operational and archival "
            "obligation: two years searchable in the application and five years exported nightly "
            "to the university's controlled archive. It assumes Morrowfield will provide Banner "
            "REST API credentials, Box enterprise app approval, a non-production Entra tenant, "
            "and representative migration extracts by week 3."
        ),
        "solution": (
            "The service is proposed in a US East cloud region with separate production and "
            "non-production accounts. A queue-based adapter layer uses documented Banner REST "
            "resources, Entra SAML plus SCIM provisioning, Microsoft Graph for Exchange notices, "
            "and Box APIs for document references. Each adapter records an idempotency key, retry "
            "count, and reconciliation status; failed messages enter a review queue rather than "
            "being silently discarded. The proposal includes 12 named data mappings and a daily "
            "integration reconciliation report."
        ),
        "timeline": [
            ("Weeks 1-2", "Discovery and tenant readiness", "Confirm data owners, API access, security boundary, and acceptance criteria."),
            ("Weeks 3-6", "Architecture and configuration", "Approve field maps, roles, retention export, and portal prototype."),
            ("Weeks 7-12", "Build and interfaces", "Configure workflow; implement and test four adapters in a shared sandbox."),
            ("Weeks 13-16", "Migration and UAT", "Reconcile three cycles; run load, accessibility, and admissions-team testing."),
            ("Weeks 17-20", "Cutover and hypercare", "Train 55 staff; launch in waves; provide 10 business days of hypercare."),
        ],
        "team": [
            ("Engagement lead", "1.0", "Delivery governance, dependencies, and weekly decision log."),
            ("Solution architect", "1.0", "Security design, data model, and technical approvals."),
            ("Integration engineers", "2.0", "Four adapters, retry handling, and reconciliation."),
            ("Configuration / QA", "1.5", "Workflow configuration, regression, and load testing."),
            ("Security / change", "0.7", "Control evidence, role review, training, and adoption."),
        ],
        "commercial": [
            ("Implementation, migration, and four interfaces", "$186,000", "One-time"),
            ("Managed subscription and standard support", "$114,000", "Per year"),
            ("Three-year total cost of ownership", "$528,000", "$186,000 + 3 x $114,000"),
        ],
        "commercial_notes": (
            "Pricing includes the four interfaces as described, migration of up to 54,000 records "
            "and 400,000 documents, two training cohorts, and standard hosting. Taxes, a fifth "
            "interface, custom document remediation, and more than 10 days of post-launch hypercare "
            "are excluded. Subscription assumes annual prepayment and no more than 20% annual "
            "growth in stored documents."
        ),
        "security": (
            "The synthetic control package states TLS 1.2+ in transit, AES-256 encryption at rest "
            "with managed key rotation, Entra MFA/SCIM, quarterly privileged-access review, and "
            "immutable administrator and decision logs. The proposal describes a fictional SOC 2 "
            "Type II report covering the hosting service and a penetration test completed in July "
            "2026; both are demonstration claims and would require independent verification. The "
            "platform keeps two years of searchable audit events and exports the remaining five "
            "years nightly to the university archive. Stated recovery objectives are RPO 1 hour and "
            "RTO 4 hours. A material risk is the university's timely provision of archive storage "
            "and identity approvals."
        ),
        "support": (
            "Standard support is staffed 08:00-18:00 Eastern on business days, with a 30-minute "
            "acknowledgement target for P1 incidents and a four-hour workaround target. After-hours "
            "P1 coverage is on-call, not a continuously staffed desk. Apex cites the fictional "
            "Westbridge College rollout (11,200 annual applications, 9 integrations) and a "
            "fictional South Quay Institute pilot (7,500 applications). References use reserved "
            "`.invalid` contact domains and are synthetic."
        ),
        "risks": [
            "The 20-week plan leaves six weeks of schedule reserve, but API approvals are on the critical path.",
            "Seven-year retention depends on a customer-managed archive export being monitored by Morrowfield.",
        ],
    },
    {
        "name": "BrightPath Tech",
        "filename": "brightpath_tech_proposal.pdf",
        "label": "Lowest quoted cost | 12-week schedule | Evidence and scope gaps",
        "summary": (
            "BrightPath offers a configurable hosted portal and standard admissions workflow with "
            "the fastest proposed launch. It prices the four requested connections on the assumption "
            "that each target can use an existing template and that Morrowfield supplies clean "
            "data extracts. The proposal emphasizes a small fixed implementation team and a low "
            "three-year price."
        ),
        "understanding": (
            "BrightPath understands the 18,000-application workload, 11 divisions, and 55 staff "
            "users. It proposes a basic portal, review queues, document checklist, decision email, "
            "and dashboard. The submission does not include a detailed throughput estimate for "
            "1,200 concurrent portal users or a field-level migration plan for 400,000 documents."
        ),
        "solution": (
            "The offer uses a shared multi-tenant web service with a relational database and cloud "
            "file storage. It lists Banner, Entra, Exchange, and Box as target interfaces and says "
            "configuration templates will be used where available. It does not identify API "
            "versions, field ownership, retry behavior, duplicate-event handling, or a named "
            "integration engineer. A two-week discovery sprint will confirm whether any interface "
            "needs custom work; the proposal does not attach connector diagrams or sample mappings."
        ),
        "timeline": [
            ("Weeks 1-2", "Kickoff and configuration", "Confirm template availability and provision the shared tenant."),
            ("Weeks 3-5", "Portal and workflow setup", "Configure forms, checklist, review roles, and notification templates."),
            ("Weeks 6-8", "Template integrations", "Connect target systems using standard templates, subject to API access."),
            ("Weeks 9-10", "Data load and user test", "Load customer-prepared extracts and run one staff test cycle."),
            ("Weeks 11-12", "Training and launch", "Train two staff champions and launch after sign-off."),
        ],
        "team": [
            ("Project coordinator", "0.5", "Weekly status and issue log; no dedicated program manager."),
            ("Configuration specialist", "1.0", "Portal fields, review workflow, and standard reports."),
            ("Shared integration pool", "0.5", "Template setup; engineer allocation is not named."),
            ("QA / trainer", "0.5", "Basic functional checks and two remote training sessions."),
        ],
        "commercial": [
            ("Implementation and standard connectors", "$64,000", "One-time"),
            ("Hosted subscription and 8x5 support", "$62,000", "Per year"),
            ("Three-year total cost of ownership", "$250,000", "$64,000 + 3 x $62,000"),
        ],
        "commercial_notes": (
            "This is the lowest quoted three-year total. It assumes all four endpoints work with "
            "BrightPath's existing templates and that the university cleans and stages migration "
            "data. A custom connector is listed at $12,000 each, outside the total; the document "
            "does not estimate the likelihood of that change. Taxes, after-hours support, and "
            "historical document repair are excluded. The quote includes one non-production "
            "environment and two training sessions."
        ),
        "security": (
            "BrightPath states HTTPS/TLS 1.2 and cloud-provider encryption at rest, plus password "
            "MFA and basic role-based permissions. It has no current independent SOC 2 or ISO "
            "27001 evidence in this synthetic submission. The proposal gives no annual penetration "
            "test report, no documented quarterly access review, and no detailed incident workflow. "
            "Application audit logs are retained online for 13 months; a seven-year archive option "
            "is described as a future add-on without a price or export schedule. US hosting is "
            "stated but the specific region is not named. These gaps leave the requested retention "
            "and assurance obligations unresolved."
        ),
        "support": (
            "Support is 08:00-17:00 Eastern on weekdays. P1 acknowledgement is targeted within "
            "two business hours; no after-hours P1 rota or contractual service credit is offered. "
            "BrightPath lists one fictional 2,400-application career-college pilot and a small "
            "internal admissions demo, with no comparable 18,000-application production reference. "
            "Reference names and contacts are synthetic; contact addresses use `.invalid`."
        ),
        "risks": [
            "Fast launch assumes all four connections are template-compatible; custom connectors add cost and time.",
            "The submitted retention, independent testing, and incident evidence do not yet meet the stated baseline.",
            "Migration cleansing and load preparation sit with the university without a quantified effort estimate.",
        ],
    },
    {
        "name": "NexaWorks",
        "filename": "nexaworks_proposal.pdf",
        "label": "Balanced solution | Detailed 22-week plan | Strong transition and support",
        "summary": (
            "NexaWorks proposes a managed, modular admissions platform with a balanced fixed-price "
            "implementation and an explicit 22-week delivery plan. The offer includes the four "
            "requested interfaces, three-cycle migration, role configuration, staff training, and "
            "a two-week hypercare period. Its schedule includes separate security review, integration "
            "testing, data reconciliation, and admissions-user acceptance gates."
        ),
        "understanding": (
            "NexaWorks treats the university's workload, retention, and launch date as acceptance "
            "constraints rather than assumptions to be revisited at cutover. It proposes a verified "
            "count and checksum for up to 54,000 records and 400,000 documents, a divisional review "
            "matrix for all 11 schools, and a peak-load rehearsal at 1,200 concurrent users."
        ),
        "solution": (
            "The design separates the applicant portal, case workflow, document service, and "
            "integration gateway. Banner is connected through a versioned REST adapter with "
            "field ownership agreed in discovery; Entra uses SAML and SCIM; Exchange Online sends "
            "templated decisions through Microsoft Graph; Box stores or references retained "
            "documents using a university-owned enterprise app. The gateway applies correlation "
            "IDs, bounded retries, dead-letter review, and a daily reconciliation dashboard. Data "
            "resides in a named US region, with distinct test and production tenants."
        ),
        "timeline": [
            ("Weeks 1-2", "Mobilize and discover", "Confirm owners, API access, baselines, and acceptance measures."),
            ("Weeks 3-5", "Design and security gate", "Approve architecture, data map, threat review, and retention schedule."),
            ("Weeks 6-11", "Configure and integrate", "Build workflow and four adapters with weekly interface demonstrations."),
            ("Weeks 12-15", "Migrate and verify", "Reconcile records/documents; complete security, accessibility, and load tests."),
            ("Weeks 16-19", "UAT and readiness", "Run divisional scenarios, train 55 staff, and close priority defects."),
            ("Weeks 20-22", "Cutover and transition", "Launch, run two weeks of hypercare, and hand over operating runbooks."),
        ],
        "team": [
            ("Delivery manager", "0.8", "Plan, dependencies, acceptance register, and decision cadence."),
            ("Product / workflow lead", "0.7", "Admissions journeys, roles, and divisional configuration."),
            ("Solution and security architects", "1.0", "Architecture, threat review, and evidence pack."),
            ("Integration / data engineers", "2.0", "Adapters, migration, reconciliation, and runbooks."),
            ("QA / change leads", "1.5", "Test cycles, training, launch readiness, and handover."),
        ],
        "commercial": [
            ("Implementation, migration, and four interfaces", "$104,000", "One-time"),
            ("Managed subscription and enhanced support", "$88,000", "Per year"),
            ("Three-year total cost of ownership", "$368,000", "$104,000 + 3 x $88,000"),
        ],
        "commercial_notes": (
            "The three-year total includes all four standard adapters, migration up to the stated "
            "record/document volumes, two non-production releases, 55 named staff users, training, "
            "and two weeks of hypercare. Taxes, a fifth interface, and migration beyond the stated "
            "volume are excluded. Annual subscription includes routine upgrades and the support "
            "service levels below; any price adjustment after year three requires a renewal quote."
        ),
        "security": (
            "The fictional evidence pack describes TLS 1.2+, AES-256 at rest, customer-managed "
            "key rotation, Entra SSO/MFA, SCIM deprovisioning, quarterly role recertification, and "
            "seven-year searchable audit retention with export. It states a SOC 2 Type II report "
            "covering the service, annual independent penetration testing, a 24-hour incident "
            "notification commitment, and US data residency. These are synthetic claims for the "
            "class exercise and would need document and scope verification before procurement. "
            "Recovery targets are RPO 1 hour and RTO 4 hours. A tabletop incident exercise and "
            "one load rehearsal are included in the plan."
        ),
        "support": (
            "Enhanced support provides 24x7 P1 intake, a 15-minute P1 acknowledgement target, "
            "one-hour P2 acknowledgement, and a named service manager. The proposed monthly "
            "availability target is 99.9%, excluding scheduled maintenance; a service-credit "
            "schedule is attached to the synthetic offer. Two fictional references are listed: "
            "Cedar Point Institute (14,600 annual applications, 4 interfaces) and Larkspur School "
            "of Public Policy (6,800 applications, 3 interfaces). Both contacts use reserved "
            "`.invalid` domains and are fictional."
        ),
        "risks": [
            "Banner sandbox and representative records must be available by week 2 to protect the 22-week plan.",
            "Divisional decision owners must attend UAT in weeks 16-19; delayed sign-off moves cutover.",
        ],
    },
    {
        "name": "Orbit Digital",
        "filename": "orbit_digital_proposal.pdf",
        "label": "Experienced delivery partner | Mid-range cost | Integration detail to confirm",
        "summary": (
            "Orbit Digital offers a mature case-management product and cites a substantial record "
            "of fictional higher-education deployments. The commercial proposal is mid-range and "
            "includes four integration workstreams. The delivery outline targets an 18-week launch, "
            "but the integration design and dependencies are intentionally less specific than the "
            "other responses and require discovery before the schedule can be treated as firm."
        ),
        "understanding": (
            "Orbit recognizes the 18,000-applicant annual workload, 11 academic divisions, 55 staff "
            "users, and three-cycle migration. It proposes a single portal and review workspace "
            "with decision notices and divisional dashboards. It confirms four target systems but "
            "does not yet explain record ownership, synchronization direction, or how integration "
            "exceptions will be reconciled."
        ),
        "solution": (
            "The platform is described as a hosted case-management service with a configurable "
            "connector framework. Orbit expects to connect Banner, Entra, Exchange Online, and "
            "Box through REST or vendor-supported interfaces. The proposal does not attach a "
            "component diagram, interface sequence, sample field map, retry/idempotency policy, "
            "or named adapter owner. It proposes a technical discovery workshop in week 1 and "
            "states that interface estimates may be revised after sandbox access. The stated "
            "18-week plan therefore depends on early clarification of integration complexity."
        ),
        "timeline": [
            ("Weeks 1-2", "Discovery and access", "Review data, API endpoints, security documents, and connector assumptions."),
            ("Weeks 3-5", "Workflow configuration", "Configure portal, review queues, and divisional reporting."),
            ("Weeks 6-11", "Connector workstreams", "Develop four connections after endpoint and ownership decisions."),
            ("Weeks 12-14", "Migration and testing", "Load three cycles and run customer-led user acceptance tests."),
            ("Weeks 15-18", "Training and launch", "Train representatives and cut over if interface dependencies close."),
        ],
        "team": [
            ("Program director", "0.5", "Executive steering and escalation; part-time allocation."),
            ("Functional consultant", "1.0", "Admissions workflow discovery and configuration."),
            ("Integration pool", "1.5", "Four workstreams; individual engineers assigned after discovery."),
            ("Data / test analysts", "1.0", "Migration checks, test scripts, and defect triage."),
            ("Change and support lead", "0.5", "Training, launch readiness, and service transition."),
        ],
        "commercial": [
            ("Implementation, migration, and four workstreams", "$92,000", "One-time"),
            ("Hosted subscription and standard support", "$96,300", "Per year"),
            ("Three-year total cost of ownership", "$380,900", "$92,000 + 3 x $96,300"),
        ],
        "commercial_notes": (
            "The stated total includes four integration workstreams, migration up to 54,000 records "
            "and 400,000 documents, standard hosting, and remote training. It assumes the named "
            "systems expose supported endpoints and that no historical document repair is needed. "
            "Taxes, bespoke connectors beyond the four listed, travel, and a fifth interface are "
            "excluded. If discovery changes an interface estimate by more than 10%, Orbit proposes "
            "a change request; no unit rates are supplied for that work."
        ),
        "security": (
            "Orbit states TLS 1.2+, AES-256 at rest, SAML SSO, configurable MFA enforcement, "
            "role-based access, and US hosting. Audit logs are retained online for three years, "
            "with export available for university archiving; the export frequency and seven-year "
            "operating procedure are not specified. A penetration-test summary is available under "
            "NDA but is not included. The proposal describes annual testing and a 24-hour incident "
            "notification target, but does not provide a sample evidence pack or define whether "
            "the target is contractual. Recovery objectives are listed as RPO 4 hours and RTO "
            "8 hours."
        ),
        "support": (
            "Orbit provides weekday support from 08:00-18:00 Eastern, with an on-call P1 route and "
            "a one-hour acknowledgement target; no 24x7 staffed desk or service-credit schedule is "
            "priced. Orbit cites nine fictional higher-education launches, including Bluevale "
            "Polytechnic (21,000 applicants), Redfern University (13,500), and North Coast Arts "
            "College (8,100). Two references are described as Banner-connected, but only one is "
            "said to have a similar four-system interface scope. Reference contacts use `.invalid` "
            "domains; all are synthetic."
        ),
        "risks": [
            "The 18-week target is conditional on four interface designs being agreed by week 2; no detailed maps are attached.",
            "Three-year audit export and retention operations need a named owner and a tested schedule.",
            "The 8-hour RTO and 4-hour RPO are weaker than the other offers and need business-owner review.",
        ],
    },
]


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ProposalTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=23, leading=27, textColor=NAVY, alignment=TA_LEFT, spaceAfter=5),
        "subtitle": ParagraphStyle("ProposalSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED, spaceAfter=12),
        "section": ParagraphStyle("Section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=NAVY, spaceBefore=6, spaceAfter=5, keepWithNext=True),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=12.3, textColor=INK, spaceAfter=5),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=8, leading=10.2, textColor=INK, spaceAfter=3),
        "banner": ParagraphStyle("Banner", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=TEAL, alignment=TA_CENTER, spaceAfter=5),
        "table_head": ParagraphStyle("TableHead", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.7, leading=9.3, textColor=colors.white),
        "table": ParagraphStyle("Table", parent=base["Normal"], fontName="Helvetica", fontSize=7.5, leading=9.2, textColor=INK),
    }


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def section(title: str, body: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [Paragraph(escape(title), styles["section"]), paragraph(body, styles["body"])]


def table(data: list[tuple[str, ...]], widths: list[float], styles: dict[str, ParagraphStyle], *, header: tuple[str, ...]) -> Table:
    rows = [[paragraph(cell, styles["table_head"]) for cell in header]]
    rows.extend([[paragraph(str(cell), styles["table"]) for cell in row] for row in data])
    result = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.35, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return result


def page_chrome(supplier: str):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = letter
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawString(48, height - 29, "MORROWFIELD UNIVERSITY  /  PROCUREMENT RESPONSE")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawRightString(width - 48, height - 29, supplier.upper())
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(48, height - 36, width - 48, height - 36)
        canvas.line(48, 35, width - 48, 35)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(48, 22, "SYNTHETIC DEMONSTRATION DATA - NOT A REAL COMMERCIAL OFFER")
        canvas.drawRightString(width - 48, 22, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def build_proposal(item: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT / item["filename"]
    doc = SimpleDocTemplate(
        str(destination),
        pagesize=letter,
        leftMargin=48,
        rightMargin=48,
        topMargin=51,
        bottomMargin=48,
        title=f'{item["name"]} - Synthetic Proposal for Morrowfield University',
        author=f'{item["name"]} (fictional demonstration supplier)',
        subject="Synthetic supplier RFP proposal for classroom evaluation",
    )
    story: list[Any] = [
        paragraph("SYNTHETIC PROCUREMENT RESPONSE  |  CLASSROOM DEMONSTRATION", styles["banner"]),
        paragraph(item["name"], styles["title"]),
        paragraph("Graduate Admissions Case Management & Document Workflow", styles["subtitle"]),
        paragraph(item["label"], styles["subtitle"]),
        *section("1. Executive summary", item["summary"], styles),
        *section("2. Understanding of the university's requirements", item["understanding"], styles),
        *section("3. Proposed solution, architecture, and integrations", item["solution"], styles),
        Spacer(1, 4),
        Table(
            [[paragraph("COMMON REQUEST - IDENTICAL FOR ALL FOUR SUPPLIERS", styles["table_head"])],
             [paragraph(escape(RFP), styles["small"])]],
            colWidths=[516],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("BACKGROUND", (0, 1), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.6, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]),
        ),
        PageBreak(),
        Paragraph("4. Implementation plan, timeline, staffing, and responsibilities", styles["section"]),
        paragraph(
            "The schedule below is the supplier's proposed sequence. Dates remain dependent on "
            "timely university decisions, access to test tenants, and acceptance of the stated scope.",
            styles["body"],
        ),
        table(
            item["timeline"], [66, 104, 346], styles,
            header=("Window", "Milestone", "Activities and exit evidence"),
        ),
        Spacer(1, 8),
        Paragraph("Proposed delivery team", styles["section"]),
        table(
            item["team"], [132, 50, 334], styles,
            header=("Role", "FTE", "Responsibility"),
        ),
        Spacer(1, 8),
        Paragraph("Integration and delivery dependencies", styles["section"]),
        paragraph(item["solution"], styles["body"]),
        PageBreak(),
        Paragraph("5. Commercial proposal", styles["section"]),
        table(
            item["commercial"], [220, 105, 191], styles,
            header=("Cost element", "Amount (USD)", "Basis"),
        ),
        Spacer(1, 5),
        paragraph(item["commercial_notes"], styles["small"]),
        *section("6. Security, compliance, privacy, auditability, and risk", item["security"], styles),
        Paragraph("7. Support arrangements, experience, references, and limitations", styles["section"]),
        paragraph(item["support"], styles["body"]),
        Paragraph("Risks and limitations", styles["section"]),
    ]
    for risk in item["risks"]:
        story.append(paragraph(f"| {risk}", styles["small"]))
    story.extend([
        Spacer(1, 3),
        paragraph(
            "All supplier organizations, employees, customers, references, contact details, "
            "attestations, prices, and performance claims in this PDF are fictional synthetic "
            "demonstration data. They are not offers, independently verified evidence, or real "
            "supplier records. Reference domains intentionally use the reserved `.invalid` suffix.",
            styles["small"],
        ),
    ])
    chrome = page_chrome(item["name"])
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return destination


def main() -> None:
    styles = make_styles()
    for proposal in PROPOSALS:
        result = build_proposal(proposal, styles)
        print(f"Generated {result.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
