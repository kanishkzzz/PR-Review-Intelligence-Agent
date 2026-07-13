import httpx
import re
import base64
import asyncio

TEXT_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".yml", ".yaml", ".md", ".txt", ".env.example"
]

def parse_pr_url(pr_url: str):
  #extracting the owner, repo and pull req number
    pattern = re.match(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url.replace("https://", ""))
    if not pattern:
      raise ValueError(f"Mtlb kuch bhi ?: {pr_url}")
    return pattern.group(1), pattern.group(2), int(pattern.group(3))
  
  
async def fetch_pr_metadata(pr_url: str, token: str):
    # Get owner, repo and pull
    owner, repo, pr_number = parse_pr_url(pr_url);
    
    khopda = {"Accept": "application/vnd.github+json"}
    
    if token and token.strip():
      khopda["Authorization"] = f"bearer {token}"
      
    async with httpx.AsyncClient(timeout=30.0) as client:
      jawaab = await client.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        headers = khopda
      )
    
    # status check
    if jawaab.status_code != 200:
      raise Exception(f"Github API error: {jawaab.status_code} - {jawaab.text}")
      
    data = jawaab.json() 
    links = data.get("_links", {})
    
    return {
      "title": data["title"],
      "author": data["user"]["login"],
      "description": data.get("body", ""),
      "state": data["state"],
      "commits_url": links.get("commits", {}).get("href"),
      "review_comments_url": links.get("review_comments", {}).get("href")
    }
        
async def fetch_pr_diff(pr_url: str, token: str=None):
  owner, repo , pr_number = parse_pr_url(pr_url);
  
  khopda = {"Accept": "application/vnd.github+diff"}
  if token and token.strip():
    khopda["Authorization"] = f"bearer {token}"
  
  async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(
      f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
      headers = khopda
    )
    
    if response.status_code != 200:
      raise Exception(f"Github API error: {response.status_code} - {response.text}")
    
    files = response.json()
    
    return [
      {
        "filename": f["filename"],
        "status": f["status"],
        "additions": f["additions"],
        "deletions": f["deletions"],
        "patch": f.get("patch", "")[:500]
      }
      for f in files
    ]
    
async def fetch_file_context(repo_full_name: str, file_path: str, token: str = None, retries: int = 2):
  if not any(file_path.endswith(ext) for ext in TEXT_EXTENSIONS):
    return f"[Skipped: binary or Unsupported file type: {file_path}]"
  
  khopda = {"Accept": "application/vnd.github+json"}
  if token and token.strip():
    khopda["Authorization"] = f"Bearer {token}"

  response = None
  for attempt in range(retries + 1):
    try:
      async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
          f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}",
          headers = khopda
        )
      break
    except httpx.ReadTimeout:
      if attempt == retries:
        return f"[Skipped: timed out fetching {file_path}]"
      await asyncio.sleep(2)

  if response.status_code != 200:
    return (f"File not found or deleted: {file_path}")
  
  data = response.json()
  
  try:
    content = base64.b64decode(data["content"]).decode("utf-8")
    lines = content.split("\n")
    return "\n".join(lines[:100]) 
  except UnicodeDecodeError:
    return f"[Skipped: Unable to decode content of {file_path}]"