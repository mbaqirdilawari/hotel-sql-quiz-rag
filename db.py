"""Database and sign-in helpers shared by the Streamlit app.

Two Postgres logins are used, both through the Supabase Session pooler
with sslmode=require:

* the owner login (DB_USER) reads the schema, the quiz questions and
  writes saved answers and the audit log, always with parameters;
* the read-only quiz_taker login (QUIZ_DB_USER) runs any SQL typed by a
  user or written by the AI. It can only SELECT from hotels, rooms and
  bookings, every transaction is read-only, and queries stop after 5s.
"""

import os

import pandas as pd
import psycopg
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # reads .env on a laptop; does nothing on Streamlit Cloud

MAX_ROWS = 200  # never show more than this many rows from one query


def setting(name, default=None):
    """Read a setting from Streamlit secrets (online) or .env (laptop)."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass  # no secrets file on this machine, fall back to .env
    return os.getenv(name, default)


SUPABASE_URL = (setting("SUPABASE_URL", "") or "").rstrip("/")
SUPABASE_KEY = setting("SUPABASE_KEY", "")


def _connect(user, password):
    return psycopg.connect(
        host=setting("DB_HOST"),
        port=int(setting("DB_PORT", "5432")),
        dbname=setting("DB_NAME", "postgres"),
        user=user,
        password=password,
        sslmode="require",
        connect_timeout=10,
    )


def owner_connection():
    return _connect(setting("DB_USER"), setting("DB_PASSWORD"))


def run_read_only(sql_text):
    """Run SQL as the read-only quiz_taker role.

    Returns (DataFrame, rows as a list of tuples, truncated flag).
    """
    with _connect(setting("QUIZ_DB_USER"), setting("QUIZ_DB_PASSWORD")) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(sql_text)
            if cur.description is None:
                return pd.DataFrame(), [], False
            cols = [d.name for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS + 1)
            truncated = len(rows) > MAX_ROWS
            rows = rows[:MAX_ROWS]
            return pd.DataFrame(rows, columns=cols), rows, truncated


@st.cache_data(ttl=300)
def load_questions():
    with owner_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT question_id, points, question_text, hint_sql, expected_result "
            "FROM quiz_questions ORDER BY question_id"
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def write_audit_log(email, action, question_id, sql_text, succeeded, row_count):
    """Append one row to audit_log (append-only table). Parameters only."""
    try:
        with owner_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log "
                "(user_email, action, question_id, sql_text, succeeded, row_count) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (email, action, question_id, sql_text, succeeded, row_count),
            )
    except Exception as exc:
        st.warning(f"Could not write to the audit log: {exc}")


def save_answer(email, question_id, sql_text):
    with owner_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO saved_answers (user_email, question_id, answer_sql) "
            "VALUES (%s, %s, %s)",
            (email, question_id, sql_text),
        )


def load_saved_answers(email):
    with owner_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT question_id AS question, answer_sql AS saved_sql, saved_at "
            "FROM saved_answers WHERE user_email = %s "
            "ORDER BY saved_at DESC LIMIT 25",
            (email,),
        )
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


# ---------------------------------------------------------------------------
# Supabase Auth (email + password), same as Week 7
# ---------------------------------------------------------------------------
class AuthError(Exception):
    pass


def _auth_request(path, payload):
    response = requests.post(
        f"{SUPABASE_URL}/auth/v1/{path}",
        json=payload,
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        timeout=15,
    )
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400:
        message = (
            data.get("msg")
            or data.get("error_description")
            or data.get("message")
            or f"Sign-in service returned status {response.status_code}"
        )
        raise AuthError(message)
    return data


def sign_in(email, password):
    data = _auth_request("token?grant_type=password", {"email": email, "password": password})
    return data["user"]["email"]


def sign_up(email, password):
    data = _auth_request("signup", {"email": email, "password": password})
    user = data.get("user") or data
    if not data.get("access_token"):
        raise AuthError(
            "Account created, but email confirmation is switched on in Supabase. "
            "Confirm your email, then sign in."
        )
    return user["email"]
