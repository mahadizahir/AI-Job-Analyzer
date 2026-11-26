import os
import re
import sys
import time
from pathlib import Path
from datetime import date
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv
from sqlalchemy import select, func
from sqlalchemy.orm import Session

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from .database import engine
    from .models import Job, Posting
except ImportError:
    from database import engine
    from models import Job, Posting


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("HEADCOUNTLABS_API_KEY")
API_URL = "https://api.headcountlabs.com/v1/jobs/"

DRY_RUN = False

# 0 = unlimited
# Positive number = stop after reaching the target
TARGET_NEW_JOBS = 0

PAGE_SIZE = 25
MAX_PAGES_PER_SEARCH = 2
MAX_RECORDS_SCANNED = 1250

MAX_RETRIES = 2
REQUEST_TIMEOUT = 35

SEARCH_TITLES = [
    "software",
    "developer",
    "programmer",
    "data",
    "machine learning",
    "artificial intelligence",
    "cybersecurity",
    "security analyst",
    "cloud",
    "devops",
    "network",
    "system administrator",
    "IT support",
    "quality assurance",
    "QA tester",
    "automation",
    "database",
    "business analyst",
    "ERP",
    "SAP",
    "embedded",
    "IoT",
    "mobile developer",
    "internship",
    "graduate"
]


# ==========================================
# JOB CATEGORY CLASSIFICATION
# ==========================================

JOB_CATEGORIES = {
    "Cybersecurity": [
        r"\bcyber[\s-]?security\b",
        r"\binformation security\b",
        r"\bsecurity analyst\b",
        r"\bsecurity engineer\b",
        r"\bsoc analyst\b",
        r"\bpenetration tester\b",
        r"\bpenetration testing\b",
        r"\bethical hacker\b",
        r"\bsecurity operations\b",
        r"\bsecurity specialist\b",
        r"\bvulnerability analyst\b",
        r"\bvulnerability assessment\b",
        r"\bgrc analyst\b",
        r"\bsecurity consultant\b",
        r"\bnetwork security engineer\b",
        r"\bcloud security engineer\b",
        r"\bincident response\b"
    ],

    "Artificial Intelligence & Machine Learning": [
        r"\bartificial intelligence\b",
        r"\bmachine learning\b",
        r"\bdeep learning\b",
        r"\bai engineer\b",
        r"\bai developer\b",
        r"\bai researcher\b",
        r"\bml engineer\b",
        r"\bnlp engineer\b",
        r"\bnatural language processing\b",
        r"\bcomputer vision\b",
        r"\bgenerative ai\b",
        r"\bllm engineer\b",
        r"\bprompt engineer\b",
        r"\bai specialist\b"
    ],

    "Software Testing & Quality Assurance": [
        r"\bsoftware qa\b",
        r"\bqa automation\b",
        r"\bqa automation engineer\b",
        r"\btest automation\b",
        r"\btest automation engineer\b",
        r"\bautomation tester\b",
        r"\bsoftware tester\b",
        r"\bsoftware test engineer\b",
        r"\bsoftware testing\b",
        r"\bperformance tester\b",
        r"\bqa engineer\b",
        r"\bqa tester\b",
        r"\bmobile application tester\b",
        r"\bapplication tester\b"
    ],

    "Cloud & Infrastructure": [
        r"\bcloud engineer\b",
        r"\bcloud architect\b",
        r"\bcloud administrator\b",
        r"\bcloud computing\b",
        r"\bcloud support\b",
        r"\bcloud operations\b",
        r"\bcloud consultant\b",
        r"\bcloud solutions\b",
        r"\bcloud system\b",
        r"\bcloud specialist\b",
        r"\bcloud developer\b",
        r"\bcloud infrastructure\b",
        r"\binfrastructure engineer\b",
        r"\binfrastructure architect\b",
        r"\bsystem administrator\b",
        r"\bsystems administrator\b",
        r"\bsystem engineer\b",
        r"\bplatform engineer\b",
        r"\bserver engineer\b",
        r"\bunix administrator\b",
        r"\blinux administrator\b",
        r"\baws administrator\b",
        r"\bvmware\b",
        r"\bvirtualization engineer\b",
        r"\bvirtualisation engineer\b"
    ],

    "Networking & IT Support": [
        r"\bnetwork engineer\b",
        r"\bnetwork administrator\b",
        r"\bnetwork specialist\b",
        r"\bnetwork technician\b",
        r"\bnetwork analyst\b",
        r"\bnetwork support\b",
        r"\bnetwork operations\b",
        r"\bnetwork architect\b",
        r"\bnetwork infrastructure\b",
        r"\bnetwork test engineer\b",
        r"\bmobile network\b",
        r"\bnetwork operations cent(?:er|re)\b",
        r"\bnoc specialist\b",
        r"\bnoc engineer\b",
        r"\bnoc analyst\b",
        r"\bnetwork\/operation and maintenance engineer\b",
        r"\bnetwork operations and maintenance engineer\b",
        r"\bnetwork maintenance engineer\b",
        r"\bit support\b",
        r"\bit engineer\b",
        r"\btechnical support engineer\b",
        r"\bhelpdesk\b",
        r"\bhelp desk\b",
        r"\bservice desk\b",
        r"\bit technician\b",
        r"\bdesktop support\b",
        r"\bapplication support\b",
        r"\bit infrastructure support\b",
        r"\bsystems support\b",
        r"\bdata cent(?:er|re) network\b"
    ],

    "DevOps & Software Operations": [
        r"\bdevops\b",
        r"\bsite reliability engineer\b",
        r"\bsre\b",
        r"\bci/cd\b",
        r"\bbuild engineer\b",
        r"\brelease engineer\b",
        r"\bdeployment engineer\b",
        r"\bdevsecops\b",
        r"\bproduction support engineer\b",
        r"\bsoftware operations engineer\b"
    ],

    "Data & Business Intelligence": [
        r"\bdata analyst\b",
        r"\bdata scientist\b",
        r"\bdata engineer\b",
        r"\bdata science\b",
        r"\bbusiness intelligence\b",
        r"\bbi developer\b",
        r"\bbi analyst\b",
        r"\bdata analytics\b",
        r"\banalytics engineer\b",
        r"\bsql developer\b",
        r"\bdatabase analyst\b",
        r"\bdatabase developer\b",
        r"\bdatabase administrator\b",
        r"\bdatabase engineer\b",
        r"\bdba\b",
        r"\bdata warehouse\b",
        r"\bbig data\b",
        r"\bdata platform engineer\b",
        r"\bdata management analyst\b",
        r"\bdata integration engineer\b"
    ],

    "Embedded Systems & IoT": [
        r"\bembedded software\b",
        r"\bembedded systems\b",
        r"\bembedded engineer\b",
        r"\bembedded applications engineer\b",
        r"\bembedded software architect\b",
        r"\bembedded architect\b",
        r"\bfirmware engineer\b",
        r"\bfirmware developer\b",
        r"\biot engineer\b",
        r"\biot developer\b",
        r"\binternet of things\b",
        r"\brobotics engineer\b",
        r"\bhardware engineer\b",
        r"\bfpga engineer\b",
        r"\bmicrocontroller\b"
    ],

    "IT Business & Enterprise Systems": [
        r"\bit business analyst\b",
        r"\bbusiness systems analyst\b",
        r"\bsystems analyst\b",
        r"\bsystem analyst\b",
        r"\bit project manager\b",
        r"\benterprise architect\b",
        r"\benterprise architecture\b",
        r"\berp\b",
        r"\bsap\b",
        r"\bmurex\b",
        r"\bservicenow\b",
        r"\bsalesforce\b",
        r"\bdynamics 365\b",
        r"\bms dynamics\b",
        r"\bcrm developer\b",
        r"\bapplication systems analyst\b",
        r"\binformation systems analyst\b",
        r"\bfinancial systems\b",
        r"\bsystems implementation\b"
    ],

    "Software & Application Development": [
        r"\bsoftware architect\b",
        r"\bsoftware engineer\b",
        r"\bsoftware developer\b",
        r"\bsoftware programmer\b",
        r"\bapplication developer\b",
        r"\bapplication development\b",
        r"\bfrontend developer\b",
        r"\bfront[\s-]?end developer\b",
        r"\bbackend developer\b",
        r"\bback[\s-]?end developer\b",
        r"\bfull[\s-]?stack developer\b",
        r"\bweb developer\b",
        r"\bweb development\b",
        r"\bmobile app developer\b",
        r"\bmobile application developer\b",
        r"\bmobile developer\b",
        r"\bflutter developer\b",
        r"\bandroid developer\b",
        r"\bios developer\b",
        r"\bjava developer\b",
        r"\bpython developer\b",
        r"\bc#\s*\.net developer\b",
        r"\b\.net developer\b",
        r"\bc# developer\b",
        r"\breact developer\b",
        r"\bangular developer\b",
        r"\bphp developer\b",
        r"\bgolang developer\b",
        r"\bgame developer\b",
        r"\bgame programmer\b",
        r"\bgameplay programmer\b",
        r"\bsoftware development\b",
        r"\bprogrammer analyst\b",
        r"\btools programmer\b"
    ]
}


