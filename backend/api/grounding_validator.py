"""Deterministic post-generation grounding validation.

The validator checks answer completeness and rejects explicit facts that cannot be
traced to selected evidence or to values supplied in the user's scenario. It is
language-tolerant for Indonesian/English paraphrases but strict for numbers,
units, money, percentages, versions, URLs, emails, and system identifiers.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from api.progress import emit_progress

from retrieval.query_expansion import CONCEPT_ALIASES, normalize_text
from retrieval.requirements import (
    EMAIL_PATTERN,
    URL_PATTERN,
    VERSION_PATTERN,
    canonical_unit,
    extract_evidence_requirements,
    is_scenario_comparison,
    requirement_satisfied,
)
from uploads.config import GENERATION_MIN_CLAIM_SUPPORT


@dataclass(frozen=True)
class GroundingDecision:
    supported: bool
    score: float
    reasons: tuple[str, ...]
    unsupported_facts: tuple[str, ...]
    unsupported_claims: tuple[str, ...] = ()
    missing_answer_requirements: tuple[str, ...] = ()
    missing_evidence_requirements: tuple[str, ...] = ()
    checked_claims: int = 0

    @property
    def support_score(self) -> float:
        """Compatibility alias used by the newer API diagnostics."""
        return self.score

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["support_score"] = self.score
        for key in (
            "reasons",
            "unsupported_facts",
            "unsupported_claims",
            "missing_answer_requirements",
            "missing_evidence_requirements",
        ):
            payload[key] = list(payload[key])
        return payload


# Backward-compatible public name from the first reliability patch.
GroundingValidation = GroundingDecision


STOPWORDS = {
    "yang", "dan", "atau", "adalah", "dengan", "untuk", "dalam", "pada", "dari",
    "ke", "sebagai", "oleh", "ini", "itu", "tersebut", "harus", "dapat", "akan",
    "juga", "kepada", "terhadap", "atas",
    "the", "and", "or", "is", "are", "was", "were", "with", "for", "to", "in",
    "on", "of", "by", "this", "that", "must", "can", "will", "a", "an",
    "according", "based", "berdasarkan", "document", "dokumen", "source", "sumber",
}

WORD_NUMBERS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "nol": "0", "satu": "1", "dua": "2", "tiga": "3", "empat": "4",
    "lima": "5", "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10",
}
WORD_NUMBER_PATTERN = "|".join(sorted((re.escape(key) for key in WORD_NUMBERS), key=len, reverse=True))
NUMBER_CORE = r"(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?|" + WORD_NUMBER_PATTERN + r")"

MONEY_PATTERN = re.compile(
    rf"\b(?:IDR|Rp\.?|USD|EUR)\s*{NUMBER_CORE}"
    r"(?:\s*(?:ribu|thousand|juta|million|miliar|billion|triliun|trillion))?\b",
    flags=re.I,
)
PERCENT_PATTERN = re.compile(
    rf"\b{NUMBER_CORE}\s*(?:%(?=$|[\s.,;:!?\)\]}}])|(?:persen|percent|percentage)\b)",
    flags=re.I,
)
NUMBER_UNIT_PATTERN = re.compile(
    rf"\b({NUMBER_CORE}|\d+\s*[x×]\s*\d+)\s*"
    r"(GB|MB|TB|KB|minutes?|mins?|hours?|hrs?|working\s+days?|business\s+days?|"
    r"consecutive\s+days?|days?|weeks?|months?|years?|seconds?|secs?|menit|jam|"
    r"hari\s+kerja|hari\s+berturut-turut|hari|minggu|bulan|tahun|detik|"
    r"characters?|chars?|karakter|requests?|calls?|customers?|pelanggan)\b",
    flags=re.I,
)
LEAVE_DAY_QUANTITY_PATTERN = re.compile(
    rf"\b({NUMBER_CORE})\s+(?:unused\s+)?leave\s+days?\b",
    flags=re.I,
)
PLAIN_NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?(?:st|nd|rd|th)?\b", flags=re.I)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
ACRONYM_PATTERN = re.compile(r"\b[A-Z][A-Z0-9/_-]{1,11}\b")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+|\s+[•-]\s+")
CLAUSE_SPLIT = re.compile(
    r"\s*(?:;|\b(?:and|but|because|due\s+to|therefore|thus|while|whereas|"
    r"dan|tetapi|namun|karena|sehingga|sedangkan)\b)\s*",
    flags=re.I,
)
CONDITIONAL_COMMA_PREFIX = re.compile(
    r"^\s*(?:if|when|once|before|after|unless|provided\s+that|"
    r"jika|ketika|apabila|bila|sebelum|setelah)\b",
    flags=re.I,
)
GROUNDING_PREAMBLE = re.compile(
    r"^\s*(?:"
    r"berdasarkan\s+(?:ketentuan\s+pada\s+)?(?:dokumen|sumber|bukti|konteks|informasi)"
    r"(?:\s+yang\s+(?:tersedia|diberikan))?"
    r"|menurut\s+(?:dokumen|sumber|bukti|konteks|informasi)"
    r"|according\s+to\s+(?:the\s+)?(?:document|source|evidence)"
    r"|based\s+on\s+(?:the\s+)?(?:document|source|evidence)"
    r")\s*[:,]?\s*",
    flags=re.I,
)

# Grounding needs a slightly richer bilingual vocabulary than retrieval.
# These aliases do not add facts or retrieval hits. They only prove that an
# Indonesian claim is a faithful rendering of the same English evidence unit.
GROUNDING_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    **CONCEPT_ALIASES,
    # GROUNDING_ID_NATIVE_V1: natural Indonesian grounding aliases.
    # FINANCIAL_METRIC_GROUNDING_V1: bilingual net-profit-margin aliases.
    # These aliases validate equivalent wording only; they do not add facts or
    # retrieval hits.
    "net_profit_margin": (
        "net profit margin",
        "the net profit margin",
        "company net profit margin",
        "company's net profit margin",
        "net margin",
        "margin laba bersih",
        "margin laba bersih perusahaan",
        "marjin laba bersih",
        "marjin laba bersih perusahaan",
        "margin keuntungan bersih",
        "marjin keuntungan bersih",
    ),
    "processing_time": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("processing_time", ()),
        "jangka waktu",
        "jangka waktu tersebut",
        "merupakan batas penyelesaian",
        "batas penyelesaian yang ditetapkan",
        "batas waktu penyelesaian yang ditetapkan",
        "waktu yang ditetapkan",
        "target waktu yang ditetapkan",
        "completion deadline",
        "defined resolution limit",
    ))),
    "incident_p1": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("incident_p1", ()),
        "insiden prioritas p1",
        "insiden it prioritas p1",
        "insiden ti prioritas p1",
        "insiden it prioritas 1",
        "insiden ti prioritas 1",
        "p1 priority incident",
    ))),
    "incident_p2": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("incident_p2", ()),
        "insiden prioritas p2",
        "insiden it prioritas p2",
        "insiden ti prioritas p2",
        "insiden it prioritas 2",
        "insiden ti prioritas 2",
        "p2 priority incident",
    ))),
    "probation": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("probation", ()),
        "serve a probation period",
        "serves a probation period",
        "probation lasts",
        "probation period lasts",
        "masa percobaan berlangsung",
        "masa percobaan selama",
        "menjalani masa percobaan",
        "berlangsung selama masa percobaan",
    ))),
    "new_employee": (
        "new employee",
        "new employees",
        "new hire",
        "new hires",
        "karyawan baru",
        "pegawai baru",
    ),
    "performance_evaluation": (
        "performance evaluation",
        "formal performance evaluation",
        "performance review",
        "evaluation is conducted",
        "evaluasi kinerja",
        "evaluasi kinerja formal",
        "evaluasi formal",
        "evaluasi dilakukan",
        "dilakukan evaluasi",
    ),
    "employment_confirmation": (
        "before confirmation",
        "employee confirmation",
        "confirmation decision",
        "sebelum konfirmasi",
        "konfirmasi karyawan",
        "keputusan konfirmasi",
    ),
    "incident_acknowledgement": (
        "incident acknowledgement",
        "incident acknowledgment",
        "must be acknowledged",
        "acknowledged within",
        "acknowledgement time",
        "acknowledgment time",
        "insiden harus diakui",
        "harus diakui",
        "diakui dalam",
        "waktu pengakuan insiden",
        "respons awal",
        "respons awal diberikan",
    ),
    "incident_escalation": (
        "incident escalation",
        "is escalated",
        "it is escalated",
        "escalated to",
        "if not resolved",
        "not resolved within",
        "eskalasi insiden",
        "insiden dieskalasikan",
        "akan dieskalasikan",
        "dieskalasikan kepada",
        "jika belum selesai",
        "jika belum diselesaikan",
        "belum terselesaikan",
    ),
    "infrastructure_head": (
        "head of infrastructure",
        "infrastructure head",
        "kepala infrastruktur",
    ),
    # BILINGUAL_POLICY_GROUNDING_V15: the local model often uses natural
    # Indonesian word order instead of the exact retrieval alias. These remain
    # subject/relation aliases only; answer values are still verified strictly
    # by ``_fact_entries`` against one evidence unit.
    "payslip": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("payslip", ()),
        "slip pembayaran gaji",
        "dokumen slip gaji",
        "akses slip gaji",
        "menemukan slip gaji",
    ))),
    "salary_payment": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("salary_payment", ()),
        "jadwal pembayaran gaji",
        "tanggal pembayaran gaji",
        "gaji diterima",
        "gaji masuk",
    ))),
    "remote_work": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("remote_work", ()),
        "melakukan pekerjaan dari rumah",
        "menjalankan pekerjaan dari rumah",
        "izin kerja dari rumah",
        "hari kerja dari rumah",
    ))),
    "lost_company_device": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("lost_company_device", ()),
        "kehilangan laptop kantor",
        "kehilangan laptop perusahaan",
        "kehilangan perangkat kantor",
        "laptop kerja hilang",
        "perangkat perusahaan hilang",
        "melaporkan laptop hilang",
    ))),
    "harassment_reporting": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("harassment_reporting", ()),
        "kebijakan anti pelecehan",
        "sikap terhadap pelecehan",
        "pelaporan pelecehan",
        "pengaduan pelecehan",
    ))),
    "byod": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("byod", ()),
        "perangkat milik pribadi",
        "gawai pribadi",
        "data pada perangkat pribadi",
        "menghapus data perangkat pribadi",
    ))),
    "conflict_of_interest": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("conflict_of_interest", ()),
        "potensi benturan kepentingan",
        "deklarasi konflik kepentingan",
        "melaporkan konflik kepentingan",
        "menyampaikan konflik kepentingan",
    ))),
    "annual_leave": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("annual_leave", ()),
        "hak cuti tahunan",
        "jatah cuti tahunan",
        "jumlah cuti tahunan",
        "cuti per tahun",
    ))),
    "hotel_limit": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("hotel_limit", ()),
        "batas biaya hotel",
        "maksimal biaya hotel",
        "biaya hotel dibatasi",
        "hotel dibatasi maksimal",
        "tarif hotel maksimum",
        "plafon hotel",
    ))),
    "remote_work_eligibility": tuple(dict.fromkeys((
        *CONCEPT_ALIASES.get("remote_work_eligibility", ()),
        "kelayakan kerja jarak jauh",
        "syarat kerja jarak jauh",
        "boleh mengajukan kerja jarak jauh",
        "dapat mengajukan remote work",
        "hak untuk bekerja jarak jauh",
    ))),
}


# Concept aliases establish the subject. These narrower equivalence groups
# establish translated relationship words inside one claim. A group contributes
# only when one of its phrases occurs in the claim and another phrase from the
# same group occurs in the same evidence unit. Unsupported explanatory tails
# therefore remain uncovered instead of receiving a blanket translation pass.
GROUNDING_EQUIVALENT_TERMS: dict[str, tuple[str, ...]] = {
    "organization": (
        "company", "the company", "corporate", "organization",
        "perusahaan", "organisasi",
    ),
    "employee": (
        "employee", "employees", "staff", "worker", "workers",
        "karyawan", "pegawai", "pekerja",
    ),
    "confirmed_employee": (
        "confirmed employee", "confirmed employees", "permanent employee",
        "permanent employees", "karyawan tetap", "pegawai tetap",
    ),
    "all": ("all", "every", "seluruh", "semua"),
    "person": (
        "person", "people", "persons", "dependent", "dependents",
        "orang", "tanggungan",
    ),
    "cover": (
        "cover", "covers", "covered", "include", "includes", "included",
        "mencakup", "meliputi", "tercakup",
    ),
    "up_to": (
        "up to", "a maximum of", "maximum of", "maximum", "hingga", "sampai dengan",
        "maksimal", "maksimum", "paling banyak",
    ),
    "unused": ("unused", "not used", "tidak terpakai", "belum terpakai"),
    "calendar_option": (
        "calendar sharing option", "sharing option", "share calendar option",
        "opsi berbagi kalender", "opsi membagikan kalender",
    ),
    "grant": (
        "grant", "grants", "give", "gives", "provide", "provides",
        "berikan", "memberikan", "beri",
    ),
    "view_access": (
        "view access", "read access", "access to view",
        "akses lihat", "akses membaca", "akses baca",
    ),
    "colleague": (
        "colleague", "colleagues", "coworker", "coworkers", "co worker",
        "rekan kerja", "kolega",
    ),
    "relevant": ("relevant", "related", "terkait", "bersangkutan"),
    "available": (
        "available", "accessible", "can find", "can access",
        "find", "found", "locate", "located", "access",
        "tersedia", "dapat ditemukan", "dapat diakses", "menemukan",
        "mengakses", "berada", "terletak",
    ),
    "portal": ("portal", "hr portal", "portal hr"),
    "section": (
        "under", "in the section", "under the section", "menu", "section",
        "pada bagian", "di bagian", "bagian", "di menu", "melalui menu",
    ),
    "after": ("after", "following", "once past", "setelah", "sesudah"),
    "salary": ("salary", "salaries", "payroll salary", "gaji"),
    "paid": (
        "paid", "is paid", "are paid", "payment", "dibayar", "dibayarkan",
        "pembayaran",
    ),
    "following": ("following", "next", "subsequent", "berikutnya", "selanjutnya"),
    "month": ("month", "monthly", "each month", "bulan", "bulanan", "setiap bulan"),
    "calendar_frequency": (
        "each", "every", "per", "setiap", "tiap", "per bulan", "per month",
    ),
    "approved": ("approved", "authorized", "disetujui", "telah disetujui"),
    "business": (
        "business", "business tool", "business tools", "work purpose",
        "bisnis", "keperluan kerja",
    ),
    "budget": ("budget", "it budget", "anggaran", "anggaran it"),
    "funded": (
        "covered by", "paid by", "paid from", "funded by",
        "ditanggung", "dibayar dari", "dibiayai",
    ),
    "policy": (
        "policy", "policies", "policy rule", "zero tolerance",
        "kebijakan", "ketentuan",
    ),
    "apply_policy": (
        "apply", "applies", "implement", "implements", "has",
        "menerapkan", "memberlakukan", "memiliki",
    ),
    "zero_tolerance": (
        "zero tolerance", "no tolerance", "without tolerance",
        "tanpa toleransi", "nol toleransi",
    ),
    "harassment": (
        "harassment", "workplace harassment", "pelecehan",
        "pelecehan di tempat kerja", "tindakan pelecehan",
    ),
    "any_form": ("any form", "all forms", "every form", "segala bentuk", "semua bentuk"),
    "complaint": ("complaint", "complaints", "grievance", "keluhan", "pengaduan"),
    "report": (
        "report", "reports", "reported", "raise", "raised", "submit",
        "notify", "inform", "contact",
        "lapor", "laporkan", "melaporkan", "dilaporkan", "diajukan",
        "mengajukan", "beri tahu", "memberi tahu", "hubungi", "menghubungi",
    ),
    "immediately": (
        "immediately", "at once", "without delay", "promptly",
        "segera", "secepatnya", "langsung", "tanpa penundaan",
    ),
    "it_team": (
        "it", "it team", "it support", "service desk", "helpdesk",
        "tim it", "bagian it", "dukungan it", "meja layanan it",
    ),
    "device": (
        "device", "devices", "laptop", "equipment",
        "perangkat", "laptop", "gawai", "peralatan",
    ),
    "purpose_link": (
        "so that", "so the", "to allow", "in order to", "so it can",
        "agar", "supaya", "sehingga dapat", "untuk memungkinkan",
    ),
    "confidential": (
        "confidential", "confidentially", "in confidence",
        "rahasia", "secara rahasia", "dengan rahasia",
    ),
    "via": (
        "via", "through", "using", "use",
        "melalui", "menggunakan", "gunakan",
    ),
    "channel": ("channel", "channels", "jalur", "saluran"),
    "enroll": (
        "enroll", "enrolled", "register", "registered",
        "daftarkan", "didaftarkan", "terdaftar",
    ),
    "work_email": (
        "work email", "corporate email", "company email",
        "email kantor", "email perusahaan",
    ),
    "remote_wipe": (
        "remote wipe", "remotely wipe", "remotely wiped", "wipe remotely",
        "remote wiping", "erase remotely", "remotely erase",
        "hapus jarak jauh", "menghapus dari jarak jauh", "dihapus dari jarak jauh",
        "penghapusan jarak jauh", "menghapus data secara jarak jauh", "jarak jauh",
    ),
    "remove_data": (
        "wipe", "wiped", "remotely wiped", "wipe data", "wipe corporate data",
        "erase data", "delete data", "remove data", "data can be wiped",
        "data can be erased",
        "hapus data", "menghapus data", "penghapusan data", "data dihapus",
        "dihapus datanya", "membersihkan data",
    ),
    "corporate_data": (
        "corporate data", "company data", "business data",
        "data korporat", "data perusahaan",
    ),
    "right_or_permission": (
        "reserves the right", "has the right", "may", "is permitted", "can",
        "berhak", "memiliki hak", "diperbolehkan", "diizinkan", "boleh", "dapat",
    ),
    "potential": ("potential", "possible", "potensi", "berpotensi"),
    "disclose": (
        "disclose", "disclosed", "declare", "declared",
        "ungkapkan", "mengungkapkan", "diungkapkan", "dideklarasikan",
    ),
    "in_writing": ("in writing", "written", "written disclosure", "secara tertulis", "tertulis"),
    "entitled": (
        "entitled", "eligible", "entitlement", "has the right",
        "berhak", "memiliki hak", "hak",
    ),
    "accrue_monthly": (
        "accrue monthly", "accrues monthly", "accruing monthly",
        "accrued monthly", "monthly accrual",
        "terakumulasi setiap bulan", "terakumulasi tiap bulan",
        "diakumulasi setiap bulan", "diakumulasi tiap bulan",
        "bertambah setiap bulan", "bertambah tiap bulan",
    ),
    "required": (
        "require", "requires", "required", "must", "mandatory", "needed",
        "diperlukan", "harus", "wajib", "dibutuhkan",
    ),
    "condition": ("if", "when", "for", "beyond", "apabila", "jika", "ketika"),
    "longer_than": (
        "beyond", "longer than", "more than", "exceed", "exceeds",
        "lebih dari", "melebihi",
    ),
    "duration_relation": (
        "last", "lasts", "lasting", "longer than",
        "berlangsung", "selama",
    ),
    "consecutive": ("consecutive", "consecutively", "berturut turut", "berturut-turut"),
    "per_year": ("per year", "each year", "annually", "per tahun", "setiap tahun"),
    "password": ("password", "passwords", "kata sandi", "sandi"),
    "minimum": ("at least", "minimum", "minimal", "sekurang kurangnya"),
    "contain": (
        "include", "includes", "including", "contain", "contains", "comprise",
        "mencakup", "terdiri dari", "memiliki",
    ),
    "uppercase": (
        "upper case", "uppercase", "capital letter", "capital letters", "huruf besar",
    ),
    "lowercase": (
        "lower case", "lowercase", "lowercase letter", "lowercase letters",
        "small letter", "small letters", "huruf kecil",
    ),
    "numeric_character": ("number", "numbers", "digit", "digits", "angka"),
    "symbol": ("symbol", "symbols", "special character", "special characters", "simbol"),
    "purchase": ("purchase", "purchases", "procurement", "pembelian", "pengadaan"),
    "below": (
        "below", "under", "less than", "valued below", "with a value below",
        "di bawah", "kurang dari", "dengan nilai di bawah",
    ),
    "approve": (
        "approval", "approve", "approves", "approved by", "requires approval from",
        "menyetujui", "disetujui oleh", "persetujuan dari",
    ),
    "manager": ("manager", "managers", "manajer"),
    "eligible": ("eligible", "may request", "can request", "berhak", "dapat mengajukan"),
    "manager_approval": (
        "manager approval", "approval from the manager", "with manager approval",
        "subject to manager approval", "manager's approval", "requires manager approval",
        "persetujuan manajer", "dengan persetujuan manajer",
        "atas persetujuan manajer", "setelah disetujui manajer",
        "memerlukan persetujuan manajer", "harus mendapat persetujuan manajer",
        "setelah mendapat persetujuan manajer", "dengan izin manajer",
    ),
    "weekly": (
        "per week", "each week", "weekly", "in a week",
        "per minggu", "setiap minggu", "dalam seminggu", "tiap minggu",
    ),
    "hotel_cost": (
        "hotel cost", "hotel rate", "hotel expense", "lodging cost",
        "biaya hotel", "tarif hotel", "ongkos hotel", "biaya penginapan",
    ),
    "cap": (
        "capped", "is capped", "limited to", "limit", "maximum",
        "dibatasi", "batas", "maksimal", "maksimum", "plafon",
    ),
    "per_night": (
        "per night", "each night", "nightly", "per malam", "setiap malam",
    ),
    "domestic_travel": (
        "domestic travel", "domestic business travel", "domestic trip",
        "perjalanan domestik", "perjalanan dinas domestik", "dinas dalam negeri",
    ),
}

# These qualifiers materially change the meaning of a claim. A generated claim
# may use an Indonesian or English alias, but the same qualifier family must be
# present in the supporting evidence unit. This blocks unsupported additions such
# as "because it is scalable", "only", "unless", or "approximately".
QUALIFIER_PATTERNS: dict[str, re.Pattern[str]] = {
    "causal": re.compile(
        r"\b(?:because|due\s+to|caused\s+by|as\s+a\s+result|karena|disebabkan\s+oleh|sehingga)\b",
        flags=re.I,
    ),
    "exclusive": re.compile(r"\b(?:only|solely|exclusively|hanya)\b", flags=re.I),
    "minimum": re.compile(
        r"\b(?:at\s+least|minimum|minimal|no\s+less\s+than|more\s+than|"
        r"longer\s+than|beyond|exceed(?:s|ed)?|sekurang-kurangnya|lebih\s+dari|"
        r"melebihi)\b",
        flags=re.I,
    ),
    "maximum": re.compile(
        r"\b(?:up\s+to|within|maximum|maximal|maksimal|maksimum|no\s+more\s+than|"
        r"capped|cap|limited\s+to|no\s+later\s+than|paling\s+banyak|paling\s+lambat|selambat-lambatnya|"
        r"dalam\s+waktu|below|under|di\s+bawah)\b",
        flags=re.I,
    ),
    "exception": re.compile(r"\b(?:except|unless|excluding|kecuali)\b", flags=re.I),
    "prohibition": re.compile(
        r"\b(?:must\s+not|cannot|may\s+not|not\s+allowed|prohibited|dilarang|tidak\s+boleh)\b",
        flags=re.I,
    ),
    "approximate": re.compile(
        r"\b(?:about|approximately|roughly|around|sekitar|kurang\s+lebih)\b",
        flags=re.I,
    ),
    "unmet_condition": re.compile(
        r"\b(?:if\b.{0,45}\bnot\s+resolved|not\s+resolved\s+within|"
        r"jika\b.{0,45}\bbelum\s+(?:selesai|diselesaikan|terselesaikan)|"
        r"belum\s+(?:selesai|diselesaikan|terselesaikan))\b",
        flags=re.I,
    ),
}

RELATIONAL_CLAIM_PATTERN = re.compile(
    r"\b(?:used\s+to|is\s+used|governs?|regulates?|covers?|includes?|defines?|"
    r"digunakan|berfungsi|mengatur|mencakup|meliputi|mendefinisikan)\b",
    flags=re.I,
)

IGNORED_ACRONYMS = {
    "IDR", "USD", "EUR", "WIB", "GB", "MB", "TB", "KB", "FAQ", "SOP",
    "PDF", "DOCX", "TXT", "AI", "IT",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_number(value: str) -> str:
    raw = normalize_text(value)
    if raw in WORD_NUMBERS:
        return WORD_NUMBERS[raw]
    raw = re.sub(r"(?:st|nd|rd|th)$", "", str(value).strip(), flags=re.I).replace(" ", "")
    if "x" in raw.casefold() or "×" in raw:
        return raw.casefold().replace("×", "x")
    # A single separator followed by one or two digits is treated as decimal.
    if raw.count(",") == 1 and raw.count(".") == 0 and len(raw.split(",")[-1]) <= 2:
        return raw.replace(",", ".")
    if raw.count(".") == 1 and raw.count(",") == 0 and len(raw.split(".")[-1]) <= 2:
        return raw
    return raw.replace(",", "").replace(".", "")


def _normalize_magnitude(value: str) -> str:
    mapping = {
        "ribu": "thousand", "thousand": "thousand",
        "juta": "million", "million": "million",
        "miliar": "billion", "billion": "billion",
        "triliun": "trillion", "trillion": "trillion",
    }
    return mapping.get(normalize_text(value), normalize_text(value))


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9à-ÿ]+", normalize_text(value))
        if len(token) >= 3 and token not in STOPWORDS
    }


def _grounding_concepts(value: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9à-ÿ]+", " ", normalize_text(value))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    padded = f" {normalized} "
    return {
        canonical
        for canonical, aliases in GROUNDING_CONCEPT_ALIASES.items()
        if any(
            (
                candidate := re.sub(
                    r"\s+",
                    " ",
                    re.sub(r"[^a-z0-9à-ÿ]+", " ", normalize_text(alias)),
                ).strip()
            )
            and f" {candidate} " in padded
            for alias in aliases
        )
    }


def _normalized_phrase(value: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9à-ÿ]+",
        " ",
        normalize_text(value),
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _matched_equivalent_tokens(
    value: str,
    aliases: tuple[str, ...],
) -> set[str]:
    """Return tokens belonging to aliases that occur as complete phrases."""
    normalized = _normalized_phrase(value)
    if not normalized:
        return set()
    padded = f" {normalized} "
    matched: set[str] = set()
    for alias in aliases:
        candidate = _normalized_phrase(alias)
        if candidate and f" {candidate} " in padded:
            matched.update(_tokenize(candidate))
    return matched


def _equivalent_group_occurs(
    value: str,
    aliases: tuple[str, ...],
) -> bool:
    """Return True even when a matched phrase contains only short words."""
    normalized = _normalized_phrase(value)
    if not normalized:
        return False
    padded = f" {normalized} "
    return any(
        candidate and f" {candidate} " in padded
        for candidate in (_normalized_phrase(alias) for alias in aliases)
    )


def _span_overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and end > other_start for other_start, other_end in occupied)


def _fact_entries(value: str) -> list[tuple[str, str, str]]:
    """Return unique (key, raw display, canonical display) facts."""
    raw = str(value or "")
    entries: list[tuple[str, str, str]] = []
    occupied: list[tuple[int, int]] = []

    def add(key: str, display: str, canonical_display: str, span: tuple[int, int] | None = None) -> None:
        if key not in {item[0] for item in entries}:
            entries.append((key, display, canonical_display))
        if span is not None:
            occupied.append(span)

    for match in URL_PATTERN.finditer(raw):
        display = match.group(0).rstrip(".,;)]}")
        add(f"url:{display.casefold()}", display, display.casefold(), match.span())
    for match in EMAIL_PATTERN.finditer(raw):
        display = match.group(0)
        add(f"email:{display.casefold()}", display, display.casefold(), match.span())

    for match in MONEY_PATTERN.finditer(raw):
        display = match.group(0)
        parsed = re.search(
            rf"\b(IDR|Rp\.?|USD|EUR)\s*({NUMBER_CORE})"
            r"(?:\s*(ribu|thousand|juta|million|miliar|billion|triliun|trillion))?\b",
            display,
            flags=re.I,
        )
        if parsed:
            currency = parsed.group(1).casefold().replace("rp.", "idr").replace("rp", "idr")
            number = _normalize_number(parsed.group(2))
            magnitude = _normalize_magnitude(parsed.group(3) or "")
            canonical = " ".join(part for part in (currency, number, magnitude) if part)
            add(f"money:{currency}:{number}:{magnitude}", display, canonical, match.span())

    for match in PERCENT_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        number_match = re.search(NUMBER_CORE, display, flags=re.I)
        if number_match:
            number = _normalize_number(number_match.group(0))
            add(f"percent:{number}", display, f"{number}%", match.span())

    for match in NUMBER_UNIT_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        number = _normalize_number(match.group(1))
        unit = canonical_unit(match.group(2))
        canonical = f"{number} {unit}".strip()
        add(f"quantity:{number}:{unit}", display, canonical, match.span())

    # English leave prose often places modifiers between the count and unit,
    # for example ``6 unused leave days``. Record the same strict quantity key
    # as Indonesian ``enam hari`` without accepting arbitrary separated units.
    for match in LEAVE_DAY_QUANTITY_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        number = _normalize_number(match.group(1))
        add(f"quantity:{number}:days", display, f"{number} days", match.span())

    for match in VERSION_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        normalized = normalize_text(display)
        add(f"version:{normalized}", display, normalized, match.span())

    for match in YEAR_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        add(f"year:{display}", display, display, match.span())

    for match in PLAIN_NUMBER_PATTERN.finditer(raw):
        if _span_overlaps(match.span(), occupied):
            continue
        display = match.group(0)
        number = _normalize_number(display)
        add(f"number:{number}", display, number, match.span())

    for match in ACRONYM_PATTERN.finditer(raw):
        display = match.group(0).upper()
        if display in IGNORED_ACRONYMS or display.isdigit():
            continue
        if re.fullmatch(r"FY(?:19|20)\d{2}", display):
            # YEAR_PATTERN already records the comparable year key.
            continue
        add(f"identifier:{display}", display, display)

    return entries


def _selected_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        chunk
        for chunk in chunks
        if chunk.get("answerabilityEvidenceSelected", True)
        and chunk.get("contextSelected", True)
        and not chunk.get("evidenceHardFailures")
    ] or [
        chunk for chunk in chunks
        if not chunk.get("evidenceHardFailures")
    ]


def _evidence_units(chunks: list[dict[str, Any]]) -> list[str]:
    """Split evidence into claim-sized units without mixing separate sources."""
    units: list[str] = []
    for chunk in _selected_chunks(chunks):
        content = _clean(chunk.get("content"))
        if not content:
            continue
        # Keep the whole chunk as a source-bounded unit so a valid answer may
        # combine adjacent sentences from the same passage. Separate chunks are
        # never merged, which still blocks cross-document relation swapping.
        if content not in units:
            units.append(content)
        parts = [
            _clean(part).lstrip("-• ")
            for part in SENTENCE_SPLIT.split(content)
            if _clean(part).lstrip("-• ")
        ]
        for part in parts:
            if part not in units:
                units.append(part)
    return units


def _context_text(chunks: list[dict[str, Any]]) -> str:
    return "\n".join(_evidence_units(chunks))


def _qualifier_families(value: str) -> set[str]:
    return {
        family
        for family, pattern in QUALIFIER_PATTERNS.items()
        if pattern.search(str(value or ""))
    }


def _atomic_claims(value: Any) -> list[str]:
    """Split an answer into independently validated factual claims.

    Besides sentence boundaries, comma-separated and semicolon-separated
    list items are checked individually. This prevents one supported item
    from hiding another unsupported item.

    Example:

        Bring your ID, academic transcripts.

    becomes:

        Bring your ID
        academic transcripts

    Commas inside numbers such as 1,000 are not treated as separators.
    """

    raw_text = str(value or "")
    claims: list[str] = []
    seen: set[str] = set()

    for raw_sentence in SENTENCE_SPLIT.split(raw_text):
        sentence = _clean(raw_sentence)
        sentence = re.sub(
            r"^(?:(?:#{1,6}|[-*•])\s+|\d{1,2}[.)]\s+)",
            "",
            sentence,
        ).lstrip("-? ")
        # Attribution is presentation text, not an independent factual claim.
        # Removing it before comma splitting prevents false rejection of
        # sentences such as 'Berdasarkan dokumen, ...'.
        sentence = GROUNDING_PREAMBLE.sub("", sentence).strip()

        if not sentence:
            continue

        # Bersihkan artefak tanda baca seperti ",." dan spasi sebelum koma.
        sentence = re.sub(
            r"\s+([,.;:!?])",
            r"\1",
            sentence,
        )
        sentence = re.sub(
            r",\s*\.$",
            ".",
            sentence,
        )
        sentence = sentence.strip()

        # Pisahkan klausa kausal/kontras terlebih dahulu. Ini memungkinkan
        # bagian fakta yang didukung tetap dipertahankan ketika model menambah
        # ekor spekulatif seperti "because it is more scalable".
        clause_parts = [
            part for part in CLAUSE_SPLIT.split(sentence)
            if _clean(part)
        ] or [sentence]

        # Pecah daftar berdasarkan koma/semicolon, tetapi jangan pecah koma
        # yang berada di antara angka, misalnya 1,000.
        parts: list[str] = []
        for clause_part in clause_parts:
            if CONDITIONAL_COMMA_PREFIX.search(clause_part):
                # Keep conditional and temporal prefixes attached to the main
                # clause. Splitting "Jika belum selesai, insiden dieskalasikan"
                # creates two fragments that cannot be grounded independently.
                parts.extend(re.split(r";", clause_part))
            else:
                parts.extend(re.split(r"(?<!\d),(?!\d)|;", clause_part))

        cleaned_parts: list[str] = []

        for part in parts:
            clean_part = _clean(part).lstrip("-? ")

            # Hilangkan kata sambung pada awal item.
            clean_part = re.sub(
                r"^(?:and|or|dan|atau|serta)\s+",
                "",
                clean_part,
                flags=re.I,
            )

            clean_part = clean_part.strip(
                " ,;:."
            )

            if clean_part:
                cleaned_parts.append(clean_part)

        # Hanya gunakan pemecahan daftar jika memang ada minimal dua item.
        candidate_claims = (
            cleaned_parts
            if len(cleaned_parts) >= 2
            else [sentence.strip(" ,;:")]
        )

        for claim in candidate_claims:
            claim = _clean(claim).strip()

            if not claim:
                continue

            normalized = re.sub(
                r"\W+",
                "",
                claim.casefold(),
            )

            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            claims.append(claim)

    return claims


_INCIDENT_CODE_PATTERN = re.compile(
    r"\b(?:p(?P<pnum>[1-4])|priority\s+(?P<priority>[1-4])|"
    r"prioritas\s+(?P<prioritas>[1-4]))\b",
    flags=re.I,
)


def _incident_relation_is_coherent(claim: str, unit: str) -> bool:
    """Bind an incident priority to the quantity in its own local row.

    PDF extraction can flatten P1 and P2 SLA rows into one passage. The quantity
    must occur after the requested priority code and before the next code, so a P2
    value cannot accidentally be attached to P1, or vice versa.
    """
    claim_entries = _fact_entries(claim)
    claim_codes = [
        key.split(":", 1)[1].casefold()
        for key, _, _ in claim_entries
        if key.startswith("identifier:P")
    ]
    claim_quantities = {
        key for key, _, _ in claim_entries
        if key.startswith("quantity:")
    }
    if len(claim_codes) != 1 or not claim_quantities:
        return True

    requested_code = claim_codes[0]
    mentions = list(_INCIDENT_CODE_PATTERN.finditer(unit))
    if not mentions:
        return True

    for index, mention in enumerate(mentions):
        number = (
            mention.group("pnum")
            or mention.group("priority")
            or mention.group("prioritas")
        )
        if f"p{number}" != requested_code:
            continue
        end = mentions[index + 1].start() if index + 1 < len(mentions) else len(unit)
        local_row = unit[mention.start():end]
        local_keys = {key for key, _, _ in _fact_entries(local_row)}
        if claim_quantities.issubset(local_keys):
            return True
    return False


def _claim_reference_units(claim: str, evidence_units: list[str]) -> list[str]:
    claim_fact_keys = {key for key, _, _ in _fact_entries(claim)}
    if not claim_fact_keys:
        return list(evidence_units)

    matched = [
        unit
        for unit in evidence_units
        if claim_fact_keys.issubset({key for key, _, _ in _fact_entries(unit)})
        and _incident_relation_is_coherent(claim, unit)
    ]
    if not matched:
        return []

    # Prefer precise evidence units while retaining flattened PDF rows when no
    # shorter sentence contains all required facts.
    shortest = min(len(unit) for unit in matched)
    return [unit for unit in matched if len(unit) <= shortest + 160]


def _canonical_claim_token_coverage(
    claim: str,
    unit: str,
    claim_concepts: set[str],
    unit_concepts: set[str],
) -> float:
    """Measure bilingual claim coverage through canonical aliases and facts.

    Literal token overlap is naturally low when the answer is Indonesian and the
    indexed evidence is English. The retrieval layer already maps both languages
    to the same domain concepts, so the grounding validator must reuse that same
    canonical vocabulary instead of treating a faithful translation as an
    unsupported claim.

    The bridge remains strict: every concept in the claim must exist in the same
    evidence unit, every explicit fact is already bound to that unit by
    ``_claim_reference_units``, and almost every remaining content token must be
    explainable by a known bilingual alias or an explicit fact. Unsupported tails
    therefore do not receive this cross-language support floor.
    """
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return 1.0
    if claim_concepts and not claim_concepts.issubset(unit_concepts):
        return 0.0

    covered = set(claim_tokens.intersection(_tokenize(unit)))

    for concept in claim_concepts:
        for alias in GROUNDING_CONCEPT_ALIASES.get(concept, ()):
            covered.update(claim_tokens.intersection(_tokenize(alias)))

    # Cover only the claim-side words from an equivalence group that is also
    # explicitly represented in this evidence unit. This supports faithful
    # translation while keeping unrelated additions visible as uncovered.
    for aliases in GROUNDING_EQUIVALENT_TERMS.values():
        claim_alias_tokens = _matched_equivalent_tokens(claim, aliases)
        if not claim_alias_tokens:
            continue
        if _equivalent_group_occurs(unit, aliases):
            covered.update(claim_tokens.intersection(claim_alias_tokens))

    for _, raw, canonical in _fact_entries(claim):
        covered.update(claim_tokens.intersection(_tokenize(raw)))
        covered.update(claim_tokens.intersection(_tokenize(canonical)))

    return len(covered) / len(claim_tokens)


def _claim_support(
    claim: str,
    evidence_units: list[str],
    *,
    question: str = "",
) -> float:
    """Return support from one evidence unit, not a token soup across documents."""
    claim_tokens = _tokenize(claim)
    claim_concepts = _grounding_concepts(claim)
    question_concepts = _grounding_concepts(question)
    claim_qualifiers = _qualifier_families(claim)
    if not claim_tokens and not claim_concepts:
        return 1.0

    scores: list[float] = []
    for unit in evidence_units:
        # Material qualifiers must be explicit in the same evidence unit. This is
        # stricter than ordinary paraphrase matching because these words change
        # the policy or causal meaning of the claim.
        if not claim_qualifiers.issubset(_qualifier_families(unit)):
            continue

        unit_tokens = _tokenize(unit)
        lexical = (
            len(claim_tokens.intersection(unit_tokens)) / len(claim_tokens)
            if claim_tokens
            else 0.0
        )
        unit_concepts = _grounding_concepts(unit) | question_concepts
        concept = (
            len(claim_concepts.intersection(unit_concepts)) / len(claim_concepts)
            if claim_concepts
            else 0.0
        )

        # Concept aliases may bridge Indonesian/English wording. Literal overlap
        # still remains the default, while a high canonical-token coverage allows
        # a faithful translation to pass without lowering the global threshold.
        if claim_tokens and claim_concepts:
            score = max(lexical, 0.75 * lexical + 0.25 * concept)
        elif claim_concepts:
            score = concept
        else:
            score = lexical

        canonical_coverage = (
            _canonical_claim_token_coverage(
                claim,
                unit,
                claim_concepts,
                unit_concepts,
            )
            if claim_tokens
            else 1.0
        )
        has_explicit_facts = bool(_fact_entries(claim))
        required_coverage = 0.85 if has_explicit_facts else 0.95
        if canonical_coverage + 1e-9 >= required_coverage:
            score = max(score, canonical_coverage)

        scores.append(score)
    return max(scores, default=0.0)


def _required_claim_support(claim: str, base_threshold: float) -> float:
    """Use a stricter floor for broad relational claims without exact facts.

    A weak title overlap may contain ``SOP``, a company name, and ``business``
    while still not supporting the relation "SOP is used to govern business
    processes". These fluent relational tails need more than the global 0.32
    lexical floor.
    """

    if (
        RELATIONAL_CLAIM_PATTERN.search(claim)
        and len(_tokenize(claim)) >= 5
        and not _fact_entries(claim)
    ):
        return max(float(base_threshold), 0.45)
    return float(base_threshold)


def prune_unsupported_claims(
    question: str,
    answer: str,
    chunks: list[dict[str, Any]],
    *,
    minimum_claim_support: float = GENERATION_MIN_CLAIM_SUPPORT,
) -> str:
    """Return only independently supported claims, or an empty string.

    The function never invents replacement text. It removes unsupported clauses
    from the model output and keeps the remaining answer only when all explicit
    answer-type requirements are still satisfied.
    """
    evidence_units = _evidence_units(chunks)
    if is_scenario_comparison(question):
        evidence_units = [*evidence_units, question]

    # A generated answer cannot repair an answer-type gap in the source. A
    # title containing "SOP" does not prove what SOP stands for.
    for requirement in extract_evidence_requirements(question):
        if not requirement.key.startswith("answer_"):
            continue
        if not requirement_satisfied(requirement, evidence_units):
            return ""

    kept: list[str] = []
    for claim in _atomic_claims(answer):
        reference_units = _claim_reference_units(claim, evidence_units)
        if not reference_units:
            continue
        required_support = _required_claim_support(claim, minimum_claim_support)
        if (
            _claim_support(claim, reference_units, question=question) + 1e-9
            < required_support
        ):
            continue
        if claim not in kept:
            kept.append(claim)

    if not kept:
        return ""

    candidate = ". ".join(item.rstrip(".!? ") for item in kept).strip()
    if candidate and candidate[-1:] not in ".!?":
        candidate += "."

    for requirement in extract_evidence_requirements(question):
        if requirement.key.startswith("answer_") and not requirement_satisfied(requirement, [candidate]):
            return ""
    return candidate


def _unsupported_fact_displays(
    answer_entries: list[tuple[str, str, str]],
    allowed_keys: set[str],
) -> list[str]:
    output: list[str] = []
    for key, raw, canonical in answer_entries:
        if key in allowed_keys:
            continue
        # Keep the original text for user-facing diagnostics and the canonical
        # text for stable regression assertions across punctuation/languages.
        for display in (raw, canonical):
            if display and display not in output:
                output.append(display)
    return output


def validate_grounded_answer(
    question: str,
    answer: str,
    chunks: list[dict[str, Any]],
    *,
    minimum_claim_support: float = GENERATION_MIN_CLAIM_SUPPORT,
) -> GroundingDecision:
    clean_answer = _clean(answer)
    evidence_units = _evidence_units(chunks)
    context = "\n".join(evidence_units)
    emit_progress(
        "grounding",
        "active",
        "Memeriksa grounding",
        detail=f"Memastikan klaim jawaban didukung oleh {len(evidence_units)} unit bukti terpilih.",
        metadata={"evidenceUnitCount": len(evidence_units)},
    )
    if not clean_answer or not context:
        decision = GroundingDecision(
            supported=False,
            score=0.0,
            reasons=("empty_answer_or_context",),
            unsupported_facts=(),
        )
        emit_progress(
            "grounding",
            "failed",
            "Pemeriksaan grounding gagal",
            detail="Jawaban atau konteks bukti kosong.",
            metadata={"supported": False, "score": 0.0},
        )
        return decision

    context_entries = _fact_entries(context)
    question_entries = _fact_entries(question) if is_scenario_comparison(question) else []
    allowed_keys = {key for key, _, _ in context_entries + question_entries}
    answer_entries = _fact_entries(clean_answer)
    unsupported_facts = _unsupported_fact_displays(answer_entries, allowed_keys)

    claim_reference_units = list(evidence_units)
    if is_scenario_comparison(question):
        claim_reference_units.append(question)

    unsupported_claims: list[str] = []
    claim_scores: list[float] = []
    for claim in _atomic_claims(answer):
        # Validate short substantive answers as well. Skipping claims with fewer
        # than four words allowed unsupported answers such as "MySQL" to pass.
        if not _tokenize(claim) and not _fact_entries(claim):
            continue
        fact_bound_units = _claim_reference_units(claim, claim_reference_units)
        # A factual claim must be supported by the same evidence unit that
        # contains its explicit values. This prevents relation swapping across
        # chunks, such as attaching a P2 deadline to a P1 incident.
        score = (
            _claim_support(claim, fact_bound_units, question=question)
            if fact_bound_units
            else 0.0
        )
        claim_scores.append(score)
        required_support = _required_claim_support(claim, minimum_claim_support)
        if score + 1e-9 < required_support:
            unsupported_claims.append(claim[:220])

    missing_requirements: list[str] = []
    missing_evidence_requirements: list[str] = []
    for requirement in extract_evidence_requirements(question):
        if not requirement.key.startswith("answer_"):
            continue
        answer_has_requirement = requirement_satisfied(requirement, [clean_answer])
        if not answer_has_requirement:
            missing_requirements.append(requirement.key)
            continue
        if not requirement_satisfied(requirement, evidence_units):
            missing_evidence_requirements.append(requirement.key)

    reasons: list[str] = []
    if unsupported_facts:
        reasons.append("unsupported_explicit_facts")
    if unsupported_claims:
        reasons.append("unsupported_claims")
    if missing_requirements:
        reasons.append("incomplete_answer_type")
    if missing_evidence_requirements:
        reasons.append("missing_evidence_requirement")

    unique_facts = tuple(dict.fromkeys(unsupported_facts))
    unique_claims = tuple(dict.fromkeys(unsupported_claims))
    unique_missing = tuple(dict.fromkeys(missing_requirements))
    unique_missing_evidence = tuple(dict.fromkeys(missing_evidence_requirements))
    mean_claim = sum(claim_scores) / len(claim_scores) if claim_scores else 1.0
    penalty = min(
        1.0,
        0.28 * len(unique_facts)
        + 0.22 * len(unique_claims)
        + 0.25 * len(unique_missing)
        + 0.30 * len(unique_missing_evidence),
    )
    score = max(0.0, min(mean_claim * (1.0 - penalty), 1.0))

    decision = GroundingDecision(
        supported=not reasons,
        score=round(score, 6),
        reasons=tuple(reasons),
        unsupported_facts=unique_facts,
        unsupported_claims=unique_claims,
        missing_answer_requirements=unique_missing,
        missing_evidence_requirements=unique_missing_evidence,
        checked_claims=len(claim_scores),
    )
    emit_progress(
        "grounding",
        "completed" if decision.supported else "failed",
        "Pemeriksaan grounding selesai",
        detail=(
            f"{decision.checked_claims} klaim diperiksa dan seluruhnya didukung dokumen."
            if decision.supported
            else f"{decision.checked_claims} klaim diperiksa; jawaban memerlukan perbaikan grounding."
        ),
        metadata={
            "supported": decision.supported,
            "score": decision.score,
            "checkedClaims": decision.checked_claims,
        },
    )
    return decision
