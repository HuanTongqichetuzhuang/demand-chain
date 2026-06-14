// 需求链平台 — 统一导航脚本 v4
// 接管所有页面的导航，无论登录状态，确保全站导航一致
(function() {
  'use strict';

  // 注入 CSS 变量覆盖（若页面内联 :root 用了旧值）
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
    'nav{backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);background:var(--bg-gradient);background:rgba(10,10,26,0.7);border-bottom:1px solid var(--border-light);position:sticky;top:0;z-index:100}' +
    'nav .links a{border-radius:8px;padding:6px 14px;transition:all 0.25s ease}' +
    'nav .links a:hover{background:rgba(124,110,240,0.08);color:var(--text)}' +
    'nav .links .btn-nav{background:linear-gradient(135deg,var(--purple),var(--purple-dark));box-shadow:0 2px 12px var(--glow-purple);padding:7px 20px;font-weight:600}' +
    'nav .links .btn-nav:hover{transform:translateY(-1px);box-shadow:0 4px 20px var(--glow-purple)}' +
    '.card{border-radius:16px;transition:all 0.25s ease}.card:hover{box-shadow:0 8px 32px rgba(0,0,0,0.2);transform:translateY(-2px)}' +
    '::-webkit-scrollbar{width:8px}::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}' +
    '::selection{background:rgba(124,110,240,0.3);color:#fff}';
    document.head.appendChild(s);
  }

  // 注入背景光晕 + 强制 body 渐变背景（内联样式确保优先）
  if (!document.querySelector('.bg-glow')) {
    var g1 = document.createElement('div'); g1.className = 'bg-glow'; document.body.appendChild(g1);
    var g2 = document.createElement('div'); g2.className = 'bg-glow-2'; document.body.appendChild(g2);
  }
  document.body.style.background = 'linear-gradient(135deg,#0a0a1a 0%,#12122a 50%,#0d0d20 100%)';

  function esc(s) { return String(s || '').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  // 统一导航
  function renderNav() {
    var nav = document.querySelector('nav');
    if (!nav) return;

    var session = null;
    try { session = JSON.parse(localStorage.getItem('dc_session')); } catch(e) {}
    var loggedIn = !!(session && session.email);

    // 标准导航链接（所有页面一致）
    var links = [
      { href: '/demand_square.html', label: '需求广场' },
      { href: '/suppliers.html', label: '供应商' },
      { href: '/forum.html', label: '论坛' },
      { href: '/docs/tutorial.html', label: '教程' },
      { href: '/api_docs.html', label: 'API文档' },
    ];

    var brandHtml = '<a class="brand" href="/"><img src="/logo.jpg" alt="">需求链平台</a>';
    var linksHtml = '<div class="links">';
    links.forEach(function(l) {
      linksHtml += '<a href="' + l.href + '">' + esc(l.label) + '</a>';
    });
    if (loggedIn) {
      linksHtml += '<a href="/flywheel_dashboard.html" style="font-size:12.5px;opacity:0.7">飞轮</a>';
      linksHtml += '<a href="/profile.html" class="user-info" style="display:inline-flex;align-items:center;gap:4px;font-size:14px;color:var(--text);text-decoration:none;margin-left:4px">' +
        '<span>' + esc(session.name || session.email) + '</span></a>';
      linksHtml += '<a href="#" onclick="localStorage.removeItem(\'dc_session\');location.reload()" style="font-size:13px;color:var(--ts);text-decoration:none">退出</a>';
    } else {
      linksHtml += '<a href="/login.html" class="btn-nav">登录</a>';
    }
    linksHtml += '</div>';

    nav.innerHTML = brandHtml + linksHtml;
  }

  // 立即执行
  renderNav();
})();