# ==========================================
# TITLE EXCLUSIONS
# Exclusions take priority over IT keywords.
# ==========================================

EXCLUDE_PATTERNS = [
    r"\bsales\b",
    r"\bbusiness development\b",
    r"\bpre[\s-]?sales\b",
    r"\bmarketing\b",
    r"\baccount executive\b",
    r"\baccount manager\b",
    r"\bcommercial manager\b",

    r"\bprofessor\b",
    r"\bassistant professor\b",
    r"\bassociate professor\b",
    r"\blecturer\b",
    r"\bdean\b",
    r"\bdeputy dean\b",
    r"\bacademic researcher\b",
    r"\bacademic quality assurance\b",

    r"\brecruiter\b",
    r"\brecruitment consultant\b",
    r"\bhr executive\b",
    r"\bhuman resources\b",
    r"\bpayroll\b",
    r"\bcontent moderator\b",
    r"\bcontent moderation\b",
    r"\btrust and safety\b",
    r"\bdata entry\b",
    r"\badministrative assistant\b",
    r"\badmin executive\b",
    r"\bfinance executive\b",
    r"\baccounting executive\b",

    r"\bpurchasing\b",
    r"\bprocurement\b",
    r"\bsourcing officer\b",
    r"\bcosting officer\b",

    r"\bcnc programmer\b",
    r"\bproduction programmer\b",
    r"\bmanufacturing programmer\b",
    r"\bcam programmer\b",
    r"\bsmt machine programmer\b",
    r"\bmachine programmer\b",
    r"\bmechanical engineer\b",
    r"\bproduction engineer\b",
    r"\bquality inspector\b",
    r"\bprocess engineer\b",

    r"\bquality assurance\b.*\b(lifescience|life science|pharma|pharmaceutical|food|manufacturing)\b",
    r"\b(quality assurance|qa)\b.*\b(lifescience|life science|pharma|pharmaceutical|food|manufacturing)\b",
    r"\bpolicy quality assurance\b",
    r"\bquality assurance analyst\b.*\b(language|bilingual)\b",
    r"\bquality assurance specialist\b.*\b(language|bilingual)\b",

    r"\bgraduate trainee\b.*\b(mechanical|purchasing|finance|accounting|human resources)\b",
    r"\bgraduate engineer\b.*\b(mechanical|civil|electrical|chemical)\b"
]


# ==========================================
# AMBIGUOUS TITLES
# ==========================================

REVIEW_PATTERNS = [
    r"\bproperty developer\b",
    r"\bstatistical programmer\b",
    r"\bautomation control engineer\b",
    r"\bprocess automation\b",
    r"\bindustrial automation\b",
    r"\bnetwork dc\b",
    r"\bdigital innovation\b"
]

GENERIC_PROGRAMME_PATTERNS = [
    r"\binternship\b",
    r"\bintern\b",
    r"\bindustrial training\b",
    r"\bgraduate programme\b",
    r"\bgraduate program\b",
    r"\bgraduate trainee\b",
    r"\bgraduate engineer\b",
    r"\bprotege\b",
    r"\bprotégé\b"
]


# ==========================================
# EXPERIENCE LEVEL CLASSIFICATION
# ==========================================

EXPERIENCE_PATTERNS = {
    "Internship": [
        r"\binternship\b",
        r"\bintern\b",
        r"\bindustrial training\b",
        r"\bindustrial trainee\b"
    ],

    "Fresh Graduate": [
        r"\bfresh graduate\b",
        r"\bfresh grad\b",
        r"\brecent graduate\b",
        r"\bgraduate programme\b",
        r"\bgraduate program\b",
        r"\bgraduate trainee\b",
        r"\bgraduate engineer\b",
        r"\bgraduate internship\b",
        r"\bnew graduate\b",
        r"\bprotege\b",
        r"\bprotégé\b"
    ],

    "Entry Level": [
        r"\bentry[\s-]?level\b",
        r"\bjunior graduate\b",
        r"\bnew entrant\b"
    ],

    "Junior": [
        r"\bjunior\b",
        r"\bjr\.?\b"
    ],

    "Senior": [
        r"\bsenior\b",
        r"\bsr\.?\b",
        r"\blead\b",
        r"\bprincipal\b",
        r"\bstaff engineer\b",
        r"\bstaff software engineer\b",
        r"\bhead of\b",
        r"\bdirector\b",
        r"\bvice president\b",
        r"\bvp\b"
    ],

    "Mid Level": [
        r"\bmid[\s-]?level\b",
        r"\bintermediate\b",
        r"\bexperienced\b"
    ]
}


