"""
将 JSON 爬取数据通过 MCP 工具插入服务器
Usage: python scripts/insert_via_mcp.py crawled_demands_20260611_122324.json [crawled_suppliers_20260611_122324.json]
"""

import http.client
import json
import sys
import re
import time


MCP_HOST = "8.154.26.92"
MCP_PORT = 8000

# Registered crawler user credentials
SESSION_TOKEN = "041b41aa424b1f73c84ed9918cd52255"
HUMAN_ID = "01KTTFE00RSRAA2V2RW7FJY4QG"
AGENT_ID = "01KTTFE00RXZWRVYVDNKKWQ2EF"


class MCPClient:
    def __init__(self):
        self.sse_conn = None
        self.sse_resp = None
        self.session_endpoint = None

    def connect(self, timeout=15):
        self.sse_conn = http.client.HTTPConnection(MCP_HOST, MCP_PORT, timeout=timeout)
        self.sse_conn.request("GET", "/sse")
        self.sse_resp = self.sse_conn.getresponse()
        for _ in range(100):
            line = self.sse_resp.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("data: ") and "session_id" in line:
                self.session_endpoint = line[6:].strip()
                return True
        return False

    def send(self, msg):
        payload = json.dumps(msg).encode("utf-8")
        pc = http.client.HTTPConnection(MCP_HOST, MCP_PORT, timeout=10)
        pc.request("POST", self.session_endpoint, body=payload,
                   headers={"Content-Type": "application/json"})
        pr = pc.getresponse()
        pr.read()
        pc.close()

    def recv(self, timeout=15):
        import select
        import socket
        while True:
            try:
                # Use socket timeout instead
                sock = self.sse_resp.fp.raw._sock if hasattr(self.sse_resp.fp, 'raw') else self.sse_resp.fp
                sock.settimeout(timeout)
                line = self.sse_resp.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("data: "):
                    return json.loads(line[6:])
            except socket.timeout:
                return {"error": "timeout"}
            except Exception as e:
                return {"error": str(e)}

    def initialize(self):
        if not self.connect():
            raise Exception("Failed to connect to SSE")
        self.send({"jsonrpc": "2.0", "id": "i1", "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "dc-crawler", "version": "1.0"}}})
        self.recv()
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call_tool(self, name, args):
        """Call an MCP tool and return the result."""
        req_id = name[:6] + "001"
        self.send({"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
                    "params": {"name": name, "arguments": args}})
        r = self.recv()
        if "error" in r:
            return {"success": False, "error": r["error"]}
        content = r.get("result", {}).get("content", [])
        texts = [c.get("text", "") for c in content if c.get("type") == "text"]
        combined = "".join(texts)
        return {"success": True, "text": combined}

    def close(self):
        if self.sse_conn:
            self.sse_conn.close()


DEMAND_SKIP_KEYWORDS = [
    "create an account", "terms of service", "privacy policy", "accessibility",
    "become a ", "meet the ", "sign in", "login", "register", "copyright",
    "all rights reserved", "powered by", "website usage", "report a website",
    "partner with us", "branches of government", "directory of",
    "feature articles", "www.", "http://", "https://",
    "grand challenges", "areas of impact",
]


def is_demand_valid(item):
    title = (item.get("title") or item.get("name") or "").lower()
    body = (item.get("body") or item.get("description") or "").lower()
    text = title + " " + body
    for kw in DEMAND_SKIP_KEYWORDS:
        if kw in text:
            return False
    if len(title.strip()) < 10:
        return False
    return True


SUPPLIER_SKIP_KEYWORDS = [
    "create an account", "terms", "privacy", "market landscape",
    "top 10", "top 53", "top 55", "top 20", "top 100",
    "hydrogen fuel startups in", "e-fuel startups", "methanol fuel startups",
    "ammonia fuel startups", "electric vehicle charging startups",
    "battery swapping startups", "energy startups by",
]

def is_supplier_valid(item):
    name = (item.get("name") or item.get("title") or "").lower()
    for kw in SUPPLIER_SKIP_KEYWORDS:
        if kw in name:
            return False
    if len(name.strip()) < 3:
        return False
    return True


def insert_demands(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        demands = json.load(f)
    
    valid = [d for d in demands if is_demand_valid(d)]
    print(f"\n=== Inserting demands ===")
    print(f"Total collected: {len(demands)}, Valid: {len(valid)}, Skipped: {len(demands)-len(valid)}")
    
    client = MCPClient()
    client.initialize()
    
    ok = 0
    dup = 0
    fail = 0
    
    for d in valid:
        raw_text = d.get("body") or d.get("title", "")
        category = d.get("category", "其他")
        
        result = client.call_tool("publish_demand", {
            "user_id": "crawler@demandchain.com",
            "raw_text": raw_text,
            "session_token": SESSION_TOKEN,
            "lang": "zh",
        })
        
        if result["success"]:
            ok += 1
            print(f"  ✅ OK: {d.get('title','')[:40]}...")
        else:
            err_msg = str(result.get("error", ""))
            if "already exists" in err_msg.lower() or "duplicate" in err_msg.lower() or "unique" in err_msg.lower():
                dup += 1
                print(f"  🔁 DUP: {d.get('title','')[:40]}...")
            else:
                fail += 1
                print(f"  ❌ FAIL: {d.get('title','')[:30]}... -> {err_msg[:80]}")
        
        time.sleep(0.3)  # Rate limiting
    
    print(f"\n  📊 Results: {ok} inserted, {dup} duplicates, {fail} failed")
    client.close()
    return ok, dup, fail


def insert_suppliers(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        suppliers = json.load(f)
    
    valid = [s for s in suppliers if is_supplier_valid(s)]
    print(f"\n=== Inserting suppliers ===")
    print(f"Total collected: {len(suppliers)}, Valid: {len(valid)}, Skipped: {len(suppliers)-len(valid)}")
    
    ok = 0
    fail = 0
    
    client = MCPClient()
    client.initialize()
    
    for s in valid:
        name = s.get("name") or s.get("title", "")
        desc = s.get("description", "")
        category = s.get("category", "其他")
        
        # register_capability requires session_token
        result = client.call_tool("register_capability", {
            "session_token": SESSION_TOKEN,
            "user_id": "crawler@demandchain.com",
            "description": f"[Auto Crawler] {name}: {desc}",
        })
        
        if result["success"]:
            ok += 1
            print(f"  ✅ OK: {name[:40]}...")
        else:
            err_msg = str(result.get("error", ""))
            fail += 1
            print(f"  ❌ FAIL: {name[:30]}... -> {err_msg[:80]}")
        
        time.sleep(0.3)
    
    print(f"\n  📊 Results: {ok} registered, {fail} failed")
    client.close()
    return ok, fail


if __name__ == "__main__":
    demands_file = None
    suppliers_file = None
    
    for arg in sys.argv[1:]:
        if "demand" in arg.lower():
            demands_file = arg
        else:
            suppliers_file = arg
    
    if demands_file:
        insert_demands(demands_file)
    if suppliers_file:
        insert_suppliers(suppliers_file)
    
    if not demands_file and not suppliers_file:
        # Default: find latest files
        import glob, os
        files = sorted(glob.glob("crawled_*.json"))
        for f in files:
            if "demand" in f:
                demands_file = f
            elif "supplier" in f:
                suppliers_file = f
        
        if demands_file or suppliers_file:
            print(f"Using files: demands={demands_file}, suppliers={suppliers_file}")
            if demands_file:
                insert_demands(demands_file)
            if suppliers_file:
                insert_suppliers(suppliers_file)
        else:
            print("No JSON files found. Run auto_crawler.py first.")
