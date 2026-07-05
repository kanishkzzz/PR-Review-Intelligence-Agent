from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from models import PRReviewRequest, PRReviewResponse
from agent import run_agent, run_multi_agent_review
from rag import index_repo
from tools import fetch_pr_diff, parse_pr_url
import httpx
import os
from fastapi.responses import StreamingResponse
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


@app.post("/review")
async def review_pr(request: PRReviewRequest):
    async def event_stream():
        try:
            owner, repo, pr_number = parse_pr_url(request.pr_url)
            repo_full_name = f"{owner}/{repo}"
            
            diff = await fetch_pr_diff(request.pr_url, request.token)
            changed_files = [f["filename"] for f in diff]
            await index_repo(repo_full_name, changed_files, request.token)
            
            async for chunk in run_multi_agent_review(request.pr_url, request.token):
                yield f"data: {json.dumps(chunk)}\n\n"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

    
    
@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    
    action = payload.get("action")
    
    #Sirf PR open hone pe ya update hone pe trigger ho
    if action not in ["opened", "synchronize"]:
        return {"status": "ignored", "action": action}
    
    pr = payload.get("pull_request", {})
    pr_url = pr.get("html_url")
    repo_full_name = payload.get("repository", {}).get("full_name")
    pr_number = pr.get("number")
    
    print(f"Webhook Received! PR:{pr_url}")
    
    background_tasks.add_task(
        process_pr_and_comment,
        pr_url,
        repo_full_name,
        pr_number
    )
    
    return {"status": "processing"}

async def process_pr_and_comment(pr_url: str, repo_full_name: str, pr_number: int):
    try:
        print(f"Processing PR: {pr_url}")
        
        diff = await fetch_pr_diff(pr_url)
        changed_files = [f["filename"] for f in diff]
        await index_repo(repo_full_name, changed_files)
        
        review = await run_multi_agent_review(pr_url)
        
        await post_github_comment(repo_full_name, pr_number, review)
        
    except Exception as e:
        print(f"Error processing PR: {e}")
        import traceback
        traceback.print_exc()

async def post_github_comment(repo_full_name: str, pr_number: int, review: dict):
    token = os.getenv("GITHUB_TOKEN")
    
    if not token:
        print("Github_token not set - Comment post nahi hoga")
        return
    
    issues_text = ""
    for issue in review.get("issues", []):
        emoji = "🚨" if issue.get("severity") == "HIGH" else "⚠️" if issue.get("severity") == "MEDIUM" else "💡"
        issues_text += f"{emoji} **{issue['type']}** - `{issue['file']}`\n{issue['description']}\n\n"
    
    comment_body = f"""## 🤖PR Review Intelligence Agent
    
**Risk Level:** {review.get('risk_level', 'UNKNOWN')}

**Summary:** {review.get('summary', '')}

---
### Issues Found:
{issues_text if issues_text else "No Major issues found!"}

### Suggestions:
{chr(10).join(f"- {s}" for s in review.get('suggestions', []))}

### Missing Tests:
{chr(10).join(f"- {t}" for t in review.get('test_cases_missing', []))}
---

*Reviewed by PR Review Intelligence Agent - Multi-Agent System (Security + Logic + Test Coverage)*"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json"
            },
            json={"body": comment_body}
        )
    
    if response.status_code == 201:
        print(f"Comment posted successfully on PR #{pr_number}!")
    else:
        print(f"Comment Post failed: {response.status_code} - {response.text}")
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