# ==========================================
# TECHNICAL DESCRIPTION KEYWORDS
# ==========================================

TECHNICAL_DESCRIPTION_PATTERNS = [
    r"\bsoftware development\b",
    r"\bapplication development\b",
    r"\bweb development\b",
    r"\bmobile development\b",
    r"\bsoftware engineering\b",
    r"\bdevelop and maintain applications\b",
    r"\bwrite and maintain code\b",
    r"\bprogramming\b",
    r"\bcoding\b",
    r"\bdevelop software\b",
    r"\bapplication programming\b",
    r"\bsoftware implementation\b",
    r"\bsoftware requirements\b",
    r"\bsoftware architecture\b",
    r"\bapi development\b",

    r"\bmachine learning\b",
    r"\bartificial intelligence\b",
    r"\bdeep learning\b",
    r"\bnatural language processing\b",
    r"\bdata engineering\b",
    r"\bdata analytics\b",
    r"\bdata modelling\b",
    r"\bdata modeling\b",
    r"\bdata pipelines\b",
    r"\bdata science\b",
    r"\bdata analysis\b",
    r"\bbusiness intelligence\b",
    r"\bdata warehouse\b",

    r"\bcyber[\s-]?security\b",
    r"\binformation security\b",
    r"\bnetwork administration\b",
    r"\bnetwork infrastructure\b",
    r"\bnetwork configuration\b",
    r"\bsecurity monitoring\b",
    r"\bvulnerability assessment\b",
    r"\bnetwork troubleshooting\b",
    r"\bnetwork maintenance\b",
    r"\bpenetration testing\b",
    r"\bincident response\b",

    r"\bcloud computing\b",
    r"\bcloud infrastructure\b",
    r"\bcloud deployment\b",
    r"\bdevops\b",
    r"\bsystem administration\b",
    r"\bserver administration\b",
    r"\bit infrastructure\b",
    r"\bvirtualisation\b",
    r"\bvirtualization\b",
    r"\bcloud platform\b",
    r"\bkubernetes\b",
    r"\bdocker\b",

    r"\bsoftware testing\b",
    r"\btest automation\b",
    r"\bautomated testing\b",
    r"\bdatabase administration\b",
    r"\bdatabase management\b",
    r"\bsql queries\b",
    r"\bsoftware quality assurance\b",
    r"\bselenium\b",
    r"\bplaywright\b",
    r"\bcypress\b",

    r"\benterprise architecture\b",
    r"\berp system implementation\b",
    r"\bsap system implementation\b",
    r"\bcrm system implementation\b",
    r"\bservicenow implementation\b",
    r"\bsystems analysis\b",
    r"\bsystem integration\b",
    r"\brequirements gathering\b",
    r"\bmurex\b",
    r"\bfinancial systems\b",

    r"\bembedded systems\b",
    r"\bembedded software\b",
    r"\bfirmware development\b",
    r"\binternet of things\b",
    r"\bmicrocontroller programming\b"
]


SOFTWARE_QA_EVIDENCE = [
    r"\bsoftware testing\b",
    r"\bsoftware tester\b",
    r"\btest automation\b",
    r"\bautomated testing\b",
    r"\bapplication testing\b",
    r"\bautomated test scripts\b",
    r"\btest cases\b",
    r"\bselenium\b",
    r"\bplaywright\b",
    r"\bcypress\b",
    r"\bsoftware quality assurance\b",
    r"\bmanual testing\b",
    r"\bfunctional testing\b",
    r"\bregression testing\b",
    r"\bapi testing\b"
]


# ==========================================
# DIAGNOSTIC COUNTERS
# ==========================================

diagnostics = {
    "missing_fields": 0,
    "excluded": 0,
    "review": 0,
    "duplicate_database": 0,
    "duplicate_api": 0,
    "eligible": 0,
    "inserted": 0,
    "postings_saved": 0,
    "existing_jobs_enriched": 0,
    "metadata_saved": 0,
    "failed_pages": 0,
    "failed_searches": 0
}

missing_field_counts = {
    "company": 0,
    "title": 0,
    "description": 0
}

rejected_titles = {
    "missing_fields": [],
    "excluded": [],
    "review": [],
    "duplicate_database": [],
    "duplicate_api": []
}

category_counts = {}
experience_counts = {}

MAX_SAMPLE_TITLES = 30


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def record_rejection(reason, title, company, missing_fields=None):
    if len(rejected_titles[reason]) >= MAX_SAMPLE_TITLES:
        return

    record = {
        "company": company or "Unknown company",
        "title": title or "Unknown title"
    }

    if missing_fields:
        record["missing_fields"] = missing_fields

    rejected_titles[reason].append(record)


def get_value(field):
    if isinstance(field, dict):
        if field.get("state") == "known":
            return field.get("value")

        return None

    return field


def clean_str(value, max_length=None):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if max_length and len(text) > max_length:
        return text[:max_length]

    return text


def normalize(value):
    if not isinstance(value, str):
        return ""

    return " ".join(value.strip().casefold().split())


def matches_any(text, patterns):
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def is_valid_url(value):
    if not isinstance(value, str) or not value.strip():
        return False

    try:
        parsed = urlsplit(value)

        return (
            parsed.scheme in ["http", "https"]
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )

    except ValueError:
        return False


def is_valid_date(value):
    if not isinstance(value, str) or not value:
        return False

    try:
        checked_date = date.fromisoformat(value)
        return checked_date <= date.today()

    except ValueError:
        return False


def has_technical_evidence(description):
    description_text = normalize(description)

    return matches_any(
        description_text,
        TECHNICAL_DESCRIPTION_PATTERNS
    )


def has_software_qa_evidence(description):
    description_text = normalize(description)

    return matches_any(
        description_text,
        SOFTWARE_QA_EVIDENCE
    )


# ==========================================
# DESCRIPTION-BASED CATEGORY CLASSIFICATION
# ==========================================

def classify_description_category(description):
    description_text = normalize(description)

    description_patterns = [
        (
            "Embedded Systems & IoT",
            [
                r"\bembedded software\b",
                r"\bembedded systems\b",
                r"\bfirmware development\b",
                r"\binternet of things\b",
                r"\bmicrocontroller programming\b"
            ]
        ),
        (
            "Software & Application Development",
            [
                r"\bsoftware architecture\b",
                r"\bsoftware development\b",
                r"\bapplication development\b",
                r"\bweb development\b",
                r"\bmobile development\b",
                r"\bsoftware programming\b",
                r"\bsoftware engineering\b",
                r"\bapi development\b"
            ]
        ),
        (
            "Software Testing & Quality Assurance",
            [
                r"\bsoftware testing\b",
                r"\btest automation\b",
                r"\bautomated testing\b",
                r"\bsoftware quality assurance\b",
                r"\bregression testing\b",
                r"\bapi testing\b"
            ]
        ),
        (
            "Cybersecurity",
            [
                r"\bcyber[\s-]?security\b",
                r"\binformation security\b",
                r"\bsecurity monitoring\b",
                r"\bvulnerability assessment\b",
                r"\bpenetration testing\b",
                r"\bincident response\b"
            ]
        ),
        (
            "Artificial Intelligence & Machine Learning",
            [
                r"\bmachine learning\b",
                r"\bartificial intelligence\b",
                r"\bdeep learning\b",
                r"\bnatural language processing\b",
                r"\bcomputer vision\b",
                r"\bgenerative ai\b"
            ]
        ),
        (
            "DevOps & Software Operations",
            [
                r"\bdevops\b",
                r"\bci/cd\b",
                r"\bcontinuous integration\b",
                r"\bcontinuous deployment\b",
                r"\bdeployment pipeline\b"
            ]
        ),
        (
            "Data & Business Intelligence",
            [
                r"\bdata engineering\b",
                r"\bdata analytics\b",
                r"\bdata pipelines\b",
                r"\bdatabase administration\b",
                r"\bdatabase management\b",
                r"\bbusiness intelligence\b",
                r"\bdata warehouse\b"
            ]
        ),
        (
            "IT Business & Enterprise Systems",
            [
                r"\benterprise architecture\b",
                r"\berp system implementation\b",
                r"\bsap system implementation\b",
                r"\bcrm system implementation\b",
                r"\bservicenow implementation\b",
                r"\bsystem integration\b",
                r"\bsystems analysis\b",
                r"\brequirements gathering\b",
                r"\bmurex\b",
                r"\bfinancial systems\b"
            ]
        ),
        (
            "Cloud & Infrastructure",
            [
                r"\bcloud infrastructure\b",
                r"\bcloud computing\b",
                r"\bcloud deployment\b",
                r"\bsystem administration\b",
                r"\bserver administration\b",
                r"\bvirtualization\b",
                r"\bvirtualisation\b",
                r"\bcloud platform\b"
            ]
        ),
        (
            "Networking & IT Support",
            [
                r"\bnetwork administration\b",
                r"\bnetwork infrastructure\b",
                r"\bnetwork configuration\b",
                r"\bnetwork troubleshooting\b",
                r"\bit support\b",
                r"\btechnical support\b"
            ]
        )
    ]

    for category, patterns in description_patterns:
        if matches_any(description_text, patterns):
            return category

    return "Other / Unclassified"


# ==========================================
# JOB CATEGORY CLASSIFICATION
# ==========================================

def classify_job_category(title, description=""):
    title_text = normalize(title)
    description_text = normalize(description)

    industrial_programmer_patterns = [
        r"\bmachine programmer\b",
        r"\bcnc programmer\b",
        r"\bsmt machine programmer\b",
        r"\bcam programmer\b",
        r"\bproduction programmer\b",
        r"\bmanufacturing programmer\b"
    ]

    if matches_any(title_text, industrial_programmer_patterns):
        return "Other / Unclassified"

    industrial_automation_patterns = [
        r"\bautomation control engineer\b",
        r"\bprocess automation\b",
        r"\bindustrial automation\b"
    ]

    if matches_any(title_text, industrial_automation_patterns):
        return "Other / Unclassified"

    if matches_any(
        title_text,
        [
            r"\bnetwork operations cent(?:er|re)\b",
            r"\bnoc specialist\b",
            r"\bnoc engineer\b",
            r"\bnoc analyst\b",
            r"\bnetwork.{0,20}maintenance\b",
            r"\bnetwork.{0,20}operation\b",
            r"^noc$"
        ]
    ):
        return "Networking & IT Support"

    generic_qa_patterns = [
        r"\bquality assurance\b",
        r"\bqa analyst\b",
        r"\bquality analyst\b",
        r"\bquality inspector\b",
        r"\bquality assurance inspector\b"
    ]

    explicit_software_qa_patterns = [
        r"\bsoftware qa\b",
        r"\bqa automation\b",
        r"\btest automation\b",
        r"\bsoftware tester\b",
        r"\bsoftware testing\b",
        r"\bsoftware test engineer\b",
        r"\bapplication tester\b",
        r"\bqa tester\b"
    ]

    if matches_any(title_text, generic_qa_patterns):
        if matches_any(title_text, explicit_software_qa_patterns):
            return "Software Testing & Quality Assurance"

        if has_software_qa_evidence(description_text):
            return "Software Testing & Quality Assurance"

        return "Other / Unclassified"

    for category, patterns in JOB_CATEGORIES.items():
        if matches_any(title_text, patterns):
            return category

    if has_technical_evidence(description_text):
        return classify_description_category(description_text)

    return "Other / Unclassified"


# ==========================================
# JOB RELEVANCE CLASSIFICATION
# ==========================================

