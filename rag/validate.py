"""Compare the result of the AI's SQL with the expected answer.

Two results count as the same when they contain the same rows, ignoring:
* row order (unless both are a single row anyway),
* column names (the AI may call a column total or total_revenue),
* small number formatting differences (7070 equals 7070.00),
* column order inside a row, as a second, looser check.
"""

import datetime
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def _normalize_value(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value).strip()


def _normalize_rows(rows):
    return [tuple(_normalize_value(v) for v in row) for row in rows]


def _sort_key(value):
    return (value is None, str(type(value)), str(value))


def compare_results(actual_rows, expected_rows):
    """Return (is_correct, explanation)."""
    actual = _normalize_rows(actual_rows)
    expected = _normalize_rows(expected_rows)

    if Counter(actual) == Counter(expected):
        return True, f"Same {len(expected)} row(s) as the expected answer."

    loose_actual = Counter(tuple(sorted(r, key=_sort_key)) for r in actual)
    loose_expected = Counter(tuple(sorted(r, key=_sort_key)) for r in expected)
    if loose_actual == loose_expected:
        return True, "Same rows as the expected answer (columns in a different order)."

    if len(actual) != len(expected):
        return False, f"Returned {len(actual)} row(s), but the expected answer has {len(expected)}."
    width_a = {len(r) for r in actual}
    width_e = {len(r) for r in expected}
    if width_a != width_e:
        return False, "Returned a different number of columns from the expected answer."
    return False, "Same number of rows, but the values are different from the expected answer."
