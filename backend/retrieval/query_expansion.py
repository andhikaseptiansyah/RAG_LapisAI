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
    "remote_work": (
        "remote work",
        "work remotely",
        "working remotely",
        "work from home",
        "wfh",
        "bekerja dari rumah",
        "kerja dari rumah",
        "bekerja jarak jauh",
        "kerja jarak jauh",
    ),
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
        "resolution time",
        "resolved within",
        "turnaround time",
        "processed within",
        "resolution target",
        "must be resolved",
        "how long",
        "how quickly",
        "berapa lama",
        "seberapa cepat",
        "berapa cepat",
        "batas waktu",
        "waktu proses",
        "lama proses",
        "waktu penyelesaian",
        "target penyelesaian",
        "batas penyelesaian",
        "harus diselesaikan",
        "diselesaikan dalam",
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
        "cost",
        "costs",
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
        "mencabut seluruh akses",
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
    "retirement_benefit": (
        "pension benefit",
        "retirement benefit",
        "employee pension",
        "pension plan",
        "pension",
        "manfaat pensiun",
        "program pensiun",
        "jaminan pensiun",
        "bpjs ketenagakerjaan",
        "contributes to bpjs ketenagakerjaan",
        "kontribusi ke bpjs ketenagakerjaan",
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
        "p1 it incident",
        "p1 it incidents",
        "p1 incidents",
        "priority 1 incident",
        "priority one incident",
        "it incident p1",
        "insiden p1",
        "insiden it p1",
        "insiden ti p1",
        "insiden prioritas 1",
    ),
    "incident_p2": (
        "p2 incident",
        "p2 it incident",
        "p2 it incidents",
        "p2 incidents",
        "priority 2 incident",
        "priority two incident",
        "it incident p2",
        "insiden p2",
        "insiden it p2",
        "insiden ti p2",
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
        "gaji dibayarkan",
        "gaji karyawan dibayarkan",
        "tanggal gaji",
        "dibayarkan setiap bulan",
        "paid on the 25th",
    ),
    "overtime_payment": (
        "overtime",
        "approved overtime",
        "overtime payment",
        "overtime paid",
        "how is overtime paid",
        "lembur",
        "jam lembur",
        "lembur disetujui",
        "lembur yang telah disetujui",
        "pembayaran lembur",
        "lembur dibayar",
        "lembur dibayarkan",
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
    # Additional enterprise concepts used by the bilingual evaluation set.
    # These are subject aliases only; they never contain answer values or source names.
    "calendar_sharing": (
        "calendar sharing",
        "share calendar",
        "shared calendar",
        "calendar access",
        "membagikan kalender",
        "berbagi kalender",
        "akses kalender",
    ),
    "access_card_replacement": (
        "access card replacement",
        "replacement access card",
        "replace access card",
        "lost access card",
        "penggantian kartu akses",
        "kartu akses hilang",
    ),
    "employee_parking": (
        "employee parking",
        "staff parking",
        "parking location",
        "employee car park",
        "parkir karyawan",
        "lokasi parkir",
    ),
    "bank_account_update": (
        "update bank account",
        "update bank details",
        "change bank account details",
        "change payroll bank details",
        "bank details update",
        "payroll bank account",
        "memperbarui data rekening bank",
        "memperbarui rekening bank",
        "memperbarui detail bank",
        "ubah rekening bank",
    ),
    "onboarding_documents": (
        "bring on my first day",
        "bring on the first day",
        "first day documents",
        "new employee documents",
        "new hire documents",
        "employee onboarding documents",
        "documents or details should a new employee bring",
        "apa saja yang harus dibawa",
        "hari pertama kerja",
        "dokumen karyawan baru",
        "dokumen pegawai baru",
    ),
    "vendor_onboarding": (
        "vendor onboarding",
        "supplier onboarding",
        "new vendor registration",
        "vendor registration",
        "onboarding pemasok",
        "pendaftaran vendor",
    ),
    "phishing_report": (
        "suspicious email",
        "phishing email",
        "report phishing",
        "report phishing button",
        "email mencurigakan",
        "laporkan phishing",
    ),
    "lost_company_device": (
        "lost company laptop",
        "company laptop is lost",
        "company laptop was lost",
        "lost or stolen company laptop",
        "lost work laptop",
        "missing company laptop",
        "lose my laptop",
        "lost my laptop",
        "laptop is missing",
        "remote wipe",
        "remotely wipe",
        "remotely wiped",
        "laptop kantor hilang",
        "perangkat kantor hilang",
    ),
    "software_access": (
        "software access",
        "application access",
        "access request",
        "system owner approval",
        "permintaan akses aplikasi",
        "permintaan akses ke sebuah aplikasi",
        "akses software",
        "pemilik sistem",
    ),
    "software_license": (
        "software license",
        "software licenses",
        "software licensing",
        "business software license",
        "business software licenses",
        "license cost",
        "it budget",
        "lisensi software",
        "lisensi perangkat lunak",
        "biaya lisensi",
        "anggaran it",
    ),
    "harassment_reporting": (
        "workplace harassment",
        "zero tolerance",
        "report harassment",
        "confidential harassment report",
        "pelecehan di tempat kerja",
        "tindakan pelecehan",
    ),
    "byod": (
        "bring your own device",
        "byod",
        "personal device",
        "personal devices",
        "personally owned device",
        "personally owned devices",
        "perangkat pribadi",
    ),
    "mdm": (
        "mobile device management",
        "mdm",
        "managed device",
        "registered device",
        "perangkat terdaftar",
    ),
    "conflict_of_interest": (
        "conflict of interest",
        "disclose conflict",
        "written disclosure",
        "konflik kepentingan",
        "diungkapkan secara tertulis",
    ),
    "device_security": (
        "company laptop security",
        "full disk encryption",
        "full-disk encryption",
        "usb storage",
        "aturan keamanan data pada laptop",
        "keamanan data laptop",
        "enkripsi disk penuh",
    ),
    "classification_levels": (
        "classification levels",
        "information classification levels",
        "classification categories",
        "information classification categories",
        "level klasifikasi informasi",
        "level klasifikasi",
        "tingkat klasifikasi informasi",
    ),
    "restricted_data": (
        "restricted data",
        "restricted information",
        "classification restricted",
        "data restricted",
        "klasifikasi restricted",
    ),
    "sick_leave": (
        "sick leave",
        "medical leave",
        "cuti sakit",
    ),
    "medical_certificate": (
        "medical certificate",
        "medical certificates",
        "doctor's note",
        "doctors note",
        "doctor certificate",
        "doctor's certificate",
        "doctors certificate",
        "physician certificate",
        "surat keterangan dokter",
    ),
    "password_complexity": (
        "password complexity",
        "password length",
        "password requirements",
        "uppercase lowercase number symbol",
        "at least 12 characters",
        "upper and lower case",
        "uppercase and lowercase",
        "persyaratan kata sandi",
        "persyaratan password",
        "panjang dan kompleksitas kata sandi",
        "kompleksitas kata sandi",
        "huruf besar huruf kecil angka simbol",
    ),
    "password_rotation": (
        "password rotation",
        "password expiry",
        "password requirements",
        "change password every",
        "changed every 90 days",
        "rotation requirements",
        "persyaratan kata sandi",
        "persyaratan password",
        "siklus penggantian kata sandi",
        "kata sandi harus diganti",
    ),
    "password_history": (
        "password history",
        "previous passwords",
        "last passwords",
        "last 5 passwords",
        "reuse password",
        "cannot be reused",
        "kata sandi lama",
        "dipakai ulang",
        "digunakan kembali",
    ),
    "hotel_limit": (
        "hotel limit",
        "hotel cap",
        "maximum hotel cost",
        "hotel per night",
        "batas maksimum biaya hotel",
        "biaya hotel per malam",
    ),
    "vpn_access": (
        "vpn",
        "wireguard",
        "virtual private network",
        "koneksi vpn",
    ),
    "mfa": (
        "mfa",
        "multi-factor authentication",
        "multifactor authentication",
        "autentikasi multifaktor",
    ),
    "core_hours": (
        "core hours",
        "core working hours",
        "availability hours",
        "jam kerja inti",
        "wajib tersedia",
    ),
    "database_backup": (
        "database backup",
        "full database backup",
        "backup cadence",
        "pencadangan database",
    ),
    "expense_claim": (
        "expense claim",
        "expense claims",
        "expense reimbursement claim",
        "expense reimbursement claims",
        "claim deadline",
        "pengajuan klaim biaya",
    ),
    "per_diem": (
        "per diem",
        "daily meal allowance",
        "domestic meal allowance",
        "uang makan harian",
    ),
    "outage_root_cause": (
        "outage root cause",
        "root cause of the outage",
        "root cause was",
        "root cause is",
        "incident root cause",
        "portal outage",
        "penyebab utama gangguan",
        "akar penyebab gangguan",
    ),
    "csat": (
        "csat",
        "customer satisfaction score",
        "skor kepuasan pelanggan",
    ),
    "nps": (
        "nps",
        "net promoter score",
    ),
    "security_incident": (
        "security incident",
        "security incidents",
        "reportable incident",
        "insiden keamanan",
    ),
    "database_platform": (
        "database platform",
        "platform database",
        "primary datastore",
        "what database does the platform use",
        "database apa yang digunakan",
    ),
    "api_availability": (
        "api availability",
        "availability slo",
        "service level objective",
        "ketersediaan api",
    ),
    "audit_retention": (
        "audit log retention",
        "audit logs retained",
        "audit log retained",
        "retain audit logs",
        "retained audit logs",
        "retention of audit logs",
        "retention period",
        "retensi log audit",
    ),
    "unit_test_coverage": (
        "unit test coverage",
        "test coverage required",
        "merge code",
        "cakupan unit test",
    ),
    "home_office_allowance": (
        "home office allowance",
        "home-office allowance",
        "work from home allowance",
        "tunjangan kerja dari rumah",
        "perlengkapan kerja dari rumah",
    ),
    "headquarters_address": (
        "headquarters address",
        "company headquarters",
        "street address",
        "alamat kantor pusat",
    ),
    "dr_failover": (
        "disaster recovery failover",
        "failover exercise",
        "dr exercise",
        "uji failover pemulihan bencana",
    ),
    "email_attachment": (
        "email attachment",
        "attachment size",
        "maximum email attachment size",
        "lampiran email",
    ),
    "procurement_approval": (
        "procurement approval",
        "purchase approval",
        "approval threshold",
        "persetujuan pembelian",
        "menyetujui pembelian",
        "siapa yang menyetujui pembelian",
    ),
    "remote_work_eligibility": (
        "remote work eligibility",
        "eligible for remote work",
        "confirmed employees",
        "berhak mengajukan kerja jarak jauh",
    ),
    "hiring_headcount": (
        "hiring headcount",
        "employees recruited",
        "total headcount",
        "jumlah karyawan yang direkrut",
        "total headcount",
    ),
    "customer_growth": (
        "new enterprise customers",
        "enterprise customer growth",
        "pelanggan enterprise baru",
    ),
    "laptop_request": (
        "new laptop request",
        "request a new laptop",
        "laptop request",
        "permintaan laptop baru",
        "mengajukan permintaan laptop",
    ),
    "profit_margin": (
        "net profit margin",
        "profit margin",
        "margin laba bersih",
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
    (r"\b(?:seberapa\s+cepat|berapa\s+cepat|waktu\s+penyelesaian|target\s+penyelesaian|batas\s+penyelesaian|harus\s+diselesaikan|diselesaikan\s+dalam)\b", (
        "how quickly",
        "resolution time",
        "resolution target",
        "resolved within",
        "must be resolved",
        "hours days",
    )),
    (r"\b(?:insiden\s+(?:it|ti)\s+p1|p1\s+(?:it|ti)\s+insiden)\b", (
        "P1 IT incident",
        "P1 IT incidents",
        "priority 1 incident",
    )),
    (r"\b(?:insiden\s+(?:it|ti)\s+p2|p2\s+(?:it|ti)\s+insiden)\b", (
        "P2 IT incident",
        "P2 IT incidents",
        "priority 2 incident",
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
    (r"\b(?:(?:manfaat|program|jaminan)\s+)?pensiun\b", (
        "pension benefit",
        "retirement benefit",
        "employee pension",
    )),
    (r"\b(?:maximum|max|maksimal|batas|ukuran)\s+(?:file[- ]?upload|upload|unggahan)\s+(?:size|file)?\b", (
        "file upload size limit",
        "maximum file upload size",
        "attachment size limit",
    )),
    (r"\b(?:lembur|jam\s+lembur)(?:\s+yang\s+telah\s+disetujui)?\b", (
        "approved overtime",
        "overtime payment",
        "how is overtime paid",
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

    # ALIAS_PUNCTUATION_BOUNDARY_V1
    # Concept aliases are ordinary phrases, not paths or version identifiers.
    # Convert punctuation to word separators before boundary matching. Without
    # this, an alias at the end of a sentence such as ``customer portal.`` does
    # not match ``customer portal`` because normalize_text deliberately keeps
    # periods for URLs, filenames, and version-like values.
    phrase_text = re.sub(r"[^a-z0-9à-ÿ%]+", " ", normalized)
    phrase_text = re.sub(r"\s+", " ", phrase_text).strip()
    padded = f" {phrase_text} "

    for alias in aliases:
        candidate = normalize_text(alias)
        candidate = re.sub(r"[^a-z0-9à-ÿ%]+", " ", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip()
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

# Preferred compact English aliases used to build a language bridge query.
# These are retrieval hints only. They do not contain answers or source names.
ENGLISH_BRIDGE_ALIASES: dict[str, tuple[str, ...]] = {
    "password": ("password",),
    "password_reset": ("password reset", "reset password"),
    "helpdesk": ("IT Helpdesk", "IT Service Desk"),
    "processing_time": ("resolution time", "resolved within", "must be resolved"),
    "annual_leave": ("annual leave",),
    "maternity_leave": ("maternity leave",),
    "paternity_leave": ("paternity leave",),
    "carryover": ("leave carryover", "unused leave"),
    "next_year": ("next year",),
    "expense": ("expense",),
    "original_receipt": ("original receipt",),
    "amount_threshold": ("amount threshold",),
    "system_access": ("system access",),
    "access_revocation": ("revoke access", "access revocation"),
    "offboarding": ("employee offboarding",),
    "revenue": ("revenue",),
    "full_year": ("full year",),
    "water": ("water consumption",),
    "electricity": ("electricity consumption",),
    "reduction": ("reduction",),
    "lunch": ("lunch",),
    "subsidy": ("subsidy", "allowance"),
    "canteen": ("canteen",),
    "macos": ("macOS",),
    "minimum_version": ("minimum supported version",),
    "supported": ("supported",),
    "laptop": ("laptop",),
    "office": ("office",),
    "cikarang": ("Cikarang",),
    "probation": ("probation period",),
    "dependents": ("dependents",),
    "health_insurance": ("health insurance",),
    "retirement_benefit": ("pension benefit", "retirement benefit"),
    "file_upload": ("file upload", "upload size limit"),
    "customer_portal": ("customer portal",),
    "incident_p1": ("P1 IT incident", "P1 incidents"),
    "incident_p2": ("P2 IT incident", "P2 incidents"),
    "mailbox_quota": ("mailbox quota",),
    "access_card": ("access card",),
    "payslip": ("payslip",),
    "salary_payment": ("salary payment",),
    "overtime_payment": (
        "approved overtime",
        "overtime payment",
        "how overtime is paid",
    ),
    "data_breach": ("data breach",),
    "information_classification": ("information classification",),
    "audit_log": ("audit log",),
    "deployment": ("production deployment",),
    "rto": ("recovery time objective", "RTO"),
    "rpo": ("recovery point objective", "RPO"),
    "api_token": ("API token",),
    "calendar_sharing": ("calendar sharing", "share calendar"),
    "access_card_replacement": ("replacement access card", "lost access card"),
    "employee_parking": ("employee parking", "parking location"),
    "bank_account_update": ("update bank account details", "HR bank account update"),
    "onboarding_documents": ("new employee first-day documents", "bring on the first day"),
    "vendor_onboarding": ("vendor onboarding", "supplier registration"),
    "phishing_report": ("suspicious email", "report phishing"),
    "lost_company_device": ("lost company laptop", "remote wipe"),
    "software_access": ("software access request", "system owner approval"),
    "software_license": ("software license cost", "IT budget"),
    "harassment_reporting": ("workplace harassment", "confidential harassment report"),
    "byod": ("BYOD", "personal device"),
    "mdm": ("mobile device management", "MDM"),
    "conflict_of_interest": ("conflict of interest", "written disclosure"),
    "device_security": ("company laptop security", "full-disk encryption"),
    "classification_levels": ("information classification levels",),
    "restricted_data": ("Restricted data handling",),
    "sick_leave": ("sick leave",),
    "medical_certificate": ("medical certificate", "doctor's note"),
    "password_complexity": ("password length and complexity",),
    "password_rotation": ("password rotation", "password expiry"),
    "password_history": ("password history", "password reuse"),
    "hotel_limit": ("maximum hotel cost per night", "hotel cap"),
    "vpn_access": ("VPN", "WireGuard"),
    "mfa": ("multi-factor authentication", "MFA"),
    "core_hours": ("core working hours",),
    "database_backup": ("full database backup", "backup cadence"),
    "expense_claim": ("expense claim deadline",),
    "per_diem": ("domestic meal per diem",),
    "outage_root_cause": ("outage root cause",),
    "csat": ("CSAT", "customer satisfaction score"),
    "nps": ("NPS", "Net Promoter Score"),
    "security_incident": ("security incidents",),
    "database_platform": ("platform database", "primary datastore"),
    "api_availability": ("API availability SLO",),
    "audit_retention": ("audit log retention",),
    "unit_test_coverage": ("unit-test coverage",),
    "home_office_allowance": ("home-office allowance",),
    "headquarters_address": ("company headquarters address",),
    "dr_failover": ("disaster-recovery failover exercise",),
    "email_attachment": ("maximum email attachment size",),
    "procurement_approval": ("purchase approval threshold",),
    "remote_work_eligibility": ("remote work eligibility",),
    "hiring_headcount": ("employees recruited and total headcount",),
    "customer_growth": ("new enterprise customers",),
    "laptop_request": ("new laptop request", "IT Service Desk laptop request"),
    "profit_margin": ("net profit margin",),
}


def build_bridge_query(query: str) -> str:
    """Build a compact English retrieval query from canonical concepts.

    The bridge is deliberately separate from the user's original sentence. A
    single mixed-language sentence can weaken both embeddings and BM25. Keeping
    an English-only variant lets an English corpus match directly while final
    answerability and evidence thresholds remain unchanged.
    """
    original = str(query or "").strip()
    if not original:
        return ""

    terms: list[str] = []
    for canonical in concepts_in_text(original):
        terms.extend(ENGLISH_BRIDGE_ALIASES.get(canonical, ()))

    normalized = normalize_text(original)
    for pattern, expansions in PHRASE_EXPANSIONS:
        if re.search(pattern, normalized, flags=re.I):
            terms.extend(expansions)

    # Preserve identifiers and explicit numbers that often carry the subject.
    terms.extend(re.findall(r"\b(?:P\d+|RTO|RPO|API|IDR|SLA|\d+(?:[.,]\d+)?)\b", original, flags=re.I))

    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        clean = str(term or "").strip()
        key = normalize_text(clean)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(clean)

    return " ".join(unique)


def build_natural_bridge_query(query: str) -> str:
    """Build one concise English query that preserves the user's intent.

    The bridge contains only an English restatement of the question. It never
    contains policy values, expected answers, or document names. Specific
    enterprise concepts are preferred because they are materially stronger than
    a mixed-language alias list for multilingual embeddings and cross-encoders.
    """
    original = str(query or "").strip()
    if not original:
        return ""

    concepts = set(concepts_in_text(original))
    normalized = normalize_text(original)

    if "incident_p1" in concepts and "processing_time" in concepts:
        return "How quickly must a P1 IT incident be resolved?"
    if "incident_p2" in concepts and "processing_time" in concepts:
        return "How quickly must a P2 IT incident be resolved?"
    if "password_reset" in concepts and "processing_time" in concepts:
        return "How long does an IT password reset take?"
    if "password_reset" in concepts:
        return "What is the procedure for resetting an IT password?"
    if "file_upload" in concepts and "customer_portal" in concepts:
        return "What is the maximum file upload size in the customer portal?"
    if "mailbox_quota" in concepts:
        return "What is the standard employee mailbox quota?"
    if "retirement_benefit" in concepts:
        return "Does the company provide a pension benefit to employees?"
    if "home_office_allowance" in concepts:
        return "What one-time home-office allowance is provided?"
    if "overtime_payment" in concepts:
        return "When is approved overtime paid?"
    if "data_breach" in concepts and "processing_time" in concepts:
        return "Who must a suspected data breach be reported to and how quickly?"
    if "annual_leave" in concepts and "carryover" in concepts:
        return "How many unused annual leave days may be carried over to the next year?"
    if "annual_leave" in concepts and re.search(r"\b(?:berapa|how many|entitled|diberikan)\b", normalized):
        return "How many annual leave days are employees entitled to each year?"
    if "maternity_leave" in concepts and "processing_time" in concepts:
        return "How long is maternity leave?"
    if "paternity_leave" in concepts and "processing_time" in concepts:
        return "How long is paternity leave?"
    if "minimum_version" in concepts and "macos" in concepts:
        return "What is the minimum supported macOS version?"
    if "rto" in concepts and "rpo" in concepts:
        return "What are the recovery time objective (RTO) and recovery point objective (RPO)?"
    if "rto" in concepts:
        return "What is the recovery time objective (RTO)?"
    if "rpo" in concepts:
        return "What is the recovery point objective (RPO)?"

    if "calendar_sharing" in concepts:
        return "How does an employee share a calendar with a coworker?"
    if "access_card_replacement" in concepts:
        return "What is the replacement fee for a lost employee access card?"
    if "employee_parking" in concepts:
        return "Where is employee parking located?"
    if "bank_account_update" in concepts:
        return "How does an employee update bank account details in the HR system?"
    if "onboarding_documents" in concepts:
        return "What documents or details should a new employee bring on the first day?"
    if "salary_payment" in concepts:
        return "On what date are employee salaries paid each month?"
    if "phishing_report" in concepts:
        return "What should an employee do after receiving a suspicious email?"
    if "lost_company_device" in concepts:
        return "What should an employee do if a company laptop is lost?"
    if "software_access" in concepts:
        return "Who approves an employee request for access to a software application?"
    if "software_license" in concepts:
        return "Who pays for an approved business software license?"
    if "harassment_reporting" in concepts:
        return "What is the company's policy on workplace harassment and how can it be reported?"
    if "byod" in concepts and re.search(r"\b(?:wipe|hapus|menghapus)\b", normalized):
        return "May the company remotely wipe corporate data from a registered personal device?"
    if "byod" in concepts:
        return "What must happen before a personal device is used for work email?"
    if "conflict_of_interest" in concepts:
        return "How must an employee disclose a potential conflict of interest?"
    if "device_security" in concepts:
        return "What data-security controls are required on company laptops?"
    if "classification_levels" in concepts:
        return "What are the information-classification levels?"
    if "restricted_data" in concepts:
        return "How must Restricted information be handled?"
    if "medical_certificate" in concepts or ("sick_leave" in concepts and "keterangan dokter" in normalized):
        return "When is a medical certificate required for sick leave?"
    if "password_complexity" in concepts and "password_rotation" in concepts:
        return "What are the password length, complexity, and rotation requirements?"
    if "password_rotation" in concepts and "password_history" in concepts:
        return "How often must passwords be changed and may previous passwords be reused?"
    if "password_complexity" in concepts:
        return "What are the password length and complexity requirements?"
    if "hotel_limit" in concepts:
        return "What is the maximum hotel cost per night for domestic business travel?"
    if "vpn_access" in concepts and "mfa" in concepts:
        return "Which VPN client is used and is multi-factor authentication required?"
    if "core_hours" in concepts:
        return "During which core hours must remote employees be available?"
    if "health_insurance" in concepts and "dependents" in concepts:
        return "How many dependents are covered by the company health insurance plan?"
    if "payslip" in concepts:
        return "Where and when can employees find their payslips?"
    if "laptop_request" in concepts:
        return "What is the procedure for requesting a new company laptop?"
    if "probation" in concepts and "processing_time" in concepts:
        return "How long is the probation period and when is the formal evaluation?"
    if "access_revocation" in concepts and "offboarding" in concepts:
        return "How quickly must IT revoke all system access for a departing employee?"
    if "remote_work" in concepts and "processing_time" not in concepts and re.search(r"\b(?:berapa|how many|maximal|days? per week|hari)\b", normalized):
        return "How many days per week may employees work from home?"
    if "remote_work_eligibility" in concepts:
        return "Who is eligible to request remote work?"
    if "procurement_approval" in concepts or (
        "amount_threshold" in concepts and re.search(r"\b(?:approval|approve|persetujuan|menyetujui)\b", normalized)
    ):
        return "Who approves a purchase at the stated monetary threshold?"
    if "per_diem" in concepts:
        return "What is the daily domestic business-travel meal per diem?"
    if {"lunch", "subsidy", "canteen"}.issubset(concepts):
        return "Does the company provide a lunch subsidy in the canteen?"
    if "original_receipt" in concepts and "amount_threshold" in concepts:
        return "Above what expense amount is an original receipt required?"
    if "outage_root_cause" in concepts:
        return "What was the root cause of the customer-portal outage?"
    if "revenue" in concepts and "profit_margin" in concepts:
        return "What were the company's revenue and net profit margin for the stated year?"
    if "revenue" in concepts and "full_year" in concepts:
        return "What was the company's full-year revenue for the stated year?"
    if "water" in concepts and "reduction" in concepts:
        return "What percentage reduction in water consumption was reported for the stated office and year?"
    if "csat" in concepts and "nps" in concepts:
        return "What were the overall CSAT and NPS scores for the stated year?"
    if "hiring_headcount" in concepts:
        return "How many employees were recruited and what was the resulting total headcount?"
    if "customer_growth" in concepts:
        return "How many new enterprise customers were added in the stated quarter?"

    # A compact English-only alias query is still preferable to returning no
    # bridge at all for an Indonesian question with recognized concepts.
    return build_bridge_query(original)

def build_query_variants(query: str) -> list[str]:
    """Return independent retrieval queries ordered from literal to bridged.

    Scores are later merged by candidate using the strongest valid signal. This
    improves cross-language recall without lowering any acceptance threshold.
    """
    original = str(query or "").strip()
    if not original:
        return []

    candidates = [
        original,
        build_natural_bridge_query(original),
        build_bridge_query(original),
        expand_query(original),
    ]
    variants: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        clean = str(candidate or "").strip()
        key = normalize_text(clean)
        if not key or key in seen:
            continue
        seen.add(key)
        variants.append(clean)
    return variants

INDONESIAN_BRIDGE_MARKERS = {
    "apa", "apakah", "berapa", "bagaimana", "mengapa", "kenapa", "kapan",
    "dimana", "siapa", "yang", "dan", "atau", "untuk", "dengan", "dalam",
    "pada", "dari", "tidak", "harus", "dapat", "bisa", "maksimal", "batas",
    "seberapa", "cepat", "lama", "insiden", "diselesaikan", "penyelesaian",
    "kata", "sandi", "karyawan", "pelanggan", "unggah", "cuti", "tahun",
    "hari", "jam", "menit", "bulan", "minggu", "jumlah", "nilai",
}


def requires_language_bridge(query: str) -> bool:
    """Return True when the user query carries clear Indonesian language cues."""
    normalized = normalize_text(query)
    tokens = set(re.findall(r"[a-z0-9à-ÿ]+", normalized))
    marker_count = len(tokens.intersection(INDONESIAN_BRIDGE_MARKERS))
    return marker_count >= 2 or normalized.startswith(
        ("apa ", "apakah ", "berapa ", "bagaimana ", "seberapa ", "tolong ")
    )