def classify_relevance(title, description=""):
    title_text = normalize(title)
    description_text = normalize(description)

    if not title_text:
        return "EXCLUDE", "Empty title"

    if matches_any(title_text, EXCLUDE_PATTERNS):
        return "EXCLUDE", "Unrelated job title"

    industrial_programmer_patterns = [
        r"\bmachine programmer\b",
        r"\bcnc programmer\b",
        r"\bsmt machine programmer\b",
        r"\bcam programmer\b",
        r"\bproduction programmer\b",
        r"\bmanufacturing programmer\b"
    ]

    if matches_any(title_text, industrial_programmer_patterns):
        return "EXCLUDE", "Industrial or manufacturing programming role"

    industrial_automation_patterns = [
        r"\bautomation control engineer\b",
        r"\bprocess automation\b",
        r"\bindustrial automation\b"
    ]

    if matches_any(title_text, industrial_automation_patterns):
        return "REVIEW", "Verify whether duties involve IT software or industrial control systems"

    non_it_description_patterns = [
        r"\bfood manufacturing\b",
        r"\bpharmaceutical manufacturing\b",
        r"\blife sciences quality\b",
        r"\blifesciences\b",
        r"\bmechanical maintenance\b",
        r"\bproduction line\b",
        r"\bchemical engineering\b",
        r"\bchemical plant\b"
    ]

    if matches_any(description_text, non_it_description_patterns):
        if matches_any(
            title_text,
            [
                r"\bquality assurance\b",
                r"\bqa analyst\b",
                r"\bquality analyst\b",
                r"\bautomation\b",
                r"\binternship\b",
                r"\bintern\b",
                r"\bgraduate\b",
                r"\btrainee\b"
            ]
        ):
            return "REVIEW", "Non-IT industry context; verify actual IT responsibilities"

    generic_qa_patterns = [
        r"\bquality assurance\b",
        r"\bqa analyst\b",
        r"\bquality analyst\b"
    ]

    explicit_software_qa_patterns = [
        r"\bsoftware qa\b",
        r"\bqa automation\b",
        r"\btest automation\b",
        r"\bsoftware tester\b",
        r"\bsoftware testing\b",
        r"\bsoftware test engineer\b",
        r"\bapplication tester\b",
        r"\bqa tester\b"
    ]

    if matches_any(title_text, generic_qa_patterns):
        if matches_any(title_text, explicit_software_qa_patterns):
            return "KEEP", "Explicit software testing role"

        if has_software_qa_evidence(description_text):
            return "REVIEW", "Description suggests software testing; verify duties"

        return "REVIEW", "Quality assurance role needs software testing confirmation"

    if re.search(r"\bbusiness analyst\b", title_text):
        explicit_it_ba_patterns = [
            r"\bit business analyst\b",
            r"\bsystems business analyst\b",
            r"\btechnical business analyst\b",
            r"\bbusiness systems analyst\b"
        ]

        if matches_any(title_text, explicit_it_ba_patterns):
            return "KEEP", "Explicit IT business analyst role"

        enterprise_ba_patterns = [
            r"\bmurex\b",
            r"\bsap\b",
            r"\berp\b",
            r"\bservicenow\b",
            r"\bsalesforce\b",
            r"\bdynamics 365\b"
        ]

        if matches_any(title_text, enterprise_ba_patterns):
            return "REVIEW", "Enterprise systems business analyst; verify actual system duties"

        return "REVIEW", "Business analyst needs technical responsibility confirmation"

    category = classify_job_category(title, description)

    if matches_any(title_text, REVIEW_PATTERNS):
        return "REVIEW", "Ambiguous job title"

    ambiguous_technical_patterns = [
        r"\bsolution consultant\b",
        r"\bsolutions consultant\b",
        r"\btechnical consultant\b",
        r"\bproject manager\b",
        r"\bproject management\b"
    ]

    explicit_it_project_patterns = [
        r"\bit project manager\b",
        r"\bcyber[\s-]?security\b",
        r"\binformation security\b",
        r"\bsoftware\b",
        r"\bcloud\b",
        r"\bdevops\b",
        r"\bdata center.{0,20}\bict\b",
        r"\bict.{0,20}\bproject\b",
        r"\benterprise architecture\b",
        r"\bembedded software\b"
    ]

    if matches_any(title_text, ambiguous_technical_patterns):
        if matches_any(title_text, explicit_it_project_patterns):
            return "KEEP", "Explicit IT project or technical role"

        if category != "Other / Unclassified":
            return "REVIEW", "Technical project or consulting duties need verification"

        return "REVIEW", "Technical responsibilities need confirmation"

    if matches_any(title_text, GENERIC_PROGRAMME_PATTERNS):
        explicit_technical_title_patterns = [
            r"\bsoftware\b",
            r"\bdeveloper\b",
            r"\bprogrammer\b",
            r"\bdata analyst\b",
            r"\bdata engineer\b",
            r"\bdata scientist\b",
            r"\bdata analytics\b",
            r"\bdata analysis\b",
            r"\bdata architecture\b",
            r"\bcyber[\s-]?security\b",
            r"\bsecurity analyst\b",
            r"\bnetwork engineer\b",
            r"\bcloud engineer\b",
            r"\bdevops\b",
            r"\bqa engineer\b",
            r"\bsoftware tester\b",
            r"\bembedded\b",
            r"\bfirmware\b",
            r"\bit support\b",
            r"\bsystem administrator\b",
            r"\bmachine learning\b",
            r"\bartificial intelligence\b",
            r"\benterprise architecture\b",
            r"\benterprise architect\b",
            r"\bdatabase\b",
            r"\bsap\b",
            r"\berp\b",
            r"\bmurex\b"
        ]

        if matches_any(title_text, explicit_technical_title_patterns):
            return "KEEP", "Technical internship or graduate role"

        return "REVIEW", "Generic programme needs IT responsibility confirmation"

    enterprise_patterns = [
        r"\berp\b",
        r"\bsap\b",
        r"\bmurex\b",
        r"\bservicenow\b",
        r"\bsalesforce\b",
        r"\bdynamics 365\b",
        r"\bms dynamics\b",
        r"\bcrm developer\b",
        r"\bfinancial systems\b"
    ]

    if matches_any(title_text, enterprise_patterns):
        return "KEEP", "IT enterprise systems role"

    if category != "Other / Unclassified":
        return "KEEP", "IT-related role"

    if has_technical_evidence(description_text):
        return "REVIEW", "Description contains technical terms; verify actual IT duties"

    return "EXCLUDE", "No clear IT role identified"


# ==========================================
# EXPERIENCE LEVEL CLASSIFICATION
# ==========================================

def classify_experience_level(title, description=""):
    title_text = normalize(title)
    description_text = normalize(description)
    combined_text = f"{title_text} {description_text}"

    if matches_any(
        combined_text,
        EXPERIENCE_PATTERNS["Internship"]
    ):
        return "Internship"

    if matches_any(
        combined_text,
        EXPERIENCE_PATTERNS["Fresh Graduate"]
    ):
        return "Fresh Graduate"

    if matches_any(title_text, EXPERIENCE_PATTERNS["Senior"]):
        return "Senior"

    if matches_any(title_text, EXPERIENCE_PATTERNS["Junior"]):
        return "Junior"

    if matches_any(title_text, EXPERIENCE_PATTERNS["Entry Level"]):
        return "Entry Level"

    if matches_any(title_text, EXPERIENCE_PATTERNS["Mid Level"]):
        return "Mid Level"

    range_pattern = (
        r"(\d+)\s*[-–]\s*(\d+)\s+"
        r"years?\s+(?:of\s+)?experience"
    )

    range_match = re.search(
        range_pattern,
        description_text,
        re.IGNORECASE
    )

    if range_match:
        minimum_years = int(range_match.group(1))
        maximum_years = int(range_match.group(2))

        if minimum_years >= 5:
            return "Senior"

        if minimum_years >= 2:
            return "Mid Level"

        if maximum_years <= 1:
            return "Entry Level"

        return "Junior"

    single_year_patterns = [
        r"(\d+)\s*\+?\s+years?\s+(?:of\s+)?experience",
        r"minimum\s+of\s+(\d+)\s+years?",
        r"at least\s+(\d+)\s+years?"
    ]

    for pattern in single_year_patterns:
        match = re.search(
            pattern,
            description_text,
            re.IGNORECASE
        )

        if match:
            years = int(match.group(1))

            if years >= 5:
                return "Senior"

            if years >= 2:
                return "Mid Level"

            return "Entry Level"

    return "Unclear"


