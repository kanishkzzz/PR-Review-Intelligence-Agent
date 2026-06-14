from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from models import PRReviewRequest, PRReviewResponse
from agent import run_agent

load_dotenv()

app = FastAPI()

# CORS — frontend se request aane ke liye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "PR Review Agent is running!"}

@app.post("/review", response_model=PRReviewResponse)
async def review_pr(request: PRReviewRequest):
    try:
        review = await run_agent(request.pr_url, request.token)
        return review
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))