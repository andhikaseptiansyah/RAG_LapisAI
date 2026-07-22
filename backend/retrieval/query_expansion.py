"""Bilingual query expansion for the LapisAI enterprise corpus.

The corpus is mostly English while users may ask in Indonesian. This module does
not call an external translator. It appends stable enterprise-domain aliases so
semantic retrieval, BM25, reranking, and evidence verification receive the same
cross-language hints.
"""

from __future__ import annotations

import re
from collections.abc import Iterable


# Canonical concepts and their Indonesian/English surface forms. The same mapping
# is reused by evidence verification so expansion and validation do not disagree.
CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "password": (
        "password",
        "kata sandi",
        "sandi",
    ),
    "password_reset": (
        "password reset",
        "reset password",
        "forgot password",
        "forgotten password",
        "lupa password",
        "kelupaan password",
        "lupa kata sandi",
        "reset kata sandi",
        "mereset kata sandi",
        "atur ulang kata sandi",
        "prosedur reset password",
    ),
    "helpdesk": (
        "it helpdesk",
        "it service desk",
        "helpdesk",
        "service desk",
        "portal it",
        "tiket it",
    ),
    "processing_time": (
        "processing time",
        "turnaround time",
        "processed within",
        "how long",
        "berapa lama",
        "batas waktu",
        "waktu proses",
        "lama proses",
        "maksimal proses",
        "maksimal prosesnya",
        "paling lama",
    ),
    "annual_leave": (
        "annual leave",
        "cuti tahunan",
    ),
    "maternity_leave": (
        "maternity leave",
        "parental leave",
        "cuti melahirkan",
        "cuti bersalin",
        "melahirkan",
        "bersalin",
    ),
    "paternity_leave": (
        "paternity leave",
        "father leave",
        "cuti ayah",
        "karyawan pria",
        "male employee",
        "spouse gives birth",
        "pasangannya melahirkan",
    ),
    "carryover": (
        "carryover",
        "carry over",
        "carried over",
        "unused leave",
        "sisa cuti",
        "dibawa ke tahun berikutnya",
    ),
    "next_year": (
        "next year",
        "tahun berikutnya",
    ),
    "expense": (
        "expense",
        "expenses",
        "pengeluaran",
        "biaya",
    ),
    "original_receipt": (
        "original receipt",
        "original receipts",
        "bukti pembayaran asli",
        "nota asli",
        "kuitansi asli",
    ),
    "amount_threshold": (
        "above idr",
        "amount",
        "threshold",
        "single expense above",
        "sebesar berapa",
        "di atas",
        "batas nominal",
    ),
    "system_access": (
        "system access",
        "access rights",
        "akses sistem",
        "seluruh akses",
    ),
    "access_revocation": (
        "access revocation",
        "revoke access",
        "revokes all system access",
        "deprovision",
        "mencabut akses",
        "pencabutan akses",
    ),
    "offboarding": (
        "offboarding",
        "departing employee",
        "employee exit",
        "termination",
        "karyawan keluar",
        "karyawan yang keluar",
        "pegawai keluar",
    ),
    "revenue": (
        "revenue",
        "pendapatan",
        "omzet",
    ),
    "full_year": (
        "full-year",
        "full year",
        "tahun penuh",
    ),
    "water": (
        "water",
        "water consumption",
        "konsumsi air",
        "air bersih",
    ),
    "electricity": (
        "electricity",
        "electricity consumption",
        "energy consumption",
        "konsumsi listrik",
        "listrik",
    ),
    "reduction": (
        "reduction",
        "reduced",
        "decrease",
        "pengurangan",
        "menurunkan",
        "berkurang",
    ),
    "lunch": (
        "lunch",
        "meal",
        "makan siang",
    ),
    "subsidy": (
        "subsidy",
        "allowance",
        "benefit",
        "subsidi",
        "tunjangan",
    ),
    "canteen": (
        "canteen",
        "cafeteria",
        "kantin",
    ),
    "macos": (
        "macos",
        "mac os",
        "os x",
    ),
    "minimum_version": (
        "minimum version",
        "minimum supported version",
        "versi minimum",
    ),
    "supported": (
        "supported",
        "support",
        "didukung",
    ),
    "laptop": (
        "laptop",
        "notebook",
    ),
    "office": (
        "office",
        "kantor",
    ),
    "cikarang": (
        "cikarang",
    ),
    "probation": (
        "probation",
        "probation period",
        "masa percobaan",
    ),
    "dependents": (
        "dependents",
        "tanggungan",
    ),
    "health_insurance": (
        "health insurance",
        "medical insurance",
        "asuransi kesehatan",
    ),
    "file_upload": (
        "file upload",
        "file-upload",
        "upload file",
        "upload files",
        "file uploads",
        "uploaded file",
        "upload size",
        "file size limit",
        "attachment upload",
        "attachment size",
        "unggah file",
        "mengunggah file",
        "unggahan file",
        "ukuran unggahan",
        "batas ukuran file",
        "ukuran maksimum file",
    ),
    "customer_portal": (
        "customer portal",
        "client portal",
        "self-service portal",
        "portal customer",
        "portal pelanggan",
        "portal nasabah",
    ),
    "incident_p1": (
        "p1 incident",
        "p1 incidents",
        "priority 1 incident",
        "priority one incident",
        "insiden p1",
        "insiden prioritas 1",
    ),
    "incident_p2": (
        "p2 incident",
        "p2 incidents",
        "priority 2 incident",
        "priority two incident",
        "insiden p2",
        "insiden prioritas 2",
    ),
    "mailbox_quota": (
        "mailbox quota",
        "mailbox size",
        "mailbox size limit",
        "mailbox storage",
        "email quota",
        "email storage",
        "kuota email",
        "ukuran mailbox",
        "batas mailbox",
        "kapasitas mailbox",
    ),
    "access_card": (
        "access card",
        "employee access card",
        "kartu akses",
    ),
    "payslip": (
        "payslip",
        "payslips",
        "salary slip",
        "slip gaji",
    ),
    "salary_payment": (
        "salary paid",
        "salaries are paid",
        "payday",
        "payroll date",
        "salary payment",
        "payment is the prior working day",
        "pembayaran gaji",
        "gaji dibayar",
    ),
    "data_breach": (
        "data breach",
        "data breaches",
        "security breach",
        "security breaches",
        "suspected data breach",
        "suspected data breaches",
        "kebocoran data",
        "dugaan kebocoran data",
        "insiden data",
    ),
    "information_classification": (
        "information classification",
        "classification levels",
        "klasifikasi informasi",
    ),
    "audit_log": (
        "audit log",
        "audit logs",
        "log audit",
    ),
    "deployment": (
        "deployment",
        "production deployment",
        "rilis produksi",
    ),
    "rto": ("rto", "recovery time objective"),
    "rpo": ("rpo", "recovery point objective"),
    "api_token": (
        "api token",
        "internal api token",
        "bearer jwt token",
        "jwt token",
        "tokens expire",
        "token api",
    ),
}