# ==========================================
# DATABASE FUNCTIONS
# ==========================================

def load_existing_jobs():
    """Map (normalized_company, normalized_title) -> job.id."""
    existing_jobs = {}

    with Session(engine) as session:
        jobs = session.scalars(select(Job)).all()

        for job in jobs:
            job_key = (
                normalize(job.company_name),
                normalize(job.job_title)
            )

            existing_jobs[job_key] = job.id

    return existing_jobs


# ==========================================
# LOCATION AND MULTI-POSTING EXTRACTION
# ==========================================

def format_location(job, posting):
    location = get_value(posting.get("location"))

    if not isinstance(location, dict):
        locations = job.get("locations") or []

        for item in locations:
            value = get_value(item)

            if isinstance(value, dict):
                location = value
                break

    if not isinstance(location, dict):
        return ""

    parts = []

    city = location.get("city")
    region = location.get("state") or location.get("region")
    country = location.get("countryRaw") or location.get("country")

    if city:
        parts.append(str(city))

    if region:
        parts.append(str(region))

    if country:
        country_text = str(country)

        if country_text == "MY":
            country_text = "Malaysia"

        parts.append(country_text)

    return ", ".join(parts)


def extract_all_postings(job_data):
    """
    Extract all valid posting records from the HeadcountLabs job payload
    plus backward-compatible summary values for the parent Job row.
    """
    raw_postings = job_data.get("postings")
    extracted_postings = []

    if isinstance(raw_postings, list):
        for posting in raw_postings:
            if not isinstance(posting, dict):
                continue

            api_posting_id = clean_str(
                get_value(posting.get("posting_id"))
                or get_value(posting.get("id")),
                max_length=100
            )
            source_posting_id = clean_str(
                get_value(posting.get("source_posting_id")),
                max_length=100
            )
            posting_source = clean_str(
                get_value(posting.get("posting_source")),
                max_length=100
            )

            raw_posting_url = clean_str(
                get_value(posting.get("posting_url")),
                max_length=1000
            )
            posting_url = (
                raw_posting_url if is_valid_url(raw_posting_url) else None
            )

            raw_application_url = clean_str(
                get_value(posting.get("application_url")),
                max_length=1000
            )
            application_url = (
                raw_application_url if is_valid_url(raw_application_url) else None
            )

            location = clean_str(
                format_location(job_data, posting),
                max_length=300
            )
            posting_status = clean_str(
                get_value(posting.get("posting_status")),
                max_length=50
            )

            check = posting.get("latest_application_check")
            latest_check_result = None
            latest_checked_at = None

            if isinstance(check, dict):
                latest_check_result = clean_str(
                    get_value(check.get("result")),
                    max_length=50
                )
                latest_checked_at = clean_str(
                    get_value(check.get("checked_at")),
                    max_length=30
                )

            source_posted_at = clean_str(
                get_value(posting.get("source_posted_at")),
                max_length=30
            )
            first_seen_at = clean_str(
                get_value(posting.get("first_seen_at")),
                max_length=30
            )
            last_completed_fetch_at = clean_str(
                get_value(posting.get("last_completed_fetch_at")),
                max_length=30
            )

            # Skip completely empty posting shells
            if not any([
                api_posting_id,
                posting_url,
                application_url,
                location
            ]):
                continue

            extracted_postings.append({
                "api_posting_id": api_posting_id,
                "source_posting_id": source_posting_id,
                "posting_source": posting_source,
                "posting_url": posting_url,
                "application_url": application_url,
                "location": location,
                "posting_status": posting_status,
                "latest_check_result": latest_check_result,
                "latest_checked_at": latest_checked_at,
                "source_posted_at": source_posted_at,
                "first_seen_at": first_seen_at,
                "last_completed_fetch_at": last_completed_fetch_at
            })

    # Choose the best primary posting for legacy Job columns
    primary_location = ""
    primary_url = ""
    primary_date = ""

    ranked_postings = sorted(
        extracted_postings,
        key=lambda p: (
            p["posting_status"] == "listed",
            p["latest_check_result"] == "available",
            p["latest_check_result"] not in ("closed", "broken"),
            bool(p["application_url"]),
            bool(p["posting_url"]),
            bool(p["location"])
        ),
        reverse=True
    )

    for item in ranked_postings:
        if not primary_location and item["location"]:
            primary_location = item["location"]

        if not primary_url:
            candidate_url = item["application_url"] or item["posting_url"]
            if candidate_url and item["latest_check_result"] not in ("closed", "broken"):
                primary_url = candidate_url
                if (
                    item["latest_check_result"] == "available"
                    and item["latest_checked_at"]
                ):
                    date_part = item["latest_checked_at"][:10]
                    if is_valid_date(date_part):
                        primary_date = date_part

    return {
        "postings": extracted_postings,
        "primary_location": primary_location,
        "primary_url": primary_url,
        "primary_date": primary_date
    }


