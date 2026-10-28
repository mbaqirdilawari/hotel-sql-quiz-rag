"""The knowledge that goes into the vector database.

Three kinds of documents are stored in ChromaDB:

1. schema   : one document per table plus one for the relationships.
              These are built from the LIVE PostgreSQL catalog
              (information_schema), so they always match the database.
2. semantics: business rules and plain-English meaning of the columns,
              plus live facts read from the data (the real city names,
              room types, date range and price range).
3. example  : few-shot pairs of a natural-language question and its SQL.
              They are deliberately NOT the quiz questions, so the AI has
              to adapt similar patterns rather than copy an answer.
"""

TABLES = ("hotels", "rooms", "bookings")

# Plain-English meaning of every column, shown next to the live data type.
COLUMN_MEANINGS = {
    ("hotels", "hotel_id"): "unique hotel number",
    ("hotels", "hotel_name"): "name of the hotel, for example Grand Palace",
    ("hotels", "city"): "city where the hotel is located",
    ("hotels", "star_rating"): "hotel star rating from 1 to 5 (5 is the most luxurious)",
    ("rooms", "room_id"): "unique room number",
    ("rooms", "hotel_id"): "the hotel this room belongs to (links to hotels.hotel_id)",
    ("rooms", "room_type"): "kind of room: Standard, Deluxe or Suite",
    ("rooms", "nightly_price"): "price of one night in this room, in US dollars",
    ("bookings", "booking_id"): "unique booking number",
    ("bookings", "room_id"): "the room that was booked (links to rooms.room_id)",
    ("bookings", "guest_name"): "full name of the guest who made the booking",
    ("bookings", "check_in_date"): "date the guest arrives",
    ("bookings", "nights"): "length of the stay in nights",
}

BUSINESS_RULES = [
    (
        "rule_revenue",
        "Business rule: revenue. The revenue (money earned) from one booking is "
        "rooms.nightly_price multiplied by bookings.nights. Total revenue for a hotel "
        "or a city is SUM(r.nightly_price * b.nights) after joining bookings to rooms "
        "on room_id and rooms to hotels on hotel_id.",
    ),
    (
        "rule_join_path",
        "Business rule: join path. bookings has no hotel or city column. To find the "
        "hotel, city or star rating of a booking, join bookings b to rooms r ON "
        "b.room_id = r.room_id, then rooms r to hotels h ON r.hotel_id = h.hotel_id. "
        "To find the price or room type of a booking, join bookings to rooms.",
    ),
    (
        "rule_star_rating",
        "Business rule: star rating. 'A 5-star hotel' means star_rating = 5. "
        "'4 stars or more' means star_rating >= 4. Star rating belongs to the hotel, "
        "not to the room.",
    ),
    (
        "rule_prices",
        "Business rule: prices and averages. nightly_price is stored as NUMERIC in "
        "US dollars. When a question asks for an average price, use "
        "ROUND(AVG(nightly_price), 2). 'Most expensive' means the highest "
        "nightly_price and 'cheapest' the lowest.",
    ),
    (
        "rule_stay_length",
        "Business rule: stay length. The length of a stay is bookings.nights. "
        "'Stayed 3 nights or more' or 'at least 3 nights' means nights >= 3. "
        "'Longer than 3 nights' means nights > 3.",
    ),
    (
        "rule_counting",
        "Business rule: counting. 'How many bookings' means COUNT(*) over bookings. "
        "'How many hotels in each city' means GROUP BY city with COUNT(*). When a "
        "question says 'show the most first' or 'highest first', add ORDER BY ... DESC.",
    ),
    (
        "rule_top_one",
        "Business rule: single winners. Questions such as 'Which hotel earned the most' "
        "or 'Which room is the cheapest' want one row: use ORDER BY on the measure "
        "and LIMIT 1.",
    ),
    (
        "rule_explain_query",
        "Business rule: 'What does this query return?' questions. When the question "
        "already contains a SQL query and asks what it returns, answer with that same "
        "query (or an equivalent one) so it can be run to show the result.",
    ),
    (
        "rule_scope",
        "Business rule: scope. Only the tables hotels, rooms and bookings can be "
        "queried. Write PostgreSQL, a single read-only SELECT statement, and never "
        "INSERT, UPDATE, DELETE or DDL.",
    ),
]

