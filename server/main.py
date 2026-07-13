from dotenv import load_dotenv
load_dotenv()

from lmnr import Laminar
import os
Laminar.initialize(project_api_key=os.getenv("LMNR_PROJECT_API_KEY"))

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import PRReviewRequest
from agent import run_multi_agent_review
from rag import index_repo
from tools import fetch_pr_diff, parse_pr_url
import httpx

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/review")
async def review_pr(request: PRReviewRequest):
    try:
        owner, repo, pr_number = parse_pr_url(request.pr_url)
        repo_full_name = f"{owner}/{repo}"

        diff = await fetch_pr_diff(request.pr_url, request.token)
        changed_files = [f["filename"] for f in diff]
        await index_repo(repo_full_name, changed_files, request.token)

        result = await run_multi_agent_review(request.pr_url, request.token, diff=diff)
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        Laminar.force_flush()


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    action = payload.get("action")

    if action not in ["opened", "synchronize"]:
        return {"status": "ignored", "action": action}

    pr = payload.get("pull_request", {})
    pr_url = pr.get("html_url")
    repo_full_name = payload.get("repository", {}).get("full_name")
    pr_number = pr.get("number")

    print(f"Webhook Received! PR:{pr_url}")

    background_tasks.add_task(process_pr_and_comment, pr_url, repo_full_name, pr_number)
    return {"status": "processing"}


async def process_pr_and_comment(pr_url: str, repo_full_name: str, pr_number: int):
    try:
        print(f"Processing PR: {pr_url}")
        token = os.getenv("GITHUB_TOKEN")
        diff = await fetch_pr_diff(pr_url, token)
        changed_files = [f["filename"] for f in diff]
        await index_repo(repo_full_name, changed_files, token)

        review = await run_multi_agent_review(pr_url, token, diff=diff)
        await post_github_comment(repo_full_name, pr_number, review)

    except Exception as e:
        print(f"Error processing PR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        Laminar.force_flush()


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
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            json={"body": comment_body}
        )

    if response.status_code == 201:
        print(f"Comment posted successfully on PR #{pr_number}!")
    else:
        print(f"Comment Post failed: {response.status_code} - {response.text}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)