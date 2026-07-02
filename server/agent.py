import json
from groq import AsyncGroq
from tools import fetch_pr_metadata, fetch_pr_diff, fetch_file_context
from dotenv import load_dotenv
from rag import search_similar_code
import asyncio
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

# ── Helper: Clean JSON from LLM response ──────────────────
def parse_llm_json(result: str, agent_name: str):
    """LLM response se JSON parse karo — markdown backticks handle karta hai"""
    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        return {"agent": agent_name, "raw": result, "issues": []}

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

Hamesha yeh EXACT order follow kar:
1. fetch_pr_metadata call kar
2. fetch_pr_diff call kar
3. Har changed file ke liye search_codebase call kar — 
   yeh batayega ki woh code aur kahan use ho raha hai
4. Suspicious files ke liye fetch_file_context call kar

Review mein yeh check karna hai:
- Security issues (exposed keys, auth bypass, injection)
- Logic bugs (null checks, edge cases)
- Breaking changes — search_codebase se pata chalega
  ki changed code kitni jagah use ho raha hai
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
            
async def gather_pr_context(pr_url: str, token: str = None):
    """
    Saara data ek baar mein gather karta hai —
    teeno specialist agents isi data ko use karenge
    """
    metadata = await fetch_pr_metadata(pr_url, token)
    diff = await fetch_pr_diff(pr_url, token)

    # Har changed file ke liye codebase context dhundo
    codebase_context = []
    for file in diff:
        filename = file["filename"]
        results = search_similar_code(filename, n_results=2)
        codebase_context.append({
            "file": filename,
            "related_code": results
        })

    return {
        "metadata": metadata,
        "diff": diff,
        "codebase_context": codebase_context
    }

# Specialist Agent 1: Security Chief
async def run_security_agent(context: dict):
    """
    Sirf security issues dhundhta hai - expose keys, auth bypass, injection,
    insecure connections, harcoded secrets
    """
    
    # Context ko readable string mein convert karo
    diff_summary = json.dumps(context["diff"], indent=2)
    codebase_summary = json.dumps(context["codebase_context"], indent=2)
    metadata = context["metadata"]
    
    messages = [
        {
        "role": "system",
        "content": """Tu ek cybersecurity expert hai jo sirf code security review karta hai. 
        
SIRF yeh cheezein dhundh:
- Hardcoded secrets (API keys, JWT secrets, passwords)
- Authentication/Authorization bypass
- SQL/NoSQL injection vulnerabilities  
- Insecure direct object references
- Sensitive data exposure
- Insecure dependencies
- Missing input validation

Logic bugs, code quality, tests — IGNORE kar. Sirf security.

Output SIRF JSON mein de, koi extra text nahi:
{
  "agent": "security",
  "issues": [
    {
      "type": "SECURITY",
      "severity": "HIGH/MEDIUM/LOW",
      "file": "filename",
      "description": "exact issue kya hai",
      "line_hint": "approximate code jo problematic hai"
    }
  ],
  "summary": "2-3 line security overview"
}"""
        },
        {
            "role": "user",
            "content": f"""PR Title: {metadata['title']}
Author: {metadata['author']}
        
Changed Files Diff:
{diff_summary[:3000]}
        
Related Codebase Context:
{codebase_summary[:2000]}
       
Sirf security issues find karo."""
        }
    ]
    
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.5,
        max_tokens=1000
    )
    
    result = response.choices[0].message.content
    
    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        return {"agent": "security", "raw": result, "issues":[]}
    
#2 Logical Bugs Specialist
async def run_logic_agent(context: dict):
    """
    Sirf Logical bugs aur edge cases dhoondhta hai
    """
    diff_summary = json.dumps(context["diff"], indent=2)
    codebase_summary = json.dumps(context["codebase_context"], indent=2)
    metadata = context["metadata"]
    
    messages = [
        {
            "role": "system",
            "content": """Tu ek expert bug hunter hai jo sirf logic errors dhundhta hai.
            
            SIRF yeh cheezien dhundh:
            - Null/undefined pointer exceptions
            - Race conditions (especially async code mein)
            - Off-by-one errors
            - Unhandled promise rejections / missing try-catch
            - Wrong error handlin (error silently swallow ho raha ho)
            - Incorrect conditional logic
            - Missing edge cases (empty array, zero, negative numbers)
            - Memory Leaks

            Security, code quality, tests - IGNORE kar. Sirf logic bugs.
            
            Outpur SIRF JSON mein de, koi extra text nahi:
            {
                "agent": "logic",
                "issues":[
                    {
                        "type": "LOGIC",
                        "severity": "HIGH/MEDIUM/LOW",
                        "file": "filename",
                        "description": "exact bug kya hai aur kab trigger hoga",
                        "line_hint": "approximate problematic code"
                    }
                ],
                "summary": "2-3 line logic overview"
            }""" 
        },
        {
            "role":"user",
            "content": f"""PR Title: {metadata['title']}
            Author: {metadata['author']}
            
            Changed Files Diff
            {diff_summary[:3000]}
            
            Related Codebase Context:
            {codebase_summary[:2000]}
            
            Sirf logic bugs aur edge cases find karo."""
        }
    ]
    
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0,
        max_tokens=1000
    )
    
    result = response.choices[0].message.content
    return parse_llm_json(result, "logic")


