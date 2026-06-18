# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from dotenv import load_dotenv
# from models import PRReviewRequest, PRReviewResponse
# from agent import run_agent
# from rag import index_repo
# from tools import fetch_pr_diff, parse_pr_url

# load_dotenv()

# app = FastAPI()

# # CORS — frontend se request aane ke liye
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.get("/")
# async def root():
#     return {"status": "PR Review Agent is running!"}

# @app.post("/review", response_model=PRReviewResponse)
# async def review_pr(request: PRReviewRequest):
#     try:
#         # Step 1 — PR ki changed files nikalo
#         owner, repo, pr_number = parse_pr_url(request.pr_url)
#         repo_full_name = f"{owner}/{repo}"
        
#         diff = await fetch_pr_diff(request.pr_url, request.token)
#         changed_files = [f["filename"] for f in diff]
        
#         print(f"📂 Changed files: {changed_files}")
        
#         # Step 2 — Sirf changed files index karo ChromaDB mein
#         await index_repo(repo_full_name, changed_files, request.token)
        
#         # Step 3 — Agent run karo — ab search_codebase tool bhi use karega
#         review = await run_agent(request.pr_url, request.token)
#         return review
        
#     except Exception as e:
#         print(f"❌ ERROR: {e}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


import asyncio
import json
from dotenv import load_dotenv
from agent import gather_pr_context, run_security_agent

load_dotenv()

async def main():
    context = await gather_pr_context(
        "https://github.com/kanishkzzz/FoodInt/pull/5"
    )
    
    print("🛡️ Running Security Agent...")
    security_result = await run_security_agent(context)
    print(json.dumps(security_result, indent=2))

asyncio.run(main())