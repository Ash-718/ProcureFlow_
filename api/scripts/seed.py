"""Seed ProcureFlow with demo data.

Everything here is sample data for the prototype.  It is deterministic: running
it twice produces exactly the same rows, so the demo can be reset mid-talk.

Run with:  python -m scripts.seed      (from the api/ directory)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, engine
from app.enums import (
    ChallengeStatus,
    CompanyType,
    DeclineReasonCode,
    KpiDirection,
    KpiStatus,
    Level,
    PilotOutcome,
    PilotStatus,
    ProposalStatus,
    RuleType,
    Tier,
    UserRole,
)
from app.models import (
    AuditLog,
    Award,
    Challenge,
    Company,
    CompanyFounder,
    Department,
    Founder,
    Kpi,
    Pilot,
    ProcurementRule,
    Proposal,
    User,
)
from app.security import hash_password
from app.services import matching
from app.services.rules import RulesService
from app.services.tiering import classify

# ---------------------------------------------------------------------------
# Procurement rules.
#
# These seven are the rules the specification names, and the only rules that
# exist.  Every one is a prototype assumption, so every source_reference is
# empty and the UI labels them as such.  Nothing is added here that the
# specification does not name: an engine that would need another threshold
# reports the fact instead of inventing a limit.
# ---------------------------------------------------------------------------

RULES = [
    dict(
        rule_name="SMALL_TENDER_LIMIT",
        rule_type=RuleType.AMOUNT,
        value=Decimal("5000000"),
        source_reference=None,
        description=(
            "Value at or below which a challenge is considered for the SMALL tier. "
            "Prototype setting - a real deployment must map this to the department's "
            "delegated financial powers."
        ),
    ),
    dict(
        rule_name="MEDIUM_TENDER_LIMIT",
        rule_type=RuleType.AMOUNT,
        value=Decimal("50000000"),
        source_reference=None,
        description=(
            "Upper value boundary of the MEDIUM tier; above this a challenge is "
            "considered for LARGE. Prototype setting."
        ),
    ),
    dict(
        rule_name="MIN_STARTUP_BIDS",
        rule_type=RuleType.COUNT,
        value=Decimal("3"),
        source_reference=None,
        description=(
            "Minimum number of qualified startup bids a MEDIUM challenge must attract "
            "before the large-firm fallback may be considered. Prototype setting."
        ),
    ),
    dict(
        rule_name="MIN_TECH_SCORE",
        rule_type=RuleType.SCORE,
        value=Decimal("60"),
        source_reference=None,
        description=(
            "Technical score out of 100 at or above which a bid counts as qualified. "
            "Prototype setting."
        ),
    ),
    dict(
        rule_name="BID_WINDOW_DAYS",
        rule_type=RuleType.DAYS,
        value=Decimal("21"),
        source_reference=None,
        description=(
            "Days a published challenge stays open for proposals before the fallback "
            "trigger is evaluated. Prototype setting."
        ),
    ),
    dict(
        rule_name="STARTUP_ALLOCATION_PCT",
        rule_type=RuleType.PERCENTAGE,
        value=Decimal("25"),
        source_reference=None,
        description=(
            "Share of procurement opportunities the platform tracks against as a "
            "startup participation target. Prototype setting - it has no source "
            "reference and the fairness dashboard must label it as such."
        ),
    ),
    dict(
        rule_name="MIN_QUALIFIED_ALTERNATIVES",
        rule_type=RuleType.COUNT,
        value=Decimal("2"),
        source_reference=None,
        description=(
            "How many other qualified startups must exist before the rotation rule is "
            "allowed to block a repeat winner. Prototype setting."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    ("Water Supply and Sanitation Department", "WSSD", "Mumbai City"),
    ("Urban Development Department", "UDD", "Mumbai City"),
    ("Public Health Department", "PHD", "Mumbai City"),
    ("Agriculture Department", "AGRI", "Pune"),
    ("Transport Department", "TRANS", "Mumbai City"),
    ("Energy Department", "ENERGY", "Mumbai City"),
    ("School Education Department", "EDU", "Pune"),
    ("Environment and Climate Change Department", "ENV", "Mumbai City"),
]

# ---------------------------------------------------------------------------
# Startups: 30 across Maharashtra districts, with varied capability profiles.
# (name, district, category, profile_text, dpiit_recognised, incorporated, staff)
# ---------------------------------------------------------------------------

STARTUPS = [
    ("AquaSense Analytics", "Pune", "WATER",
     "Acoustic leak detection and non-revenue water analytics for municipal water "
     "networks. Pressure sensor meshes, district metering area balancing, burst "
     "localisation within 50 metres. Deploys on existing SCADA feeds.",
     True, date(2019, 6, 11), 24),
    ("PureFlow Systems", "Nashik", "WATER",
     "Low-cost inline water quality monitoring: turbidity, residual chlorine and "
     "TDS telemetry for rural piped schemes, with SMS alerts to gram panchayat "
     "operators.",
     True, date(2021, 2, 3), 12),
    ("JalNet Telemetry", "Nagpur", "WATER",
     "LoRaWAN telemetry for overhead tanks and borewell pumps. Remote pump "
     "scheduling, dry-run protection and consumption dashboards for ULBs.",
     True, date(2020, 9, 15), 18),
    ("EcoCycle Robotics", "Pune", "WASTE",
     "Optical sorting robots for dry waste segregation at material recovery "
     "facilities. Computer vision classification of plastics by polymer grade.",
     True, date(2020, 1, 20), 31),
    ("WasteWise Analytics", "Thane", "WASTE",
     "Route optimisation and bin fill-level prediction for solid waste collection "
     "fleets, using GPS traces and weighbridge records.",
     True, date(2021, 7, 8), 15),
    ("BinBuddy Systems", "Nagpur", "WASTE",
     "RFID-tagged household bin tracking with door-to-door collection compliance "
     "reporting for municipal corporations.",
     False, date(2022, 3, 14), 9),
    ("UrbanFlow Mobility", "Mumbai Suburban", "TRANSPORT",
     "Bus bunching prediction and headway control for city transport undertakings. "
     "Real-time AVL ingestion, depot scheduling support, passenger ETA feeds.",
     True, date(2018, 11, 5), 42),
    ("TransitIQ Labs", "Pune", "TRANSPORT",
     "Origin-destination demand modelling from ticketing data, used to redesign "
     "bus route networks and rationalise frequencies.",
     True, date(2021, 5, 19), 16),
    ("SafeRoute AI", "Nashik", "TRANSPORT",
     "Computer vision black-spot detection on highway camera feeds, with crash risk "
     "scoring for road engineering teams.",
     True, date(2020, 8, 27), 21),
    ("MedBridge Health", "Mumbai City", "HEALTH",
     "Teleconsultation and referral tracking between primary health centres and "
     "district hospitals, with offline-first clinical record capture.",
     True, date(2019, 3, 12), 38),
    ("AshaCare Diagnostics", "Chhatrapati Sambhajinagar", "HEALTH",
     "Point-of-care haemoglobin and anaemia screening devices for ASHA workers, "
     "with automatic upload to the district health register.",
     True, date(2020, 12, 1), 27),
    ("VitalTrack Systems", "Kolhapur", "HEALTH",
     "Remote patient vitals monitoring for post-operative follow-up in rural "
     "hospitals; wearable integration and escalation workflows.",
     True, date(2022, 1, 25), 11),
    ("AgriTrace Solutions", "Nashik", "AGRICULTURE",
     "Crop disease early warning from multispectral drone imagery and weather "
     "models, specialised in grape and pomegranate horticulture.",
     True, date(2019, 10, 9), 29),
    ("FarmSight AI", "Ahmednagar", "AGRICULTURE",
     "Satellite-based crop acreage estimation and yield forecasting for crop "
     "insurance verification and procurement planning.",
     True, date(2021, 4, 16), 19),
    ("GreenYield Labs", "Jalgaon", "AGRICULTURE",
     "Soil nutrient testing kits with app-based fertiliser recommendations "
     "calibrated to local soil health card data.",
     True, date(2022, 6, 30), 8),
    ("KrishiConnect", "Amravati", "AGRICULTURE",
     "Farmer producer organisation marketplace with mandi price discovery, "
     "aggregation logistics and payment reconciliation.",
     False, date(2021, 11, 22), 14),
    ("SolarGrid Analytics", "Solapur", "ENERGY",
     "Remote monitoring of solar agricultural pumps: generation telemetry, theft "
     "detection and preventive maintenance scheduling.",
     True, date(2020, 5, 7), 23),
    ("VoltEdge Systems", "Chandrapur", "ENERGY",
     "Distribution transformer health monitoring and outage prediction for state "
     "distribution companies.",
     True, date(2021, 9, 13), 17),
    ("ShikshaLoop", "Pune", "EDUCATION",
     "Teacher training workflow and classroom observation tooling for state school "
     "systems, with competency tracking.",
     True, date(2020, 2, 18), 13),
    ("LearnSetu", "Latur", "EDUCATION",
     "Foundational literacy and numeracy diagnostics in Marathi, delivered offline "
     "on low-end Android devices in zilla parishad schools.",
     True, date(2021, 8, 4), 10),
    ("SurakshaVision", "Mumbai City", "PUBLIC_SAFETY",
     "Video analytics for crowd density estimation and abandoned object detection "
     "at transport hubs and public events.",
     True, date(2019, 7, 23), 34),
    ("RespondNow Systems", "Thane", "PUBLIC_SAFETY",
     "Emergency dispatch optimisation for ambulance and fire services, with live "
     "unit tracking and nearest-resource routing.",
     True, date(2021, 1, 11), 20),
    ("CivicDesk Technologies", "Pune", "GOVTECH",
     "Citizen grievance intake and SLA tracking across departments, with Marathi "
     "voice-to-text complaint registration.",
     True, date(2020, 4, 6), 26),
    ("GovForms Digital", "Mumbai City", "GOVTECH",
     "Digitisation of departmental forms and approvals, e-sign integration and "
     "audit-ready workflow records.",
     True, date(2021, 3, 29), 22),
    ("NagarSeva Apps", "Nagpur", "GOVTECH",
     "Municipal property tax assessment support using drone survey imagery and "
     "GIS parcel reconciliation.",
     False, date(2022, 2, 8), 7),
    ("StreetLight IQ", "Nashik", "URBAN_INFRA",
     "Centralised control and fault detection for municipal street lighting, "
     "including energy audit reporting and NOC compliance.",
     True, date(2020, 10, 14), 16),
    ("BridgeScan Robotics", "Ratnagiri", "URBAN_INFRA",
     "Drone and crawler based structural inspection of bridges and culverts, with "
     "crack width measurement and defect classification.",
     True, date(2021, 6, 2), 12),
    ("DrainMap Systems", "Sangli", "URBAN_INFRA",
     "Storm water drain mapping and flood hotspot prediction using elevation models "
     "and rainfall nowcasts.",
     True, date(2022, 4, 19), 9),
    ("AirSense Monitors", "Chandrapur", "ENVIRONMENT",
     "Low-cost calibrated air quality micro-sensor networks with source "
     "apportionment reporting for industrial clusters.",
     True, date(2020, 7, 21), 25),
    ("TreeCensus Analytics", "Satara", "ENVIRONMENT",
     "Urban tree census and canopy change detection from aerial imagery, with "
     "species identification and health scoring.",
     False, date(2022, 8, 26), 6),
]

# ---------------------------------------------------------------------------
# Legacy firms (the incumbents the SMALL tier excludes).
# ---------------------------------------------------------------------------

LEGACY_FIRMS = [
    ("Deshmukh Infra Ltd", "Mumbai City",
     "Turnkey civil and electrical infrastructure contractor; 30 years of state "
     "and municipal projects.", date(1994, 5, 2), 1450),
    ("Konkan Constructions Pvt Ltd", "Ratnagiri",
     "Coastal roads, bridges and water supply headworks execution.",
     date(1998, 8, 17), 820),
    ("Sahyadri Engineering Works", "Pune",
     "Mechanical and pumping station erection, O&M contracts for water utilities.",
     date(1991, 2, 11), 1100),
    ("Godavari Systems Ltd", "Nashik",
     "Systems integration for municipal SCADA, command centres and networking.",
     date(2003, 6, 24), 640),
    ("Vidarbha Infratech Ltd", "Nagpur",
     "Urban infrastructure execution, street lighting and drainage packages.",
     date(2000, 9, 8), 930),
    ("Bharat Civil Projects Ltd", "Mumbai Suburban",
     "Large civil works, depot construction and transport infrastructure.",
     date(1987, 11, 30), 2200),
    ("Maratha Power Systems Ltd", "Solapur",
     "Distribution network works, substation build and electrical maintenance.",
     date(1996, 1, 19), 760),
    ("Krishna Water Works Ltd", "Sangli",
     "Water treatment plant construction and pipeline laying at district scale.",
     date(1999, 4, 5), 580),
    ("Ajanta Technologies Ltd", "Chhatrapati Sambhajinagar",
     "IT systems integration, data centre operations and departmental helpdesks.",
     date(2005, 7, 14), 1300),
    ("Pratap Industrial Services Ltd", "Thane",
     "Facilities management, fleet operations and industrial maintenance.",
     date(1993, 3, 27), 1720),
]

# ---------------------------------------------------------------------------
# Founders.
#
# Four founders deliberately appear on more than one company: the fairness
# dashboard counts opportunities per founder group, and the rotation rule in
# the SMALL tier resolves at founder level so that re-entering through a newly
# incorporated entity does not reset the counter.
# ---------------------------------------------------------------------------

SHARED_FOUNDERS = [
    ("Aditi Deshmukh", "aditi.deshmukh@example.in", "DIN-1000241",
     [("AquaSense Analytics", "Co-founder, CEO"), ("PureFlow Systems", "Co-founder")]),
    ("Rohan Kulkarni", "rohan.kulkarni@example.in", "DIN-1000318",
     [("UrbanFlow Mobility", "Founder"), ("TransitIQ Labs", "Co-founder, CTO")]),
    ("Sneha Pawar", "sneha.pawar@example.in", "DIN-1000452",
     [("AgriTrace Solutions", "Co-founder"), ("FarmSight AI", "Co-founder"),
      ("GreenYield Labs", "Director")]),
    ("Imran Shaikh", "imran.shaikh@example.in", "DIN-1000577",
     [("CivicDesk Technologies", "Co-founder"), ("GovForms Digital", "Director"),
      ("NagarSeva Apps", "Director")]),
]

# One further founder per remaining startup, so every company has at least one.
SOLO_FOUNDER_NAMES = {
    "AquaSense Analytics": "Vikram Rane",
    "PureFlow Systems": "Meera Joshi",
    "JalNet Telemetry": "Sagar Bhosale",
    "EcoCycle Robotics": "Nandini Iyer",
    "WasteWise Analytics": "Prathamesh Gaikwad",
    "BinBuddy Systems": "Ritu Chavan",
    "UrbanFlow Mobility": "Farah Qureshi",
    "TransitIQ Labs": "Anand Sathe",
    "SafeRoute AI": "Kiran More",
    "MedBridge Health": "Dr Ananya Rao",
    "AshaCare Diagnostics": "Dr Sameer Wagh",
    "VitalTrack Systems": "Pooja Nikam",
    "AgriTrace Solutions": "Harshad Patil",
    "FarmSight AI": "Yogesh Kadam",
    "GreenYield Labs": "Trupti Sonawane",
    "KrishiConnect": "Balasaheb Jadhav",
    "SolarGrid Analytics": "Nikhil Mane",
    "VoltEdge Systems": "Swati Dhote",
    "ShikshaLoop": "Rutuja Kale",
    "LearnSetu": "Mahesh Salunkhe",
    "SurakshaVision": "Zoya Ansari",
    "RespondNow Systems": "Ajinkya Pathare",
    "CivicDesk Technologies": "Neha Bhagat",
    "GovForms Digital": "Tushar Vaidya",
    "NagarSeva Apps": "Shubham Ingle",
    "StreetLight IQ": "Devendra Shinde",
    "BridgeScan Robotics": "Omkar Naik",
    "DrainMap Systems": "Aarti Kulkarni",
    "AirSense Monitors": "Ketan Deshpande",
    "TreeCensus Analytics": "Snehal Bagade",
}

# ---------------------------------------------------------------------------
# Eight completed past challenges, each with a pilot and validated KPI results.
# These are the cross-department knowledge base and the verified track record
# that replaces turnover and prior-experience requirements.
#
# (title, dept_code, district, category, value, criticality, innovation, tier,
#  startup, cost, outcome, lessons, [(kpi, target, unit, method, claimed,
#  validated, direction)], months_ago)
# ---------------------------------------------------------------------------

PAST_CHALLENGES = [
    (
        "Reduce non-revenue water losses in Nashik zone 3",
        "WSSD", "Nashik", "WATER", Decimal("4200000"), Level.MEDIUM, Level.HIGH,
        Tier.SMALL, "AquaSense Analytics", Decimal("3980000"), PilotOutcome.SCALE,
        "District metering areas had to be re-balanced before the acoustic sensors "
        "gave stable readings. Budget two weeks for baseline data collection before "
        "measuring anything.",
        [("Leak localisation accuracy", Decimal("85"), "percent",
          "Field verification of flagged leaks against excavation results",
          Decimal("91"), Decimal("88"),
          KpiDirection.HIGHER_IS_BETTER),
         ("Non-revenue water reduction", Decimal("15"), "percent",
          "Monthly zone water balance against billed consumption",
          Decimal("19"), Decimal("17"),
          KpiDirection.HIGHER_IS_BETTER)],
        26,
    ),
    (
        "Street light fault detection across Pune ward offices",
        "UDD", "Pune", "URBAN_INFRA", Decimal("3500000"), Level.LOW, Level.MEDIUM,
        Tier.SMALL, "StreetLight IQ", Decimal("3410000"), PilotOutcome.SCALE,
        "Ward-level electricians needed a Marathi mobile view; the web dashboard "
        "alone was not used in the field.",
        [("Fault detection lead time", Decimal("24"), "hours",
          "Time between lamp failure and ticket creation, sampled weekly",
          Decimal("9"), Decimal("11"),
          KpiDirection.LOWER_IS_BETTER),
         ("Complaint volume reduction", Decimal("30"), "percent",
          "Citizen complaints on street lighting, compared with the prior quarter",
          Decimal("38"), Decimal("34"),
          KpiDirection.HIGHER_IS_BETTER)],
        22,
    ),
    (
        "Anaemia screening coverage at primary health centres",
        "PHD", "Chhatrapati Sambhajinagar", "HEALTH", Decimal("12000000"),
        Level.HIGH, Level.MEDIUM, Tier.MEDIUM, "AshaCare Diagnostics",
        Decimal("11600000"), PilotOutcome.MODIFY,
        "Device accuracy met the target but upload reliability over rural networks "
        "did not. The modified scope adds offline queueing before any wider rollout.",
        [("Screening coverage of registered women", Decimal("70"), "percent",
          "District health register cross-check, monthly",
          Decimal("74"), Decimal("68"),
          KpiDirection.HIGHER_IS_BETTER),
         ("Result upload within 24 hours", Decimal("90"), "percent",
          "Server-side timestamp comparison against device capture time",
          Decimal("88"), Decimal("71"),
          KpiDirection.HIGHER_IS_BETTER)],
        19,
    ),
    (
        "Early warning for grape crop disease in Nashik belt",
        "AGRI", "Nashik", "AGRICULTURE", Decimal("2800000"), Level.MEDIUM,
        Level.HIGH, Tier.SMALL, "AgriTrace Solutions", Decimal("2750000"),
        PilotOutcome.SCALE,
        "Advisories worked best when pushed three days before a predicted downy "
        "mildew window; anything earlier was ignored by growers.",
        [("Disease prediction lead time", Decimal("72"), "hours",
          "Comparison of advisory timestamp with field-confirmed onset",
          Decimal("84"), Decimal("78"),
          KpiDirection.HIGHER_IS_BETTER),
         ("Fungicide spray reduction", Decimal("20"), "percent",
          "Grower spray logs against the previous season on matched plots",
          Decimal("26"), Decimal("22"),
          KpiDirection.HIGHER_IS_BETTER)],
        17,
    ),
    (
        "Reduce bus bunching on high-frequency Mumbai corridors",
        "TRANS", "Mumbai Suburban", "TRANSPORT", Decimal("18000000"), Level.MEDIUM,
        Level.HIGH, Tier.MEDIUM, "UrbanFlow Mobility", Decimal("17200000"),
        PilotOutcome.SCALE,
        "Headway control only held once depot supervisors were given the same "
        "screen as the control room. Driver incentives were out of scope and "
        "remain the main constraint.",
        [("Headway adherence", Decimal("75"), "percent",
          "AVL trace analysis of scheduled versus actual headway",
          Decimal("81"), Decimal("79"),
          KpiDirection.HIGHER_IS_BETTER),
         ("Average passenger wait time", Decimal("7"), "minutes",
          "Stop-level boarding data sampled across the pilot corridors",
          Decimal("6"), Decimal("6"),
          KpiDirection.LOWER_IS_BETTER)],
        14,
    ),
    (
        "Remote monitoring of solar agricultural pumps in Solapur",
        "ENERGY", "Solapur", "ENERGY", Decimal("4900000"), Level.MEDIUM, Level.MEDIUM,
        Tier.SMALL, "SolarGrid Analytics", Decimal("4850000"), PilotOutcome.MODIFY,
        "Theft detection produced too many false positives on cloudy days. The "
        "generation baseline needs seasonal calibration before scaling.",
        [("Pump uptime visibility", Decimal("95"), "percent",
          "Share of installed pumps reporting at least daily",
          Decimal("96"), Decimal("93"),
          KpiDirection.HIGHER_IS_BETTER),
         ("Maintenance response time", Decimal("48"), "hours",
          "Ticket creation to field engineer closure, monthly average",
          Decimal("41"), Decimal("52"),
          KpiDirection.LOWER_IS_BETTER)],
        11,
    ),
    (
        "Foundational numeracy diagnostics in Latur zilla parishad schools",
        "EDU", "Latur", "EDUCATION", Decimal("1900000"), Level.MEDIUM, Level.MEDIUM,
        Tier.SMALL, "LearnSetu", Decimal("1850000"), PilotOutcome.SCALE,
        "Offline-first mattered more than any model quality: 40 percent of the "
        "schools had no usable data connection during school hours.",
        [("Students assessed", Decimal("8000"), "students",
          "Unique student assessment records synced to the district server",
          Decimal("9120"), Decimal("8740"),
          KpiDirection.HIGHER_IS_BETTER),
         ("Teacher adoption", Decimal("60"), "percent",
          "Share of trained teachers running at least one assessment cycle",
          Decimal("71"), Decimal("64"),
          KpiDirection.HIGHER_IS_BETTER)],
        8,
    ),
    (
        "Industrial air quality micro-sensing in Chandrapur cluster",
        "ENV", "Chandrapur", "ENVIRONMENT", Decimal("9500000"), Level.HIGH,
        Level.HIGH, Tier.MEDIUM, "AirSense Monitors", Decimal("9200000"),
        PilotOutcome.REJECT,
        "Sensor drift against the reference station exceeded acceptable limits "
        "after six weeks in high-particulate conditions. Co-location calibration "
        "must be a contractual milestone, not a commissioning step.",
        [("Agreement with reference station", Decimal("80"), "percent",
          "Hourly PM2.5 correlation with the MPCB reference analyser",
          Decimal("78"), Decimal("61"),
          KpiDirection.HIGHER_IS_BETTER),
         ("Sensor network uptime", Decimal("90"), "percent",
          "Share of sensors reporting valid data per day",
          Decimal("92"), Decimal("86"),
          KpiDirection.HIGHER_IS_BETTER)],
        5,
    ),
]


def wipe(db: Session) -> None:
    """Empty every table, children first, and restart the identity sequences."""
    tables = [
        "audit_log",
        "award",
        "partnership",
        "pilot",
        "proposal",
        "kpi",
        "challenge",
        "company_founder",
        "founder",
        "app_user",
        "department",
        "company",
        "procurement_rule",
    ]
    db.execute(text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
    db.commit()


def seed_rules(db: Session) -> None:
    for rule in RULES:
        db.add(
            ProcurementRule(
                active=True,
                effective_from=date(2026, 4, 1),
                **rule,
            )
        )
    db.flush()


def seed_departments(db: Session) -> dict[str, Department]:
    departments = {}
    for name, code, district in DEPARTMENTS:
        dept = Department(name=name, code=code, district=district)
        db.add(dept)
        departments[code] = dept
    db.flush()
    return departments


def seed_companies(db: Session) -> dict[str, Company]:
    companies: dict[str, Company] = {}

    for name, district, category, profile, dpiit, incorporated, staff in STARTUPS:
        company = Company(
            name=name,
            type=CompanyType.STARTUP,
            district=district,
            # The category is kept in the profile text so the semantic matcher
            # has it; embeddings are computed when the matcher is built.
            profile_text=f"[{category}] {profile}",
            dpiit_recognised=dpiit,
            incorporation_date=incorporated,
            employee_count=staff,
        )
        db.add(company)
        companies[name] = company

    for name, district, profile, incorporated, staff in LEGACY_FIRMS:
        company = Company(
            name=name,
            type=CompanyType.LEGACY,
            district=district,
            profile_text=profile,
            dpiit_recognised=False,
            incorporation_date=incorporated,
            employee_count=staff,
        )
        db.add(company)
        companies[name] = company

    db.flush()
    return companies


def seed_founders(db: Session, companies: dict[str, Company]) -> None:
    for name, email, identity_ref, links in SHARED_FOUNDERS:
        founder = Founder(name=name, email=email, identity_ref=identity_ref)
        db.add(founder)
        db.flush()
        for company_name, role_title in links:
            db.add(
                CompanyFounder(
                    company_id=companies[company_name].id,
                    founder_id=founder.id,
                    role_title=role_title,
                )
            )

    for index, (company_name, founder_name) in enumerate(SOLO_FOUNDER_NAMES.items(), start=1):
        slug = founder_name.lower().replace(" ", ".").replace("dr.", "dr")
        founder = Founder(
            name=founder_name,
            email=f"{slug}@example.in",
            identity_ref=f"DIN-20{index:05d}",
        )
        db.add(founder)
        db.flush()
        db.add(
            CompanyFounder(
                company_id=companies[company_name].id,
                founder_id=founder.id,
                role_title="Founder",
            )
        )
    db.flush()


def seed_users(
    db: Session, companies: dict[str, Company], departments: dict[str, Department]
) -> dict[str, User]:
    """The four demo accounts, one per role."""
    password_hash = hash_password(settings.demo_password)
    accounts = [
        ("officer@mahagov.in", "Priya Kulkarni", UserRole.GOVERNMENT, None, "WSSD"),
        ("founder@startup.in", "Aditi Deshmukh", UserRole.STARTUP, "AquaSense Analytics", None),
        ("expert@evaluator.in", "Dr Ramesh Iyer", UserRole.EXPERT, None, None),
        ("admin@procureflow.in", "Platform Admin", UserRole.ADMIN, None, None),
    ]
    users: dict[str, User] = {}
    for email, full_name, role, company_name, dept_code in accounts:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=role,
            company_id=companies[company_name].id if company_name else None,
            department_id=departments[dept_code].id if dept_code else None,
        )
        db.add(user)
        users[email] = user
    db.flush()
    return users


def seed_history(
    db: Session,
    companies: dict[str, Company],
    departments: dict[str, Department],
    officer: User,
) -> None:
    """Past challenges, their pilots, validated KPIs and awards."""
    now = datetime.now(timezone.utc)

    for entry in PAST_CHALLENGES:
        (
            title,
            dept_code,
            district,
            category,
            value,
            criticality,
            innovation,
            tier,
            startup_name,
            cost,
            outcome,
            lessons,
            kpi_rows,
            months_ago,
        ) = entry

        startup = companies[startup_name]
        started = now - timedelta(days=months_ago * 30)
        completed = started + timedelta(days=120)

        challenge = Challenge(
            title=title,
            description_raw=(
                f"Historical challenge completed by the {departments[dept_code].name}. "
                f"Sample data for the ProcureFlow prototype."
            ),
            department_id=departments[dept_code].id,
            created_by_user_id=officer.id,
            value=value,
            criticality=criticality,
            innovation_potential=innovation,
            tier=tier,
            tier_explanation=(
                "Seeded historical record: tier as recorded at the time of award. "
                "Live challenges are classified by the tier engine."
            ),
            status=ChallengeStatus.COMPLETED,
            district=district,
            requires_onsite=True,
            category=category,
            structured_spec={
                "problem_statement": title,
                "source": "seed",
            },
            missing_fields=[],
            kpis_locked=True,
            approved_by_user_id=officer.id,
            approved_at=started,
            published_at=started,
            bid_closes_at=started + timedelta(days=21),
        )
        db.add(challenge)
        db.flush()

        for kpi_name, target, unit, method, claimed, validated, direction in kpi_rows:
            db.add(
                Kpi(
                    challenge_id=challenge.id,
                    startup_id=startup.id,
                    name=kpi_name,
                    target_value=target,
                    unit=unit,
                    measurement_method=method,
                    direction=direction,
                    claimed_value=claimed,
                    evidence=f"Pilot closure report for {title}.",
                    claimed_at=completed,
                    validated_value=validated,
                    validated_by=None,  # validated by an external evaluator on paper
                    validated_at=completed + timedelta(days=7),
                    validation_note=(
                        "Validated during pilot closure by an evaluator independent of "
                        "the submitting company."
                    ),
                    status=KpiStatus.VERIFIED,
                )
            )

        db.add(
            Proposal(
                challenge_id=challenge.id,
                startup_id=startup.id,
                summary=f"Winning proposal from {startup_name}.",
                status=ProposalStatus.AWARDED,
                submitted_at=started + timedelta(days=10),
            )
        )

        db.add(
            Pilot(
                challenge_id=challenge.id,
                startup_id=startup.id,
                plan={"note": "Seeded historical pilot."},
                milestones=[],
                status=PilotStatus.CLOSED,
                recommended_outcome=outcome,
                recommendation_reasoning={
                    "note": "Seeded historical record; recorded outcome after officer decision."
                },
                outcome=outcome,
                outcome_decided_by=officer.id,
                outcome_decided_at=completed + timedelta(days=14),
                outcome_note="Recorded at pilot closure.",
                cost=cost,
                lessons_learned=lessons,
                started_on=started.date(),
                planned_end_on=completed.date(),
                completed_on=completed.date(),
            )
        )

        db.add(
            Award(
                challenge_id=challenge.id,
                company_id=startup.id,
                awarded_at=started + timedelta(days=25),
                awarded_by_user_id=officer.id,
                value=value,
            )
        )

        db.add(
            AuditLog(
                actor_user_id=officer.id,
                actor_label="seed script",
                action="AWARD_RECORDED",
                entity_type="challenge",
                entity_id=challenge.id,
                reason=(
                    f"Seeded historical award to {startup_name} for {title}. "
                    f"Pilot outcome recorded as {outcome.value}."
                ),
                details={
                    "tier": tier.value,
                    "value": str(value),
                    "pilot_cost": str(cost),
                    "sample_data": True,
                },
            )
        )

    db.flush()


def seed_demo_challenges(
    db: Session,
    companies: dict[str, Company],
    departments: dict[str, Department],
    users: dict[str, User],
) -> None:
    """Comprehensive demo challenges covering all tiers, all statuses, and full lifecycles."""
    now = datetime.now(timezone.utc)
    officer = users["officer@mahagov.in"]
    expert = users["expert@evaluator.in"]
    rules = RulesService(db)

    # -----------------------------------------------------------------------
    # 1. DRAFT (Incomplete) - SMALL scale
    # Missing budget, timeline, location, criticality, innovation_potential, analysis
    # -----------------------------------------------------------------------
    c1 = Challenge(
        title="Street Light Fault Detection for Municipal Wards",
        description_raw=(
            "Street light outages across municipal wards are currently detected only after resident "
            "complaints or monthly manual inspections. The department seeks an automated fault detection "
            "and alert system using smart metering or feeder monitoring to cut response times and reduce "
            "night-time public safety risks."
        ),
        department_id=departments["UDD"].id,
        created_by_user_id=officer.id,
        value=None,  # missing budget
        district=None,  # missing location
        criticality=None,  # missing
        innovation_potential=None,  # missing
        tier=None,
        tier_explanation="Incomplete draft: cannot classify tier until budget and risk factors are provided.",
        status=ChallengeStatus.DRAFT,
        requires_onsite=True,
        category="URBAN_INFRA",
        structured_spec=None,
        missing_fields=["budget", "timeline", "location", "criticality", "innovation_potential", "analysis"],
        kpis_locked=False,
    )
    db.add(c1)
    db.flush()

    # -----------------------------------------------------------------------
    # 2. ANALYZED (Incomplete) - MEDIUM scale
    # Structured spec generated, but missing budget and timeline
    # -----------------------------------------------------------------------
    c2 = Challenge(
        title="Automated Diagnostic Pathology Tele-Reporting for Rural PHCs",
        description_raw=(
            "Primary health centres in rural talukas lack on-site pathologists, causing delays of 4 to 7 "
            "days for basic blood smear, urine analysis, and biochemistry reports. We need automated digital "
            "microscopy imaging and tele-pathology reporting to provide certified diagnostic turnaround "
            "within 4 hours for pregnant women and acute fever patients."
        ),
        department_id=departments["PHD"].id,
        created_by_user_id=officer.id,
        value=None,  # missing budget
        district="Kolhapur",
        criticality=Level.MEDIUM,
        innovation_potential=Level.HIGH,
        tier=None,
        tier_explanation="Analysis complete: awaiting budget and implementation timeline from department.",
        status=ChallengeStatus.ANALYZED,
        requires_onsite=True,
        category="HEALTH",
        structured_spec={
            "problem_statement": "Deliver certified pathology tele-reports to rural PHCs within 4 hours using digital imaging telemetry.",
            "required_capabilities": [
                "Digital microscopy tele-reporting",
                "HL7 / FHIR health register sync",
                "Offline-capable sample tracking",
            ],
            "expected_outcomes": [
                "Same-day diagnostic decision support for rural medical officers",
                "Eliminate travel burden for pregnant mothers",
            ],
            "suggested_kpis": [
                {
                    "name": "Report turnaround time",
                    "target_value": None,
                    "unit": "hours",
                    "direction": "LOWER_IS_BETTER",
                    "measurement_method": "Sample collection timestamp to validated tele-report delivery",
                },
                {
                    "name": "Diagnostic concordance with reference laboratory",
                    "target_value": None,
                    "unit": "percent",
                    "direction": "HIGHER_IS_BETTER",
                    "measurement_method": "Blind monthly audit of 50 samples against district hospital lab",
                },
            ],
            "analysis_source": "template",
            "missing_fields": ["budget", "timeline"],
        },
        missing_fields=["budget", "timeline"],
        kpis_locked=False,
    )
    db.add(c2)
    db.flush()

    # -----------------------------------------------------------------------
    # 3. APPROVED (Complete, ready to publish) - SMALL tier
    # All fields provided, KPIs locked, ready for officer to publish
    # -----------------------------------------------------------------------
    v3 = Decimal("3800000")  # 38 Lakhs <= 50L
    d3 = classify(rules, value=v3, criticality=Level.MEDIUM, innovation_potential=Level.HIGH)
    c3 = Challenge(
        title="Solar Pump Remote Monitoring for Rural Farms",
        description_raw=(
            "Remote telemetry and anti-theft monitoring for agricultural solar pumps across drought-prone "
            "rural farmlands. Solar pump installations often experience unnoticed inverter faults, dry runs, "
            "and component theft. The department requires an IoT retrofit solution for 500 pumps in Solapur."
        ),
        department_id=departments["ENERGY"].id,
        created_by_user_id=officer.id,
        value=v3,
        district="Solapur",
        criticality=Level.MEDIUM,
        innovation_potential=Level.HIGH,
        tier=d3.tier,
        tier_explanation=d3.explanation,
        status=ChallengeStatus.APPROVED,
        requires_onsite=True,
        category="ENERGY",
        structured_spec={
            "problem_statement": "Deploy IoT telemetry across 500 solar agricultural pump installations to deliver real-time uptime visibility and dry-run alerts.",
            "timeline": "6 months",
            "required_capabilities": ["Cellular IoT telemetry", "Dry-run pump protection", "Theft detection"],
            "expected_outcomes": ["Zero unreported pump failures", "Farmer mobile SMS notifications"],
        },
        missing_fields=[],
        kpis_locked=True,
        approved_by_user_id=officer.id,
        approved_at=now - timedelta(days=2),
    )
    db.add(c3)
    db.flush()

    db.add(
        Kpi(
            challenge_id=c3.id,
            name="Pump uptime visibility",
            target_value=Decimal("95"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Percentage of pumps successfully transmitting telemetry at least once daily",
            status=KpiStatus.PENDING,
        )
    )
    db.add(
        Kpi(
            challenge_id=c3.id,
            name="Fault notification lead time",
            target_value=Decimal("30"),
            unit="minutes",
            direction=KpiDirection.LOWER_IS_BETTER,
            measurement_method="Time elapsed between inverter fault trigger and SMS notification to farmer",
            status=KpiStatus.PENDING,
        )
    )

    # -----------------------------------------------------------------------
    # 4. PUBLISHED (Open for bidding) - MEDIUM tier
    # -----------------------------------------------------------------------
    v4 = Decimal("24000000")  # 2.4 Crores
    d4 = classify(rules, value=v4, criticality=Level.MEDIUM, innovation_potential=Level.MEDIUM)
    c4 = Challenge(
        title="Smart Bus Fleet Monitoring for Pune Urban Transit",
        description_raw=(
            "Intelligent transit management system for 250 municipal buses in Pune: automatic vehicle "
            "location (AVL), schedule adherence tracking, headway regulation on high-density corridors, and "
            "passenger information display feeds at major terminals."
        ),
        department_id=departments["TRANS"].id,
        created_by_user_id=officer.id,
        value=v4,
        district="Pune",
        criticality=Level.MEDIUM,
        innovation_potential=Level.MEDIUM,
        tier=d4.tier,
        tier_explanation=d4.explanation,
        status=ChallengeStatus.PUBLISHED,
        requires_onsite=True,
        category="TRANSPORT",
        structured_spec={
            "problem_statement": "Implement real-time bus tracking and headway regulation across Pune bus corridors.",
            "timeline": "12 months",
            "required_capabilities": ["AVL GPS telematics", "Depot dispatch integration", "GTFS-RT public feeds"],
            "expected_outcomes": ["Reduced passenger waiting time", "Reliable real-time arrival estimates"],
        },
        missing_fields=[],
        kpis_locked=True,
        approved_by_user_id=officer.id,
        approved_at=now - timedelta(days=10),
        published_at=now - timedelta(days=7),
        bid_closes_at=now + timedelta(days=14),
    )
    db.add(c4)
    db.flush()

    db.add(
        Kpi(
            challenge_id=c4.id,
            name="Headway adherence on core corridors",
            target_value=Decimal("80"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="AVL trace verification of scheduled vs observed bus headway",
            status=KpiStatus.PENDING,
        )
    )
    db.add(
        Kpi(
            challenge_id=c4.id,
            name="Average passenger wait time",
            target_value=Decimal("8"),
            unit="minutes",
            direction=KpiDirection.LOWER_IS_BETTER,
            measurement_method="Sampled stop-level commuter boarding records across peak hours",
            status=KpiStatus.PENDING,
        )
    )

    # -----------------------------------------------------------------------
    # 5. PUBLISHED (Open for bidding) - LARGE tier
    # District-scale deployment, high budget, hardware + software + maintenance
    # -----------------------------------------------------------------------
    v5 = Decimal("85000000")  # 8.5 Crores
    d5 = classify(rules, value=v5, criticality=Level.HIGH, innovation_potential=Level.MEDIUM)
    c5 = Challenge(
        title="District-Wide Smart Public Transport and Fleet Optimization Platform",
        description_raw=(
            "Large-scale multimodal transit tracking, automated passenger counting (APC), and intelligent "
            "timetable dynamic dispatch platform covering 1,200 buses and 45 depots across Mumbai Suburban."
        ),
        department_id=departments["TRANS"].id,
        created_by_user_id=officer.id,
        value=v5,
        district="Mumbai Suburban",
        criticality=Level.HIGH,
        innovation_potential=Level.MEDIUM,
        tier=d5.tier,
        tier_explanation=d5.explanation,
        status=ChallengeStatus.PUBLISHED,
        requires_onsite=True,
        category="TRANSPORT",
        structured_spec={
            "problem_statement": "Deploy an integrated fleet management, IoT telemetry, and passenger counting platform for 1,200 buses across Mumbai Suburban.",
            "timeline": "24 months",
            "required_capabilities": [
                "Enterprise fleet SCADA",
                "Depot ERP integration",
                "Automated passenger counting (APC)",
                "Predictive maintenance",
            ],
            "expected_outcomes": [
                "15% fleet operating cost reduction",
                "Statewide mobility data exchange compliance",
            ],
        },
        missing_fields=[],
        kpis_locked=True,
        approved_by_user_id=officer.id,
        approved_at=now - timedelta(days=8),
        published_at=now - timedelta(days=5),
        bid_closes_at=now + timedelta(days=16),
    )
    db.add(c5)
    db.flush()

    db.add(
        Kpi(
            challenge_id=c5.id,
            name="Fleet availability percentage",
            target_value=Decimal("92"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Daily depot operational availability ratio across scheduled routes",
            status=KpiStatus.PENDING,
        )
    )
    db.add(
        Kpi(
            challenge_id=c5.id,
            name="Peak-hour headway reliability",
            target_value=Decimal("85"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="GPS trace adherence within 2-minute tolerance band",
            status=KpiStatus.PENDING,
        )
    )

    # -----------------------------------------------------------------------
    # 6. EVALUATION (Bids closed, under review) - LARGE tier
    # -----------------------------------------------------------------------
    v6 = Decimal("68000000")  # 6.8 Crores
    d6 = classify(rules, value=v6, criticality=Level.HIGH, innovation_potential=Level.MEDIUM)
    c6 = Challenge(
        title="Statewide Telemedicine and Rural Specialist Consultation Grid",
        description_raw=(
            "Comprehensive tele-consultation, electronic health records (ABDM-compliant), and remote "
            "specialist referral grid connecting 350 rural primary health centres to 12 government medical colleges."
        ),
        department_id=departments["PHD"].id,
        created_by_user_id=officer.id,
        value=v6,
        district="Chhatrapati Sambhajinagar",
        criticality=Level.HIGH,
        innovation_potential=Level.MEDIUM,
        tier=d6.tier,
        tier_explanation=d6.explanation,
        status=ChallengeStatus.EVALUATION,
        requires_onsite=True,
        category="HEALTH",
        structured_spec={
            "problem_statement": "Establish statewide tele-consultation grid linking 350 PHCs with specialist doctors at regional medical colleges.",
            "timeline": "18 months",
            "required_capabilities": [
                "ABDM FHIR architecture",
                "Low-bandwidth video consultations",
                "Digital prescription and diagnostic orders",
            ],
            "expected_outcomes": [
                "Over 50,000 rural tele-consultations per month",
                "Reduction of non-emergency hospital referrals",
            ],
        },
        missing_fields=[],
        kpis_locked=True,
        approved_by_user_id=officer.id,
        approved_at=now - timedelta(days=30),
        published_at=now - timedelta(days=25),
        bid_closes_at=now - timedelta(days=4),
    )
    db.add(c6)
    db.flush()

    db.add(
        Kpi(
            challenge_id=c6.id,
            name="Specialist consultation completion rate",
            target_value=Decimal("85"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Referrals resulting in signed clinical consultation within 24 hours",
            status=KpiStatus.PENDING,
        )
    )
    db.add(
        Kpi(
            challenge_id=c6.id,
            name="Average patient wait time for tele-triage",
            target_value=Decimal("15"),
            unit="minutes",
            direction=KpiDirection.LOWER_IS_BETTER,
            measurement_method="Time from nurse intake to remote doctor connection",
            status=KpiStatus.PENDING,
        )
    )

    # 3 Applicant proposals scored by matching engine
    eval_candidates = [
        (
            "MedBridge Health",
            "MedBridge TeleGrid: ABDM-compliant offline-first telemedicine suite with automated specialist triage and peripheral device telemetry.",
            True,
        ),
        (
            "AshaCare Diagnostics",
            "AshaCare TeleLink: Mobile health diagnostic cart integration with central hospital specialist roster.",
            False,
        ),
        (
            "VitalTrack Systems",
            "VitalTrack RuralConnect: Vital sensors with video escalation for remote medical officer support.",
            False,
        ),
    ]
    for startup_name, summary, evaluated in eval_candidates:
        company = companies[startup_name]
        score_res = matching.score_company(db, c6, company)
        prop = Proposal(
            challenge_id=c6.id,
            startup_id=company.id,
            summary=summary,
            status=ProposalStatus.UNDER_REVIEW if evaluated else ProposalStatus.SUBMITTED,
            submitted_at=now - timedelta(days=12),
            total_score=matching.decimal_score(score_res),
            sub_scores=matching.as_sub_scores_json(score_res),
        )
        if evaluated:
            prop.claimed_by_user_id = expert.id
            prop.expert_scores = {
                "scores": [
                    {"criterion": "technical_soundness", "score": 90, "reason": "Robust offline-first architecture for rural connectivity."},
                    {"criterion": "feasibility_in_the_field", "score": 88, "reason": "Demonstrated field pilots in primary health settings."},
                    {"criterion": "value_for_money", "score": 85, "reason": "Competitive per-consultation pricing."},
                    {"criterion": "risk_and_mitigation", "score": 87, "reason": "Sound data privacy and ABDM compliance mitigation."},
                    {"criterion": "team_and_delivery_capacity", "score": 90, "reason": "Experienced clinical informatics team."},
                ],
                "evaluator_user_id": expert.id,
                "recorded_at": (now - timedelta(days=2)).isoformat(),
                "note": "Top-tier technical capability with proven rural health record.",
            }
            prop.expert_note = "Top-tier technical capability with proven rural health record."
        db.add(prop)

    # -----------------------------------------------------------------------
    # 7. PILOT (Awarded, running pilot with claimed KPIs) - MEDIUM tier
    # -----------------------------------------------------------------------
    v7 = Decimal("16000000")  # 1.6 Crores
    d7 = classify(rules, value=v7, criticality=Level.MEDIUM, innovation_potential=Level.MEDIUM)
    c7 = Challenge(
        title="Digital Health Screening Platform for Primary Health Centres",
        description_raw=(
            "Point-of-care digital screening for non-communicable diseases (diabetes, hypertension, and anaemia) "
            "deployed across 40 PHCs in Chhatrapati Sambhajinagar."
        ),
        department_id=departments["PHD"].id,
        created_by_user_id=officer.id,
        value=v7,
        district="Chhatrapati Sambhajinagar",
        criticality=Level.MEDIUM,
        innovation_potential=Level.MEDIUM,
        tier=d7.tier,
        tier_explanation=d7.explanation,
        status=ChallengeStatus.PILOT,
        requires_onsite=True,
        category="HEALTH",
        structured_spec={
            "problem_statement": "Screen 25,000 citizens in rural blocks for early NCD signs using portable diagnostic kits.",
            "timeline": "8 months",
            "required_capabilities": [
                "Portable blood glucose and Hb testing",
                "Aadhaar e-KYC integration",
                "Offline data synchronization",
            ],
            "expected_outcomes": [
                "Early detection of chronic ailments",
                "Seamless sync with NCD district portal",
            ],
        },
        missing_fields=[],
        kpis_locked=True,
        approved_by_user_id=officer.id,
        approved_at=now - timedelta(days=65),
        published_at=now - timedelta(days=60),
        bid_closes_at=now - timedelta(days=39),
    )
    db.add(c7)
    db.flush()

    # Challenge-level locked KPIs
    db.add(
        Kpi(
            challenge_id=c7.id,
            name="Screening coverage target",
            target_value=Decimal("80"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Verified screening entries in district registry vs registered target population",
            status=KpiStatus.PENDING,
        )
    )
    db.add(
        Kpi(
            challenge_id=c7.id,
            name="Data synchronization within 24 hours",
            target_value=Decimal("90"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Telemetry timestamp of upload vs device timestamp of screening",
            status=KpiStatus.PENDING,
        )
    )

    pilot_startup = companies["AshaCare Diagnostics"]
    score_p7 = matching.score_company(db, c7, pilot_startup)
    db.add(
        Proposal(
            challenge_id=c7.id,
            startup_id=pilot_startup.id,
            summary="AshaCare Point-of-Care NCD Screening Suite with automatic ASHA register sync.",
            status=ProposalStatus.AWARDED,
            submitted_at=now - timedelta(days=50),
            total_score=matching.decimal_score(score_p7),
            sub_scores=matching.as_sub_scores_json(score_p7),
        )
    )
    db.add(
        Award(
            challenge_id=c7.id,
            company_id=pilot_startup.id,
            awarded_at=now - timedelta(days=35),
            awarded_by_user_id=officer.id,
            value=v7,
        )
    )
    db.add(
        Pilot(
            challenge_id=c7.id,
            startup_id=pilot_startup.id,
            plan={"approved_by": officer.id, "note": "Pilot approved across 40 PHCs in 3 talukas."},
            milestones=[
                {"name": "Device distribution and ASHA worker training", "purpose": "Deploy 120 screening kits to 40 PHCs", "status": "COMPLETED"},
                {"name": "Field screening Phase 1", "purpose": "Complete first 10,000 screenings in taluka blocks", "status": "RUNNING"},
                {"name": "Cloud analytics and registry sync", "purpose": "Full integration with district health dashboard", "status": "PENDING"},
            ],
            status=PilotStatus.RUNNING,
            cost=Decimal("15200000"),
            started_on=(now - timedelta(days=30)).date(),
            planned_end_on=(now + timedelta(days=90)).date(),
        )
    )
    # Supplier reporting KPIs
    db.add(
        Kpi(
            challenge_id=c7.id,
            startup_id=pilot_startup.id,
            name="Screening coverage target",
            target_value=Decimal("80"),
            claimed_value=Decimal("82"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Verified screening entries in district registry vs registered target population",
            evidence="Mid-term field report: 11,400 screened across taluka blocks.",
            claimed_at=now - timedelta(days=5),
            status=KpiStatus.UNDER_REVIEW,
        )
    )
    db.add(
        Kpi(
            challenge_id=c7.id,
            startup_id=pilot_startup.id,
            name="Data synchronization within 24 hours",
            target_value=Decimal("90"),
            claimed_value=Decimal("88"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Telemetry timestamp of upload vs device timestamp of screening",
            evidence="Server upload sync logs for October.",
            claimed_at=now - timedelta(days=5),
            status=KpiStatus.PENDING,
        )
    )

    # -----------------------------------------------------------------------
    # 8. FULL LIFECYCLE DEMONSTRATION - LARGE & COMPLETED
    # Multi-applicant -> awarded -> pilot executed -> validated KPIs -> scale decision
    # -----------------------------------------------------------------------
    v8 = Decimal("78000000")  # 7.8 Crores
    d8 = classify(rules, value=v8, criticality=Level.HIGH, innovation_potential=Level.MEDIUM)
    c8 = Challenge(
        title="Integrated Smart Water Management and Non-Revenue Water Reduction — Nashik District",
        description_raw=(
            "Full district-scale smart water network: deployment of 350 electromagnetic flow meters, acoustic "
            "leak localizers, pressure-management valves, and district metering area (DMA) water-balance telemetry "
            "across 8 urban zones in Nashik District to combat 38% non-revenue water loss."
        ),
        department_id=departments["WSSD"].id,
        created_by_user_id=officer.id,
        value=v8,
        district="Nashik",
        criticality=Level.HIGH,
        innovation_potential=Level.MEDIUM,
        tier=d8.tier,
        tier_explanation=d8.explanation,
        status=ChallengeStatus.COMPLETED,
        requires_onsite=True,
        category="WATER",
        structured_spec={
            "problem_statement": "District-scale non-revenue water reduction across 8 urban municipal distribution networks in Nashik District.",
            "timeline": "18 months",
            "required_capabilities": [
                "Acoustic leak localizers",
                "District metering area (DMA) SCADA",
                "Hydraulic network modelling",
                "Automated billing reconciliation",
            ],
            "expected_outcomes": [
                "Reduce NRW from 38% to under 20%",
                "Conserve 24 million litres of potable water per day",
            ],
        },
        missing_fields=[],
        kpis_locked=True,
        approved_by_user_id=officer.id,
        approved_at=now - timedelta(days=240),
        published_at=now - timedelta(days=230),
        bid_closes_at=now - timedelta(days=209),
    )
    db.add(c8)
    db.flush()

    # Challenge-level locked KPIs
    db.add(
        Kpi(
            challenge_id=c8.id,
            name="Non-revenue water reduction",
            target_value=Decimal("18"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Monthly volumetric DMA mass balance against billed meter volume",
            status=KpiStatus.PENDING,
        )
    )
    db.add(
        Kpi(
            challenge_id=c8.id,
            name="Acoustic leak pinpointing accuracy",
            target_value=Decimal("85"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Field excavation validation of acoustic anomaly coordinates",
            status=KpiStatus.PENDING,
        )
    )

    full_startup = companies["AquaSense Analytics"]
    score_p8 = matching.score_company(db, c8, full_startup)
    db.add(
        Proposal(
            challenge_id=c8.id,
            startup_id=full_startup.id,
            summary="AquaSense Enterprise NRW: Acoustic pressure-transient leak pinpointing with automated DMA balance balancing.",
            status=ProposalStatus.AWARDED,
            submitted_at=now - timedelta(days=215),
            total_score=matching.decimal_score(score_p8),
            sub_scores=matching.as_sub_scores_json(score_p8),
        )
    )
    db.add(
        Proposal(
            challenge_id=c8.id,
            startup_id=companies["PureFlow Systems"].id,
            summary="PureFlow inline sensor network for DMA flow and pressure monitoring.",
            status=ProposalStatus.DECLINED,
            submitted_at=now - timedelta(days=214),
            decline_reason_code=DeclineReasonCode.STRONGER_ALTERNATIVE_SELECTED,
            decline_detail="AquaSense offered superior DMA balancing algorithms and demonstrated integration with Nashik municipal SCADA.",
        )
    )
    db.add(
        Proposal(
            challenge_id=c8.id,
            startup_id=companies["JalNet Telemetry"].id,
            summary="JalNet tank and pump telemetry for rural water distribution.",
            status=ProposalStatus.DECLINED,
            submitted_at=now - timedelta(days=213),
            decline_reason_code=DeclineReasonCode.CAPABILITY_MISMATCH,
            decline_detail="Solution focused on storage tank telemetry rather than underground distribution acoustic leak localisation.",
        )
    )
    db.add(
        Award(
            challenge_id=c8.id,
            company_id=full_startup.id,
            awarded_at=now - timedelta(days=200),
            awarded_by_user_id=officer.id,
            value=v8,
        )
    )
    db.add(
        Pilot(
            challenge_id=c8.id,
            startup_id=full_startup.id,
            plan={"approved_by": officer.id, "note": "Full 8-zone district deployment."},
            milestones=[
                {"name": "DMA zoning and flow meter installation", "purpose": "Establish 8 distinct metering zones", "status": "COMPLETED"},
                {"name": "Acoustic leak sensor grid deployment", "purpose": "Sensor mesh over 140km distribution network", "status": "COMPLETED"},
                {"name": "SCADA telemetry integration and mass balance", "purpose": "Live water auditing dashboard", "status": "COMPLETED"},
                {"name": "Pilot closure and independent validation", "purpose": "Third-party audit of saved water volume", "status": "COMPLETED"},
            ],
            status=PilotStatus.CLOSED,
            recommended_outcome=PilotOutcome.SCALE,
            recommendation_reasoning={
                "outcome": "SCALE",
                "reasoning": [
                    "Validated NRW loss reduction of 19.4% exceeds the target of 18%.",
                    "Acoustic localisation accuracy of 88.5% exceeds the target of 85%.",
                ],
            },
            outcome=PilotOutcome.SCALE,
            outcome_decided_by=officer.id,
            outcome_decided_at=now - timedelta(days=30),
            outcome_note="Full district rollout approved. Non-revenue water losses dropped by 19.4%, outperforming target.",
            cost=Decimal("74500000"),
            lessons_learned="Acoustic sensors required initial calibration against pipeline material age records; once calibrated, burst detection was accurate within 35 meters.",
            started_on=(now - timedelta(days=190)).date(),
            planned_end_on=(now - timedelta(days=40)).date(),
            completed_on=(now - timedelta(days=35)).date(),
        )
    )
    # Validated supplier KPIs
    db.add(
        Kpi(
            challenge_id=c8.id,
            startup_id=full_startup.id,
            name="Non-revenue water reduction",
            target_value=Decimal("18"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Monthly volumetric DMA mass balance against billed meter volume",
            claimed_value=Decimal("20.2"),
            evidence="District metering zone mass balance report for Q2.",
            claimed_at=now - timedelta(days=38),
            validated_value=Decimal("19.4"),
            validated_by=expert.id,
            validated_at=now - timedelta(days=32),
            validation_note="Verified by National Environmental Engineering Research Institute (NEERI) audit.",
            status=KpiStatus.VERIFIED,
        )
    )
    db.add(
        Kpi(
            challenge_id=c8.id,
            startup_id=full_startup.id,
            name="Acoustic leak pinpointing accuracy",
            target_value=Decimal("85"),
            unit="percent",
            direction=KpiDirection.HIGHER_IS_BETTER,
            measurement_method="Field excavation validation of acoustic anomaly coordinates",
            claimed_value=Decimal("91.0"),
            evidence="87 excavation logs from Nashik municipal water division.",
            claimed_at=now - timedelta(days=38),
            validated_value=Decimal("88.5"),
            validated_by=expert.id,
            validated_at=now - timedelta(days=32),
            validation_note="Excavation ground-truthing confirmed 77 of 87 flagged leaks within 50m radius.",
            status=KpiStatus.VERIFIED,
        )
    )

    # -----------------------------------------------------------------------
    # 9. CANCELLED - MEDIUM tier
    # -----------------------------------------------------------------------
    v9 = Decimal("18000000")  # 1.8 Crores
    d9 = classify(rules, value=v9, criticality=Level.MEDIUM, innovation_potential=Level.MEDIUM)
    c9 = Challenge(
        title="Municipal Solid Waste Drone Survey and Landfill Volume Mapping",
        description_raw=(
            "High-resolution photogrammetric drone surveying and volumetric modeling of legacy municipal landfill "
            "sites in Thane to determine waste compaction rates and bio-mining progress."
        ),
        department_id=departments["UDD"].id,
        created_by_user_id=officer.id,
        value=v9,
        district="Thane",
        criticality=Level.MEDIUM,
        innovation_potential=Level.MEDIUM,
        tier=d9.tier,
        tier_explanation=d9.explanation,
        status=ChallengeStatus.CANCELLED,
        requires_onsite=True,
        category="WASTE",
        structured_spec={
            "problem_statement": "Deploy LiDAR and photogrammetry drone surveys to quantify landfill volume across Thane municipal dump sites.",
            "timeline": "6 months",
            "required_capabilities": [
                "Aerial photogrammetry",
                "Digital elevation modeling (DEM)",
                "GIS waste compaction analysis",
            ],
            "expected_outcomes": ["Accurate volume calculation for legacy dumpsite bioremediation"],
        },
        missing_fields=[],
        kpis_locked=True,
        approved_by_user_id=officer.id,
        approved_at=now - timedelta(days=25),
        published_at=now - timedelta(days=20),
    )
    db.add(c9)
    db.flush()

    db.add(
        AuditLog(
            actor_user_id=officer.id,
            actor_label="officer",
            action="CHALLENGE_CANCELLED",
            entity_type="challenge",
            entity_id=c9.id,
            reason="Procurement cancelled: Municipal boundary re-alignment merged the landfill site under Thane-MMRDA joint development zone.",
            details={"previous_status": "PUBLISHED", "tier": "MEDIUM"},
        )
    )

    db.flush()


def index_embeddings(db: Session) -> None:
    """Embed the seeded challenges and companies, when the model is available.

    Doing it here keeps the first search in a demo fast. If sentence-transformers
    is not installed, or the model has not been downloaded, seeding still
    succeeds and says so rather than failing.
    """
    from app.services import embeddings, knowledge

    if not embeddings.is_available():
        print()
        print(f"Embeddings skipped: {embeddings.status().error}")
        print("Semantic search will report itself unavailable until the model can load.")
        return

    print()
    print("Computing embeddings (first run downloads the model)...")
    counts = knowledge.reindex_all(db)
    db.commit()
    print(
        f"  embedded {counts['indexed_challenges']} challenges "
        f"and {counts['indexed_companies']} companies"
    )


def report_counts(db: Session) -> None:
    from app.routers.admin import COUNTED_MODELS

    print("\nRow counts after seeding")
    print("-" * 40)
    for model in COUNTED_MODELS:
        rows = db.scalar(select(func.count()).select_from(model)) or 0
        print(f"{model.__tablename__:<20} {rows:>6}")

    shared = db.execute(
        select(Founder.id, Founder.name, func.count(CompanyFounder.company_id))
        .join(CompanyFounder, CompanyFounder.founder_id == Founder.id)
        .group_by(Founder.id, Founder.name)
        .having(func.count(CompanyFounder.company_id) > 1)
        .order_by(Founder.name)
    ).all()
    print("-" * 40)
    print(f"Founders linked to more than one company: {len(shared)}")
    for founder_id, name, count in shared:
        print(f"  founder {founder_id:>3}  {name:<20} {count} companies")


def main() -> None:
    print(f"Seeding {engine.url.render_as_string(hide_password=True)}")
    with SessionLocal() as db:
        wipe(db)
        seed_rules(db)
        departments = seed_departments(db)
        companies = seed_companies(db)
        seed_founders(db, companies)
        users = seed_users(db, companies, departments)
        seed_history(db, companies, departments, users["officer@mahagov.in"])
        seed_demo_challenges(db, companies, departments, users)
        db.commit()
        index_embeddings(db)
        report_counts(db)
    print("\nDemo accounts (password from DEMO_PASSWORD in .env):")
    for email in [
        "officer@mahagov.in",
        "founder@startup.in",
        "expert@evaluator.in",
        "admin@procureflow.in",
    ]:
        print(f"  {email}")
    print("\nSeed complete.")


if __name__ == "__main__":
    main()
