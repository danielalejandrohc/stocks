import requests
import streamlit as st
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from config import QDRANT_URL, OLLAMA_URL, QDRANT_COLLECTION, EMBEDDING_MODEL


@st.cache_data(ttl=300)
def get_qdrant_models() -> list[str]:
    client  = QdrantClient(url=QDRANT_URL)
    results, _ = client.scroll(
        collection_name=QDRANT_COLLECTION,
        limit=1000,
        with_payload=["model"],
        with_vectors=False,
    )
    models = sorted({r.payload.get("model", "") for r in results if r.payload.get("model")})
    return models if models else ["gemma4:e4b"]


def embed_query(text: str) -> list[float]:
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text.replace("\n", " ").strip()},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def search_news(query_vector: list[float], model: str, stocks: list[str], limit: int = 10) -> list[dict]:
    client     = QdrantClient(url=QDRANT_URL)
    conditions = [FieldCondition(key="model", match=MatchValue(value=model))]
    if stocks:
        conditions.append(FieldCondition(key="stock", match=MatchAny(any=stocks)))

    response = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=query_vector,
        query_filter=Filter(must=conditions),
        limit=limit,
        with_payload=True,
    )
    return [{"score": round(h.score, 4), **h.payload} for h in response.points]
