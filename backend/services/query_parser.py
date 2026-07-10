"""
services/query_parser.py — Natural language query parser for search.
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


def _parse_price_value(value_str: str) -> float | None:
    """Convert price strings to float rupees."""
    value_str = value_str.strip().replace(',', '')
    try:
        if value_str.lower().endswith('k'):
            return float(value_str[:-1]) * 1000
        return float(value_str)
    except ValueError:
        return None


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
        'max'  # treat as max
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

_CLEANUP_WORDS = re.compile(
    r'\b(?:under|below|above|over|between|from|and|to|less|than|more|'
    r'min|max|minimum|maximum|upto|atleast|within|cheap|cheapest|'
    r'affordable|budget|expensive|price|cost)\b',
    re.IGNORECASE
)


def parse_query(raw: str) -> ParsedQuery:
    """Parse a natural language search query into structured filters."""
    text = raw.strip()
    min_price = None
    max_price = None
    available = None
    store = None

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

        break

    match = _AVAILABILITY_PATTERN.search(text)
    if match:
        available = True
        text = text[:match.start()] + text[match.end():]

    for pattern, store_name in _STORE_PATTERNS:
        match = pattern.search(text)
        if match:
            store = store_name
            text = text[:match.start()] + text[match.end():]
            break

    if min_price is not None or max_price is not None:
        text = _CLEANUP_WORDS.sub(' ', text)

    text = re.sub(r'\s+', ' ', text).strip()

    if not text:
        text = raw.strip()

    return ParsedQuery(
        q=text,
        min_price=min_price,
        max_price=max_price,
        available=available,
        store=store,
    )
