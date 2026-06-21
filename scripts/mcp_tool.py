"""
MCP SSE 工具调用器 — 完整的 MCP 协议握手
Usage: python scripts/mcp_tool.py list
       python scripts/mcp_tool.py call <tool_name> '<json_args>'
"""

import http.client
import json
import uuid
import sys
import threading
import queue


MCP_HOST = "demand-chain.duckdns.org"
MCP_PORT = 8000


class MCPClient:
    def __init__(self):
        self.sse_conn = None
        self.sse_resp = None
        self.session_endpoint = None
        self.results = queue.Queue()
        self._running = True

    def connect(self, timeout=15):
        """Connect to SSE endpoint and get session."""
        self.sse_conn = http.client.HTTPConnection(MCP_HOST, MCP_PORT, timeout=timeout)
        self.sse_conn.request("GET", "/sse")
        self.sse_resp = self.sse_conn.getresponse()

        for _ in range(100):
            line = self.sse_resp.readline().decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:].strip()
                if "session_id" in data_str:
                    self.session_endpoint = data_str
                    return True
        return False

    def send_request(self, method, params=None, req_id=None):
        """Send a JSON-RPC request via POST to the session endpoint."""
        if req_id is None:
            req_id = str(uuid.uuid4())[:8]
        
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            msg["params"] = params

        payload = json.dumps(msg).encode("utf-8")
        
        post_conn = http.client.HTTPConnection(MCP_HOST, MCP_PORT, timeout=10)
        post_conn.request("POST", self.session_endpoint, body=payload,
                          headers={"Content-Type": "application/json"})
        post_resp = post_conn.getresponse()
        post_resp.read()  # consume
        post_conn.close()
        
        return req_id

    def wait_for_response(self, req_id, timeout=15):
        """Wait for a response with matching ID from SSE stream."""
        while self._running:
            try:
                line = self.sse_resp.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    msg_id = data.get("id")
                    if msg_id == req_id:
                        if "result" in data:
                            return {"success": True, "data": data["result"]}
                        elif "error" in data:
                            return {"success": False, "error": data["error"]}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "Connection closed"}

    def close(self):
        self._running = False
        if self.sse_conn:
            self.sse_conn.close()

    def call_tool(self, tool_name, arguments=None) -> dict:
        """
        Full MCP protocol: initialize → get tools → call tool.
        """
        if not self.session_endpoint:
            if not self.connect():
                return {"success": False, "error": "Failed to connect to SSE"}

        # Step 1: Initialize
        init_id = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "dc-crawler", "version": "1.0"}
        })
        result = self.wait_for_response(init_id)
        if not result["success"]:
            return result
        print(f"  [MCP] Initialized: protocol={result['data'].get('protocolVersion', '?')}")

        # Step 2: Send initialized notification (no response expected)
        self.send_request("notifications/initialized")
        
        # Step 3: Send tools/list
        list_id = self.send_request("tools/list", {})
        result = self.wait_for_response(list_id)
        if not result["success"]:
            return result
        
        tools = result["data"].get("tools", [])
        print(f"  [MCP] Available tools: {[t['name'] for t in tools]}")

        # Step 4: Call the specific tool
        if tool_name == "list":
            return result  # Return the list result

        call_id = self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {}
        })
        return self.wait_for_response(call_id)


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/mcp_tool.py list")
        print("  python scripts/mcp_tool.py call <tool_name> [json_args]")
        return

    client = MCPClient()
    command = sys.argv[1]

    try:
        if command == "list":
            result = client.call_tool("list")
            if result["success"]:
                tools = result["data"].get("tools", [])
                print(f"\n=== {len(tools)} tools available ===")
                for t in tools:
                    print(f"\n  📌 {t.get('name')}")
                    print(f"     {t.get('description', '')[:120]}")
                    if "inputSchema" in t:
                        props = t["inputSchema"].get("properties", {})
                        for p_name, p_info in props.items():
                            print(f"     - {p_name}: {p_info.get('type', 'any')}")
            else:
                print(f"Error: {result.get('error')}")

        elif command == "call":
            if len(sys.argv) < 3:
                print("Missing tool name")
                return
            tool_name = sys.argv[2]
            args = {}
            if len(sys.argv) > 3:
                try:
                    args = json.loads(sys.argv[3])
                except json.JSONDecodeError:
                    print(f"Invalid JSON: {sys.argv[3]}")
                    return
            result = client.call_tool(tool_name, args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()


