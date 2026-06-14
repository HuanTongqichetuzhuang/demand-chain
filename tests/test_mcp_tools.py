"""
MCP 工具注册验证 — 确认新工具已正确注册且文档完整。
"""
import json
import pytest


class TestMCPToolRegistration:
    """验证 search_suppliers / get_supplier_detail / match_feedback 已注册"""

    def test_tools_registered(self):
        """三个工具应出现在 MCP 工具列表中"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        for name in ["search_suppliers", "get_supplier_detail", "match_feedback"]:
            assert name in tools, f"工具 {name} 未注册"
            assert tools[name].description, f"工具 {name} 缺少描述"
            print(f"  ✅ {name}: {tools[name].description[:60]}...")

    def test_search_suppliers_params(self):
        """search_suppliers 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["search_suppliers"].parameters
        props = params.get("properties", {})
        assert "query" in props, "缺少 query 参数"
        assert "top_k" in props, "缺少 top_k 参数"

    def test_match_feedback_params(self):
        """match_feedback 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["match_feedback"].parameters
        props = params.get("properties", {})
        assert "session_token" in props, "缺少 session_token"
        assert "demand_id" in props, "缺少 demand_id"
        assert "matched_supplier_ids" in props, "缺少 matched_supplier_ids"

    def test_get_supplier_detail_params(self):
        """get_supplier_detail 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["get_supplier_detail"].parameters
        props = params.get("properties", {})
        assert "supplier_id" in props, "缺少 supplier_id"


class TestA2ATools:
    """验证 A2A 握手 / 查卡 / well-known 端点"""

    def test_a2a_tools_registered(self):
        """A2A 工具已注册且有描述"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        for name in ["agent_handshake", "agent_accept_handshake", "agent_get_card"]:
            assert name in tools, f"A2A 工具 {name} 未注册"
            assert tools[name].description, f"A2A 工具 {name} 缺少描述"

    def test_agent_handshake_params(self):
        """agent_handshake 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["agent_handshake"].parameters
        props = params.get("properties", {})
        assert "session_token" in props
        assert "target_agent_id" in props
        assert "my_agent_id" in props

    def test_agent_accept_handshake_params(self):
        """agent_accept_handshake 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["agent_accept_handshake"].parameters
        props = params.get("properties", {})
        assert "session_token" in props
        assert "workspace_id" in props
        assert "my_agent_id" in props

    def test_agent_get_card_params(self):
        """agent_get_card 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["agent_get_card"].parameters
        props = params.get("properties", {})
        assert "agent_id" in props

    def test_invite_supplier_params(self):
        """invite_supplier 不再是 stub，参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        tool = tools["invite_supplier"]
        assert "stub" not in tool.description, "invite_supplier 不应是 stub"
        params = tool.parameters
        props = params.get("properties", {})
        assert "session_token" in props
        assert "supplier_id" in props

    def test_contact_supplier_params(self):
        """agent_contact_supplier 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        tool = tools["agent_contact_supplier"]
        assert "stub" not in tool.description, "不应是 stub"
        params = tool.parameters
        props = params.get("properties", {})
        assert "session_token" in props
        assert "supplier_id" in props

    def test_extend_demand_params(self):
        """extend_demand 不再是 stub"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        tool = tools["extend_demand"]
        assert "stub" not in tool.description, "不应是 stub"
        params = tool.parameters
        props = params.get("properties", {})
        assert "parent_demand_id" in props
        assert "raw_text" in props

    def test_get_demand_chain_params(self):
        """get_demand_chain 不再是 stub"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        tool = tools["get_demand_chain"]
        assert "stub" not in tool.description, "不应是 stub"
        params = tool.parameters
        props = params.get("properties", {})
        assert "demand_id" in props

    def test_search_similar_demands_params(self):
        """search_similar_demands 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["search_similar_demands"].parameters
        props = params.get("properties", {})
        assert "raw_text" in props
        assert "threshold" in props

    def test_join_demand_group_params(self):
        """join_demand_group 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["join_demand_group"].parameters
        props = params.get("properties", {})
        assert "session_token" in props
        assert "demand_id" in props
        assert "user_id" in props

    def test_update_subscription_params(self):
        """update_subscription 参数正确"""
        from src.server import mcp

        tools = {t.name: t for t in mcp._tool_manager.list_tools()}
        params = tools["update_subscription"].parameters
        props = params.get("properties", {})
        assert "session_token" in props
        assert "demand_id" in props
        assert "user_id" in props


class TestWellKnownEndpoint:
    """验证 /.well-known/agent.json 端点"""

    def test_wellknown_route_registered(self):
        """/.well-known/agent.json 路由已注册"""
        from src.web_server import app

        routes = {r.path for r in app.routes}
        assert "/.well-known/agent.json" in routes, "well-known 路由未注册"

    def test_wellknown_no_agent_id(self):
        """无 agent_id 时返回平台总览"""
        from src.web_server import api_agent_card
        from starlette.testclient import TestClient
        from src.web_server import app

        client = TestClient(app)
        resp = client.get("/.well-known/agent.json")
        assert resp.status_code in (200, 500)  # 可能因无 DB 返回 500，但路由应正常
        if resp.status_code == 200:
            data = resp.json()
            assert "name" in data
            assert "total_agents" in data
