// 需求链平台 — 统一导航脚本 v5
// 双重保障：立即执行 + DOM就绪后重试 + 监控DOM变化
(function() {
  'use strict';

  // 注入样式（只执行一次）
  if (!document.getElementById('dc-design-inject')) {
    var s = document.createElement('style');
    s.id = 'dc-design-inject';
    s.textContent = ':root{' +
      '--bg:#0a0a1a;--bg-gradient:linear-gradient(135deg,#0a0a1a 0%,#12122a 50%,#0d0d20 100%);' +
      '--card-bg:rgba(20,20,43,0.8);--card-bg-solid:#14142b;' +
      '--text:#e8e8f0;--ts:#9090b0;--muted:#8888aa;' +
      '--purple:#7c6ef0;--purple-light:#9b8ff5;--purple-dark:#5a4ed8;' +
      '--accent:#7c6ef0;' +
      '--border:rgba(42,42,74,0.6);--border-light:rgba(42,42,74,0.3);' +
      '--green:#00d4a0;--amber:#f0b429;--red:#e85454;--blue:#4a8cf7;' +
      '--radius:12px;--radius-sm:8px;--radius-lg:16px;' +
      '--shadow:0 4px 24px rgba(0,0,0,0.3);' +
      '--glow-purple:rgba(124,110,240,0.15);' +
      '--transition:0.25s cubic-bezier(0.4,0,0.2,1);' +
    '} body{background:var(--bg-gradient)}' +
    'nav{backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);background:rgba(10,10,26,0.7);border-bottom:1px solid var(--border-light);position:sticky;top:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:14px 28px;max-width:1140px;margin:0 auto}' +
    'nav .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:17px;color:var(--text);text-decoration:none}' +
    'nav .brand img{width:34px;height:34px;border-radius:8px;object-fit:cover}' +
    'nav .links{display:flex;gap:6px;align-items:center;flex-wrap:wrap}' +
    'nav .links a{font-size:13.5px;color:var(--ts);padding:6px 14px;border-radius:8px;transition:all 0.25s ease;text-decoration:none}' +
    'nav .links a:hover{background:rgba(124,110,240,0.08);color:var(--text)}' +
    'nav .links .btn-nav{background:linear-gradient(135deg,var(--purple),var(--purple-dark));box-shadow:0 2px 12px var(--glow-purple);padding:7px 20px;font-weight:600;color:#fff!important}' +
    'nav .links .btn-nav:hover{transform:translateY(-1px);box-shadow:0 4px 20px var(--glow-purple)}' +
    'nav .dropdown{position:relative;display:inline-flex;padding-bottom:12px;margin-bottom:-12px}' +
    'nav .dropdown-trigger{font-size:13.5px;color:var(--ts);padding:6px 14px;border-radius:8px;cursor:pointer;transition:all 0.25s ease;text-decoration:none;background:none;border:none;font-family:inherit}' +
    'nav .dropdown-trigger:hover{background:rgba(124,110,240,0.08);color:var(--text)}' +
    'nav .dropdown-menu{position:absolute;top:100%;right:0;margin-top:0;min-width:160px;background:var(--card-bg-solid);border:1px solid var(--border);border-radius:12px;padding:6px;box-shadow:0 8px 32px rgba(0,0,0,0.4);display:none;z-index:200}' +
    'nav .dropdown:hover .dropdown-menu{display:block}' +
    'nav .dropdown-menu a{display:block;font-size:13px;color:var(--ts);padding:8px 12px;border-radius:8px;text-decoration:none;transition:all 0.15s ease}' +
    'nav .dropdown-menu a:hover{background:rgba(124,110,240,0.12);color:var(--text)}' +
    '.notif-bell{position:relative;display:inline-flex;align-items:center;padding:6px 10px!important;font-size:16px!important}' +
    '.notif-bell .badge{position:absolute;top:-2px;right:-2px;background:var(--red);color:#fff;font-size:10px;font-weight:700;min-width:16px;height:16px;border-radius:8px;display:flex;align-items:center;justify-content:center;padding:0 4px}' +
    '.card{border-radius:16px;transition:all 0.25s ease}.card:hover{box-shadow:0 8px 32px rgba(0,0,0,0.2);transform:translateY(-2px)}' +
    '::-webkit-scrollbar{width:8px}::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}' +
    '::selection{background:rgba(124,110,240,0.3);color:#fff}';
    document.head.appendChild(s);
  }

  // 注入背景光晕+强制渐变背景
  if (!document.querySelector('.bg-glow')) {
    var g1 = document.createElement('div'); g1.className = 'bg-glow'; document.body.appendChild(g1);
    var g2 = document.createElement('div'); g2.className = 'bg-glow-2'; document.body.appendChild(g2);
  }
  document.body.style.background = 'linear-gradient(135deg,#0a0a1a 0%,#12122a 50%,#0d0d20 100%)';

  function esc(s) { return String(s || '').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  // 渲染导航
  function renderNav() {
    var nav = document.querySelector('nav');
    if (!nav) {
      // 如果页面没有 <nav>，创建一个
      nav = document.createElement('nav');
      document.body.insertBefore(nav, document.body.firstChild);
    }

    var session = null;
    try { session = JSON.parse(localStorage.getItem('dc_session')); } catch(e) {}
    var loggedIn = !!(session && session.email);

    var brandHtml = '<a class="brand" href="/"><img src="/logo_small.png" width="34" height="34" style="width:34px;height:34px;border-radius:8px;object-fit:cover" alt="" loading="lazy">需求链平台</a>';
    var linksHtml = '<div class="links">';
    linksHtml += '<a href="/demand_square.html" style="font-weight:600;color:var(--text)!important">📋 发布需求</a>';
    linksHtml += '<a href="/suppliers.html" style="font-weight:600;color:var(--text)!important">🔍 找供应商</a>';
    linksHtml += '<a href="/forum.html" style="font-weight:600;color:var(--text)!important">💬 论坛</a>';
    linksHtml += '<span class="dropdown"><span class="dropdown-trigger">🔬 实验室 ▾</span><span class="dropdown-menu">';
    linksHtml += '<a href="/scientist_workbench.html">🔬 科研工作台</a>';
    linksHtml += '<a href="/flywheel_dashboard.html">⚙️ 数据飞轮</a>';
    linksHtml += '<a href="/docs/tutorial.html">📖 教程</a>';
    linksHtml += '<a href="/api_docs.html">📡 API文档</a>';
    linksHtml += '</span></span>';
    if (loggedIn) {
      linksHtml += '<a href="/notifications.html" class="notif-bell" id="notifBell" title="通知中心">🔔<span class="badge" id="notifBadge">0</span></a>';
      var avatarUrl = session.avatar || '';
      var avatarHtml = avatarUrl
        ? '<img src="'+avatarUrl+'" style="width:28px;height:28px;border-radius:50%;object-fit:cover;margin-right:4px;vertical-align:middle" loading="lazy">'
        : '';
      linksHtml += '<a href="/profile.html" style="display:inline-flex;align-items:center;gap:4px;font-size:14px;color:var(--text);margin-left:4px">' +
        avatarHtml + esc(session.name || session.email) + '</a>';
      linksHtml += '<a href="#" onclick="localStorage.removeItem(\'dc_session\');location.reload()" style="font-size:13px;color:var(--ts)">退出</a>';
    } else {
      linksHtml += '<a href="/login.html" class="btn-nav">登录</a>';
    }
    linksHtml += '</div>';

    nav.innerHTML = brandHtml + linksHtml;
  }

  // 立即执行（如果 DOM 已就绪）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderNav);
  } else {
    renderNav();
  }

  // 监控 DOM 变化，如果导航被篡改则重新渲染
  var observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(m) {
      if (m.type === 'childList' && m.target.tagName === 'NAV') {
        renderNav();
      }
    });
  });
  setTimeout(function() {
    var nav = document.querySelector('nav');
    if (nav) {
      observer.observe(nav, { childList: true, subtree: true });
    }
  }, 500);

  // 更新导航栏头像（profile.html 上传后调用）
  window.updateNav = function(displayName, avatarUrl) {
    var session = null;
    try { session = JSON.parse(localStorage.getItem('dc_session')); } catch(e) {}
    if (session && avatarUrl) {
      session.avatar = avatarUrl;
      localStorage.setItem('dc_session', JSON.stringify(session));
    }
    renderNav();
  };

  // 通知未读计数
  function updateNotifCount() {
    var session = null;
    try { session = JSON.parse(localStorage.getItem('dc_session')); } catch(e) {}
    if (!session || !session.email) return;
    var badge = document.getElementById('notifBadge');
    if (!badge) return;
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/api/notifications/unread-count?email=' + encodeURIComponent(session.email), true);
    xhr.onload = function() {
      if (xhr.status === 200) {
        try {
          var data = JSON.parse(xhr.responseText);
          var count = data.count || 0;
          badge.textContent = count;
          badge.style.display = count > 0 ? 'flex' : 'none';
        } catch(e) {}
      }
    };
    xhr.send();
  }

  // 首次加载后更新通知计数
  setTimeout(updateNotifCount, 1000);
  // 每30秒轮询
  setInterval(updateNotifCount, 30000);
})();

