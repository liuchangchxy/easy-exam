/* ==========================================================================
   EasyExam 产品原型 · 统一导航层（第三轮：跨页面交互收敛）
   --------------------------------------------------------------------------
   15 个屏幕原本都把侧脊/底导写成 <button>（点了没反应）。本脚本按「唯一导航契约」
   把它们换成真实链接：
     · 标签 → 目标页的映射只有这一份（ROUTES），改导航只改这里；
     · 当前页自动高亮（is-active + aria-current），不依赖每个页面自己标；
     · 侧脊计数（题库/资料/复习）从共享状态读，全产品一致；
     · 页面专属按钮（无匹配标签）保持原样，不影响各页自有交互。
   依赖：assets/store.js（在其后加载）。

   【底部导航收敛为五个主要入口】今天 / 题库 / 复习 / 模考 / 资料。
   原第六格「更多」是一颗只开不动的死按钮，已删除；「设置」是低频管理入口，
   改由移动顶栏与桌面顶栏的**账户菜单**承载（侧栏在手机端整块隐藏，账户菜单
   是设置在手机端的唯一可达路径）。同一入口在全产品行为一致。
   ========================================================================== */
(function () {
  /* 标签 → 页面（相对当前屏幕目录；flows 目录同层，文件名唯一，可直接用）。
     中英双语都认：界面语言切成英文后，导航仍然是真实链接。 */
  var ROUTES = {
    '今天': 'home.html', 'Today': 'home.html',
    '题库': 'banks.html', 'Banks': 'banks.html',
    '复习': 'review.html', 'Review': 'review.html',
    '模考': 'exams.html', 'Exams': 'exams.html',
    '资料': 'notes.html', 'Materials': 'notes.html',
    '设置': 'settings.html', 'Settings': 'settings.html',
    '导入向导': 'import.html',
    '实例管理': 'instance.html', 'Instance': 'instance.html',
    '命令面板': 'palette.html',
    '题库工作区': 'workspace.html',
    '题目页': 'question.html',
    '练习会话': 'practice.html',
    '模考会话': 'exam.html',
    '无法访问 403': 'forbidden.html',
    '登录 / 注册': 'login.html',
    '完整产品原型': 'product.html'
  };
  /* 计数来源：与共享状态联动，改完数据立刻一致 */
  var COUNTS = {
    '题库': function () { return window.eeStore ? window.eeStore.banks({ archived: false }).length : null; },
    '资料': function () { return window.eeStore ? window.eeStore.notes().length : null; },
    '复习': function () { return window.eeStore ? window.eeStore.executableReview().length : null; }
  };

  function currentFile() {
    var p = location.pathname.split('/');
    return (p[p.length - 1] || 'home.html').toLowerCase();
  }
  function labelOf(el) {
    var s = el.querySelector('.nav-label');
    if (s) return s.textContent.trim();
    return (el.textContent || '').trim().split('\n')[0].trim();
  }
  function convert(scope) {
    var items = scope.querySelectorAll('.nav-item, .bn-item');
    Array.prototype.forEach.call(items, function (el) {
      if (el.tagName === 'A') { mark(el); return; }
      var label = labelOf(el);
      var target = ROUTES[label];
      if (!target) return;                       /* 页面专属入口：保持按钮 */
      /* 带上下文的入口：从题库页/工作区进导入向导时，目标题库不丢 */
      var href = target;
      if (label === '导入向导') {
        var m = /[?&]bank=([^&]+)/.exec(location.search);
        if (m) href = target + (target.indexOf('?') > -1 ? '&' : '?') + 'bank=' + m[1];
      }
      var a = document.createElement('a');
      a.className = el.className;
      a.setAttribute('href', href);
      a.innerHTML = el.innerHTML;
      /* 保留原始属性（aria-label / title / data-*），去掉按钮态属性 */
      Array.prototype.forEach.call(el.attributes, function (attr) {
        if (attr.name === 'class' || attr.name === 'type') return;
        try { a.setAttribute(attr.name, attr.value); } catch (e) {}
      });
      if (el.parentNode) el.parentNode.replaceChild(a, el);
      mark(a);
    });
  }
  function mark(a) {
    var href = (a.getAttribute('href') || '').split('?')[0];
    if (!href) return;
    var isCurrent = href.toLowerCase() === currentFile();
    a.classList.toggle('is-active', isCurrent);
    if (isCurrent) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
  function counts() {
    if (!window.eeStore) return;
    Object.keys(COUNTS).forEach(function (label) {
      var n = COUNTS[label]();
      if (n == null) return;
      var items = document.querySelectorAll('.nav-item, .bn-item');
      Array.prototype.forEach.call(items, function (el) {
        if (labelOf(el) !== label) return;
        var badge = el.querySelector('.nav-count');
        if (!badge) {
          badge = document.createElement('span');
          badge.className = 'nav-count';
          el.appendChild(badge);
        }
        badge.textContent = String(n);
        badge.hidden = n === 0;
      });
    });
  }

  /* ---- 账户入口：全产品同一形态 ----
     原来有三种写法：点了没反应的 <button>、不可点的 <span aria-hidden>、
     直接跳设置的 <a>。统一为「头像按钮 + 账户菜单」，并保证菜单里一定有
     「设置」——侧栏在手机端整块隐藏，账户菜单是设置在手机端的唯一入口。
     实例管理仍按 relevant('instance.manage') 判定（CR-12 两向规则）。 */
  function ensureAccountEntry() {
    Array.prototype.forEach.call(
      document.querySelectorAll('.topbar .user-mini, .mobile-top .user-mini'),
      function (btn) {
        if (btn.tagName !== 'BUTTON') {
          var b = document.createElement('button');
          b.type = 'button';
          b.className = btn.className;
          b.textContent = (btn.textContent || '').trim() || 'A';
          b.title = '账户菜单';
          b.setAttribute('aria-label', '账户菜单');
          if (btn.parentNode) btn.parentNode.replaceChild(b, btn);
          btn = b;
        }
        if (!btn.getAttribute('aria-label')) {
          btn.title = '账户菜单';
          btn.setAttribute('aria-label', '账户菜单');
        }
        if (btn.tagName === 'BUTTON' && !btn.getAttribute('type')) btn.type = 'button';
      });
    /* 设置页自己的账户菜单不再挂「设置」：那一页就是设置本身 */
    if (currentFile() === 'settings.html') return;
    Array.prototype.forEach.call(document.querySelectorAll('.menu'), function (menu) {
      var anchor = menu.closest('.menu-anchor');
      if (!anchor) return;
      if (!anchor.querySelector('.user-mini')) return;
      if (menu.querySelector('.menu-item[href^="settings.html"]')) return;
      var item = document.createElement('a');
      item.className = 'menu-item';
      item.setAttribute('role', 'menuitem');
      item.setAttribute('href', 'settings.html');
      item.setAttribute('data-i18n', 'shell.menu.settings');
      item.innerHTML =
        '<svg class="od-icon" aria-hidden="true"><use href="#i-settings"/></svg>' +
        '<span data-i18n="shell.menu.settings">设置</span>';
      var sep = menu.querySelector('.menu-sep');
      if (sep) sep.parentNode.insertBefore(item, sep);
      else menu.appendChild(item);
    });
  }

  function run() {
    /* 覆盖侧脊（含底部设置项）、底导与顶栏里的导航项 */
    var scopes = document.querySelectorAll('.sidebar, .bottomnav, .topbar');
    if (!scopes.length) scopes = [document.body];
    Array.prototype.forEach.call(scopes, convert);
    /* 侧脊品牌 = 回到今天页（原版同行为；原来是 <button>，点了没反应） */
    Array.prototype.forEach.call(document.querySelectorAll('.side-brand'), function (el) {
      if (el.tagName === 'A') return;
      var a = document.createElement('a');
      a.className = el.className;
      a.setAttribute('href', 'home.html');
      a.setAttribute('aria-label', '易考宝 · 回到今天');
      a.innerHTML = el.innerHTML;
      if (el.parentNode) el.parentNode.replaceChild(a, el);
    });
    counts();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
  /* 账户入口补形 + 账户菜单补「设置」。跑在 load 而不是 DOMContentLoaded：
     spec-boot 的 wireShell 会给没有菜单的头像补一个标准账户菜单，那个菜单
     也要有「设置」，所以必须等它建完。两次调用都幂等。 */
  ensureAccountEntry();
  window.addEventListener('load', ensureAccountEntry);
  /* 其他页改了数据（storage 事件）→ 刷新计数 */
  window.addEventListener('storage', function (e) {
    if (e.key && e.key.indexOf('eeStore') === 0) setTimeout(counts, 30);
  });
  window.eeNav = {
    routes: ROUTES,
    /* CR-12 两向规则：与当前用户完全无关的管理入口不进入命令面板。
       实例管理只对实例管理员有意义；题库面的管理操作由各产品屏按 relevant() 判定。 */
    visibleRoutes: function () {
      var out = {};
      var store = window.eeStore;
      Object.keys(ROUTES).forEach(function (label) {
        if ((label === '实例管理' || label === 'Instance') && store && !store.relevant('instance.manage')) return;
        out[label] = ROUTES[label];
      });
      return out;
    },
    refresh: function () { run(); ensureAccountEntry(); }
  };

  /* ---- 滚动位置：离开页面时记住，返回同一页面时回到原处 ----
     语义：只有「这个页面本轮已经看过」才恢复；第一次进入停在被引导的位置。
     筛选/搜索/页签由各页用 eeStore.view 自己保存，这里只管滚动这一项。 */
  (function () {
    if (!window.eeStore) return;
    var key = 'scroll:' + currentFile();
    var last = 0, timer = null;
    window.addEventListener('scroll', function () {
      if (timer) return;
      timer = setTimeout(function () {
        timer = null;
        var y = window.scrollY || window.pageYOffset || 0;
        if (Math.abs(y - last) < 40) return;
        last = y;
        window.eeStore.view.save(key, { y: y });
      }, 250);
    }, { passive: true });
    window.addEventListener('pagehide', function () {
      window.eeStore.view.save(key, { y: window.scrollY || window.pageYOffset || 0 });
    });
    var saved = window.eeStore.view.load(key);
    if (saved && saved.y > 0) {
      setTimeout(function () { window.scrollTo(0, saved.y); }, 60);
    }
  })();
})();
