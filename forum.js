// 需求链论坛 - 主逻辑 v3 (分页+loading)
var API = "";
var currentCategory = "";
var currentSort = "hot";
var activeTopicId = null;
var currentPage = 1;
var perPage = 20;

function esc(s) { return String(s||"").replace(/</g,"&lt;"); }
function md2html(text) {
  if (typeof marked !== 'undefined' && text) {
    try { return marked.parse(text); } catch(e) {}
  }
  return String(text||"").replace(/\n/g, '<br>');
}
async function fetchJSON(path, opts) {
  var r = await fetch(API + path, opts || {});
  return r.json();
}

// 分类
async function loadCategories() {
  try {
    var data = await fetchJSON("/api/forum/categories");
    var bar = document.getElementById("categoryBar");
    bar.innerHTML = '<span class="cat-btn active" onclick="setCategory(\'\')">全部</span>';
    for (var i = 0; i < data.length; i++) {
      var c = data[i];
      var id = String(c.id).replace(/'/g,"\\'");
      bar.innerHTML += '<span class="cat-btn" onclick="setCategory(\''+id+'\')">'+esc(c.name)+' <span class="count">'+(c.count||0)+'</span></span>';
    }
  } catch(e) {}
}

function setCategory(c) {
  currentCategory = c;
  var btns = document.querySelectorAll("#categoryBar .cat-btn");
  for (var i = 0; i < btns.length; i++) {
    var raw = btns[i].textContent.replace(/\s+\d+$/,"").trim();
    var target = (c||"全部");
    btns[i].classList.toggle("active", raw === target || (i === 0 && !c));
  }
  loadTopics();
}

// 排序
function setSort(s) {
  currentSort = s;
  document.getElementById("sortHot").classList.toggle("active", s==="hot");
  document.getElementById("sortNew").classList.toggle("active", s==="new");
  document.getElementById("sortTop").classList.toggle("active", s==="top");
  loadTopics();
}

// 时间格式化（中文友好）
function timeAgo(d) {
  if (!d) return "";
  var diff = (Date.now() - new Date(d)) / 1000;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return Math.floor(diff/60) + " 分钟前";
  if (diff < 86400) return Math.floor(diff/3600) + " 小时前";
  if (diff < 2592000) return Math.floor(diff/86400) + " 天前";
  return Math.floor(diff/2592000) + " 个月前";
}

// 分类标签显示名称（与后端 CATEGORIES 保持一致）
var CAT_LABELS = {
  "ai": "人工智能",
  "biomedicine": "生物医药",
  "new_energy": "新能源",
  "semiconductor": "半导体",
  "materials": "材料科学",
  "aerospace": "航空航天",
  "information": "信息技术",
  "sensor": "传感器技术",
  "robotics": "机器人与智能系统",
  "environmental": "环境工程",
  "manufacturing": "制造业",
  "electronics": "电子科学与技术",
  "chemistry": "化学工程",
  "transport": "交通运输",
  "agriculture": "农业科学",
  "ocean": "海洋科学",
  "general": "综合讨论"
};
// 兼容旧分类（迁移期间）
var CAT_LEGACY = {
  "demand_board": "综合讨论",
  "capability_showcase": "综合讨论",
  "matching_feedback": "综合讨论",
  "bug_report": "综合讨论",
  "feature_request": "综合讨论"
};
function catLabel(c) { return CAT_LABELS[c] || CAT_LEGACY[c] || c || "综合讨论"; }

// 构建帖子卡片
function buildCard(t) {
  var pin = t.is_pinned ? '<span class="pin">📌</span>' : '';
  return '<div class="topic-card" onclick="openTopic(\''+t.id+'\')">'+
    '<div class="topic-title">'+pin+esc(t.title)+'</div>'+
    '<div class="topic-body">'+esc((t.content||"").substring(0,120))+'</div>'+
    '<div class="topic-meta">'+catLabel(t.category)+' · '+(t.vote_count||0)+' 赞 · '+(t.reply_count||0)+' 回复 · '+timeAgo(t.created_at)+'</div></div>';
}

// 加载列表
async function loadTopics() {
  var div = document.getElementById("content");
  div.innerHTML = '<div class="skeleton-row"><div class="skeleton" style="height:24px"></div><div class="skeleton"></div><div class="skeleton"></div></div><div class="skeleton-row"><div class="skeleton" style="height:24px"></div><div class="skeleton"></div><div class="skeleton"></div></div><div class="skeleton-row"><div class="skeleton" style="height:24px"></div><div class="skeleton"></div><div class="skeleton"></div></div>';

  var url = "/api/forum/topics?sort="+encodeURIComponent(currentSort)+"&limit="+perPage+"&offset="+((currentPage-1)*perPage);
  if (currentCategory) url += "&category="+encodeURIComponent(currentCategory);
  var data = {};
  try { data = await fetchJSON(url); } catch(e) { data = {topics: []}; }
  var topics = Array.isArray(data) ? data : (data.topics || []);
  if (!topics.length) {
    div.innerHTML = '<p style="color:var(--ts);text-align:center;padding:40px">暂无帖子，快来发第一个吧！</p>';
  } else {
    var h = '<div class="topic-list">';
    for (var i = 0; i < topics.length; i++) h += buildCard(topics[i]);
    h += '</div>';
    h += '<div class="pagination" id="pager"></div>';
    div.innerHTML = h;
    buildPager(topics.length);
  }
  showNewTopicForm();
}

function buildPager(itemCount) {
  var pager = document.getElementById("pager");
  if (!pager) return;
  var h = '';
  h += '<button class="page-btn" onclick="goPage('+(currentPage-1)+')" '+(currentPage<=1?'disabled':'')+'>上一页</button>';
  h += '<span class="page-btn active">第 '+currentPage+' 页</span>';
  h += '<button class="page-btn" onclick="goPage('+(currentPage+1)+')" '+(itemCount<perPage?'disabled':'')+'>下一页</button>';
  pager.innerHTML = h;
}

function goPage(p) {
  if (p < 1) return;
  currentPage = p;
  loadTopics();
  window.scrollTo(0, 0);
}

// 发帖表单（中文化）
function showNewTopicForm() {
  var catOpts = '';
  var keys = Object.keys(CAT_LABELS);
  for (var i = 0; i < keys.length; i++) {
    catOpts += '<option value="'+keys[i]+'">'+CAT_LABELS[keys[i]]+'</option>';
  }
  document.getElementById("content").innerHTML +=
    '<div style="margin-top:20px;background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:16px" id="newTopicForm">'+
    '<h3 style="margin:0 0 12px">发表新帖</h3>'+
    '<select id="newCategory" style="width:100%;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.9em;margin-bottom:8px">'+catOpts+'</select>'+
    '<input id="newTitle" placeholder="标题" style="width:100%;margin-bottom:8px;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text)">'+
    '<textarea id="newBody" placeholder="内容（支持 Markdown）" rows="4" style="width:100%;margin-bottom:8px;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text)"></textarea>'+
    '<button onclick="createTopic()" style="padding:10px 24px;border-radius:8px;background:var(--accent);color:#fff;border:none;cursor:pointer;font-size:.9em;width:100%">发布帖子</button></div>';
}

async function createTopic() {
  var t = document.getElementById("newTitle").value.trim();
  var b = document.getElementById("newBody").value.trim();
  var c = document.getElementById("newCategory").value;
  if (!t) { alert("请输入标题"); return; }
  // 获取登录用户信息
  var authorId = "web_user";
  try {
    var session = JSON.parse(localStorage.getItem("dc_session") || "{}");
    if (session.email) authorId = session.email;
  } catch(e) {}
  var r = await fetchJSON("/api/forum/topics/create", {
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({title:t,body:b,category:c,author_id:authorId})
  });
  if (r.status==="ok") { loadTopics(); }
  else { alert(r.error||"发布失败"); }
}

// 详情
async function openTopic(id) {
  var t = null;
  try { t = await fetchJSON("/api/forum/topics/"+id); } catch(e) {}
  if (!t || t.error) return;

  var replies = [];
  try { var rd = await fetchJSON("/api/forum/topics/"+id+"/replies"); replies = Array.isArray(rd) ? rd : (rd.replies||[]); } catch(e) {}

  var rh = '';
  for (var i = 0; i < replies.length; i++) {
    var r = replies[i];
    rh += '<div class="reply"><div class="reply-agent">'+esc(r.author_id)+' · '+timeAgo(r.created_at)+'</div><div class="reply-body">'+md2html(r.content)+'</div></div>';
  }

  document.getElementById("content").innerHTML =
    '<div class="detail-card">'+
    '<span class="back-btn" onclick="loadTopics()">← 返回列表</span>'+
    '<h2>'+esc(t.title)+'</h2>'+
    '<div style="font-size:.8em;color:var(--ts);margin:8px 0">'+catLabel(t.category)+' · '+(t.vote_count||0)+' 赞 · '+(t.reply_count||0)+' 回复 · '+timeAgo(t.created_at)+'</div>'+
    '<div class="detail-body">'+md2html(t.content||"")+'</div>'+
    '<div class="vote-row"><button class="vote-btn" onclick="voteTopic(\''+id+'\',\'up\')">👍 点赞 ('+(t.vote_count||0)+')</button></div>'+
    '<h4 style="margin:20px 0 10px">回复 ('+replies.length+')</h4>'+
    (rh?'<div>'+rh+'</div>':'<p style="color:var(--ts)">暂无回复，来发表第一条吧</p>')+
    textareaReply(id)+
    '</div>';
}

function textareaReply(id) {
  return '<textarea id="replyBody" placeholder="写下你的回复..." rows="2" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:8px;color:var(--text);font-size:.9em;margin-top:16px"></textarea>'+
    '<button onclick="replyTopic(\''+id+'\')" style="margin-top:8px;padding:8px 16px;border-radius:8px;background:var(--accent);color:#fff;border:none;cursor:pointer">提交回复</button>';
}

async function voteTopic(id, dir) {
  var r = await fetchJSON("/api/forum/topics/"+id+"/vote", {
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({direction:dir})
  });
  if (r.status==="ok") openTopic(id);
  else alert("请先登录再投票");
}

async function replyTopic(id) {
  var b = document.getElementById("replyBody").value.trim();
  if (!b) return;
  // 获取登录用户信息
  var authorId = "web_user";
  try {
    var session = JSON.parse(localStorage.getItem("dc_session") || "{}");
    if (session.email) authorId = session.email;
  } catch(e) {}
  var r = await fetchJSON("/api/forum/topics/"+id+"/reply", {
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({body:b,author_id:authorId})
  });
  if (r.status==="ok") openTopic(id);
  else alert(r.error||"回复失败");
}

loadCategories();
loadTopics();

