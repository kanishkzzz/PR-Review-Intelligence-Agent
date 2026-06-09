import asyncio
from tools import fetch_pr_metadata  # temporarily modify karenge

async def main():
    # seedha tools.py ka function call mat karo
    # pehle raw response dekho
    import httpx
    
    url = "https://api.github.com/repos/kanishkzzz/FoodInt/pulls/5/files"
    khopda = {"Accept": "application/vnd.github+json"}
    
    async with httpx.AsyncClient() as client:
        jawaab = await client.get(url, headers=khopda)
    
    data = jawaab.json()
    # links = data.get("_links", {})
    
    # pretty print karo
    import json
    print(json.dumps(data, indent=2))

asyncio.run(main())