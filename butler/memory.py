"""Memory of past deaths, kept in Pinecone because a restore wipes the Taster."""
import json
import time
import urllib.request

from . import config

NAMESPACE = "deaths"
EMBED_MODEL = "multilingual-e5-large"


def _post(path, body):
    request = urllib.request.Request(
        config.PINECONE_URL + path, method="POST", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "X-Pinecone-API-Version": "2025-04"})
    return json.loads(urllib.request.urlopen(request, timeout=30).read() or b"{}")


def _embed(text):
    result = _post("/embed", {
        "model": EMBED_MODEL, "inputs": [{"text": text[:2000]}],
        "parameters": {"input_type": "passage", "truncate": "END"}})
    return result["data"][0]["values"]


def recall(meal, limit=3):
    """Earlier meals that mean the same thing as this one, most similar first."""
    if not config.PINECONE_URL:
        return []
    try:
        result = _post(f"/indexes/{config.PINECONE_INDEX}/query", {
            "namespace": NAMESPACE, "topK": limit, "includeMetadata": True, "vector": _embed(meal)})
    except Exception:
        return []
    return [{"id": match["id"], "score": round(match["score"], 2), **match["metadata"]}
            for match in result.get("matches", []) if match["score"] >= config.SAME_DEATH_SCORE]


def remember(death_id, meal, verdict, cause):
    """Store this death so a later life can recall it. Returns True if saved."""
    if not config.PINECONE_URL:
        return False
    try:
        _post(f"/indexes/{config.PINECONE_INDEX}/vectors/upsert", {"namespace": NAMESPACE, "vectors": [{
            "id": death_id, "values": _embed(meal),
            "metadata": {"meal": meal[:500], "verdict": verdict, "cause": cause[:300], "ts": time.time()}}]})
        return True
    except Exception:
        return False
