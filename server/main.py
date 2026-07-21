import os
import traceback

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from lmnr import Laminar
except ImportError:
    Laminar = None

from models import PRReviewRequest
from rag import index_repo
from tools import fetch_pr_diff, parse_pr_url

load_dotenv()


# Laminar is optional and must not prevent hosted deploys from starting.
LMNR_KEY = os.getenv("LMNR_PROJECT_API_KEY")
LMNR_ENABLED = False

if LMNR_KEY and Laminar is not None:
    try:
        Laminar.initialize(project_api_key=LMNR_KEY)
        LMNR_ENABLED = True
        print("Laminar initialized successfully", flush=True)
    except Exception as exc:
        print(f"Laminar initialization failed: {exc}", flush=True)
elif LMNR_KEY:
    print("Laminar key configured, but lmnr is not installed", flush=True)


def flush_laminar():
    if LMNR_ENABLED and Laminar is not None:
        try:
            Laminar.force_flush()
        except Exception as exc:
            print(f"Laminar flush failed: {exc}", flush=True)


def get_review_runner():
    """
    Import the AI agent only when a review is requested.
    This keeps Azure startup and health checks lightweight.
    """
    from agent import run_multi_agent_review

    return run_multi_agent_review


app = FastAPI(
    title="BugBeGone API",
    description="Multi-agent GitHub pull-request review service",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "BugBeGone",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/review")
async def review_pr(request: PRReviewRequest):
    try:
        configured_token = os.getenv("GITHUB_TOKEN")

        if not configured_token:
            raise HTTPException(
                status_code=503,
                detail="GITHUB_TOKEN is not configured in Azure.",
            )

        token = request.token or configured_token

        owner, repo, _ = parse_pr_url(request.pr_url)
        repo_full_name = f"{owner}/{repo}"

        diff = await fetch_pr_diff(request.pr_url, token)
        changed_files = [file["filename"] for file in diff]

        await index_repo(repo_full_name, changed_files, token)

        run_multi_agent_review = get_review_runner()

        result = await run_multi_agent_review(
            request.pr_url,
            token,
            diff=diff,
        )

        return result

    except HTTPException:
        raise

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    finally:
        flush_laminar()


@app.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload.",
        ) from exc

    action = payload.get("action")

    if action not in ["opened", "synchronize"]:
        return {
            "status": "ignored",
            "action": action,
        }

    pull_request = payload.get("pull_request", {})

    pr_url = pull_request.get("html_url")
    repo_full_name = payload.get("repository", {}).get("full_name")
    pr_number = pull_request.get("number") or payload.get("number")

    if not pr_url or not repo_full_name or not pr_number:
        raise HTTPException(
            status_code=400,
            detail="Webhook payload is missing pull-request information.",
        )

    print(f"Webhook received for PR: {pr_url}", flush=True)

    background_tasks.add_task(
        process_pr_and_comment,
        pr_url,
        repo_full_name,
        pr_number,
    )

    return {"status": "processing"}


async def process_pr_and_comment(
    pr_url: str,
    repo_full_name: str,
    pr_number: int,
):
    try:
        print(f"Processing PR: {pr_url}", flush=True)

        token = os.getenv("GITHUB_TOKEN")

        if not token:
            print(
                "GITHUB_TOKEN is not configured; review cannot run.",
                flush=True,
            )
            return

        diff = await fetch_pr_diff(pr_url, token)
        changed_files = [file["filename"] for file in diff]

        await index_repo(repo_full_name, changed_files, token)

        run_multi_agent_review = get_review_runner()

        review = await run_multi_agent_review(
            pr_url,
            token,
            diff=diff,
        )

        await post_github_comment(
            repo_full_name,
            pr_number,
            review,
        )

    except Exception as exc:
        print(f"Error processing PR: {exc}", flush=True)
        traceback.print_exc()

    finally:
        flush_laminar()


async def post_github_comment(
    repo_full_name: str,
    pr_number: int,
    review: dict,
):
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        print(
            "GITHUB_TOKEN is not set; comment will not be posted.",
            flush=True,
        )
        return

    issues_text = ""

    for issue in review.get("issues", []) or []:
        severity = issue.get("severity", "LOW")

        if severity == "HIGH":
            emoji = "🚨"
        elif severity == "MEDIUM":
            emoji = "⚠️"
        else:
            emoji = "💡"

        issue_type = issue.get("type", "ISSUE")
        file_name = issue.get("file", "Unknown file")
        description = issue.get("description", "")

        issues_text += (
            f"{emoji} **{issue_type}** - `{file_name}`\n"
            f"{description}\n\n"
        )

    suggestions = review.get("suggestions", []) or []
    missing_tests = review.get("test_cases_missing", []) or []

    suggestions_text = "\n".join(
        f"- {suggestion}" for suggestion in suggestions
    )

    missing_tests_text = "\n".join(
        f"- {test}" for test in missing_tests
    )

    comment_body = f"""## 🤖 PR Review Intelligence Agent

**Risk Level:** {review.get("risk_level", "UNKNOWN")}

**Summary:** {review.get("summary", "")}

---

### Issues Found

{issues_text if issues_text else "No major issues found!"}

### Suggestions

{suggestions_text if suggestions_text else "- No additional suggestions."}

### Missing Tests

{missing_tests_text if missing_tests_text else "- No missing tests identified."}

---

*Reviewed by PR Review Intelligence Agent — Security, Logic and Test Coverage*
"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            (
                f"https://api.github.com/repos/{repo_full_name}"
                f"/issues/{pr_number}/comments"
            ),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"body": comment_body},
        )

    if response.status_code == 201:
        print(
            f"Comment posted successfully on PR #{pr_number}",
            flush=True,
        )
    else:
        print(
            f"Comment failed: {response.status_code} - {response.text}",
            flush=True,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )