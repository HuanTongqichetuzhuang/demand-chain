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

    // 已专注中文，导航栏固定显示中文
    var links = nav.querySelectorAll("a");
    links.forEach(function(a) {
      var href = (a.getAttribute("href") || "").toLowerCase();
      if (href.indexOf("demand_square") >= 0 || href.indexOf("demands") >= 0) {
        a.textContent = "需求广场";
      } else if (href.indexOf("forum") >= 0) {
        a.textContent = "论坛";
      } else if (href.indexOf("tutorial") >= 0 || href.indexOf("guide") >= 0) {
        a.textContent = "教程";
      } else if (href.indexOf("login") >= 0) {
        a.textContent = "登录";
        a.className = "btn-nav";
      }
    });
    // Find and update logout link — by checking onclick attribute
    links.forEach(function(a) {
      var oc = a.getAttribute("onclick") || "";
      if (oc.indexOf("removeItem") >= 0) {
        a.textContent = "退出";
      }
    });
  }
  
  // [已移除] addLangToggle — 暂时专注中文，不再显示 EN/中文 切换按钮
  
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
  
  // Apply — 语言切换已禁用，专注中文
  applyLang();
})();

