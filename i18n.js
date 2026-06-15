// 需求链平台 - 中英文语言切换
(function(){
  var LANG_KEY = "dc_lang";
  var stored = localStorage.getItem(LANG_KEY);
  // 如果存储的是空字符串或无效值，重置为中文
  var currentLang = (stored === "zh" || stored === "en") ? stored : "zh";
  if (stored !== currentLang) {
    localStorage.setItem(LANG_KEY, currentLang);
  }
  
  // 暴露全局 API，方便调试
  window.__dc_lang = currentLang;
  window.__dc_switchLang = function(lang) {
    if (lang !== "zh" && lang !== "en") return;
    currentLang = lang;
    localStorage.setItem(LANG_KEY, lang);
    window.__dc_lang = lang;
    applyLang();
  };
  
  function switchTo(lang) {
    window.__dc_switchLang(lang);
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
    // Find and update logout link — by checking onclick attribute
    links.forEach(function(a) {
      var oc = a.getAttribute("onclick") || "";
      if (oc.indexOf("removeItem") >= 0) {
        a.textContent = logoutText;
      }
    });
  }
  
  // Add language toggle button
  function addLangToggle() {
    var nav = document.querySelector("nav .links");
    if (!nav) return;
    // 避免重复添加
    if (document.getElementById("dc-lang-toggle")) return;
    var sep = document.createElement("span");
    sep.textContent = " | ";
    sep.style.cssText = "font-size:13px;color:var(--ts)";
    nav.appendChild(sep);
    
    var btn1 = document.createElement("a");
    btn1.id = "dc-lang-toggle";
    btn1.href = "#";
    var updateBtn = function() {
      btn1.textContent = currentLang === "zh" ? "EN" : "中文";
      btn1.title = currentLang === "zh" ? "切换到英文" : "切换到中文";
    };
    updateBtn();
    btn1.style.cssText = "font-size:13px;color:var(--ts);cursor:pointer;text-decoration:none"; 
    btn1.onclick = function(e) {
      e.preventDefault();
      switchTo(currentLang === "zh" ? "en" : "zh");
      updateBtn();
    };
    nav.appendChild(btn1);
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
