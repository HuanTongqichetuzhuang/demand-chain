// 需求链平台 - 中英文语言切换
(function(){
  var LANG_KEY = "dc_lang";
  var currentLang = localStorage.getItem(LANG_KEY) || "zh";
  
  function switchTo(lang) {
    currentLang = lang;
    localStorage.setItem(LANG_KEY, lang);
    applyLang();
  }
  
  function applyLang() {
    // Update all [data-i18n] elements
    document.querySelectorAll("[data-i18n]").forEach(function(el) {
      var key = el.getAttribute("data-i18n");
      if (i18nData[currentLang] && i18nData[currentLang][key]) {
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
          el.placeholder = i18nData[currentLang][key];
        } else {
          el.textContent = i18nData[currentLang][key];
        }
      }
    });
    // Update nav login button
    navCheck();
  }
  
  function navCheck() {
    var nav = document.querySelector("nav .links");
    if (!nav) return;
    var session = localStorage.getItem("dc_session");
    var user = null;
    try { user = JSON.parse(session); } catch(e) {}
    
    var loginText = currentLang === "zh" ? "登录" : "Login";
    var demandSquare = currentLang === "zh" ? "需求广场" : "Demands";
    var forumText = currentLang === "zh" ? "论坛" : "Forum";
    var tutorialText = currentLang === "zh" ? "教程" : "Guide";
    var logoutText = currentLang === "zh" ? "退出" : "Logout";
    
    // Update link text only — don't rebuild nav (nav.js handles structure)
    var links = nav.querySelectorAll("a");
    links.forEach(function(a) {
      var href = (a.getAttribute("href") || "").toLowerCase();
      if (href.indexOf("demand_square") >= 0 || href.indexOf("demands") >= 0) {
        a.textContent = demandSquare;
      } else if (href.indexOf("forum") >= 0) {
        a.textContent = forumText;
      } else if (href.indexOf("tutorial") >= 0 || href.indexOf("guide") >= 0) {
        a.textContent = tutorialText;
      } else if (href.indexOf("login") >= 0) {
        a.textContent = loginText;
        a.className = "btn-nav";
      }
    });
    // Find and update logout link
    links.forEach(function(a) {
      if (a.textContent === "退出" || a.textContent === "Logout" || (a.onclick && a.onclick.toString().indexOf("removeItem") >= 0)) {
        a.textContent = logoutText;
      }
    });
  }
  
  // Add language toggle button
  function addLangToggle() {
    var nav = document.querySelector("nav .links");
    if (!nav) return;
    var btn1 = document.createElement("a");
    btn1.href = "#";
    btn1.textContent = currentLang === "zh" ? "中文" : "EN";
    btn1.style.cssText = "font-size:13px;color:var(--ts);margin-left:8px"; 
    btn1.onclick = function(e) {
      e.preventDefault();
      switchTo(currentLang === "zh" ? "en" : "zh");
    };
    // Insert after last child
    nav.insertBefore(btn1, nav.lastChild.nextSibling);
    // Also insert a separator
    var sep = document.createElement("span");
    sep.textContent = " | ";
    sep.style.cssText = "font-size:13px;color:var(--ts)";
    nav.insertBefore(sep, btn1);
  }
  
  // i18n data - define per page
  var i18nData = {
    zh: {},
    en: {}
  };
  
  // Collect from meta tags if present
  document.querySelectorAll("meta[name^='i18n-']").forEach(function(meta) {
    var name = meta.getAttribute("name");
    var lang = name.indexOf("zh") >= 0 ? "zh" : "en";
    if (name.indexOf("key-") >= 0) {
      var key = name.substring(name.lastIndexOf("-") + 1);
      i18nData[lang][key] = meta.getAttribute("content");
    }
  });
  
  // Apply and add toggle
  applyLang();
  if (document.querySelector("nav")) {
    // Call addLangToggle after DOM-ready
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", addLangToggle);
    } else {
      addLangToggle();
    }
  }
})();