# Phrase-oriented expansion improves the specific cross-language failure mode
# without hardcoding an answer or a source filename.
PHRASE_EXPANSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"\b(?:lupa|kelupaan)\s+(?:password|kata sandi|sandi)\b", (
        "forgot password",
        "password reset",
        "reset password",
        "IT Helpdesk portal",
        "processed within",
    )),
    (r"\b(?:prosedur|cara|langkah)\s+(?:untuk\s+)?(?:reset|mereset|mengatur ulang)\b", (
        "password reset procedure",
        "reset request",
        "IT Helpdesk portal",
    )),
    (r"\b(?:reset|mereset|mengatur ulang|atur ulang)\s+(?:kata sandi|password)\b", (
        "password reset",
        "IT Helpdesk portal",
        "processed within",
    )),
    (r"\b(?:berapa\s+lama(?:\s+(?:maksimal|maximum))?(?:\s+prosesnya)?|maksimal\s+prosesnya|paling\s+lama)\b", (
        "how long",
        "maximum processing time",
        "processing time",
        "processed within",
        "hours days",
    )),
    (r"\bsisa\s+cuti(?:\s+tahunan)?\b", (
        "unused annual leave",
        "leave carryover",
    )),
    (r"\bdibawa\s+ke\s+tahun\s+berikutnya\b", (
        "carried over to the next year",
        "carryover",
    )),
    (r"\bbukti\s+pembayaran\s+asli\b", (
        "original receipt",
        "original receipts",
    )),
    (r"\bmencabut\s+(?:seluruh\s+)?akses\b", (
        "revoke all system access",
        "access revocation",
    )),
    (r"\bkaryawan\s+(?:yang\s+)?keluar\b", (
        "departing employee",
        "employee exit",
        "offboarding",
    )),
    (r"\bcuti\s+melahirkan\b", (
        "maternity leave",
        "parental leave",
    )),
    (r"\bsubsidi\s+makan\s+siang\b", (
        "lunch subsidy",
        "meal allowance",
        "canteen benefit",
    )),
    (r"\bkonsumsi\s+air\b", (
        "water consumption",
    )),
    (r"\bpendapatan(?:\s+resmi)?\b", (
        "revenue",
    )),
    (r"\bversi\s+minimum\s+mac\s*os\b", (
        "minimum supported macOS version",
    )),
    (r"\b(?:maximum|max|maksimal|batas|ukuran)\s+(?:file[- ]?upload|upload|unggahan)\s+(?:size|file)?\b", (
        "file upload size limit",
        "maximum file upload size",
        "attachment size limit",
    )),
    (r"\b(?:customer|client|pelanggan|nasabah)\s+portal\b", (
        "customer portal",
        "self-service portal",
    )),
)


