"""Tests for comparing a generated result with the expected answer."""

import datetime
from decimal import Decimal

from rag.validate import compare_results


def test_same_rows_any_order_is_correct():
    expected = [("Lahore", 3), ("Islamabad", 2), ("Karachi", 2), ("Hunza", 1)]
    actual = [("Lahore", 3), ("Karachi", 2), ("Islamabad", 2), ("Hunza", 1)]
    ok, _ = compare_results(actual, expected)
    assert ok


def test_number_formatting_is_ignored():
    ok, _ = compare_results([("Grand Palace", 7070)], [("Grand Palace", Decimal("7070.00"))])
    assert ok


def test_unrounded_average_matches_rounded_expected():
    ok, _ = compare_results([("Deluxe", Decimal("172.5000000"))], [("Deluxe", Decimal("172.50"))])
    assert ok


def test_column_order_is_ignored_in_loose_check():
    ok, why = compare_results([(7070, "Grand Palace")], [("Grand Palace", 7070)])
    assert ok
    assert "different order" in why


def test_wrong_row_count_is_incorrect():
    ok, why = compare_results([("Grand Palace", "Lahore")], [("Grand Palace", "Lahore"), ("Margalla Heights", "Islamabad")])
    assert not ok
    assert "1 row" in why


def test_wrong_values_are_incorrect():
    ok, _ = compare_results([(17,)], [(18,)])
    assert not ok


def test_dates_compare_by_value():
    day = datetime.date(2026, 12, 20)
    ok, _ = compare_results([(day,)], [(datetime.date(2026, 12, 20),)])
    assert ok
