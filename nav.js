// 需求链平台 - 共享导航脚本 v2（统一全站导航）
// 根据登录状态显示/隐藏导航项
(function(){
  var PAGES = {
    main: [
      { href: "/demand_square.html", label: "需求广场" },
      { href: "/suppliers.html", label: "供应商" },
      { href: "/forum.html", label: "论坛" },
      { href: "/docs/tutorial.html", label: "教程" },
    ],
    tools: [
      { href: "/flywheel_dashboard.html", label: "飞轮" },
      { href: "/global_search.html", label: "全局搜索" },
      { href: "/targeted_demand.html", label: "定向需求" },
      { href: "/discovered_demands.html", label: "发现需求" },
      { href: "/batch_export.html", label: "批量导出" },
      { href: "/timeline.html", label: "动态" },
      { href: "/leaderboard.html", label: "排行榜" },
      { href: "/zones.html", label: "专区" },
      { href: "/tools_extra.html", label: "翻译·搜索·审核" },
      { href: "/api_docs.html", label: "API文档" },
    ],
  };

  function esc(s) { return String(s||'').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  function buildNavLinks(loggedIn) {
    var html = '';
    // Main pages
    PAGES.main.forEach(function(p) {
      html += '<a href="' + p.href + '">' + esc(p.label) + '</a>';
    });
    // Tools dropdown or inline (show fewer when not logged in)
    if (loggedIn) {
      PAGES.tools.forEach(function(p) {
        html += '<a href="' + p.href + '">' + esc(p.label) + '</a>';
      });
    } else {
      // Show just a few tools for non-logged-in
      html += '<a href="/api_docs.html">API文档</a>';
    }
    return html;
  }

  function updateNav() {
    var nav = document.querySelector('nav');
    if (!nav) return;
    
    var linksDiv = nav.querySelector('.links');
    if (!linksDiv) return;
    
    var session = localStorage.getItem('dc_session');
    var user = null;
    try { user = JSON.parse(session); } catch(e) {}
    
    var loggedIn = !!(user && user.email);
    var links = buildNavLinks(loggedIn);
    
    if (loggedIn) {
      links += '<a href="profile.html" class="user-info" style="display:inline-flex;align-items:center;gap:6px;font-size:14px;color:var(--text);text-decoration:none;margin-left:4px">' +
        '<span>' + esc(user.name || user.email) + '</span></a>' +
        '<a href="#" onclick="localStorage.removeItem(\'dc_session\');location.reload()" style="font-size:13px;color:var(--ts);text-decoration:none">退出</a>';
    } else {
      links += '<a href="/login.html" class="btn-nav">登录</a>';
    }
    
    linksDiv.innerHTML = links;
  }
  
  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateNav);
  } else {
    updateNav();
  }
})();

// ── 全局错误处理 ────────────────────────────────────────────
window.onerror = function(msg, source, line, col, err) {
  console.error("[Global] " + msg, source + ":" + line);
  return true;
};

window.addEventListener("unhandledrejection", function(e) {
  console.error("[Global] Unhandled Promise rejection:", e.reason);
  e.preventDefault();
});

// 统一错误提示
function showError(containerId, message) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div class="msg msg-err" style="margin:8px 0;padding:10px 14px;border-radius:8px">' +
    encodeHTML(message) + '</div>';
}

function encodeHTML(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