FEW_SHOT_EXAMPLES = [
    (
        "List all hotels in Karachi with their star rating.",
        "SELECT hotel_name, star_rating\nFROM hotels\nWHERE city = 'Karachi';",
    ),
    (
        "How many hotels have 4 stars or more?",
        "SELECT COUNT(*) AS hotel_count\nFROM hotels\nWHERE star_rating >= 4;",
    ),
    (
        "How many rooms does each hotel have? Show the hotel with the most rooms first.",
        "SELECT h.hotel_name, COUNT(*) AS room_count\nFROM rooms r\n"
        "JOIN hotels h ON r.hotel_id = h.hotel_id\nGROUP BY h.hotel_name\n"
        "ORDER BY room_count DESC;",
    ),
    (
        "Which guests stayed 5 nights or longer?",
        "SELECT guest_name, nights\nFROM bookings\nWHERE nights >= 5;",
    ),
    (
        "How many bookings were made for Suite rooms?",
        "SELECT COUNT(*) AS suite_bookings\nFROM bookings b\n"
        "JOIN rooms r ON b.room_id = r.room_id\nWHERE r.room_type = 'Suite';",
    ),
    (
        "What is the average nightly price of Deluxe rooms in Islamabad?",
        "SELECT ROUND(AVG(r.nightly_price), 2) AS avg_price\nFROM rooms r\n"
        "JOIN hotels h ON r.hotel_id = h.hotel_id\n"
        "WHERE h.city = 'Islamabad' AND r.room_type = 'Deluxe';",
    ),
    (
        "What is the cheapest room price in each city?",
        "SELECT h.city, MIN(r.nightly_price) AS cheapest_price\nFROM rooms r\n"
        "JOIN hotels h ON r.hotel_id = h.hotel_id\nGROUP BY h.city\nORDER BY h.city;",
    ),
    (
        "What was the total booking revenue in each city?",
        "SELECT h.city, SUM(r.nightly_price * b.nights) AS total_revenue\n"
        "FROM bookings b\nJOIN rooms r ON b.room_id = r.room_id\n"
        "JOIN hotels h ON r.hotel_id = h.hotel_id\nGROUP BY h.city\n"
        "ORDER BY total_revenue DESC;",
    ),
    (
        "Which room type earned the least revenue?",
        "SELECT r.room_type, SUM(r.nightly_price * b.nights) AS total_revenue\n"
        "FROM bookings b\nJOIN rooms r ON b.room_id = r.room_id\n"
        "GROUP BY r.room_type\nORDER BY total_revenue ASC\nLIMIT 1;",
    ),
    (
        "How many bookings check in during December 2026?",
        "SELECT COUNT(*) AS december_bookings\nFROM bookings\n"
        "WHERE check_in_date >= DATE '2026-12-01' AND check_in_date < DATE '2027-01-01';",
    ),
    (
        "Which hotels have never been booked?",
        "SELECT h.hotel_name\nFROM hotels h\nWHERE NOT EXISTS (\n"
        "    SELECT 1 FROM rooms r JOIN bookings b ON b.room_id = r.room_id\n"
        "    WHERE r.hotel_id = h.hotel_id\n);",
    ),
    (
        "What does this query return? SELECT MAX(nights) FROM bookings;",
        "SELECT MAX(nights)\nFROM bookings;",
    ),
]


# ---------------------------------------------------------------------------
# Reading the live database
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
SELECT c.table_name, c.column_name, c.data_type, c.is_nullable
FROM information_schema.columns c
WHERE c.table_schema = 'public' AND c.table_name = ANY(%s)
ORDER BY c.table_name, c.ordinal_position
"""

KEYS_SQL = """
SELECT tc.constraint_type, kcu.table_name, kcu.column_name,
       ccu.table_name AS ref_table, ccu.column_name AS ref_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
  AND kcu.table_name = ANY(%s)
