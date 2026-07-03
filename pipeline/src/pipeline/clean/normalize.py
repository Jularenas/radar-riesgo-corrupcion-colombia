"""
NIT and name normalization utilities.

NIT (Número de Identificación Tributaria) rules (Colombia):
  - 9 digits + 1 verification digit (written with hyphen: 900.123.456-7)
  - Cédulas (personal ID) are 6–10 digits
  - For NITs starting with 8 or 9 AND exactly 10 digits long → last digit is
    the verification digit; nit_base = first 9 digits.
  - Otherwise (cédulas, short IDs) → nit_base = doc_norm itself.

Name normalization:
  - Upper-case, strip accents, collapse whitespace.
  - Strip trailing legal suffixes: S.A.S, S.A., LTDA, E.U., S EN C, etc.
"""

import re
import unicodedata

# Legal suffixes to strip (order matters — longest first)
_LEGAL_SUFFIXES = [
    r"S\.?\s*A\.?\s*S\.?",          # SAS / S.A.S.
    r"S\.?\s*A\.?",                  # SA / S.A.
    r"S\s+EN\s+C\.?\s*S?\.?",       # S EN C / S EN CS
    r"S\s+EN\s+C\.?",               # S EN C
    r"LTDA\.?",                      # LTDA
    r"E\.?\s*U\.?",                  # EU / E.U.
    r"S\.?\s*C\.?\s*S?\.?",         # SCS
    r"E\.?\s*S\.?\s*E\.?",          # ESE
    r"E\.?\s*P\.?\s*S\.?",          # EPS
    r"S\.?\s*P\.?\s*S\.?",          # SPS
    r"I\.?\s*P\.?\s*S\.?",          # IPS
]
_SUFFIX_RE = re.compile(
    r"[\s,]+(?:" + "|".join(_LEGAL_SUFFIXES) + r")[\s.]*$",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def strip_accents(s: str) -> str:
    """Decompose unicode and strip combining diacritical marks."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def normalize_name(raw: str | None) -> str | None:
    """
    Normalize a company/person name for deduplication and matching.

    Steps:
      1. Strip whitespace.
      2. Upper-case.
      3. Strip accents.
      4. Collapse internal whitespace.
      5. Remove trailing legal suffixes.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    s = s.upper()
    s = strip_accents(s)
    s = _WHITESPACE_RE.sub(" ", s)
    s = _SUFFIX_RE.sub("", s).strip()
    return s or None


def normalize_doc(raw: str | None) -> dict:
    """
    Normalize a document number (NIT or cédula).

    Returns a dict with:
      - doc_raw:  original string
      - doc_norm: digits only
      - nit_base: first 9 digits if 10-digit NIT starting with 8/9,
                  else same as doc_norm (None if empty)

    Heuristic for persona natural:
      - doc_norm length ≤ 10 AND NOT (starts with 8 or 9 AND length == 10):
        likely cédula → persona natural
      - length == 10 AND starts with 8 or 9: likely NIT (empresa)
      - length == 9 AND starts with 8 or 9: likely NIT without check digit
    """
    doc_raw = raw
    if raw is None:
        return {"doc_raw": None, "doc_norm": None, "nit_base": None}
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return {"doc_raw": doc_raw, "doc_norm": None, "nit_base": None}

    doc_norm = digits
    # 10-digit starting with 8 or 9 → NIT with check digit
    if len(digits) == 10 and digits[0] in ("8", "9"):
        nit_base = digits[:9]
    else:
        nit_base = doc_norm

    return {"doc_raw": doc_raw, "doc_norm": doc_norm, "nit_base": nit_base}


def is_persona_natural(doc_norm: str | None) -> bool | None:
    """
    Heuristic: is this document number a cédula (natural person) vs NIT (entity)?

    Rules (documented, imperfect):
      - None → None (unknown)
      - 1–7 digits: likely old/foreign ID → natural person
      - 8 digits: likely old cédula → natural person
      - 9 digits starting 8 or 9: likely NIT sin dígito verificación → entity
      - 10 digits starting 8 or 9: NIT with check digit → entity
      - 10 digits starting 1: cédula (newer format) → natural person
      - All other: unknown → None
    """
    if not doc_norm:
        return None
    n = len(doc_norm)
    if n <= 8:
        return True
    if n == 9 and doc_norm[0] in ("8", "9"):
        return False  # entity NIT (no check digit)
    if n == 10 and doc_norm[0] in ("8", "9"):
        return False  # entity NIT with check digit
    if n == 10 and doc_norm[0] == "1":
        return True   # cédula ciudadanía (newer)
    return None  # ambiguous


def normalize_dpto_name(raw: str | None) -> str | None:
    """
    Normalize department name for DIVIPOLA join.
    Upper-case, strip accents, trim.
    """
    if raw is None:
        return None
    s = raw.strip().upper()
    s = strip_accents(s)
    s = _WHITESPACE_RE.sub(" ", s)
    # Handle known aliases
    _ALIASES = {
        "DISTRITO CAPITAL DE BOGOTA": "BOGOTA, D.C.",
        "BOGOTA D.C.": "BOGOTA, D.C.",
        "BOGOTA DC": "BOGOTA, D.C.",
        "BOGOTA": "BOGOTA, D.C.",
        "D.C.": "BOGOTA, D.C.",
        "SAN ANDRES": "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA",
        "SAN ANDRES, PROVIDENCIA Y SANTA CATALINA":
            "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA",
    }
    return _ALIASES.get(s, s)
