"""Hotel Bookings SQL Quiz with RAG-powered Text-to-SQL.

Week 7 built a SQL quiz on a hosted Supabase PostgreSQL database.
Week 8 adds Retrieval-Augmented Generation (RAG):

    question -> ChromaDB vector retrieval -> Gemini -> generated SQL
             -> (bonus) run read-only -> result table -> compare with expected
"""

import streamlit as st

import db
from rag import knowledge, llm, validate, vector_store

st.set_page_config(page_title="Hotel SQL Quiz with RAG", page_icon="🏨", layout="wide")

KIND_LABELS = {"schema": "Schema", "semantics": "Business rule / data fact", "example": "Few-shot example"}
CUSTOM_CHOICE = "Type my own question"


# ---------------------------------------------------------------------------
# Vector database: built once per server process from the live database
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Building the ChromaDB vector database from the live schema...")
def get_knowledge_base():
    with db.owner_connection() as conn:
        schema = knowledge.load_live_schema(conn)
    documents = knowledge.build_documents(schema)
    collection = vector_store.build_collection(documents)
    return collection, documents


def gemini_models():
    preferred = db.setting("GEMINI_MODEL")
    models = [preferred] if preferred else []
    return models + [m for m in llm.DEFAULT_MODELS if m != preferred]


# ---------------------------------------------------------------------------
# Sidebar: Supabase Auth, same as Week 7
# ---------------------------------------------------------------------------
if "user_email" not in st.session_state:
    st.session_state.user_email = None
signed_in = st.session_state.user_email is not None

with st.sidebar:
    st.header("Account")
    if signed_in:
        st.success(f"Signed in as {st.session_state.user_email}")
        if st.button("Sign out"):
            st.session_state.user_email = None
            st.session_state.pop("rag_result", None)
            st.rerun()
    else:
        st.info("Sign in to generate, run and save SQL.")
        sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])
        with sign_in_tab:
            with st.form("sign_in_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Sign in"):
                    try:
                        st.session_state.user_email = db.sign_in(email.strip(), password)
                        st.rerun()
                    except db.AuthError as exc:
                        st.error(str(exc))
        with sign_up_tab:
            with st.form("sign_up_form"):
                new_email = st.text_input("Email", key="new_email")
                new_password = st.text_input(
                    "Password (at least 6 characters)", type="password", key="new_password"
                )
                if st.form_submit_button("Create account"):
                    try:
                        st.session_state.user_email = db.sign_up(new_email.strip(), new_password)
                        st.rerun()
                    except db.AuthError as exc:
                        st.error(str(exc))

# ---------------------------------------------------------------------------
# Header and shared data
# ---------------------------------------------------------------------------
st.title("🏨 Hotel Bookings SQL Quiz, now with RAG")
st.write(
    "Ask a question in plain English and get PostgreSQL back. The app retrieves the most "
    "relevant schema, business rules and examples from a **ChromaDB** vector database, "
    "sends them with your question to **Google Gemini**, then runs the generated SQL "
    "read-only against the live **Supabase PostgreSQL** database and checks the answer."
)

try:
    questions = db.load_questions()
except Exception as exc:
    st.error(f"Could not connect to the database: {exc}")
    st.stop()

rag_tab, quiz_tab, about_tab = st.tabs(
    ["🤖 Ask in plain English (RAG)", "📝 SQL Quiz (write SQL yourself)", "🔎 How the RAG works"]
)

