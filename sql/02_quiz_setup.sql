-- Hotel Bookings SQL Quiz: quiz tables, security and the quiz_taker role
-- Run this whole file once in the Supabase SQL Editor, AFTER 01_seed.sql.
-- The last line prints a new password for the quiz_taker role. Save it.

-- =========================================================
-- Part A: the quiz questions (5 questions x 4 points = 20)
-- =========================================================
DROP TABLE IF EXISTS saved_answers;
DROP TABLE IF EXISTS quiz_questions;

CREATE TABLE quiz_questions (
    question_id      INTEGER PRIMARY KEY,
    points           INTEGER NOT NULL,
    question_text    TEXT NOT NULL,
    hint_sql         TEXT NOT NULL,
    expected_result  TEXT NOT NULL
);

INSERT INTO quiz_questions (question_id, points, question_text, hint_sql, expected_result) VALUES
(1, 4,
 'Filtering: List the name and city of every 5-star hotel.',
 'SELECT hotel_name, city
FROM hotels
WHERE star_rating = 5;',
 '2 rows: Grand Palace (Lahore), Margalla Heights (Islamabad)'),

(2, 4,
 'Counting by group: How many hotels are there in each city? Show the city with the most hotels first.',
 'SELECT city, COUNT(*) AS hotel_count
FROM hotels
GROUP BY city
ORDER BY hotel_count DESC;',
 '4 rows: Lahore 3, Islamabad 2, Karachi 2, Hunza 1 (Islamabad and Karachi are tied, so their order may vary)'),

(3, 4,
 'What does this query return? Run it and state the number and what it means:
SELECT COUNT(*) FROM bookings WHERE nights >= 3;',
 'SELECT COUNT(*)
FROM bookings
WHERE nights >= 3;',
 '1 row: 18. It means 18 bookings were for 3 or more nights.'),

(4, 4,
 'Joining two tables: What is the average nightly price of each room type, for hotels in Lahore only? Round to 2 decimal places.',
 'SELECT r.room_type, ROUND(AVG(r.nightly_price), 2) AS avg_price
FROM rooms r
JOIN hotels h ON r.hotel_id = h.hotel_id
WHERE h.city = ''Lahore''
GROUP BY r.room_type
ORDER BY r.room_type;',
 '3 rows: Deluxe 172.50, Standard 97.50, Suite 385.00'),

(5, 4,
 'Joining three tables: Which hotel earned the most money from bookings? Revenue for one booking is nightly_price multiplied by nights.',
 'SELECT h.hotel_name, SUM(r.nightly_price * b.nights) AS total_revenue
FROM bookings b
JOIN rooms r ON b.room_id = r.room_id
JOIN hotels h ON r.hotel_id = h.hotel_id
GROUP BY h.hotel_name
ORDER BY total_revenue DESC
LIMIT 1;',
 '1 row: Grand Palace, 7070.00');

-- =========================================================
-- Part B: answers that signed-in users save
-- =========================================================
CREATE TABLE saved_answers (
    answer_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email   TEXT NOT NULL,
    question_id  INTEGER NOT NULL REFERENCES quiz_questions(question_id),
    answer_sql   TEXT NOT NULL,
    saved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================
-- Part C: audit log (extra credit). Rows can be added, never changed.
-- =========================================================
DROP TABLE IF EXISTS audit_log;

CREATE TABLE audit_log (
    log_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_email   TEXT NOT NULL,
    action       TEXT NOT NULL CHECK (action IN ('run', 'save')),
    question_id  INTEGER,
    sql_text     TEXT NOT NULL,
    succeeded    BOOLEAN NOT NULL,
    row_count    INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION block_audit_changes() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP;
END;
$$;

CREATE TRIGGER audit_log_no_update_or_delete
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION block_audit_changes();

-- Lock the new tables from the public Supabase API (same as the data tables)
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_answers  ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log      ENABLE ROW LEVEL SECURITY;

-- =========================================================
-- Part D: quiz_taker role. It can ONLY read the 3 data tables.
-- Student SQL runs as this role, so it cannot change anything.
-- =========================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'quiz_taker') THEN
        CREATE ROLE quiz_taker LOGIN;
    END IF;
END;
$$;

ALTER ROLE quiz_taker SET default_transaction_read_only = on;
ALTER ROLE quiz_taker SET statement_timeout = '5s';

GRANT USAGE ON SCHEMA public TO quiz_taker;
GRANT SELECT ON hotels, rooms, bookings TO quiz_taker;

DROP POLICY IF EXISTS quiz_taker_read ON hotels;
DROP POLICY IF EXISTS quiz_taker_read ON rooms;
DROP POLICY IF EXISTS quiz_taker_read ON bookings;
CREATE POLICY quiz_taker_read ON hotels   FOR SELECT TO quiz_taker USING (true);
CREATE POLICY quiz_taker_read ON rooms    FOR SELECT TO quiz_taker USING (true);
CREATE POLICY quiz_taker_read ON bookings FOR SELECT TO quiz_taker USING (true);

-- Give quiz_taker a fresh random password and show it (save it!)
CREATE OR REPLACE FUNCTION pg_temp.new_quiz_taker_password() RETURNS TEXT
LANGUAGE plpgsql AS $$
DECLARE
    pw TEXT := replace(gen_random_uuid()::text, '-', '');
BEGIN
    EXECUTE format('ALTER ROLE quiz_taker WITH PASSWORD %L', pw);
    RETURN pw;
END;
$$;

SELECT pg_temp.new_quiz_taker_password() AS quiz_taker_password;
