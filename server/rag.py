import os
import chromadb
from tools import fetch_file_context
from sentence_transformers import SentenceTransformer

#setup
chroma_client = chromadb.PersistentClient(path="./chroma-db")
collection = chroma_client.get_or_create_collection(name="repo_index")

_local_model = None

def get_local_embedding_model():
    global _local_model
    if _local_model is None:
        _local_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _local_model


def get_embedding(text: str) -> list:
    model = get_local_embedding_model()
    return model.encode(text[:8000]).tolist()

def chunk_code(content: str, file_path: str):
    lines = content.split("\n")
    chunks = []
    current_chunk = []

    BOUNDARY_KEYWORDS = (
        "def", "async def", "class", "function",
        "const ", "export function", "export const", "module.exports"
    )

    for line in lines:
        stripped = line.strip()

        if any(stripped.startswith(kw) for kw in BOUNDARY_KEYWORDS):
            if len(current_chunk) > 3:
                chunk_text = "\n".join(current_chunk)
                if chunk_text.strip():
                    chunks.append(f"# File: {file_path}\n{chunk_text}")
            current_chunk = [line]
        else:
            current_chunk.append(line)

        if len(current_chunk) > 80:
            chunk_text = "\n".join(current_chunk)
            if chunk_text.strip():
                chunks.append(f"# File: {file_path}\n{chunk_text}")
            current_chunk = []

    if current_chunk:
        chunk_text = "\n".join(current_chunk)
        if chunk_text.strip():
            chunks.append(f"# File: {file_path}\n{chunk_text}")

    return chunks  

def get_embeddings_batch(texts: list) -> list:
    model = get_local_embedding_model()
    truncated = [t[:8000] for t in texts]
    embeddings = model.encode(truncated)
    return [e.tolist() for e in embeddings]


#Indexing the Report
async def index_repo(repo_full_name: str, file_paths: list, token: str = None):
    print(f"Indexing {len(file_paths)} files...")

    all_chunks = []
    all_ids = []
    all_metadatas = []

    for file_path in file_paths:
        # Check if this file is already indexed — skip re-fetching/re-embedding
        existing = collection.get(where={"file": file_path})
        if existing["ids"]:
            print(f"Skipping already-indexed file: {file_path}")
            continue

        content = await fetch_file_context(repo_full_name, file_path, token)

        if content.startswith("[Skipped]") or content.startswith("[File not"):
            continue

        chunks = chunk_code(content, file_path)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_ids.append(f"{file_path}_{i}")
            all_metadatas.append({"file": file_path, "chunk_index": i})

    if not all_chunks:
        print("No new chunks to index")
        return

    BATCH_SIZE = 20
    for start in range(0, len(all_chunks), BATCH_SIZE):
        batch_chunks = all_chunks[start:start + BATCH_SIZE]
        batch_ids = all_ids[start:start + BATCH_SIZE]
        batch_metadatas = all_metadatas[start:start + BATCH_SIZE]

        embeddings = get_embeddings_batch(batch_chunks)

        collection.upsert(
            ids=batch_ids,
            embeddings=embeddings,
            documents=batch_chunks,
            metadatas=batch_metadatas
        )

    print("Indexing Complete")
 
  
def search_similar_code_batch(queries: list, n_results: int = 2):
    embeddings = get_embeddings_batch(queries)  # one API call for all filenames
    results_map = {}
    for query, embedding in zip(queries, embeddings):
        results = collection.query(query_embeddings=[embedding], n_results=n_results)
        similar_chunks = []
        for i, doc in enumerate(results["documents"][0]):
            similar_chunks.append({
                "content": doc,
                "file": results["metadatas"][0][i]["file"],
                "score": results["distances"][0][i]
            })
        results_map[query] = similar_chunks
    return results_map
