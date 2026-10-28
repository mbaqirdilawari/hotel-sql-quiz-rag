"""Tests for turning the live schema into vector database documents."""

from rag.knowledge import FEW_SHOT_EXAMPLES, build_documents, schema_documents

QUIZ_QUESTIONS = [
    "List the name and city of every 5-star hotel.",
    "How many hotels are there in each city? Show the city with the most hotels first.",
    "Which hotel earned the most money from bookings?",
]

FAKE_SCHEMA = {
    "columns": {
        "hotels": [{"name": "hotel_id", "type": "integer", "nullable": False},
                   {"name": "city", "type": "text", "nullable": False}],
        "rooms": [{"name": "room_id", "type": "integer", "nullable": False},
                  {"name": "hotel_id", "type": "integer", "nullable": False}],
        "bookings": [{"name": "booking_id", "type": "integer", "nullable": False},
                     {"name": "room_id", "type": "integer", "nullable": False}],
    },
    "primary_keys": {"hotels": "hotel_id", "rooms": "room_id", "bookings": "booking_id"},
    "foreign_keys": [
        {"table": "rooms", "column": "hotel_id", "ref_table": "hotels", "ref_column": "hotel_id"},
        {"table": "bookings", "column": "room_id", "ref_table": "rooms", "ref_column": "room_id"},
    ],
    "facts": {
        "cities": ["Hunza", "Lahore"],
        "room_types": ["Deluxe", "Standard"],
        "stars": (2, 5),
        "dates": ("2026-09-01", "2026-12-31"),
        "prices": (40, 500),
        "counts": (8, 25, 40),
    },
}


def test_schema_documents_mark_keys():
    docs = {d["id"]: d["text"] for d in schema_documents(FAKE_SCHEMA)}
    assert "hotel_id (integer, primary key)" in docs["schema_hotels"]
    assert "foreign key to hotels.hotel_id" in docs["schema_rooms"]
    assert "bookings.room_id references rooms.room_id" in docs["schema_relationships"]


def test_all_three_kinds_are_present_with_unique_ids():
    docs = build_documents(FAKE_SCHEMA)
    kinds = {d["kind"] for d in docs}
    assert kinds == {"schema", "semantics", "example"}
    ids = [d["id"] for d in docs]
    assert len(ids) == len(set(ids))


def test_live_facts_use_real_values():
    text = " ".join(d["text"] for d in build_documents(FAKE_SCHEMA))
    assert "'Hunza'" in text and "'Deluxe'" in text


def test_examples_are_not_copies_of_quiz_questions():
    example_questions = {q.lower() for q, _ in FEW_SHOT_EXAMPLES}
    for quiz in QUIZ_QUESTIONS:
        assert quiz.lower() not in example_questions
