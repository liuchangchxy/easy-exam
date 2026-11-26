/* 规格页引导：应用 URL 主题参数 → 上报高度供外层文档自适应 → 提供小型交互助手 */
(function () {
  var q = new URLSearchParams(location.search);
  /* 主题/配色/密度：URL 参数优先（设计规范浏览器用），
     没有参数时保持 store.js 已按用户设置写入的值（完整产品原型用）。 */
  var theme = q.get('theme');
  if (theme) document.documentElement.setAttribute('data-theme', theme);
  var palette = q.get('palette');
  if (palette) document.documentElement.setAttribute('data-theme-palette', palette);
  var density = q.get('density');
  if (density === 'compact' || density === 'cozy') document.documentElement.setAttribute('data-density', density);

  /* 产品模式：页面作为最终产品被独立打开时（无 ?spec=1），只呈现最终用户内容——
     设计规格区、状态格、浮层演示与规格工具条由 ee.css §15 隐藏。
     规范浏览器 index.html 以 ?spec=1 打开同一批页面，保留规格内容。 */
  if (!q.get('spec')) document.documentElement.setAttribute('data-ee-product', '');

  function report() {
    var h = Math.max(document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0);
    try { parent.postMessage({ eeSpecHeight: h, eeSpecId: location.pathname }, '*'); } catch (e) {}
  }
  if (document.readyState === 'complete') report();
  else window.addEventListener('load', report);
  window.addEventListener('resize', report);
  if (window.MutationObserver) {
    var mo = new MutationObserver(report);
    mo.observe(document.documentElement, { childList: true, subtree: true, attributes: true });
  }

  /* ======================================================================
     对话框助手
     - 打开：聚焦 [data-autofocus] 或首个可聚焦元素，并记录「打开时的原值」
     - 关闭回焦：触发按钮
     - 未保存保护（T6，渐进增强）：取消类关闭（Escape / 遮罩 / 无动作的关闭钮）
       若用户改过表单且没改回原值，先问「放弃未保存的更改？」；
       带动作的按钮（onclick / data-dlg-commit）是提交，不过问。
     页面可用 data-dlg-guard 声明「内容被改过就保护」、data-dlg-noguard 退出保护，
     或用 eeDialog.markDirty(dlg) 显式标记（如编辑器类内容）。
     ====================================================================== */
  function dlgControls(d) {
    return Array.prototype.filter.call(d.querySelectorAll('input, select, textarea'), function (c) {
      return c.type !== 'hidden';
    });
  }
  function valOf(c) {
    if (c.type === 'checkbox' || c.type === 'radio') return c.checked ? '1' : '0';
    if (c.tagName === 'SELECT' && c.multiple) {
      return Array.prototype.filter.call(c.options, function (o) { return o.selected; })
        .map(function (o) { return o.index; }).join(',');
    }
    return c.value;
  }
  function snapshot(d) {
    d._eePristine = dlgControls(d).map(function (c) { return { el: c, v: valOf(c) }; });
    d._eeEdited = false;
    d._eeForced = false;
  }
  function differs(d) {
    var p = d._eePristine;
    if (!p) return false;
    for (var i = 0; i < p.length; i++) {
      if (!p[i].el.isConnected) continue;
      if (valOf(p[i].el) !== p[i].v) return true;
    }
    return false;
  }
  function isDirty(d) {
    if (!d || d.hasAttribute('data-dlg-noguard')) return false;
    if (d._eeForced) return true;
    if (!d._eeEdited) return false;          /* 用户没动过：程序预填不算未保存 */
    return differs(d);
  }
  /* 用户真实编辑：只在 input/change 由用户触发时打标记（程序赋值不打） */
  document.addEventListener('input', function (e) {
    var d = e.target && e.target.closest ? e.target.closest('dialog') : null;
    if (d) d._eeEdited = true;
  }, true);
  document.addEventListener('change', function (e) {
    var d = e.target && e.target.closest ? e.target.closest('dialog') : null;
    if (d) d._eeEdited = true;
  }, true);

  var guardDlg = null;
  var guardClickBound = false;
  function bindGuard() {
    if (guardClickBound || !guardDlg) return;
    guardClickBound = true;
    guardDlg.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('[data-dlg-guard]') : null;
      if (!b || !guardDlg.contains(b)) return;
      var mode = b.getAttribute('data-dlg-guard');
      var d = guardDlg._eeTarget;
      window.eeDialog.close(guardDlg);       /* 先关确认（焦点回到原对话框） */
      if (mode === 'discard' && d) forceClose(d);
    });
  }
  function ensureGuard() {
    if (guardDlg) return guardDlg;
    var ico = window.eeIcon || function () { return ''; };
    guardDlg = document.createElement('dialog');
    guardDlg.className = 'dlg narrow';
    guardDlg.id = 'ee-dlg-guard';
    guardDlg.setAttribute('data-dlg-noguard', '');
    guardDlg.setAttribute('aria-labelledby', 'ee-dlg-guard-t');
    guardDlg.innerHTML =
      '<div class="dlg-head"><div class="dlg-head-text">' +
      '<p class="dlg-eyebrow">未保存</p>' +
      '<h2 class="dlg-title" id="ee-dlg-guard-t">放弃未保存的更改？</h2></div>' +
      '<button class="icon-btn" type="button" aria-label="关闭" data-dlg-guard="keep">' + ico('x', '15px') + '</button></div>' +
      '<div class="dlg-body">' +
      '<p class="dlg-p" id="ee-dlg-guard-desc"></p>' +
      '<div class="notice warn">' + ico('alert-triangle') + '<div class="notice-body">放弃后这些修改无法恢复；选择「继续编辑」可回到原对话框。</div></div>' +
      '</div>' +
      '<div class="dlg-foot">' +
      '<button class="btn btn-quiet" type="button" data-dlg-guard="keep" data-autofocus>继续编辑</button>' +
      '<button class="btn btn-danger-solid" type="button" data-dlg-guard="discard">放弃更改</button>' +
      '</div>';
    document.body.appendChild(guardDlg);
    bindGuard();
    return guardDlg;
  }
  function askGuard(d) {
    var g = ensureGuard();
    g._eeTarget = d;
    var t = d.querySelector('.dlg-title');
    var name = t && t.textContent.trim() ? t.textContent.trim() : '这个对话框';
    g.querySelector('#ee-dlg-guard-t').textContent = '放弃「' + name + '」里未保存的更改？';
    g.querySelector('#ee-dlg-guard-desc').textContent = '你在「' + name + '」里做了修改，还没有保存。';
    /* 回焦目标=父对话框内首个控件，关闭确认后焦点回到原对话框 */
    var back = d.querySelector('[data-autofocus]') || d.querySelector('button, [href], input, select, textarea');
    window.eeDialog.open(g.id, back || d);
  }
  function restorePristine(d) {
    var p = d._eePristine;
    if (!p) return;
    p.forEach(function (x) {
      if (!x.el.isConnected) return;
      if (x.el.type === 'checkbox' || x.el.type === 'radio') x.el.checked = x.v === '1';
      else if (x.el.tagName === 'SELECT' && x.el.multiple) {
        Array.prototype.forEach.call(x.el.options, function (o) { o.selected = x.v.split(',').indexOf(String(o.index)) >= 0; });
      } else x.el.value = x.v;
    });
  }
  function forceClose(d) {
    restorePristine(d);
    d._eeEdited = false; d._eeForced = false; d._eePristine = null;
    if (typeof d.close === 'function') d.close();
    else d.removeAttribute('open');
  }
  /* 取消类关闭的统一判定：返回 true=允许关，false=已转去确认 */
  function requestClose(d) {
    if (!d) return true;
    if (d.hasAttribute('data-dlg-guard') ? differs(d) : isDirty(d)) { askGuard(d); return false; }
    return true;
  }

  /* 回焦目标：触发器可见可聚焦时用它；触发器是菜单项（打开后菜单已收起）
     时改用菜单触发器；都不可用则返回 null，不强行 focus。 */
  function canFocus(el) {
    if (!el || el.nodeType !== 1 || !el.isConnected) return false;
    if (el.disabled || el.inert) return false;
    if (typeof el.focus !== 'function') return false;
    if (el === document.body || el === document.documentElement) return false;
    if (el.getAttribute('aria-hidden') === 'true') return false;
    var cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    if (el.offsetParent === null && cs.position !== 'fixed') return false;
    return true;
  }
  function restoreTarget(d) {
    var t = d._trigger;
    if (canFocus(t)) return t;
    var menu = t && t.closest ? t.closest('.menu') : null;
    if (menu) { var mt = menuTrigger(menu); if (canFocus(mt)) return mt; }
    var p = t && t.parentElement;
    while (p && p !== document.body) {
      if (p.matches && p.matches('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])') && canFocus(p)) return p;
      p = p.parentElement;
    }
    /* 脚本打开且没有可用触发器（如流程步骤 afterRender）：先试打开前的焦点元素，
       再退到页面主内容里的第一个可用控件——比把焦点丢给 body 好，
       键盘用户不会因为「不知道焦点去哪了」而重新从头 Tab。 */
    if (canFocus(d._eePrevFocus)) return d._eePrevFocus;
    var fb = document.querySelector('#main-content button:not([disabled]), main button:not([disabled]), .content button:not([disabled])');
    if (canFocus(fb)) return fb;
    return null;
  }
  function restoreFocus(d) {
    var t = restoreTarget(d);
    if (t) t.focus();
  }

  window.eeDialog = {
    open: function (id, trigger) {
      var d = document.getElementById(id);
      if (!d) return;
      d._trigger = trigger || document.activeElement;
      /* 打开前的焦点元素：触发器不可用时（隐藏的菜单项、脚本打开）的后备回焦目标 */
      var pf = document.activeElement;
      d._eePrevFocus = (pf && pf !== document.body && pf !== document.documentElement) ? pf : null;
      if (typeof d.showModal === 'function') d.showModal();
      else d.setAttribute('open', '');
      snapshot(d);
      /* Escape 拦截：cancel 不冒泡，必须绑在对话框自身上；
         页面自己注册的 cancel 监听先跑（注册顺序在前），它 preventDefault 后这里不再插手 */
      if (!d._eeCancelBound) {
        d._eeCancelBound = true;
        d.addEventListener('cancel', function (e) {
          if (e.defaultPrevented) return;
          if (isDirty(e.currentTarget)) { e.preventDefault(); askGuard(e.currentTarget); }
        });
      }
      /* 关闭回焦：close 同样不冒泡，也绑在对话框上。
         只在焦点真的丢了（落在 body / 对话框自身）时才补一次回焦，
         不覆盖页面自己安排的关闭后焦点。脚本触发的打开（如流程步骤的
         afterRender）不会让触发器获得焦点，原生回焦也就无从生效。 */
      if (!d._eeCloseBound) {
        d._eeCloseBound = true;
        d.addEventListener('close', function () {
          var ae = document.activeElement;
          if (ae && ae !== document.body && ae !== document.documentElement && ae !== d) return;
          restoreFocus(d);
        });
      }
      var f = d.querySelector('[data-autofocus]') || d.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      if (f) f.focus();
    },
    close: function (d) {
      if (typeof d.close === 'function') d.close();
      else d.removeAttribute('open');
      restoreFocus(d);
    },
    /* 页面显式标记「有未保存内容」（用于非表单类编辑器内容） */
    markDirty: function (d) {
      if (typeof d === 'string') d = document.getElementById(d);
      if (d) { d._eeEdited = true; d._eeForced = true; }
    },
    isDirty: function (d) {
      if (typeof d === 'string') d = document.getElementById(d);
      return isDirty(d);
    }
  };

  /* 关闭钮：带动作（onclick / data-dlg-commit）= 提交，不过问；其余=取消 */
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-dlg-close]') : null;
    if (!t) return;
    var d = t.closest('dialog');
    if (!d) return;
    e.preventDefault();
    var commit = t.hasAttribute('data-dlg-commit') || t.hasAttribute('onclick') || !!t.onclick;
    if (commit || requestClose(d)) window.eeDialog.close(d);
  });

  /* 点击遮罩 = 取消（与 Escape 同权；components.html §09 已文档化） */
  document.addEventListener('click', function (e) {
    var d = e.target;
    if (!d || d.tagName !== 'DIALOG' || !d.open) return;
    if (e.defaultPrevented) return;
    if (isDirty(d)) { e.preventDefault(); e.stopPropagation(); askGuard(d); return; }
    window.eeDialog.close(d);
  });

  /* 关闭后回焦由对话框自身的 close 监听完成（见 eeDialog.open）：
     cancel 与 close 都不冒泡，document 级监听收不到。 */

  /* 菜单助手：方向键 + Escape + 外部点击；Escape/外部点击后焦点回迁触发器 */
  function menuTrigger(menu) {
    if (menu._trigger && menu._trigger.isConnected) return menu._trigger;
    var p = menu.parentElement;
    if (p) { var t = p.querySelector('[data-menu-trigger]'); if (t) return t; }
    var prev = menu.previousElementSibling;
    while (prev) {
      if (prev.matches && prev.matches('[data-menu-trigger]')) return prev;
      prev = prev.previousElementSibling;
    }
    return null;
  }
  document.addEventListener('keydown', function (e) {
    var menu = e.target.closest ? e.target.closest('.menu') : null;
    if (menu && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      var items = Array.prototype.filter.call(menu.querySelectorAll('.menu-item:not(:disabled)'), function (el) { return el.offsetParent !== null; });
      var i = items.indexOf(document.activeElement);
      e.preventDefault();
      var n = e.key === 'ArrowDown' ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
      if (items[n]) items[n].focus();
    }
    if (e.key === 'Escape') {
      var open = document.querySelector('.menu');
      if (open && open.offsetParent !== null) {
        var trig = menuTrigger(open);
        open.hidden = true;
        if (trig && trig.isConnected) trig.focus();
      }
    }
  });
  document.addEventListener('click', function (e) {
    var trig = e.target.closest ? e.target.closest('[data-menu-trigger]') : null;
    if (trig) {
      var m = trig.parentElement ? trig.parentElement.querySelector('.menu') : null;
      if (m) m._trigger = trig;
    }
    var open = document.querySelector('.menu');
    if (open && open.offsetParent !== null && !open.contains(e.target) && !(e.target.closest && e.target.closest('[data-menu-trigger]'))) {
      var t2 = menuTrigger(open);
      open.hidden = true;
      if (t2 && t2.isConnected && document.activeElement && open.contains(document.activeElement)) t2.focus();
    }
  });

  /* 分段控件 / 标签页：点击切换 aria（演示用，无后端） */
  document.addEventListener('click', function (e) {
    var seg = e.target.closest ? e.target.closest('.segmented .segment') : null;
    if (seg && !seg.disabled) {
      var group = seg.closest('.segmented');
      group.querySelectorAll('.segment').forEach(function (s) { s.setAttribute('aria-checked', 'false'); });
      seg.setAttribute('aria-checked', 'true');
      /* 信息密度分段是唯一「点了立刻生效」的分段：写 / 删 data-density（ee.css §1.5）。
         页面若要自己做（如 tokens.html），行为一致，不会冲突。
         有 store 时同步写回设置，密度才跨页面一致（第三轮：配置全局生效）。 */
      if (group.getAttribute('data-seg') === 'density') {
        var dv = seg.getAttribute('data-v');
        if (dv === 'compact') document.documentElement.setAttribute('data-density', 'compact');
        else document.documentElement.removeAttribute('data-density');
        if (window.eeStore) window.eeStore.setSetting('density', dv === 'compact' ? 'compact' : 'cozy');
      }
    }
    var tab = e.target.closest ? e.target.closest('.tabs .tab') : null;
    if (tab && !tab.disabled && tab.hasAttribute('data-panel')) {
      var tabs = tab.closest('.tabs');
      tabs.querySelectorAll('.tab').forEach(function (t) { t.setAttribute('aria-selected', 'false'); });
      tab.setAttribute('aria-selected', 'true');
      var scope = tab.closest('[data-tab-scope]') || document;
      scope.querySelectorAll('[data-tab-panel]').forEach(function (p) { p.hidden = p.getAttribute('data-tab-panel') !== tab.getAttribute('data-panel'); });
      report();
    }
  });

  /* Toast 助手（瞬态成功反馈的唯一通道） */
  window.eeToast = function (msg, kind) {
    var host = document.querySelector('.toast-host');
    if (!host) {
      host = document.createElement('div');
      host.className = 'toast-host';
      host.setAttribute('aria-live', 'polite');
      host.setAttribute('role', 'status');
      document.body.appendChild(host);
    }
    var t = document.createElement('div');
    t.className = 'toast' + (kind === 'bad' ? ' bad' : '');
    t.innerHTML = (window.eeIcon ? window.eeIcon(kind === 'bad' ? 'alert-triangle' : 'check') : '') +
      '<span>' + msg + '</span>' +
      '<button class="toast-close" aria-label="关闭提示">' + (window.eeIcon ? window.eeIcon('x', '13px') : '×') + '</button>';
    t.querySelector('.toast-close').addEventListener('click', function () { t.remove(); });
    host.appendChild(t);
    setTimeout(function () { t.remove(); }, 4000);
    report();
  };

  /* ======================================================================
     产品外壳统一接线（第四轮：消灭死控件）
     ----------------------------------------------------------------------
     15 个屏幕都加载本脚本，侧栏品牌、顶栏搜索 / 明暗 / 语言 / 账户菜单与
     命令面板统一在这里接线。规则：
       · 顶栏控件带 data-ee-shell 才由本模块接管；页面自己的入口
         （如工作区「聚焦页内搜索」）保持原样，不重复绑定；
       · 明暗 / 语言写回共享设置，并给页面留钩子
         （window.eeShellThemeChanged / eeShellLangChanged）；
       · 账户按钮旁边没有菜单时，补一个标准账户菜单；
       · 搜索入口打开命令面板（Ctrl/⌘+K 同入口），面板条目来自 nav.js 的
         唯一导航契约，不另建一份路由表。
     ====================================================================== */
  var ico = function (name, size) { return window.eeIcon ? window.eeIcon(name, size || '15px') : ''; };
  var DICT = window.eeI18N || {};
  function t(key) {
    var pair = DICT[key];
    if (!pair) return null;
    var lang = (window.eeStore && window.eeStore.settings().lang) || 'zh';
    return pair[lang === 'en' ? 1 : 0];
  }
  var SHELL = {
    theme: function () { return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'; },
    lang: function () { return (window.eeStore && window.eeStore.settings().lang) || 'zh'; },
    routes: function () {
      /* 命令面板只列出与当前用户相关的入口（CR-12）：实例管理对普通用户不出现 */
      if (window.eeNav && window.eeNav.visibleRoutes) return window.eeNav.visibleRoutes();
      return (window.eeNav && window.eeNav.routes) || {};
    },
    setTheme: setTheme,
    setLang: setLang,
    openPalette: openPalette
  };
  window.eeShell = SHELL;

  /* ---------- 明暗 ---------- */
  function syncThemeButtons() {
    var dark = SHELL.theme() === 'dark';
    document.querySelectorAll('[data-ee-shell="theme"]').forEach(function (b) {
      var use = b.querySelector('use');
      if (use) use.setAttribute('href', dark ? '#i-moon' : '#i-sun');
      var label = dark ? t('shell.tb.theme.toLight') : t('shell.tb.theme.toDark');
      b.title = label;
      b.setAttribute('aria-label', label);
    });
  }
  function setTheme(next, announce) {
    if (next !== 'dark' && next !== 'light') return;
    document.documentElement.setAttribute('data-theme', next);
    if (window.eeStore) window.eeStore.setSetting('theme', next);
    syncThemeButtons();
    if (typeof window.eeShellThemeChanged === 'function') window.eeShellThemeChanged(next);
    if (announce) window.eeToast(next === 'dark' ? '已切换为深色' : '已切换为浅色');
  }

  /* ---------- 语言（只覆盖产品外壳，见 assets/i18n.js） ---------- */
  function applyI18n() {
    var en = SHELL.lang() === 'en';
    document.documentElement.setAttribute('lang', en ? 'en' : 'zh-CN');
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var pair = DICT[el.getAttribute('data-i18n')];
      if (!pair) return;                       /* 页面自己的词典：不动 */
      var value = pair[en ? 1 : 0];
      if (value == null) return;
      /* 纯文本：整体替换；带图标：只换第一个文本节点；无文本：写 title + aria-label */
      if (!el.children.length) { el.textContent = value; return; }
      var done = false;
      for (var i = 0; i < el.childNodes.length; i++) {
        var n = el.childNodes[i];
        if (n.nodeType === 3 && n.nodeValue.trim()) { n.nodeValue = value; done = true; break; }
      }
      if (!done) { el.title = value; el.setAttribute('aria-label', value); }
    });
  }
  function syncLangButtons() {
    document.querySelectorAll('[data-ee-shell="lang"]').forEach(function (b) {
      var label = t('shell.tb.lang');
      if (label) { b.title = label; b.setAttribute('aria-label', label); }
    });
  }
  function setLang(next, announce) {
    if (next !== 'en' && next !== 'zh') return;
    if (window.eeStore) window.eeStore.setSetting('lang', next);
    applyI18n();
    syncLangButtons();
    if (typeof window.eeShellLangChanged === 'function') window.eeShellLangChanged(next);
    if (announce) window.eeToast(next === 'en' ? 'Interface language: English' : '界面语言：简体中文');
  }

  /* ---------- 命令面板（搜索入口的唯一落地） ---------- */
  var palette = null;
  function buildPalette() {
    if (palette) return palette;
    var host = document.createElement('div');
    host.className = 'cmd-host';
    host.hidden = true;
    host.innerHTML =
      '<div class="cmd-scrim" data-cmd-close></div>' +
      '<div class="cmd-panel" role="dialog" aria-modal="true" aria-label="' + (t('shell.cmd.title') || '搜索与跳转') + '">' +
      '<div class="cmd-input-row">' + ico('search', '15px') +
      '<input class="cmd-input" type="text" placeholder="' + (t('shell.cmd.placeholder') || '') + '" aria-label="' + (t('shell.cmd.title') || '') + '">' +
      '<kbd class="cmd-kbd">Esc</kbd></div>' +
      '<ul class="cmd-list" role="listbox"></ul>' +
      '<div class="cmd-foot">' + (t('shell.cmd.foot') || '') + '</div>' +
      '</div>';
    document.body.appendChild(host);
    palette = host;
    var input = host.querySelector('.cmd-input');
    var list = host.querySelector('.cmd-list');
    var active = 0;
    var items = [];
    function render() {
      var q = input.value.trim().toLowerCase();
      var routes = SHELL.routes();
      items = Object.keys(routes).filter(function (label) {
        if (label === '完整产品原型' || label === '命令面板') return false;
        return !q || label.toLowerCase().indexOf(q) > -1;
      }).map(function (label) { return { label: label, href: routes[label] }; });
      active = 0;
      list.innerHTML = items.length ? items.map(function (it, i) {
        return '<li class="cmd-item' + (i === 0 ? ' is-on' : '') + '" role="option" aria-selected="' + (i === 0) + '" data-href="' + it.href + '">' +
          ico('arrow-right', '14px') + '<span>' + it.label + '</span></li>';
      }).join('') : '<li class="cmd-empty">' + (t('shell.cmd.empty') || '没有匹配的页面') + '</li>';
    }
    function move(step) {
      var els = list.querySelectorAll('.cmd-item');
      if (!els.length) return;
      els[active].classList.remove('is-on');
      els[active].setAttribute('aria-selected', 'false');
      active = (active + step + els.length) % els.length;
      els[active].classList.add('is-on');
      els[active].setAttribute('aria-selected', 'true');
      els[active].scrollIntoView({ block: 'nearest' });
    }
    function go(el) {
      var href = el && el.getAttribute('data-href');
      if (!href) return;
      closePalette();
      location.href = href;
    }
    input.addEventListener('input', render);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); go(list.querySelector('.cmd-item.is-on')); }
      else if (e.key === 'Escape') { e.preventDefault(); closePalette(); }
    });
    list.addEventListener('click', function (e) {
      var item = e.target.closest ? e.target.closest('.cmd-item') : null;
      if (item) go(item);
    });
    host.querySelector('[data-cmd-close]').addEventListener('click', closePalette);
    palette._render = render;
    palette._input = input;
    return palette;
  }
  function openPalette() {
    var p = buildPalette();
    p.hidden = false;
    p._render();
    setTimeout(function () { p._input.focus(); p._input.select(); }, 20);
  }
  function closePalette() {
    if (palette) palette.hidden = true;
  }

  /* ---------- 账户菜单：旁边没有菜单的按钮，补一个标准菜单 ---------- */
  function ensureAccountMenu() {
    document.querySelectorAll('.user-mini, [data-ee-shell="account"]').forEach(function (btn) {
      var anchor = btn.closest('.menu-anchor');
      if (anchor && anchor.querySelector('.menu')) return;      /* 页面已有菜单 */
      if (!anchor) {
        anchor = document.createElement('div');
        anchor.className = 'menu-anchor';
        if (btn.parentNode) { btn.parentNode.insertBefore(anchor, btn); anchor.appendChild(btn); }
      }
      btn.setAttribute('data-menu-trigger', '');
      btn.setAttribute('aria-haspopup', 'menu');
      var menu = document.createElement('div');
      menu.className = 'menu';
      menu.setAttribute('role', 'menu');
      menu.hidden = true;
      /* CR-12 两向规则：实例管理只对实例管理员有意义，普通用户的菜单里整项不出现——
         不是置灰。题库面的管理入口由各产品屏按 relevant() 自行判定。 */
      var instItem = (window.eeStore && !window.eeStore.relevant('instance.manage')) ? '' :
        '<a class="menu-item" role="menuitem" href="instance.html" data-ee-instance-item data-i18n="shell.menu.instance">' + ico('users') + (t('shell.menu.instance') || '实例管理') + '</a>';
      menu.innerHTML =
        '<a class="menu-item" role="menuitem" href="settings.html#account" data-i18n="shell.menu.profile">' + ico('user') + (t('shell.menu.profile') || '账户资料') + '</a>' +
        instItem +
        '<div class="menu-sep" role="separator"></div>' +
        '<button class="menu-item is-danger" type="button" role="menuitem" data-ee-signout data-i18n="shell.menu.logout">' + ico('logout') + (t('shell.menu.logout') || '退出登录') + '</button>';
      anchor.appendChild(menu);
    });
  }
  /* 角色可能在本页切换（演示壳/设置页），账户菜单要跟着相关性重算：
     实例管理只对实例管理员有意义，普通用户整项不出现（CR-12）。 */
  function syncAccountMenus() {
    var store = window.eeStore;
    if (!store || !store.relevant) return;
    var show = store.relevant('instance.manage');
    document.querySelectorAll('.menu [data-ee-instance-item]').forEach(function (el) {
      el.hidden = !show;
    });
  }
  function ensureSignoutDialog() {
    if (document.getElementById('ee-dlg-signout')) return;
    var d = document.createElement('dialog');
    d.className = 'dlg narrow';
    d.id = 'ee-dlg-signout';
    d.setAttribute('data-dlg-noguard', '');
    d.setAttribute('aria-labelledby', 'ee-dlg-signout-t');
    d.innerHTML =
      '<div class="dlg-head"><div class="dlg-head-text">' +
      '<p class="dlg-eyebrow">' + (t('shell.menu.logout') || '退出登录') + '</p>' +
      '<h2 class="dlg-title" id="ee-dlg-signout-t">' + (t('shell.signout.title') || '退出登录') + '</h2></div>' +
      '<button class="icon-btn" type="button" aria-label="关闭" data-dlg-close>' + ico('x', '15px') + '</button></div>' +
      '<div class="dlg-body"><p class="dlg-p">' + (t('shell.signout.desc') || '') + '</p></div>' +
      '<div class="dlg-foot">' +
      '<button class="btn btn-quiet" type="button" data-dlg-close data-autofocus>' + (t('shell.signout.cancel') || '取消') + '</button>' +
      '<button class="btn btn-danger-solid" type="button" id="ee-dlg-signout-go">' + (t('shell.signout.ok') || '退出登录') + '</button>' +
      '</div>';
    document.body.appendChild(d);
    d.querySelector('#ee-dlg-signout-go').addEventListener('click', function () {
      window.eeDialog.close(d);
      if (window.eeStore) window.eeStore.logout();
      location.href = 'login.html';
    });
  }

  /* ---------- 菜单开闭：页面没接的，这里统一接（Escape/外点由上方通用逻辑管） ---------- */
  document.addEventListener('click', function (e) {
    var trig = e.target.closest ? e.target.closest('[data-menu-trigger]') : null;
    if (!trig) return;
    if (e.defaultPrevented) return;
    var anchor = trig.closest('.menu-anchor') || trig.parentElement;
    var menu = anchor ? anchor.querySelector('.menu') : null;
    if (!menu) return;
    e.preventDefault();
    var willOpen = menu.hidden;
    document.querySelectorAll('.menu').forEach(function (m) { m.hidden = true; });
    document.querySelectorAll('[data-menu-trigger]').forEach(function (x) { x.setAttribute('aria-expanded', 'false'); });
    if (willOpen) {
      menu.hidden = false;
      menu._trigger = trig;
      trig.setAttribute('aria-expanded', 'true');
      var first = menu.querySelector('.menu-item:not(:disabled)');
      if (first) first.focus();
    }
  });
  /* 退出登录：页面自己的对话框优先，否则用外壳确认框 */
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-ee-signout]') : null;
    if (!b) return;
    e.preventDefault();
    var menu = b.closest('.menu');
    if (menu) menu.hidden = true;
    var own = document.getElementById('dlg-logout');
    if (own) window.eeDialog.open('dlg-logout', b);
    else window.eeDialog.open('ee-dlg-signout', b);
  });

  /* ---------- 绑定 ---------- */
  function wireShell() {
    ensureAccountMenu();
    ensureSignoutDialog();
    applyI18n();
    syncThemeButtons();
    syncLangButtons();
    syncAccountMenus();
    document.querySelectorAll('[data-ee-shell="theme"]').forEach(function (b) {
      if (b._eeShellTheme) return;
      b._eeShellTheme = true;
      b.addEventListener('click', function () { setTheme(SHELL.theme() === 'dark' ? 'light' : 'dark', true); });
    });
    document.querySelectorAll('[data-ee-shell="lang"]').forEach(function (b) {
      if (b._eeShellLang) return;
      b._eeShellLang = true;
      b.addEventListener('click', function () { setLang(SHELL.lang() === 'en' ? 'zh' : 'en', true); });
    });
    document.querySelectorAll('[data-ee-shell="search"]').forEach(function (b) {
      if (b._eeShellSearch) return;
      b._eeShellSearch = true;
      b.addEventListener('click', function (e) { e.preventDefault(); openPalette(); });
    });
    /* 顶栏搜索框：聚焦即打开命令面板 */
    document.querySelectorAll('.tb-search input, [data-ee-shell="search-input"]').forEach(function (inp) {
      if (inp._eeShellSearch) return;
      inp._eeShellSearch = true;
      inp.addEventListener('focus', function () { inp.blur(); openPalette(); });
    });
    /* Ctrl/⌘+K：与顶栏搜索同一入口 */
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        if (palette && !palette.hidden) closePalette();
        else openPalette();
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wireShell);
  else wireShell();
  /* 其他页改了设置（storage 事件）→ 同步外壳 */
  window.addEventListener('storage', function (e) {
    if (e.key && e.key.indexOf('eeStore') === 0) { setTimeout(function () { applyI18n(); syncThemeButtons(); syncAccountMenus(); }, 30); }
  });
  /* 本页改了角色/实例角色 → 账户菜单与命令面板的相关性要立刻重算 */
  if (window.eeStore && window.eeStore.subscribe) {
    window.eeStore.subscribe(function () { syncAccountMenus(); });
  }
})();
