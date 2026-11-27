/* ==========================================================================
   EasyExam 产品原型 · 统一导航层
   --------------------------------------------------------------------------
   第五轮：导航选中态按「功能域」决定，不再按文件名。
     · 页面可在 <body data-nav-domain="banks|review|exams|notes|settings|today">
       声明所属域；缺省回落到本文件里的文件名映射（旧页面无需改动也能工作）。
     · 子页面继承父域：workspace / question / import → banks；
       practice / diagnosis → review；exam → exams；instance → settings。
     · 一级导航只有一项属于一个域，因此「当前页」永远只有一项带
       aria-current="page"；同域的父级入口只带 is-active（弱态），
       告诉用户「你在这一块里」，但不谎称当前页就是它。
     · 标签 → 目标页的映射只有这一份（ROUTES），改导航只改这里。
     · 计数（题库 / 复习 / 资料）一律从 eeStore 读，页面不得自己写第二份。
     · 所有交互对象先归一化成 data-act="nav" + data-route，之后的行为只认
       data 属性；旧页面的 .nav-item / .bn-item 只是迁移入口（见报告）。
   依赖：assets/store.js（在其后加载）；没有 store 时计数留空、不报错。
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
    '导入向导': 'import.html', 'Import wizard': 'import.html',
    '实例管理': 'instance.html', 'Instance': 'instance.html',
    '命令面板': 'palette.html', 'Command palette': 'palette.html',
    '题库工作区': 'workspace.html', 'Bank workspace': 'workspace.html',
    '题目页': 'question.html', 'Question page': 'question.html',
    '练习会话': 'practice.html', 'Practice session': 'practice.html',
    '模考会话': 'exam.html', 'Exam session': 'exam.html',
    '无法访问 403': 'forbidden.html', 'Forbidden 403': 'forbidden.html',
    '登录 / 注册': 'login.html', 'Sign in / Register': 'login.html',
    '完整产品原型': 'product.html'
  };

  /* 文件名 → 功能域。只用于「页面没写 data-nav-domain」时的回落。
     login / forbidden 不属于任何一级导航域：不制造假高亮。 */
  var FILE_DOMAIN = {
    'home.html': 'today',
    'palette.html': 'today',
    'banks.html': 'banks',
    'workspace.html': 'banks',
    'question.html': 'banks',
    'import.html': 'banks',
    'review.html': 'review',
    'diagnosis.html': 'review',
    'practice.html': 'review',
    'exams.html': 'exams',
    'exam.html': 'exams',
    'notes.html': 'notes',
    'settings.html': 'settings',
    'instance.html': 'settings'
  };

  /* 计数来源：与共享状态联动，改完数据立刻一致。
     题库 = 未归档题库数；资料 = 资料条数；复习 = 可执行复习集合（CR-05）。
     今天 / 模考没有定义计数——页面上残留的角标会被移除，不留假数字。 */
  var COUNTS = {
    '题库': function () { return window.eeStore ? window.eeStore.banks({ archived: false }).length : null; },
    '资料': function () { return window.eeStore ? window.eeStore.notes().length : null; },
    '复习': function () { return window.eeStore ? window.eeStore.executableReview().length : null; }
  };
  /* 计数标签：中英两套导航文案指向同一个计数口径（界面语言切换后角标不丢） */
  var COUNT_KEY = {
    '题库': '题库', 'Banks': '题库',
    '资料': '资料', 'Materials': '资料',
    '复习': '复习', 'Review': '复习'
  };

  function currentFile() {
    var p = location.pathname.split('/');
    return (p[p.length - 1] || 'home.html').toLowerCase();
  }
  function currentDomain() {
    var declared = document.body && document.body.getAttribute('data-nav-domain');
    if (declared) return declared.trim().toLowerCase();
    return FILE_DOMAIN[currentFile()] || '';
  }
  function labelOf(el) {
    var s = el.querySelector('.nav-label');
    if (s) return s.textContent.trim();
    return (el.textContent || '').trim().split('\n')[0].trim();
  }
  function routeOf(el) {
    return el.getAttribute('data-route') || ROUTES[labelOf(el)] || '';
  }
  function fileOfRoute(href) {
    return (href || '').split('?')[0].split('#')[0].toLowerCase();
  }

  /* 把旧页面的 class 导航项归一化成行为属性。这是唯一的 class → data 迁移点；
     迁移之后所有查找、转换、高亮、计数都只认 data-act / data-route。 */
  function normalize(scope) {
    Array.prototype.forEach.call(scope.querySelectorAll('.nav-item, .bn-item'), function (el) {
      if (!el.getAttribute('data-act')) el.setAttribute('data-act', 'nav');
      if (!el.getAttribute('data-nav-kind')) el.setAttribute('data-nav-kind', 'switch-page');
      var label = labelOf(el);
      if (label && !el.getAttribute('data-nav-label')) el.setAttribute('data-nav-label', label);
      var target = ROUTES[label];
      if (target && !el.getAttribute('data-route')) el.setAttribute('data-route', target);
    });
  }

  /* 重建 DOM 时保留中文原文：语言已切到英文后，el.innerHTML 里是英文译文，
     直接搬进新节点会脱离 i18n 的还原表——之后切回中文时这些导航永远停在英文。
     逐节点对齐，把每个文本节点的原文（eeSourceZh）写回新节点。 */
  function copySource(srcEl, dstEl) {
    var src = [], dst = [];
    var w1 = document.createTreeWalker(srcEl, NodeFilter.SHOW_TEXT, null);
    while (w1.nextNode()) src.push(w1.currentNode);
    var w2 = document.createTreeWalker(dstEl, NodeFilter.SHOW_TEXT, null);
    while (w2.nextNode()) dst.push(w2.currentNode);
    src.forEach(function (n, i) {
      var zh = window.eeSourceZh ? window.eeSourceZh(n) : null;
      if (zh != null && dst[i]) dst[i].nodeValue = zh;
    });
  }

  /* 按钮 → 真实链接。带上下文的入口：从题库页 / 工作区进导入向导时，目标题库不丢。 */
  function convertNav(scope) {
    Array.prototype.forEach.call(scope.querySelectorAll('[data-act="nav"]'), function (el) {
      var target = routeOf(el);
      if (!target) return;
      if (el.tagName === 'A') { mark(el); return; }
      var href = target;
      if (target === 'import.html') {
        var m = /[?&]bank=([^&]+)/.exec(location.search);
        if (m) href = target + (target.indexOf('?') > -1 ? '&' : '?') + 'bank=' + m[1];
      }
      var a = document.createElement('a');
      a.className = el.className;
      a.setAttribute('href', href);
      a.innerHTML = el.innerHTML;
      copySource(el, a);
      /* 保留原始属性（aria-label / title / data-*），去掉按钮态属性 */
      Array.prototype.forEach.call(el.attributes, function (attr) {
        if (attr.name === 'class' || attr.name === 'type' || attr.name === 'href') return;
        try { a.setAttribute(attr.name, attr.value); } catch (e) {}
      });
      a.setAttribute('data-act', 'nav');
      a.setAttribute('data-route', target);
      if (el.parentNode) el.parentNode.replaceChild(a, el);
      mark(a);
    });
  }

  /* 选中态：域决定「这一块」，文件决定「这一页」。
     - 当前文件对应的导航项：is-active + aria-current="page"
     - 同域的父级入口：is-active，但没有 aria-current（不冒充当前页）
     - 域为空（登录 / 403）：全部清除，不制造假高亮 */
  function mark(el) {
    var href = routeOf(el);
    if (!href) return;
    var file = fileOfRoute(href);
    var domain = FILE_DOMAIN[file] || '';
    var here = currentFile();
    var hereDomain = currentDomain();
    var declared = document.body && document.body.getAttribute('data-nav-domain');
    /* 显式声明域时，文件名不再单独决定「当前页」：
       例如 notes.html 声明 review，就不该同时点亮「资料」和「复习」。 */
    var isHere = file === here && (!declared || domain === hereDomain);
    var inDomain = !!domain && domain === hereDomain;
    el.classList.toggle('is-active', isHere || inDomain);
    if (isHere) el.setAttribute('aria-current', 'page');
    else el.removeAttribute('aria-current');
    if (inDomain && !isHere) el.setAttribute('data-domain-match', 'true');
    else el.removeAttribute('data-domain-match');
  }

  /* 计数：只认 data-act="nav"；没有定义的标签（今天 / 模考）移除角标。 */
  function counts() {
    var hasStore = !!window.eeStore;
    Array.prototype.forEach.call(document.querySelectorAll('[data-act="nav"]'), function (el) {
      var label = el.getAttribute('data-nav-label') || labelOf(el);
      var key = COUNT_KEY[label];
      var badge = el.querySelector('.nav-count');
      if (!key) {
        if (badge) badge.remove();
        return;
      }
      if (!hasStore) return;
      var n = COUNTS[key]();
      if (n == null) return;
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'nav-count';
        el.appendChild(badge);
      }
      badge.textContent = String(n);
      badge.hidden = n === 0;
    });
  }

  function run() {
    /* 覆盖侧脊（含底部设置项）、底导与顶栏里的导航项 */
    var scopes = document.querySelectorAll('.sidebar, .bottomnav, .topbar');
    if (!scopes.length) scopes = [document.body];
    Array.prototype.forEach.call(scopes, normalize);
    Array.prototype.forEach.call(scopes, convertNav);
    /* 侧脊品牌 = 回到今天页 */
    Array.prototype.forEach.call(document.querySelectorAll('.side-brand'), function (el) {
      if (el.tagName === 'A') return;
      var a = document.createElement('a');
      a.className = el.className;
      a.setAttribute('href', 'home.html');
      a.setAttribute('aria-label', '易考宝 · 回到今天');
      /* 品牌不是导航项：不参与计数与选中态，只是回到今天页 */
      a.setAttribute('data-act', 'brand');
      a.setAttribute('data-nav-kind', 'switch-page');
      a.innerHTML = el.innerHTML;
      copySource(el, a);
      if (el.parentNode) el.parentNode.replaceChild(a, el);
    });
    /* 域高亮要重算所有导航项（包括已经是链接的） */
    Array.prototype.forEach.call(document.querySelectorAll('[data-act="nav"]'), mark);
    counts();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();

  /* 数据变化 → 计数重算（另一页写了 storage 时也跟） */
  function refreshCounts() { counts(); }
  if (window.eeStore && window.eeStore.subscribe) {
    window.eeStore.subscribe(function (state, evt) {
      if (evt && evt.type === 'settings') return;
      refreshCounts();
    });
  }
  window.addEventListener('storage', function (e) {
    if (e.key && e.key.indexOf('eeStore') === 0) setTimeout(refreshCounts, 30);
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
    domain: currentDomain,
    fileDomain: function (file) { return FILE_DOMAIN[String(file || '').toLowerCase()] || ''; },
    refresh: function () { run(); },
    refreshCounts: refreshCounts
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
