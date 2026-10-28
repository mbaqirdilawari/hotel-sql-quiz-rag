"""Tests for prompt building and SQL extraction (no API call is made)."""

from rag.llm import build_prompt, extract_sql

RETRIEVED = [
    {"id": "schema_hotels", "kind": "schema", "text": "Table hotels ...", "similarity": 0.8},
    {"id": "rule_revenue", "kind": "semantics", "text": "Business rule: revenue ...", "similarity": 0.7},
    {"id": "example_01", "kind": "example", "text": "Example question: ...", "similarity": 0.6},
]


def test_prompt_contains_retrieved_context_and_question():
    prompt = build_prompt("Which hotel earned the most?", RETRIEVED)
    assert "Table hotels" in prompt
    assert "Business rule: revenue" in prompt
    assert "Example question" in prompt
    assert prompt.index("Retrieved context") < prompt.index("Which hotel earned the most?")


def test_extract_sql_from_code_block():
    reply = "Here you go:\n```sql\nSELECT * FROM hotels\n```\nDone."
    assert extract_sql(reply) == "SELECT * FROM hotels;"


def test_extract_sql_without_code_block():
    assert extract_sql("SELECT COUNT(*) FROM bookings;") == "SELECT COUNT(*) FROM bookings;"


def test_extract_sql_empty_reply():
    assert extract_sql("") == ""