# ---------------------------------------------------------------------------
# Tab 1: RAG Text-to-SQL
# ---------------------------------------------------------------------------
with rag_tab:
    labels = [f"Quiz question {q['question_id']}" for q in questions] + [CUSTOM_CHOICE]
    choice = st.selectbox("Start from a quiz question, or type your own", labels)
    question = None if choice == CUSTOM_CHOICE else questions[labels.index(choice)]

    default_text = question["question_text"] if question else ""
    user_question = st.text_area(
        "Your question in plain English",
        value=default_text,
        key=f"rag_q_{choice}",
        height=110,
        placeholder="For example: Which city has the most expensive Suite rooms?",
    )

    generate = st.button(
        "✨ Generate SQL with RAG", type="primary", disabled=not signed_in or not user_question.strip()
    )
    if not signed_in:
        st.warning("You are signed out. Sign in using the sidebar to generate SQL.")

    if signed_in and generate:
        result = {"question": user_question.strip(), "question_id": question["question_id"] if question else None}
        try:
            with st.spinner("Step 1: retrieving relevant knowledge from ChromaDB..."):
                collection, documents = get_knowledge_base()
                result["retrieved"] = vector_store.retrieve(collection, result["question"], documents)
            with st.spinner("Step 2: asking Gemini to write the SQL..."):
                sql, model, prompt = llm.generate_sql(
                    db.setting("GEMINI_API_KEY"), result["question"], result["retrieved"], gemini_models()
                )
                result.update(sql=sql, model=model, prompt=prompt)
        except llm.GenerationError as exc:
            result["error"] = str(exc)
        except Exception as exc:
            result["error"] = f"Something went wrong: {exc}"

        if "sql" in result:
            with st.spinner("Step 3: running the SQL read-only..."):
                try:
                    df, rows, truncated = db.run_read_only(result["sql"])
                    result.update(df=df, rows=rows, truncated=truncated)
                    db.write_audit_log(
                        st.session_state.user_email, "run", result["question_id"], result["sql"], True, len(rows)
                    )
                except Exception as exc:
                    result["run_error"] = str(exc)
                    db.write_audit_log(
                        st.session_state.user_email, "run", result["question_id"], result["sql"], False, None
                    )
            if question and "rows" in result:
                try:
                    expected_df, expected_rows, _ = db.run_read_only(question["hint_sql"])
                    ok, why = validate.compare_results(result["rows"], expected_rows)
                    result.update(expected_df=expected_df, correct=ok, why=why)
                except Exception as exc:
                    result["validate_error"] = str(exc)
        st.session_state.rag_result = result

    result = st.session_state.get("rag_result") if signed_in else None
    if result:
        st.divider()
        if "error" in result:
            st.error(result["error"])
        if result.get("retrieved"):
            st.subheader("Step 1: Knowledge retrieved from ChromaDB")
            st.caption(
                "Vector search ran once for each kind of knowledge. Similarity is cosine "
                "similarity between the question and the document (1.0 means identical meaning)."
            )
            for r in result["retrieved"]:
                with st.expander(f"{KIND_LABELS[r['kind']]}: {r['id']}  (similarity {r['similarity']:.3f})"):
                    st.code(r["text"], language="text")

        if "sql" in result:
            st.subheader("Step 2: SQL generated by Gemini")
            st.caption(f"Model: {result['model']}")
            st.code(result["sql"], language="sql")
            with st.expander("Show the exact prompt sent to Gemini"):
                st.code(result["prompt"], language="markdown")

            st.subheader("Step 3: Result of running the SQL (read-only)")
            if "run_error" in result:
                st.error(f"The generated SQL failed to run: {result['run_error']}")
            elif result["df"].columns.empty:
                st.info("The SQL ran, but did not return a table.")
            else:
                st.dataframe(result["df"], use_container_width=True, hide_index=True)
                if result["truncated"]:
                    st.caption(f"Only the first {db.MAX_ROWS} rows are shown.")

            st.subheader("Step 4: Validation against the expected answer")
            if result.get("question_id") is None:
                st.info("This is your own question, so there is no expected answer to compare with.")
            elif "validate_error" in result:
                st.warning(f"Could not run the expected answer: {result['validate_error']}")
            elif "correct" in result:
                if result["correct"]:
                    st.success(f"✅ Correct. {result['why']}")
                else:
                    st.error(f"❌ Incorrect. {result['why']}")
                with st.expander("Show the expected result"):
                    st.dataframe(result["expected_df"], use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Tab 2: the Week 7 quiz (write SQL yourself)
# ---------------------------------------------------------------------------
with quiz_tab:
    st.write(
        "Five SQL questions, 4 points each (20 points total). Write a PostgreSQL query, "
        "click **Run**, and compare your result with the hint."
    )
    with st.expander("📋 The tables you can query"):
        st.markdown(
            "**hotels**: `hotel_id`, `hotel_name`, `city`, `star_rating`\n\n"
            "**rooms**: `room_id`, `hotel_id` (links to hotels), `room_type`, `nightly_price`\n\n"
            "**bookings**: `booking_id`, `room_id` (links to rooms), `guest_name`, "
            "`check_in_date`, `nights`"
        )
    quiz_labels = [f"Question {q['question_id']} ({q['points']} points)" for q in questions]
    quiz_choice = st.radio("Choose a question", quiz_labels, horizontal=True)
    quiz_q = questions[quiz_labels.index(quiz_choice)]
    qid = quiz_q["question_id"]
    st.markdown(f"**{quiz_choice}**  \n" + quiz_q["question_text"].replace("\n", "  \n"))

    sql_text = st.text_area("Your SQL", key=f"sql_{qid}", height=160, disabled=not signed_in)
    run_col, save_col, _ = st.columns([1, 1, 6])
    run_clicked = run_col.button("▶ Run", disabled=not signed_in)
    save_clicked = save_col.button("💾 Save answer", disabled=not signed_in)
    if not signed_in:
        st.warning("You are signed out. Sign in using the sidebar to run or save queries.")

    if signed_in and run_clicked and sql_text.strip():
        try:
            df, rows, truncated = db.run_read_only(sql_text)
            db.write_audit_log(st.session_state.user_email, "run", qid, sql_text, True, len(rows))
            st.success(f"{len(rows)} row(s) returned.")
            st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as exc:
            db.write_audit_log(st.session_state.user_email, "run", qid, sql_text, False, None)
            st.error(f"Your query failed: {exc}")

    if signed_in and save_clicked and sql_text.strip():
        try:
            db.save_answer(st.session_state.user_email, qid, sql_text)
            db.write_audit_log(st.session_state.user_email, "save", qid, sql_text, True, None)
            st.success("Answer saved.")
        except Exception as exc:
            st.error(f"Could not save your answer: {exc}")

    with st.expander("💡 Show hint (expected SQL and expected result)"):
        st.code(quiz_q["hint_sql"], language="sql")
        st.markdown(f"**Expected result:** {quiz_q['expected_result']}")

    if signed_in:
        st.subheader("Your saved answers")
        try:
            saved = db.load_saved_answers(st.session_state.user_email)
            if saved.empty:
                st.caption("Nothing saved yet.")
            else:
                st.dataframe(saved, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Could not load your saved answers: {exc}")

# ---------------------------------------------------------------------------
# Tab 3: what is inside the vector database
# ---------------------------------------------------------------------------
with about_tab:
    st.markdown(
        """
**Pipeline:** your question → **ChromaDB** vector retrieval → **Gemini** → generated SQL →
run read-only as the `quiz_taker` role → result table → compared with the expected answer.

* **Schema documents** are built from the live PostgreSQL catalog (`information_schema`),
  so they always match the real tables, columns and foreign keys.
* **Business rule and data fact documents** explain what the columns mean (for example,
  revenue is `nightly_price * nights`) and list real values read from the data.
* **Few-shot examples** are question and SQL pairs that are similar to, but not the same as,
  the quiz questions.

Every document is embedded with ChromaDB's built-in all-MiniLM-L6-v2 model. For each question,
vector search picks the closest documents of each kind, and only those are sent to Gemini.
"""
    )
    try:
        collection, documents = get_knowledge_base()
        counts = {}
        for d in documents:
            counts[d["kind"]] = counts.get(d["kind"], 0) + 1
        cols = st.columns(4)
        cols[0].metric("Documents in ChromaDB", collection.count())
        cols[1].metric("Schema", counts.get("schema", 0))
        cols[2].metric("Business rules / facts", counts.get("semantics", 0))
        cols[3].metric("Few-shot examples", counts.get("example", 0))
        with st.expander("Show every document stored in the vector database"):
            for d in documents:
                st.markdown(f"**{d['id']}** ({KIND_LABELS[d['kind']]})")
                st.code(d["text"], language="text")
    except Exception as exc:
        st.error(f"Could not build the vector database: {exc}")