def upsert_postings_for_job(db_session, job, extracted_postings):
    """
    Attach new Posting rows to `job` without creating duplicates
    locally or globally across the postings table.
    Returns the number of newly added postings.
    """
    existing_api_ids = {
        p.api_posting_id
        for p in job.postings
        if p.api_posting_id
    }

    candidate_api_ids = [
        item["api_posting_id"]
        for item in extracted_postings
        if item["api_posting_id"]
    ]

    if candidate_api_ids:
        global_existing_ids = set(
            db_session.scalars(
                select(Posting.api_posting_id).where(
                    Posting.api_posting_id.in_(candidate_api_ids)
                )
            ).all()
        )
        existing_api_ids.update(global_existing_ids)

    existing_urls = {
        (p.application_url or "", p.posting_url or "")
        for p in job.postings
        if p.application_url or p.posting_url
    }

    added_postings = 0

    for item in extracted_postings:
        api_id = item["api_posting_id"]
        url_pair = (
            item["application_url"] or "",
            item["posting_url"] or ""
        )

        if api_id and api_id in existing_api_ids:
            continue

        if not api_id and any(url_pair) and url_pair in existing_urls:
            continue

        new_posting = Posting(
            job_id=job.id,
            api_posting_id=api_id,
            source_posting_id=item["source_posting_id"],
            posting_source=item["posting_source"],
            posting_url=item["posting_url"],
            application_url=item["application_url"],
            location=item["location"],
            posting_status=item["posting_status"],
            latest_check_result=item["latest_check_result"],
            latest_checked_at=item["latest_checked_at"],
            source_posted_at=item["source_posted_at"],
            first_seen_at=item["first_seen_at"],
            last_completed_fetch_at=item["last_completed_fetch_at"]
        )

        job.postings.append(new_posting)

        if api_id:
            existing_api_ids.add(api_id)
        if any(url_pair):
            existing_urls.add(url_pair)

        added_postings += 1

    return added_postings


# ==========================================
# API REQUEST FUNCTION
# ==========================================

def request_jobs(api_session, params):
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = api_session.get(
                API_URL,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 401:
                raise RuntimeError(
                    "API key is invalid or unauthorized."
                )

            if response.status_code == 429:
                raise RuntimeError(
                    "API rate limit reached."
                )

            if response.status_code == 400:
                print(
                    "Bad request or invalid cursor. "
                    "This page will be marked as failed."
                )
                return None

            if response.status_code in [500, 502, 503, 504]:
                if attempt < MAX_RETRIES:
                    delay = 2 ** (attempt + 1)

                    print(
                        f"API error {response.status_code}. "
                        f"Retrying after {delay} seconds..."
                    )

                    time.sleep(delay)
                    continue

                print(
                    f"API error {response.status_code}. "
                    "Skipping this page."
                )
                return None

            response.raise_for_status()
            return response.json()

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError
        ) as error:
            if attempt < MAX_RETRIES:
                delay = 2 ** (attempt + 1)

                print(
                    f"Connection issue: {type(error).__name__}"
                )

                print(
                    f"Retrying after {delay} seconds..."
                )

                time.sleep(delay)
                continue

            print("Request failed after all retries.")
            return None

        except requests.RequestException as error:
            print(f"API request failed: {error}")
            return None

        except ValueError:
            print("API returned invalid JSON.")
            return None

    return None


# ==========================================
# DIAGNOSTIC REPORT
# ==========================================

def print_diagnostic_report(
    total_received,
    total_jobs,
    total_postings,
    attempted_searches,
    successful_searches
):
    print("\n========================================")
    print("EXPANDED IT JOB COLLECTION REPORT")
    print("========================================")

    print(f"Dry-run mode: {DRY_RUN}")
    print(f"Search terms configured: {len(SEARCH_TITLES)}")
    print(f"Search terms attempted: {attempted_searches}")
    print(f"Search terms with successful pages: {successful_searches}")

    print(
        f"Search terms without successful pages: "
        f"{diagnostics['failed_searches']}"
    )

    print(f"API records received: {total_received}")

    print(
        f"Failed page requests: "
        f"{diagnostics['failed_pages']}"
    )

    print("----------------------------------------")

    print(
        f"Missing required fields: "
        f"{diagnostics['missing_fields']}"
    )

    print("Missing-field breakdown:")

    for field, count in missing_field_counts.items():
        print(f"  {field}: {count}")

    print(f"Excluded jobs: {diagnostics['excluded']}")
    print(f"Jobs requiring review: {diagnostics['review']}")
    print(f"Already in SQLite: {diagnostics['duplicate_database']}")
    print(f"Repeated API results: {diagnostics['duplicate_api']}")

    print("----------------------------------------")

    print(
        f"Eligible new IT jobs (KEEP): "
        f"{diagnostics['eligible']}"
    )

    print(f"Actually inserted jobs: {diagnostics['inserted']}")
    print(f"New postings saved: {diagnostics['postings_saved']}")
    print(f"Existing jobs enriched with new postings: {diagnostics['existing_jobs_enriched']}")
    print(f"New jobs with metadata: {diagnostics['metadata_saved']}")

    print("----------------------------------------")
    print(f"Total SQLite jobs: {total_jobs}")
    print(f"Total SQLite postings: {total_postings}")

    print("\nJOB CATEGORY BREAKDOWN")

    for category, count in sorted(category_counts.items()):
        print(f"{category}: {count}")

    print("\nEXPERIENCE LEVEL BREAKDOWN")

    for level, count in sorted(experience_counts.items()):
        print(f"{level}: {count}")

    print("\nSAMPLE EXCLUDED TITLES")

    for record in rejected_titles["excluded"]:
        print(
            f"- {record['title']} "
            f"| {record['company']}"
        )

    print("\nSAMPLE TITLES REQUIRING REVIEW")

    for record in rejected_titles["review"]:
        print(
            f"- {record['title']} "
            f"| {record['company']}"
        )

    print("\nSAMPLE MISSING-FIELD RECORDS")

    for record in rejected_titles["missing_fields"]:
        missing_fields = record.get("missing_fields", [])

        print(
            f"- {record['title']} "
            f"| {record['company']} "
            f"| Missing: {', '.join(missing_fields)}"
        )

    print("\n========================================")


# ==========================================
# MAIN COLLECTION FUNCTION
# ==========================================

