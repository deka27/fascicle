from functools import cache

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

EMBED_MODEL = "all-MiniLM-L6-v2"
CHROMA_DIR = "chroma"


@cache
def collection():
    """The Chroma collection shared by ingestion and retrieval. Cached so the embedding model loads once."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_or_create_collection(
        "papers", embedding_function=SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    )
