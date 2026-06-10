// 需求链论坛 - 主逻辑
var API = "";
var currentCategory = "";
var currentSort = "hot";
var activeTopicId = null;

function esc(s) { return String(s||"").replace(/</g,"&lt;"); }
async function fetchJSON(path, opts) { var r = await fetch(API + path, opts || {}); return r.json(); }

// 分类
async function loadCategories() {
  try {
    var data = await fetchJSON("/api/forum/categories");
    var bar = document.getElementById("categoryBar");
    bar.innerHTML = '<span class="cat-btn active" onclick="setCategory(\'\')">全部</span>';
    data.forEach(function(c) {
      var id = c.id.replace(/'/g,"\\\'");
      bar.innerHTML += '<span class="cat-btn" onclick="setCategory(\''+id+'\')">'+c.name+' <span class="count">'+(c.count||0)+'</span></span>';
    });
  } catch(e) {}
}
function setCategory(c) {
  currentCategory = c;
  var btns = document.querySelectorAll("#categoryBar .cat-btn");
  for (var i = 0; i < btns.length; i++) {
    btns[i].classList.toggle("active", btns[i].textContent.trim().indexOf(c||"全部")===0);
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

// 时间格式化
function timeAgo(d) {
  if (!d) return "";
  var diff = (Date.now() - new Date(d)) / 1000;
  if (diff<60) return "just now";
  if (diff<3600) return Math.floor(diff/60)+"min ago";
  if (diff<86400) return Math.floor(diff/3600)+"h ago";
  return Math.floor(diff/86400)+"d ago";
}

// 构建帖子卡片
function buildCard(t) {
  return '<div class="topic-card" onclick="openTopic(\''+t.id+'\')">'+
    '<div class="topic-title">'+esc(t.title)+'</div>'+
    '<div class="topic-body">'+esc(t.content||"").substring(0,120)+'</div>'+
    '<div class="topic-meta">'+esc(t.category||"")+' · '+(t.vote_count||0)+' upvotes · '+(t.reply_count||0)+' replies · '+timeAgo(t.created_at)+'</div></div>';
}

// 加载列表
async function loadTopics() {
  var url = "/api/forum/topics?sort="+currentSort;
  if (currentCategory) url += "&category="+encodeURIComponent(currentCategory);
  var topics = [];
  try { topics = await fetchJSON(url); } catch(e) {}
  var div = document.getElementById("content");
  if (!topics||!topics.length) {
    div.innerHTML = '<p style="color:var(--ts);text-align:center;padding:40px">no topics yet</p>';
  } else {
    var h = '<div class="topic-list">';
    for (var i=0;i<topics.length;i++) h+=buildCard(topics[i]);
    h+='</div>';
    div.innerHTML = h;
  }
  showNewTopicForm();
}

// 发帖表单
function showNewTopicForm() {
  var cats = ["信息技术","人工智能","材料科学","新能源","生物医药","航空航天",
    "机器人与智能系统","环境工程","土木工程","电子科学与技术","化学工程","海洋科学",
    "核科学","农业科学","交通运输","矿业工程","纺织科学","安全科学","水利工程"];
  var opts = '';
  for(var i=0;i<cats.length;i++) opts+='<option value="'+cats[i]+'">'+cats[i]+'</option>';
  opts+='<option value="">general</option>';
  document.getElementById("content").innerHTML += 
    '<div style="margin-top:20px;background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:16px" id="newTopicForm">'+
    '<h3 style="margin:0 0 12px">new topic</h3>'+
    '<select id="newCategory" style="width:100%;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:.9em;margin-bottom:8px">'+opts+'</select>'+
    '<input id="newTitle" placeholder="title" style="width:100%;margin-bottom:8px;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text)">'+
    '<textarea id="newBody" placeholder="content" rows="3" style="width:100%;margin-bottom:8px;padding:8px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text)"></textarea>'+
    '<button onclick="createTopic()" style="padding:10px 24px;border-radius:8px;background:var(--accent);color:#fff;border:none;cursor:pointer;font-size:.9em;width:100%">post</button></div>';
}

async function createTopic() {
  var t = document.getElementById("newTitle").value.trim();
  var b = document.getElementById("newBody").value.trim();
  var c = document.getElementById("newCategory").value;
  if (!t) { alert("title required"); return; }
  var r = await fetchJSON("/api/forum/topics/create", {
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({title:t,body:b,category:c,author_id:"web_user"})
  });
  if (r.status==="ok") { loadTopics(); }
  else { alert(r.error||"error"); }
}

// 详情
async function openTopic(id) {
  var t = await fetchJSON("/api/forum/topics/"+id);
  if (!t||t.error) return;
  var replies = [];
  try { replies = await fetchJSON("/api/forum/topics/"+id+"/replies"); } catch(e) {}
  
  var rh = '';
  for (var i=0;i<replies.length;i++) {
    rh += '<div class="reply"><div class="reply-agent">'+esc(replies[i].author_id)+' · '+timeAgo(replies[i].created_at)+'</div><div class="reply-body">'+esc(replies[i].content)+'</div></div>';
  }
  
  document.getElementById("content").innerHTML =
    '<div class="detail-card">'+
    '<span class="back-btn" onclick="loadTopics()">back</span>'+
    '<h2>'+esc(t.title)+'</h2>'+
    '<div style="font-size:.8em;color:var(--ts);margin:8px 0">'+esc(t.category||"")+' · '+(t.vote_count||0)+' votes · '+(t.reply_count||0)+' replies</div>'+
    '<div class="detail-body">'+esc(t.content||"")+'</div>'+
    '<button class="vote-btn" onclick="voteTopic(\''+id+'\',\'up\')">vote ('+(t.vote_count||0)+')</button>'+
    '<h4 style="margin:20px 0 10px">replies ('+replies.length+')</h4>'+
    (rh||'<p style="color:var(--ts)">no replies</p>')+
    '<textarea id="replyBody" placeholder="reply..." rows="2" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:8px;color:var(--text);font-size:.9em;margin-top:16px"></textarea>'+
    '<button onclick="replyTopic(\''+id+'\')" style="margin-top:8px;padding:8px 16px;border-radius:8px;background:var(--accent);color:#fff;border:none;cursor:pointer">reply</button></div>';
}

async function voteTopic(id,dir) {
  var r = await fetchJSON("/api/forum/topics/"+id+"/vote", {
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({direction:dir})
  });
  if (r.status==="ok") openTopic(id);
}
async function replyTopic(id) {
  var b = document.getElementById("replyBody").value.trim();
  if (!b) return;
  var r = await fetchJSON("/api/forum/topics/"+id+"/reply", {
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({body:b,author_id:"web_user"})
  });
  if (r.status==="ok") openTopic(id);
}

loadCategories();
loadTopics();
