import os
import chromadb
from sentence_transformers import SentenceTransformer
from tools import fetch_file_context

#setup
chroma_client = chromadb.PersistentClient(path="./chroma-db")
collection = chroma_client.get_or_create_collection(name="repo_index")


#free local embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

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
    

#Indexing the Report
async def index_repo(repo_full_name: str, file_paths: list, token: str = None):
 """
 Saari files fetch karo aur ChromaDB mein store karo
 """
 print(f"Indexing {len(file_paths)} files...")
 
 for file_path in file_paths:
   #File content fetch karo
   content = await fetch_file_context(repo_full_name, file_path, token)
   
   #Skip karo agar binary ya error hai
   if content.startswith("[Skipped]") or content.startswith("[File not"):
     continue
   
   #Chunks banao - har 50 lines ek chunk
   chunks = chunk_code(content, file_path)
   
   for i, chunk in enumerate(chunks):
     #Embedding banao
      embedding = embedder.encode(chunk).tolist()
     
     # ChromaDB mein store karo
      collection.upsert(
       ids=[f"{file_path}_{i}"],
       embeddings = [embedding],
       documents=[chunk],
       metadatas=[{"file": file_path, "chunk_index":i}]
     )
     
 print(f"Indexing Complete")
 
 
# #Code ko chunks ma todenge
# def chunk_code(content: str, file_path: str, chunk_size: int = 50):
#   """
#   File ko 50-line chunks ma todo
#   """
#   lines = content.split("\n")
#   chunks = []
  
#   for i in range(0, len(lines), chunk_size):
#     chunk = "\n".join(lines[i:i + chunk_size])
#     if chunk.strip():
#       chunks.append(f"# {file_path}\n{chunk}")
  
#   return chunks

def search_similar_code(query: str, n_results: int = 3):
  """
  Query ke basis pe similar code chunks dhundho
  """
  
  # Query ki embedding krna
  query_embedding = embedder.encode(query).tolist()
  
  #ChromaDB mein search karo
  results = collection.query(
    query_embeddings=[query_embedding],
    n_results=n_results
  )
  
  #Clean format mein return karo
  similar_chunks = []
  for i, doc in enumerate(results["documents"][0]):
    similar_chunks.append({
      "content":doc,
      "file": results["metadatas"][0][i]["file"],
      "score": results["distances"][0][i]
    })
    
  return similar_chunks
  
