"""
api/query_parser.py — Natural language query parser for search.

Extracts structured filters from free-text queries before search runs.

Examples:
  "jordan 1 under 10k"         → {q: "jordan 1", max_price: 10000}
  "nike dunk below 15000"      → {q: "nike dunk", max_price: 15000}
  "yeezy available"            → {q: "yeezy", available: True}
  "adidas samba on hypefly"    → {q: "adidas samba", store: "hypefly"}
  "jordan 1 between 5k and 15k"→ {q: "jordan 1", min_price: 5000, max_price: 15000}

Design principles:
  1. Non-destructive — if parser extracts nothing, original query is unchanged
  2. Explicit filters win — if user set filters via UI, parser is skipped
  3. Regex only — deterministic, zero latency, no external dependencies
  4. Clean remaining query — after extracting filters, remove matched tokens
     so MongoDB doesn't try to match "under", "10k", "available" as words
"""

import re
from dataclasses import dataclass


@dataclass
class ParsedQuery:
    q: str                    # cleaned search text
    min_price: float | None = None
    max_price: float | None = None
    available: bool | None = None
    store: str | None = None

    def has_extracted_anything(self) -> bool:
        return any([
            self.min_price is not None,
            self.max_price is not None,
            self.available is not None,
            self.store is not None,
        ])


# ── Price normalization ────────────────────────────────────────────────────────

def _parse_price_value(value_str: str) -> float | None:
    """
    Convert price strings to float rupees.

    "10k"    → 10000.0
    "10K"    → 10000.0
    "10000"  → 10000.0
    "10,000" → 10000.0
    "10.5k"  → 10500.0
    """
    value_str = value_str.strip().replace(',', '')
    try:
        if value_str.lower().endswith('k'):
            return float(value_str[:-1]) * 1000
        return float(value_str)
    except ValueError:
        return None


# ── Regex patterns ────────────────────────────────────────────────────────────
# Each pattern is a tuple of (regex, handler_function)
# Patterns are applied in order — more specific patterns first

# Price value pattern: matches "10k", "10000", "10,000", "10.5k"
_PRICE_VAL = r'(\d+(?:[.,]\d+)?(?:k|K)?)'

_PRICE_PATTERNS = [
    # "between 5k and 15k" / "between 5k-15k"
    (
        re.compile(
            rf'\b(?:between|from)\s+{_PRICE_VAL}\s*(?:and|to|-)\s*{_PRICE_VAL}\b',
            re.IGNORECASE
        ),
        'between'
    ),
    # "under 10k" / "below 10k" / "less than 10k" / "upto 10k" / "max 10k"
    (
        re.compile(
            rf'\b(?:under|below|less\s+than|upto|up\s+to|max|maximum|within)\s+{_PRICE_VAL}\b',
            re.IGNORECASE
        ),
        'max'
    ),
    # "above 5k" / "over 5k" / "more than 5k" / "min 5k" / "atleast 5k"
    (
        re.compile(
            rf'\b(?:above|over|more\s+than|min|minimum|atleast|at\s+least)\s+{_PRICE_VAL}\b',
            re.IGNORECASE
        ),
        'min'
    ),
    # Trailing price with rupee sign: "₹10000", "rs 10000", "inr 10000"
    (
        re.compile(
            rf'(?:₹|rs\.?\s*|inr\s*){_PRICE_VAL}',
            re.IGNORECASE
        ),
        'max'  # bare price with currency = treat as max
    ),
]

_AVAILABILITY_PATTERN = re.compile(
    r'\b(?:available|in[\s-]?stock|in\s+stock|only\s+available|instock)\b',
    re.IGNORECASE
)

_STORE_PATTERNS = [
    (re.compile(r'\b(?:on|from|at)\s+hypefly\b', re.IGNORECASE), 'hypefly'),
    (re.compile(r'\b(?:on|from|at)\s+mainstreet\b', re.IGNORECASE), 'mainstreet'),
    (re.compile(r'\bhypefly\b', re.IGNORECASE), 'hypefly'),
    (re.compile(r'\bmainstreet\b', re.IGNORECASE), 'mainstreet'),
]

# Words to strip from the remaining query after extraction
_CLEANUP_WORDS = re.compile(
    r'\b(?:under|below|above|over|between|from|and|to|less|than|more|'
    r'min|max|minimum|maximum|upto|atleast|within|cheap|cheapest|'
    r'affordable|budget|expensive|price|cost)\b',
    re.IGNORECASE
)


def parse_query(raw: str) -> ParsedQuery:
    """
    Parse a natural language search query into structured filters.

    Returns a ParsedQuery with:
      - q: cleaned search text (filters removed)
      - min_price, max_price, available, store: extracted filters

    If nothing is extracted, q equals the original input.
    """
    text = raw.strip()
    min_price = None
    max_price = None
    available = None
    store = None

    # ── Price extraction ───────────────────────────────────────────────────────
    for pattern, kind in _PRICE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        if kind == 'between':
            v1 = _parse_price_value(match.group(1))
            v2 = _parse_price_value(match.group(2))
            if v1 is not None and v2 is not None:
                min_price = min(v1, v2)
                max_price = max(v1, v2)
            text = text[:match.start()] + text[match.end():]

        elif kind == 'max':
            v = _parse_price_value(match.group(1))
            if v is not None:
                max_price = v
            text = text[:match.start()] + text[match.end():]

        elif kind == 'min':
            v = _parse_price_value(match.group(1))
            if v is not None:
                min_price = v
            text = text[:match.start()] + text[match.end():]

        # Only match the first price pattern found
        break

    # ── Availability extraction ────────────────────────────────────────────────
    match = _AVAILABILITY_PATTERN.search(text)
    if match:
        available = True
        text = text[:match.start()] + text[match.end():]

    # ── Store extraction ───────────────────────────────────────────────────────
    for pattern, store_name in _STORE_PATTERNS:
        match = pattern.search(text)
        if match:
            store = store_name
            text = text[:match.start()] + text[match.end():]
            break

    # ── Clean up remaining query ───────────────────────────────────────────────
    # Remove leftover filter words that would pollute the text search
    if min_price is not None or max_price is not None:
        text = _CLEANUP_WORDS.sub(' ', text)

    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # If cleaning left nothing meaningful, keep original
    if not text:
        text = raw.strip()

    return ParsedQuery(
        q=text,
        min_price=min_price,
        max_price=max_price,
        available=available,
        store=store,
    )