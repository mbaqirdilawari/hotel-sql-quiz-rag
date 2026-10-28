"""ChromaDB vector database: store the knowledge documents and retrieve them.

Each document is turned into an embedding (a list of numbers that captures
its meaning) by ChromaDB's built-in all-MiniLM-L6-v2 model, which runs
locally inside the app, so no extra API key is needed for retrieval. A
user question is embedded the same way, and ChromaDB returns the stored
documents whose embeddings are closest to it (cosine similarity).
"""

# ChromaDB needs SQLite 3.35 or newer. If the optional pysqlite3 package
# is installed (only needed on old Linux images), use it instead.
try:  # pragma: no cover - depends on the hosting image
    __import__("pysqlite3")
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import chromadb
from chromadb.utils import embedding_functions

COLLECTION_NAME = "hotel_knowledge"

# How many documents of each kind to retrieve for one question.
RETRIEVAL_PLAN = {"schema": 3, "semantics": 3, "example": 3}


def build_collection(documents):
    """Create an in-memory ChromaDB collection holding the documents."""
    client = chromadb.EphemeralClient()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # first run: nothing to delete
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=[d["id"] for d in documents],
        documents=[d["text"] for d in documents],
        metadatas=[{"kind": d["kind"]} for d in documents],
    )
    return collection


def retrieve(collection, question, documents, plan=None):
    """Return the most relevant documents for a question, best first.

    Retrieval runs once per document kind (schema, semantics, example), so
    the AI always gets some table structure, some business rules and some
    worked examples, each chosen by vector similarity to the question.
    """
    plan = plan or RETRIEVAL_PLAN
    kind_counts = {}
    for d in documents:
        kind_counts[d["kind"]] = kind_counts.get(d["kind"], 0) + 1

    results = []
    for kind, wanted in plan.items():
        n = min(wanted, kind_counts.get(kind, 0))
        if n == 0:
            continue
        found = collection.query(query_texts=[question], n_results=n, where={"kind": kind})
        for doc_id, text, meta, distance in zip(
            found["ids"][0], found["documents"][0], found["metadatas"][0], found["distances"][0]
        ):
            results.append(
                {
                    "id": doc_id,
                    "kind": meta["kind"],
                    "text": text,
                    "similarity": round(1.0 - float(distance), 3),
                }
            )
    return results
