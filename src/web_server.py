"""
静态文件服务器 — 服务需求链平台的17个 HTML 页面。
运行在端口 80，供人类浏览。
"""
import os
import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

WEB_ROOT = "/app"

async def serve_file(request, filename):
    """服务单个 HTML 文件"""
    path = os.path.join(WEB_ROOT, filename)
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse({"error": "not found"}, status_code=404)

async def index(request):
    return await serve_file(request, "index.html")

async def login_page(request):
    return await serve_file(request, "login.html")

async def demand_square(request):
    return await serve_file(request, "demand_square.html")

async def zones(request):
    return await serve_file(request, "zones.html")

async def forum(request):
    return await serve_file(request, "forum.html")

async def chat(request):
    return await serve_file(request, "chat.html")

async def timeline(request):
    return await serve_file(request, "timeline.html")

async def leaderboard(request):
    return await serve_file(request, "leaderboard.html")

async def global_search(request):
    return await serve_file(request, "global_search.html")

async def targeted(request):
    return await serve_file(request, "targeted_demand.html")

async def discovered(request):
    return await serve_file(request, "discovered_demands.html")

async def public_demand(request):
    return await serve_file(request, "public_demand.html")

async def batch_export(request):
    return await serve_file(request, "batch_export.html")

async def api_docs(request):
    return await serve_file(request, "api_docs.html")

async def tools_extra(request):
    return await serve_file(request, "tools_extra.html")

async def tutorial(request):
    return await serve_file(request, "docs/tutorial.html")


async def static_file(request):
    """Serve any static file from the web root."""
    path = request.path_params.get("path", "")
    if ".." in path:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    filepath = os.path.join(WEB_ROOT, path)
    if os.path.isfile(filepath):
        return FileResponse(filepath)
    return JSONResponse({"error": "not found"}, status_code=404)


routes = [
    Route("/", index),
    Route("/login.html", login_page),
    Route("/index.html", index),
    Route("/demand_square.html", demand_square),
    Route("/zones.html", zones),
    Route("/forum.html", forum),
    Route("/chat.html", chat),
    Route("/timeline.html", timeline),
    Route("/leaderboard.html", leaderboard),
    Route("/global_search.html", global_search),
    Route("/targeted_demand.html", targeted),
    Route("/discovered_demands.html", discovered),
    Route("/public_demand.html", public_demand),
    Route("/batch_export.html", batch_export),
    Route("/api_docs.html", api_docs),
    Route("/tools_extra.html", tools_extra),
    Route("/docs/tutorial.html", tutorial),
    Route("/{path:path}", static_file),
]

app = Starlette(routes=routes)

def run():
    uvicorn.run(app, host="0.0.0.0", port=80, log_level="info")

if __name__ == "__main__":
    run()
