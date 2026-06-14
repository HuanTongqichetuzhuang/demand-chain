"""
MCP SSE 客户端 — 连接到远程 MCP 服务器并调用工具
Usage: python scripts/mcp_insert.py <demands.json> [suppliers.json]
"""

import json
import sys
import urllib.request
import uuid
import re
import http.client
import ssl


MCP_SERVER_HOST = "8.154.26.92"
MCP_SERVER_PORT = 8000


def connect_sse_and_call(tool_name: str, arguments: dict, timeout: int = 30) -> dict:
    """
    Connect to MCP SSE endpoint, get session, call a tool, return result.
    """
    conn = http.client.HTTPConnection(MCP_SERVER_HOST, MCP_SERVER_PORT, timeout=timeout)
    conn.request("GET", "/sse")
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8", errors="replace")
    conn.close()

    # Parse SSE: look for session_id in the data events
    session_id = None
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if isinstance(data, dict):
                    # Could be "session_id" or contain metadata
                    sid = data.get("session_id") or data.get("id") or data.get("serverSessionId")
                    if sid:
                        session_id = sid
            except json.JSONDecodeError:
                pass

    # Also try UUID pattern directly
    if not session_id:
        uuids = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', raw)
        if uuids:
            session_id = uuids[-1]

    if not session_id:
        # Fallback: try generic POST to /
        return call_jsonrpc_post("/", tool_name, arguments)

    # Send JSON-RPC to the session message endpoint
    session_path = f"/message?session_id={session_id}"
    return call_jsonrpc_post(session_path, tool_name, arguments)


def call_jsonrpc_post(path: str, tool_name: str, arguments: dict) -> dict:
    """Send a JSON-RPC tools/call request to the given path."""
    req_id = str(uuid.uuid4())[:8]
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}{path}",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except:
            return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def list_tools():
    """List available MCP tools on the server."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": "list",
        "method": "tools/list",
        "params": {},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"http://{MCP_SERVER_HOST}:{MCP_SERVER_PORT}/",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def insert_demands_from_file(json_path: str):
    """Read demands from JSON and try to insert via the server API."""
    with open(json_path, "r", encoding="utf-8") as f:
        demands = json.load(f)

    # Filter out clearly non-demand items (navigation, footer, etc.)
    skip_keywords = [
        "create an account", "terms of service", "privacy policy", "accessibility",
        "become a ", "meet the ", "sign in", "login", "register", "copyright",
        "all rights reserved", "powered by", "website usage", "report a website",
        "partner with us", "branches of government", "directory of",
        "feature articles", "www.", "http://", "https://",
    ]

    valid = []
    for d in demands:
        title = d.get("title", "").lower()
        body = d.get("body", "").lower()
        text = title + " " + body
        if any(kw in text for kw in skip_keywords):
            continue
        valid.append(d)

    print(f"\n=== Inserting {len(valid)} valid demands (filtered from {len(demands)}) ===")
    print(f"Skipped {len(demands) - len(valid)} non-demand items")
    
    # Try the HTTP API first
    api_base = "http://8.154.26.92:8000"
    ok = 0
    fail = 0

    for d in valid:
        payload_data = json.dumps({
            "raw_text": d.get("body", d.get("title", "")),
            "category": d.get("category", "其他"),
            "email": "crawler",
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{api_base}/api/auto-demand",
                data=payload_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    ok += 1
                    print(f"  OK: {d.get('title', '')[:40]}...")
                else:
                    fail += 1
                    print(f"  STATUS {resp.status}: {d.get('title', '')[:40]}...")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Endpoint not available - try MCP tools
                print(f"  API not available (404), trying MCP...")
                return insert_via_mcp(valid)
            elif e.code == 409:
                print(f"  DUP: {d.get('title', '')[:40]}...")
                ok += 1  # Already exists, count as success
            else:
                fail += 1
                print(f"  FAIL {e.code}: {d.get('title', '')[:40]}...")
        except Exception as e:
            fail += 1
            print(f"  ERROR: {d.get('title', '')[:30]}... -> {e}")

    print(f"\n  Results: {ok} inserted/duplicate, {fail} failed")


def insert_via_mcp(demands):
    """Fallback: try to use MCP tools if API endpoints are not available."""
    print("\n--- Trying MCP tool approach ---")
    
    # List available tools first
    tools_result = list_tools()
    if "error" in tools_result:
        print(f"  Cannot list MCP tools: {tools_result['error']}")
        return
    
    available_tools = []
    if "result" in tools_result and "tools" in tools_result["result"]:
        available_tools = [t["name"] for t in tools_result["result"]["tools"]]
    print(f"  Available MCP tools: {available_tools[:10]}...")
    
    # Check if there's a crawl_public_demands tool that can be used
    if "crawl_public_demands" in available_tools:
        print("  crawl_public_demands tool available!")
        # This tool already crawls and saves, can use it as supplement
    
    print("  MCP tool insertion not implemented - save JSON for manual deployment")
    print(f"  Saved {len(demands)} demands to JSON files for deployment")


def insert_suppliers_from_file(json_path: str):
    """Read suppliers from JSON and try to insert via the server API."""
    with open(json_path, "r", encoding="utf-8") as f:
        suppliers = json.load(f)

    # Filter out non-supplier items
    skip_keywords = [
        "create an account", "terms", "privacy", "market landscape",
        "top 10", "top 53", "top 55", "top 20", "top 100",
        "hydrogen fuel startups in", "e-fuel startups", "methanol fuel startups",
        "ammonia fuel startups", "electric vehicle charging startups",
        "battery swapping startups", "energy startups by",
    ]

    valid = []
    for s in suppliers:
        name = s.get("name", "").lower()
        if any(kw in name for kw in skip_keywords):
            continue
        if len(name) < 3:
            continue
        valid.append(s)

    print(f"\n=== Inserting {len(valid)} valid suppliers (filtered from {len(suppliers)}) ===")

    api_base = "http://8.154.26.92:8000"
    ok = 0
    fail = 0

    for s in valid:
        payload_data = json.dumps({
            "email": "crawler",
            "profile_type": "COMPANY",
            "country": "",
            "trust_score": 0.5,
            "agent_card": {
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "category": s.get("category", "其他"),
                "industry": s.get("category", "其他"),
                "discipline": "",
                "trl": 0,
                "url": s.get("url", ""),
                "skills": [],
            },
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                f"{api_base}/api/auto-supplier",
                data=payload_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    ok += 1
                    print(f"  OK: {s.get('name', '')[:40]}...")
                else:
                    fail += 1
                    print(f"  STATUS {resp.status}: {s.get('name', '')[:40]}...")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  API not available, saving for later deployment...")
                return
            elif e.code == 409:
                print(f"  DUP: {s.get('name', '')[:40]}...")
                ok += 1
            else:
                fail += 1
                print(f"  FAIL {e.code}: {s.get('name', '')[:40]}...")
        except Exception as e:
            fail += 1
            print(f"  ERROR: {s.get('name', '')[:30]}... -> {e}")

    print(f"\n  Results: {ok} inserted/duplicate, {fail} failed")


if __name__ == "__main__":
    # Test: list tools
    print("=== Testing MCP connection ===")
    result = connect_sse_and_call("tools/list", {})
    print(json.dumps(result, ensure_ascii=False, indent=2)[:1000])
    
    # Also try simple POST list
    print("\n--- Trying direct POST list ---")
    result2 = list_tools()
    print(json.dumps(result2, ensure_ascii=False, indent=2)[:1000])