#3 Test Cases Specialist
async def run_test_agent(context: dict):
    """
    Sirf missing test cases dhundta hai
    """
    diff_summary = json.dumps(context["diff"], indent=2)
    codebase_summary = json.dumps(context["codebase_context"], indent=2)
    metadata = context["metadata"]

    messages = [
        {
            "role": "system",
            "content": """Tu ek QA engineer hai jo sirf test coverage review karta hai.

SIRF yeh cheezein dhundh:
- Naye functions/endpoints jinke koi unit tests nahi hain
- Edge cases jo test nahi hue (empty input, null, error paths)
- Integration tests missing (jaise API endpoints, DB calls)
- Error handling paths jo untested hain
- Existing tests jo is PR ke baad break ho sakte hain

Security, logic bugs, code quality — IGNORE kar. Sirf test coverage.

Output SIRF JSON mein de, koi extra text nahi:
{
  "agent": "test_coverage",
  "issues": [
    {
      "type": "MISSING_TEST",
      "severity": "HIGH/MEDIUM/LOW",
      "file": "filename",
      "description": "kaunsa scenario test nahi hua aur kyun zaroori hai"
    }
  ],
  "summary": "2-3 line test coverage overview"
}"""
        },
        {
            "role": "user",
            "content": f"""PR Title: {metadata['title']}
Author: {metadata['author']}

Changed Files Diff:
{diff_summary[:3000]}

Related Codebase Context:
{codebase_summary[:2000]}

Sirf missing test cases find karo."""
        }
    ]

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0,
        max_tokens=1000
    )

    result = response.choices[0].message.content
    return parse_llm_json(result, "test_coverage")


# Orchestrator: Multi-Agent Review
async def run_multi_agent_review(pr_url: str, token: str = None):
    print("Gathering PR context...")
    context = await gather_pr_context(pr_url, token)
    
    print("Running 3 specialist agents in parallel")
    security, logic, test = await asyncio.gather(
        run_security_agent(context),
        run_logic_agent(context),
        run_test_agent(context)
    )
    
    # combining all issues
    all_issues = (
        security.get("issues", []) +
        logic.get("issues", []) +
        test.get("issues", [])
    )
    
    draft_review = {
        "summary": " ".join(filter(None, [
            security.get("summary", ""),
            logic.get("summary", ""),
            test.get("summary", "")
        ])),
        "risk_level": "HIGH" if any(
            i.get("severity") == "HIGH" for i in all_issues
        ) else "MEDIUM",
        "issues": all_issues,
        "suggestions": [],
        "test_cases_missing": [
            i["description"] for i in test.get("issues", [])
        ]
    }

    # ✅ Self-Critique Loop
    print("🔍 Running critic agent...")
    critique = await run_critic_agent(draft_review, context)
    
    # Critic ka refined output use karo
    final_issues = critique.get("approved_issues", all_issues)
    
    return {
        "summary": critique.get("final_summary", draft_review["summary"]),
        "risk_level": critique.get("final_risk_level", draft_review["risk_level"]),
        "issues": final_issues,
        "suggestions": [
            f"Fix: {i['description']}"
            for i in final_issues
            if i.get("severity") == "HIGH"
        ],
        "test_cases_missing": [
            i["description"]
            for i in final_issues
            if i.get("type") == "MISSING_TEST"
        ]
    }

    
async def run_critic_agent(draft_review: dict, context: dict):
    diff_summary = json.dumps(context["diff"], indent=2)
    draft = json.dumps(draft_review, indent=2)
    
    messages = [
        {
            "role": "system",
            "content": """ Tu ek strict senior engineering manager hai.
            Tujhe ek AI agent ka draft code review evaluate karna hai.
            
            Yeh check karo har issue ke liye:
            1. Kya yeh issue actually exist karta hai diff mein? (False positive toh nahi?)
            2. Kya severity sahi hai? (Low ko High toh nahi bola?)
            3. Kya description accurate hai?
            4. Koi important issue miss toh nahi hua?
            
            Output SIRF JSON mein de, koi extra bakchodi nahi:
            {
                "approved_issues": [
                    {
                        "type": "SECURITY/LOGIC/MISSING_TEST",
                        "severity": "HIGH/MEDIUM/LOW",
                        "file": "filename",
                        "description": "refined description"
                    }
                ],
                "removed_issues": ["reason 1", "reason 2"],
                "added_issues": [].
                "final_summary": "refined 2-3 lines summary".
                "final_risk_level": "HIGH/MEDIUM/LOW"
            }"""
        },
        {
            "role": "user",
            "content": f"""Draft Review:
            {draft}
            
            Actual PR Diff (gorund truth):
            {diff_summary[:3000]}
            
            Is draft review ko validate karo -
            false positives hata, severity fix karo"""
        }
    ]
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0,
        max_tokens=1000
    )
    
    result = response.choices[0].message.content
    return parse_llm_json(result, "critic")