INVENTORY_EXPANSION_TERMS = (
    "inventory",
    "warehouse",
    "stock",
    "asset code",
    "item name",
    "brand",
    "type",
    "item location",
    "owner",
    "quantity",
    "incoming goods",
    "outgoing goods",
    "Microsoft Excel",
)


def normalize_text(text: str) -> str:
    value = str(text or "").casefold()
    value = re.sub(r"[^a-z0-9à-ÿ%._\-/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def contains_alias(text: str, aliases: Iterable[str]) -> bool:
    """Return True only for a complete word/phrase match.

    The previous implementation also used ``candidate in normalized``. That
    caused short aliases such as ``rpo`` to match unrelated words such as
    ``corporate`` and produced false hard constraints in evidence verification.
    Normalization turns punctuation into stable separators, so a padded phrase
    comparison is sufficient and works for both one-word and multi-word aliases.
    """
    normalized = normalize_text(text)
    if not normalized:
        return False

    padded = f" {normalized} "
    for alias in aliases:
        candidate = normalize_text(alias)
        if candidate and f" {candidate} " in padded:
            return True
    return False


def concepts_in_text(text: str) -> list[str]:
    return [
        canonical
        for canonical, aliases in CONCEPT_ALIASES.items()
        if contains_alias(text, aliases)
    ]


def _is_inventory_query(query: str) -> bool:
    normalized = normalize_text(query)
    hints = (
        "inventori",
        "inventory",
        "persediaan",
        "gudang",
        "barang",
        "aset",
        "stok",
        "warehouse",
    )
    return any(hint in normalized for hint in hints)


def expand_query(query: str) -> str:
    """Append bilingual aliases while preserving the user's original wording."""
    original = str(query or "").strip()
    if not original:
        return ""

    additions: list[str] = []
    normalized = normalize_text(original)

    for pattern, expansions in PHRASE_EXPANSIONS:
        if re.search(pattern, normalized, flags=re.I):
            additions.extend(expansions)

    for canonical in concepts_in_text(original):
        aliases = CONCEPT_ALIASES[canonical]
        # Add only a few compact aliases; repeating every form inflates BM25.
        additions.extend(aliases[:3])

    if _is_inventory_query(original):
        additions.extend(INVENTORY_EXPANSION_TERMS)

    unique: list[str] = []
    seen: set[str] = set()
    for addition in additions:
        clean = str(addition).strip()
        key = normalize_text(clean)
        if not key or key in seen or key in normalized:
            continue
        seen.add(key)
        unique.append(clean)

    if not unique:
        return original
    return f"{original} {' '.join(unique)}"
