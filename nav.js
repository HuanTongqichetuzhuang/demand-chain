// 需求链平台 - 共享导航脚本
// 检查登录状态，更新导航栏
(function(){
  function updateNav() {
    var nav = document.querySelector('nav');
    if (!nav) return;
    
    var linksDiv = nav.querySelector('.links');
    if (!linksDiv) return;
    
    var session = localStorage.getItem('dc_session');
    var user = null;
    try { user = JSON.parse(session); } catch(e) {}
    
    if (user && user.email) {
      // Logged in: replace login button with user info
      linksDiv.innerHTML = 
        '<a href="/demand_square.html">需求广场</a>' +
        '<a href="/suppliers.html">供应商</a>' +
        '<a href="/forum.html">论坛</a>' +
        '<a href="/docs/tutorial.html">教程</a>' +
        '<a href="/flywheel_dashboard.html">飞轮</a>' +
        '<a href="profile.html" class="user-info" style="display:flex;align-items:center;gap:6px;font-size:14px;color:var(--text);text-decoration:none">' +
        '<span>' + esc(user.name || user.email) + '</span></a>' +
        '<a href="#" onclick="localStorage.removeItem(\'dc_session\');location.reload()" style="font-size:13px;color:var(--ts);text-decoration:none">退出</a>';
    }
    // If not logged in, leave the default nav as-is (shows login button)
  }
  
  function esc(s) { return String(s||'').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  
  updateNav();
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

// 统一错误提示 — 在任何容器中显示错误信息
function showError(containerId, message) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '<div class="msg msg-err" style="margin:8px 0;padding:10px 14px;border-radius:8px">' +
    encodeHTML(message) + '</div>';
}

function encodeHTML(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