ORDER BY kcu.table_name, kcu.column_name
"""

# Fixed, parameter-free queries that read real values from the data.
LIVE_FACT_QUERIES = {
    "cities": "SELECT DISTINCT city FROM hotels ORDER BY city",
    "room_types": "SELECT DISTINCT room_type FROM rooms ORDER BY room_type",
    "stars": "SELECT MIN(star_rating), MAX(star_rating) FROM hotels",
    "dates": "SELECT MIN(check_in_date), MAX(check_in_date) FROM bookings",
    "prices": "SELECT MIN(nightly_price), MAX(nightly_price) FROM rooms",
    "counts": (
        "SELECT (SELECT COUNT(*) FROM hotels), (SELECT COUNT(*) FROM rooms), "
        "(SELECT COUNT(*) FROM bookings)"
    ),
}


def load_live_schema(conn):
    """Read columns, keys and a few real data facts from PostgreSQL."""
    schema = {"columns": {t: [] for t in TABLES}, "primary_keys": {}, "foreign_keys": []}
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL, (list(TABLES),))
        for table, column, data_type, nullable in cur.fetchall():
            schema["columns"][table].append(
                {"name": column, "type": data_type, "nullable": nullable == "YES"}
            )

        cur.execute(KEYS_SQL, (list(TABLES),))
        for kind, table, column, ref_table, ref_column in cur.fetchall():
            if kind == "PRIMARY KEY":
                schema["primary_keys"][table] = column
            else:
                schema["foreign_keys"].append(
                    {"table": table, "column": column, "ref_table": ref_table, "ref_column": ref_column}
                )

        facts = {}
        for name, sql in LIVE_FACT_QUERIES.items():
            cur.execute(sql)
            rows = cur.fetchall()
            facts[name] = [r[0] for r in rows] if name in ("cities", "room_types") else rows[0]
        schema["facts"] = facts
    return schema


# ---------------------------------------------------------------------------
# Turning the schema into documents
# ---------------------------------------------------------------------------
def schema_documents(schema):
    docs = []
    for table in TABLES:
        lines = [f"Table {table} (PostgreSQL). Columns:"]
        pk = schema["primary_keys"].get(table)
        fks = {f["column"]: f for f in schema["foreign_keys"] if f["table"] == table}
        for col in schema["columns"].get(table, []):
            notes = []
            if col["name"] == pk:
                notes.append("primary key")
            if col["name"] in fks:
                fk = fks[col["name"]]
                notes.append(f"foreign key to {fk['ref_table']}.{fk['ref_column']}")
            meaning = COLUMN_MEANINGS.get((table, col["name"]), "")
            extra = f", {', '.join(notes)}" if notes else ""
            lines.append(f"- {col['name']} ({col['type']}{extra}): {meaning}")
        docs.append({"id": f"schema_{table}", "kind": "schema", "text": "\n".join(lines)})

    rel_lines = ["Relationships between the tables (from the foreign keys):"]
    for fk in schema["foreign_keys"]:
        rel_lines.append(
            f"- {fk['table']}.{fk['column']} references {fk['ref_table']}.{fk['ref_column']}"
        )
    rel_lines.append(
        "So a booking belongs to one room, and a room belongs to one hotel: "
        "bookings -> rooms -> hotels."
    )
    docs.append({"id": "schema_relationships", "kind": "schema", "text": "\n".join(rel_lines)})
    return docs


def live_fact_documents(schema):
    facts = schema.get("facts", {})
    if not facts:
        return []
    stars = facts["stars"]
    dates = facts["dates"]
    prices = facts["prices"]
    counts = facts["counts"]
    return [
        {
            "id": "facts_values",
            "kind": "semantics",
            "text": (
                "Live data facts: the cities are "
                + ", ".join(f"'{c}'" for c in facts["cities"])
                + ". The room types are "
                + ", ".join(f"'{t}'" for t in facts["room_types"])
                + ". Use these exact spellings in WHERE clauses. "
                f"Star ratings range from {stars[0]} to {stars[1]}."
            ),
        },
        {
            "id": "facts_ranges",
            "kind": "semantics",
            "text": (
                f"Live data facts: there are {counts[0]} hotels, {counts[1]} rooms and "
                f"{counts[2]} bookings. Check-in dates run from {dates[0]} to {dates[1]}. "
                f"Nightly prices range from {prices[0]} to {prices[1]} US dollars."
            ),
        },
    ]


def rule_documents():
    return [{"id": rid, "kind": "semantics", "text": text} for rid, text in BUSINESS_RULES]


def example_documents():
    return [
        {
            "id": f"example_{i:02d}",
            "kind": "example",
            "text": f"Example question: {question}\nSQL:\n{sql}",
        }
        for i, (question, sql) in enumerate(FEW_SHOT_EXAMPLES, start=1)
    ]


def build_documents(schema):
    """All documents for the vector database."""
    return schema_documents(schema) + live_fact_documents(schema) + rule_documents() + example_documents()
