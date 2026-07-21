import asyncio
import os
import sys
import tempfile
import threading

from tools import fetch_file_context


_chroma_client = None
_collection = None
_local_model = None

_collection_lock = threading.Lock()
_model_lock = threading.Lock()


def use_hosted_sqlite_driver():
    """
    Hosted Python images can ship an old sqlite3 module. Chroma needs
    SQLite >= 3.35, so use pysqlite3-binary when it is installed.
    """
    try:
        import pysqlite3
    except ImportError:
        return

    sys.modules["sqlite3"] = pysqlite3


def get_collection():
    """
    Initialize ChromaDB only when a review is requested.

    Azure can start the API and answer health checks without loading
    ChromaDB during application startup.
    """
    global _chroma_client, _collection

    if _collection is None:
        with _collection_lock:
            if _collection is None:
                use_hosted_sqlite_driver()
                import chromadb

                chroma_path = os.getenv(
                    "CHROMA_PATH",
                    os.path.join(
                        tempfile.gettempdir(),
                        "bugbegone-chroma",
                    ),
                )

                os.makedirs(chroma_path, exist_ok=True)

                print(
                    f"Initializing ChromaDB at: {chroma_path}",
                    flush=True,
                )

                _chroma_client = chromadb.PersistentClient(
                    path=chroma_path
                )

                _collection = (
                    _chroma_client.get_or_create_collection(
                        name="repo_index"
                    )
                )

    return _collection


def get_local_embedding_model():
    """
    Load SentenceTransformer and PyTorch only when embeddings are needed.
    """
    global _local_model

    if _local_model is None:
        with _model_lock:
            if _local_model is None:
                from sentence_transformers import SentenceTransformer

                model_name = os.getenv(
                    "EMBEDDING_MODEL",
                    "all-MiniLM-L6-v2",
                )

                print(
                    f"Loading embedding model: {model_name}",
                    flush=True,
                )

                model_options = {
                    "device": "cpu",
                }

                cache_folder = os.getenv(
                    "SENTENCE_TRANSFORMERS_HOME"
                )

                if cache_folder:
                    model_options["cache_folder"] = cache_folder

                _local_model = SentenceTransformer(
                    model_name,
                    **model_options,
                )

                print(
                    "Embedding model loaded successfully",
                    flush=True,
                )

    return _local_model


def get_embedding(text: str) -> list:
    model = get_local_embedding_model()

    embedding = model.encode(
        text[:8000],
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    return embedding.tolist()


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = get_local_embedding_model()
    truncated_texts = [text[:8000] for text in texts]

    embeddings = model.encode(
        truncated_texts,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    return embeddings.tolist()


def chunk_code(content: str, file_path: str) -> list[str]:
    lines = content.split("\n")

    chunks = []
    current_chunk = []

    boundary_keywords = (
        "def",
        "async def",
        "class",
        "function",
        "const ",
        "export function",
        "export const",
        "module.exports",
    )

    for line in lines:
        stripped = line.strip()

        if any(
            stripped.startswith(keyword)
            for keyword in boundary_keywords
        ):
            if len(current_chunk) > 3:
                chunk_text = "\n".join(current_chunk)

                if chunk_text.strip():
                    chunks.append(
                        f"# File: {file_path}\n{chunk_text}"
                    )

            current_chunk = [line]

        else:
            current_chunk.append(line)

        if len(current_chunk) > 80:
            chunk_text = "\n".join(current_chunk)

            if chunk_text.strip():
                chunks.append(
                    f"# File: {file_path}\n{chunk_text}"
                )

            current_chunk = []

    if current_chunk:
        chunk_text = "\n".join(current_chunk)

        if chunk_text.strip():
            chunks.append(
                f"# File: {file_path}\n{chunk_text}"
            )

    return chunks


async def index_repo(
    repo_full_name: str,
    file_paths: list[str],
    token: str | None = None,
):
    collection = get_collection()

    print(
        f"Indexing {len(file_paths)} files from {repo_full_name}",
        flush=True,
    )

    all_chunks = []
    all_ids = []
    all_metadatas = []

    for file_path in file_paths:
        existing = collection.get(
            where={
                "$and": [
                    {"repo": repo_full_name},
                    {"file": file_path},
                ]
            }
        )

        if existing.get("ids"):
            print(
                f"Skipping already indexed file: {file_path}",
                flush=True,
            )
            continue

        content = await fetch_file_context(
            repo_full_name,
            file_path,
            token,
        )

        if not content:
            continue

        if content.startswith("[Skipped]"):
            continue

        if content.startswith("[File not"):
            continue

        chunks = chunk_code(content, file_path)

        for index, chunk in enumerate(chunks):
            safe_repo_name = repo_full_name.replace("/", "_")
            safe_file_name = file_path.replace("/", "_")

            all_chunks.append(chunk)

            all_ids.append(
                f"{safe_repo_name}_{safe_file_name}_{index}"
            )

            all_metadatas.append(
                {
                    "repo": repo_full_name,
                    "file": file_path,
                    "chunk_index": index,
                }
            )

    if not all_chunks:
        print("No new chunks to index", flush=True)
        return

    batch_size = 20

    for start in range(0, len(all_chunks), batch_size):
        batch_chunks = all_chunks[start : start + batch_size]
        batch_ids = all_ids[start : start + batch_size]
        batch_metadatas = all_metadatas[
            start : start + batch_size
        ]

        # Model loading and encoding run outside the main event loop.
        embeddings = await asyncio.to_thread(
            get_embeddings_batch,
            batch_chunks,
        )

        await asyncio.to_thread(
            collection.upsert,
            ids=batch_ids,
            embeddings=embeddings,
            documents=batch_chunks,
            metadatas=batch_metadatas,
        )

    print("Indexing complete", flush=True)


def search_similar_code_batch(
    queries: list[str],
    n_results: int = 2,
) -> dict:
    collection = get_collection()

    if not queries:
        return {}

    collection_count = collection.count()

    if collection_count == 0:
        return {query: [] for query in queries}

    result_limit = min(n_results, collection_count)
    embeddings = get_embeddings_batch(queries)

    results_map = {}

    for query, embedding in zip(queries, embeddings):
        results = collection.query(
            query_embeddings=[embedding],
            n_results=result_limit,
        )

        documents = (results.get("documents") or [[]])[0] or []
        metadatas = (results.get("metadatas") or [[]])[0] or []
        distances = (results.get("distances") or [[]])[0] or []

        similar_chunks = []

        for index, document in enumerate(documents):
            metadata = (
                metadatas[index]
                if index < len(metadatas)
                else {}
            )

            score = (
                distances[index]
                if index < len(distances)
                else None
            )

            similar_chunks.append(
                {
                    "content": document,
                    "file": metadata.get("file", "Unknown file"),
                    "score": score,
                }
            )

        results_map[query] = similar_chunks

    return results_map