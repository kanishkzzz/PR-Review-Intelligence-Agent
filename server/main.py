from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from models import PRReviewRequest, PRReviewResponse
from agent import run_agent, run_multi_agent_review
from rag import index_repo
from tools import fetch_pr_diff, parse_pr_url
import asyncio
import json

load_dotenv()

app = FastAPI()

# CORS — frontend se request aane ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/review", response_model=PRReviewResponse)
async def review_pr(request: PRReviewRequest):
    try:
        owner, repo, pr_number = parse_pr_url(request.pr_url)
        repo_full_name = f"{owner}/{repo}"
        
        diff = await fetch_pr_diff(request.pr_url, request.token)
        changed_files = [f["filename"] for f in diff]
        
        print(f" Changed Files: {changed_files}")
        
        await index_repo(repo_full_name, changed_files, request.token)
        
        review = await run_multi_agent_review(request.pr_url, request.token)
        return review
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))