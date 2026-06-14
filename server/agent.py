import json
from groq import AsyncGroq
from tools import fetch_pr_metadata, fetch_pr_diff, fetch_file_context
from dotenv import load_dotenv
from rag import search_similar_code

load_dotenv()

client = AsyncGroq()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_pr_metadata",
            "description": "PR ka title, author, description, state fetch karta hai",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_url": {"type": "string", "description": "GitHub PR URL"}
                },
                "required": ["pr_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_pr_diff",
            "description": "PR mein kya kya changes hue — file wise diff fetch karta hai",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_url": {"type": "string", "description": "GitHub PR URL"}
                },
                "required": ["pr_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_file_context",
            "description": "Kisi specific file ka poora content fetch karta hai",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_full_name": {
                        "type": "string",
                        "description": "owner/repo format mein"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "File ka path jaise src/auth.js"
                    }
                },
                "required": ["repo_full_name", "file_path"]
            }
        }
    },
    # TOOLS list mein add karo
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "Poori repo mein similar code dhundho — impact analysis ke liye",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Kya dhundhna hai — function name ya concept"
                    }
                },
                "required": ["query"]
            }
        }
    }    
]

async def run_tool(tool_name: str, tool_args: dict, token: str = None):
    if tool_name == "fetch_pr_metadata":
        return await fetch_pr_metadata(tool_args["pr_url"], token)
    elif tool_name == "fetch_pr_diff":
        return await fetch_pr_diff(tool_args["pr_url"], token)
    elif tool_name == "fetch_file_context":
        return await fetch_file_context(
            tool_args["repo_full_name"],
            tool_args["file_path"],
            token
        )
    elif tool_name == "search_codebase":   
        return search_similar_code(tool_args["query"])
    else:
        raise ValueError(f"Unknown tool: {tool_name}")
      
async def run_agent(pr_url: str, token: str = None):
    messages = [
        {
            "role": "system",
            "content": """Tu ek senior software engineer hai.
Tera kaam hai GitHub PR ko deeply review karna.

Hamesha yeh order follow kar:
1. Pehle fetch_pr_metadata call kar
2. Phir fetch_pr_diff call kar  
3. Agar koi file suspicious lage toh fetch_file_context call kar

Review mein yeh check karna hai:
- Security issues (exposed keys, auth bypass, injection)
- Logic bugs (null checks, edge cases)
- Breaking changes
- Code quality
- Missing tests

Final output SIRF JSON mein dena — koi extra text nahi:
{
  "summary": "...",
  "risk_level": "HIGH/MEDIUM/LOW",
  "issues": [
    {"type": "SECURITY", "file": "...", "description": "..."}
  ],
  "suggestions": ["..."],
  "test_cases_missing": ["..."]
}"""
        },
        {
            "role": "user",
            "content": f"Is PR ko review karo: {pr_url}"
        }
    ]

    # ── Loop ─────────────────────────────────────────────
    while True:
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=TOOLS,
            temperature=0,  # structured output ke liye
            max_tokens=1000
        )

        message = response.choices[0].message

        # Case A: LLM ne tool manga
        if message.tool_calls:
            # Assistant ka message history mein add karo
            messages.append(message)

            # Har tool call run karo
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"🔧 Tool call: {tool_name} — {tool_args}")

                result = await run_tool(tool_name, tool_args, token)

                # Result history mein add karo
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

        # Case B: LLM ne final answer diya — loop khatam
        else:
            final_review = message.content
            print("✅ Review ready!")

            # JSON parse karo
            try:
                return json.loads(final_review)
            except json.JSONDecodeError:
                return {"raw_review": final_review}