def fetch_more_jobs():
    if not API_KEY:
        print("HEADCOUNTLABS_API_KEY not found.")
        return

    existing_jobs = load_existing_jobs()
    seen_api_jobs = set()

    print(
        f"Existing unique database jobs: "
        f"{len(existing_jobs)}"
    )

    print(f"Dry-run mode: {DRY_RUN}")

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    total_received = 0
    attempted_searches = 0
    successful_searches = 0

    with requests.Session() as api_session:
        api_session.headers.update(headers)

        try:
            for search_title in SEARCH_TITLES:
                if not DRY_RUN and TARGET_NEW_JOBS > 0:
                    if diagnostics["inserted"] >= TARGET_NEW_JOBS:
                        break

                if total_received >= MAX_RECORDS_SCANNED:
                    print("Maximum record scan limit reached.")
                    break

                attempted_searches += 1

                print(f"\nSearching: {search_title}")

                cursor = None
                search_had_success = False

                for page_number in range(1, MAX_PAGES_PER_SEARCH + 1):

                    if not DRY_RUN and TARGET_NEW_JOBS > 0:
                        if diagnostics["inserted"] >= TARGET_NEW_JOBS:
                            break

                    if total_received >= MAX_RECORDS_SCANNED:
                        print("Maximum record scan limit reached.")
                        break

                    params = {
                        "country": "MY",
                        "title": search_title,
                        "currentness": "current",
                        "limit": PAGE_SIZE
                    }

                    if cursor:
                        params["cursor"] = cursor

                    print(f"Requesting page {page_number}")

                    data = request_jobs(
                        api_session,
                        params
                    )

                    if data is None:
                        diagnostics["failed_pages"] += 1
                        break

                    search_had_success = True

                    records = data.get("data", [])

                    if not isinstance(records, list):
                        print("Unexpected API response format.")
                        break

                    total_received += len(records)

                    print(f"Records received: {len(records)}")

                    if not records:
                        break

                    page_added = 0
                    page_skipped = 0
                    page_review = 0

                    for job_data in records:
                        if not isinstance(job_data, dict):
                            diagnostics["missing_fields"] += 1
                            page_skipped += 1

                            record_rejection(
                                "missing_fields",
                                "",
                                "",
                                ["invalid API record"]
                            )
                            continue

                        company = get_value(
                            job_data.get("employer_name")
                        )

                        title = get_value(
                            job_data.get("title")
                        )

                        description = get_value(
                            job_data.get("description")
                        )

                        missing_record_fields = []

                        if not isinstance(company, str) or not company.strip():
                            missing_field_counts["company"] += 1
                            missing_record_fields.append("company")

                        if not isinstance(title, str) or not title.strip():
                            missing_field_counts["title"] += 1
                            missing_record_fields.append("title")

                        if (
                            not isinstance(description, str)
                            or not description.strip()
                        ):
                            missing_field_counts["description"] += 1
                            missing_record_fields.append("description")

                        if missing_record_fields:
                            diagnostics["missing_fields"] += 1
                            page_skipped += 1

                            record_rejection(
                                "missing_fields",
                                title,
                                company,
                                missing_record_fields
                            )
                            continue

                        company = company.strip()
                        title = title.strip()
                        description = description.strip()

                        job_key = (
                            normalize(company),
                            normalize(title)
                        )

                        if job_key in seen_api_jobs:
                            diagnostics["duplicate_api"] += 1
                            page_skipped += 1

                            record_rejection(
                                "duplicate_api",
                                title,
                                company
                            )
                            continue

                        seen_api_jobs.add(job_key)

                        relevance, reason = classify_relevance(
                            title,
                            description
                        )

                        if relevance == "EXCLUDE":
                            diagnostics["excluded"] += 1
                            page_skipped += 1

                            record_rejection(
                                "excluded",
                                title,
                                company
                            )
                            continue

                        if job_key in existing_jobs:
                            diagnostics["duplicate_database"] += 1
                            page_skipped += 1

                            record_rejection(
                                "duplicate_database",
                                title,
                                company
                            )

                            # Still attach any newly discovered postings to the existing Job
                            if not DRY_RUN:
                                extracted = extract_all_postings(job_data)
                                if extracted["postings"]:
                                    existing_job_id = existing_jobs[job_key]
                                    with Session(engine) as db_session:
                                        existing_job = db_session.get(Job, existing_job_id)
                                        if existing_job is not None:
                                            newly_added = upsert_postings_for_job(
                                                db_session,
                                                existing_job,
                                                extracted["postings"]
                                            )
                                            if newly_added > 0:
                                                if not existing_job.location and extracted["primary_location"]:
                                                    existing_job.location = extracted["primary_location"]
                                                if not existing_job.application_url and extracted["primary_url"]:
                                                    existing_job.application_url = extracted["primary_url"]
                                                if not existing_job.date_verified and extracted["primary_date"]:
                                                    existing_job.date_verified = extracted["primary_date"]

                                                db_session.commit()
                                                diagnostics["postings_saved"] += newly_added
                                                diagnostics["existing_jobs_enriched"] += 1

                            continue

                        category = classify_job_category(
                            title,
                            description
                        )

                        experience = classify_experience_level(
                            title,
                            description
                        )

                        if relevance == "REVIEW":
                            diagnostics["review"] += 1
                            page_review += 1

                            record_rejection(
                                "review",
                                title,
                                company
                            )

                            print(
                                f"Review: {title} "
                                f"| {category} "
                                f"| {experience} "
                                f"| {reason}"
                            )
                            continue

                        diagnostics["eligible"] += 1

                        if category not in category_counts:
                            category_counts[category] = 0

                        category_counts[category] += 1

                        if experience not in experience_counts:
                            experience_counts[experience] = 0

                        experience_counts[experience] += 1

                        print(
                            f"Eligible: {title} "
                            f"| {category} "
                            f"| {experience}"
                        )

                        if DRY_RUN:
                            continue

                        extracted = extract_all_postings(job_data)

                        new_job = Job(
                            company_name=company,
                            job_title=title,
                            description=description,
                            location=extracted["primary_location"] or None,
                            application_url=extracted["primary_url"] or None,
                            date_verified=extracted["primary_date"] or None
                        )

                        with Session(engine) as db_session:
                            db_session.add(new_job)
                            db_session.flush()

                            added_postings = upsert_postings_for_job(
                                db_session,
                                new_job,
                                extracted["postings"]
                            )

                            db_session.commit()
                            existing_jobs[job_key] = new_job.id

                        diagnostics["inserted"] += 1
                        diagnostics["postings_saved"] += added_postings
                        page_added += 1

                        if (
                            extracted["primary_location"]
                            or extracted["primary_url"]
                            or extracted["primary_date"]
                        ):
                            diagnostics["metadata_saved"] += 1

                    print(f"New jobs this page: {page_added}")
                    print(f"Review jobs this page: {page_review}")
                    print(f"Skipped records this page: {page_skipped}")

                    print(
                        f"Eligible jobs so far: "
                        f"{diagnostics['eligible']}"
                    )

                    cursor = data.get("next_cursor")

                    if not cursor:
                        break

                    time.sleep(1)

                if search_had_success:
                    successful_searches += 1
                else:
                    diagnostics["failed_searches"] += 1

                if total_received >= MAX_RECORDS_SCANNED:
                    break

        except RuntimeError as error:
            print(f"API stopped: {error}")

        except Exception as error:
            print(
                "Unexpected error while fetching jobs: "
                f"{type(error).__name__}: {error}"
            )

    with Session(engine) as session:
        total_jobs = session.scalar(
            select(func.count()).select_from(Job)
        )
        total_postings = session.scalar(
            select(func.count()).select_from(Posting)
        )

    print_diagnostic_report(
        total_received,
        total_jobs,
        total_postings,
        attempted_searches,
        successful_searches
    )


if __name__ == "__main__":
    fetch_more_jobs()