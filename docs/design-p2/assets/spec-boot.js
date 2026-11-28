/* 规格页引导：应用 URL 主题参数 → 上报高度供外层文档自适应 → 提供小型交互助手 */
(function () {
  /* 空 favicon：避免浏览器对 /favicon.ico 的默认请求在控制台留下 404。
     页面自己声明了 icon 时不覆盖。 */
  if (!document.querySelector('link[rel~="icon"]')) {
    var fav = document.createElement('link');
    fav.rel = 'icon';
    fav.href = 'data:,';
    (document.head || document.documentElement).appendChild(fav);
  }
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
     设计规格区、状态格、浮层演示与规格工具条由 ee.css §18 隐藏。
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

  /* 菜单助手：方向键 + Escape + 外部点击；Escape/外部点击后焦点回迁触发器。
     行为只认 role="menu" / role="menuitem"（语义属性），不认 .menu class。 */
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
  function menuItems(menu) {
    return Array.prototype.filter.call(menu.querySelectorAll('[role="menuitem"]:not(:disabled)'), function (el) {
      return el.offsetParent !== null;
    });
  }
  function closeMenu(menu, refocus) {
    if (!menu) return;
    var trig = menuTrigger(menu);
    menu.hidden = true;
    if (trig && trig.isConnected) trig.setAttribute('aria-expanded', 'false');
    if (refocus && trig && trig.isConnected) trig.focus();
  }
  document.addEventListener('keydown', function (e) {
    var menu = e.target.closest ? e.target.closest('[role="menu"]') : null;
    if (menu && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      var items = menuItems(menu);
      if (!items.length) return;
      var i = items.indexOf(document.activeElement);
      e.preventDefault();
      var n = e.key === 'ArrowDown' ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
      if (items[n]) items[n].focus();
    }
    if (e.key === 'Escape') {
      var open = document.querySelector('[role="menu"]');
      if (open && open.offsetParent !== null) closeMenu(open, true);
    }
  });
  /* 触发器开闭：捕获阶段接管，页面自己的触发器监听不再执行——全产品只有这一套。 */
  document.addEventListener('click', function (e) {
    var trig = e.target.closest ? e.target.closest('[data-menu-trigger]') : null;
    if (!trig) return;
    var anchor = trig.closest('.menu-anchor') || trig.parentElement;
    var menu = anchor ? anchor.querySelector('[role="menu"]') : null;
    if (!menu) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    var willOpen = menu.hidden;
    document.querySelectorAll('[role="menu"]').forEach(function (m) { m.hidden = true; });
    document.querySelectorAll('[data-menu-trigger]').forEach(function (x) { x.setAttribute('aria-expanded', 'false'); });
    if (willOpen) {
      menu.hidden = false;
      menu._trigger = trig;
      trig.setAttribute('aria-expanded', 'true');
      placeMenu(menu, trig);
      var first = menuItems(menu)[0];
      if (first) first.focus();
    }
  }, true);
  /* 菜单项点击后收起（页面自己不再各写一份） */
  document.addEventListener('click', function (e) {
    var item = e.target.closest ? e.target.closest('[role="menu"] [role="menuitem"]') : null;
    if (item) {
      var menu = item.closest('[role="menu"]');
      if (menu) menu.hidden = true;
    }
  });
  document.addEventListener('click', function (e) {
    var open = document.querySelector('[role="menu"]');
    if (open && open.offsetParent !== null && !open.contains(e.target) && !(e.target.closest && e.target.closest('[data-menu-trigger]'))) {
      var t2 = menuTrigger(open);
      open.hidden = true;
      if (t2 && t2.isConnected && document.activeElement && open.contains(document.activeElement)) t2.focus();
    }
  });

  /* 分段控件 / 标签页：点击切换 aria（演示用，无后端）。
     行为只认 data-act（由 normalizeShell 从旧 class 归一化而来）。 */
  document.addEventListener('click', function (e) {
    var seg = e.target.closest ? e.target.closest('[data-act="segment"]') : null;
    if (seg && !seg.disabled) {
      var group = seg.closest('[data-act="segmented"]') || seg.closest('.segmented');
      if (!group) return;
      group.querySelectorAll('[data-act="segment"]').forEach(function (s) { s.setAttribute('aria-checked', 'false'); });
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
    var tab = e.target.closest ? e.target.closest('[data-act="tab"]') : null;
    if (tab && !tab.disabled && tab.hasAttribute('data-panel')) {
      var tabs = tab.closest('[data-act="tabs"]') || tab.closest('.tabs');
      if (!tabs) return;
      tabs.querySelectorAll('[data-act="tab"]').forEach(function (t) { t.setAttribute('aria-selected', 'false'); });
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
     产品外壳统一接线（第五轮）
     ----------------------------------------------------------------------
     这一层只做四件事，全部按行为属性识别对象：
       · 账户菜单：唯一实现。头像按钮 → 设置 / 账户资料 / 实例管理（按
         relevant('instance.manage')）/ 分隔线 / 退出登录；退出走同一个
         确认对话框与同一个跳转目标（login.html）。
       · 命令面板：同时索引页面、题库、题目、资料，分组显示；Ctrl/⌘+K
         与顶栏搜索同一入口。搜索入口在捕获阶段接管，页面自带的页内搜索
         绑定不会抢走这次点击。
       · 动作语义：data-act="open-row" / data-row-href（整行可点）、
         data-act="exit-task"（退出当前任务，必须确认）、
         data-act="signout"（统一退出）、aria-disabled 的可见原因。
       · 迁移：旧页面的 class / onclick 只在 normalizeShell() 里读一次，
         之后所有行为只认 data-act / data-ee-shell / role。
     ====================================================================== */
  var ico = function (name, size) { return window.eeIcon ? window.eeIcon(name, size || '15px') : ''; };
  var DICT = window.eeI18N || {};
  function lang() { return (window.eeStore && window.eeStore.settings().lang) || 'zh'; }
  function t(key) {
    var pair = DICT[key];
    if (!pair) return null;
    return pair[lang() === 'en' ? 1 : 0];
  }
  /* 第五轮新增文案的本地兜底；词条已列进报告，待 assets/i18n.js 收录。 */
  var COPY = {
    'cmd.title': ['搜索与跳转', 'Search and jump'],
    'cmd.placeholder': ['搜索页面、题库、题目或资料…', 'Search pages, banks, questions, or notes…'],
    'cmd.group.page': ['页面', 'Pages'],
    'cmd.group.bank': ['题库', 'Banks'],
    'cmd.group.question': ['题目', 'Questions'],
    'cmd.group.note': ['资料', 'Notes'],
    'cmd.foot': ['↑↓ 选择 · Enter 打开 · Esc 关闭 · 搜索页面、题库、题目与资料', '↑↓ select · Enter open · Esc close · searches pages, banks, questions and notes'],
    'cmd.empty': ['没有匹配「{q}」的页面、题库、题目或资料', 'Nothing matches “{q}” among pages, banks, questions, or notes'],
    'cmd.emptyHint': ['试试题库名、题干片段或资料标题', 'Try a bank name, a phrase from a question, or a note title'],
    'cmd.noData': ['这里还没有可搜索的页面、题库、题目或资料', 'No pages, banks, questions, or notes to search yet'],
    'cmd.count': ['{n} 题', '{n} questions'],
    'cmd.shared': ['共享', 'Shared'],
    'disabled.reason': ['此操作当前不可用', 'This action is unavailable right now'],
    'exit.title': ['退出当前任务？', 'Leave this task?'],
    'exit.desc.practice': ['退出后这一组的作答会存成草稿，可以从今天页继续；已提交的评级不会撤回。', 'Your answers in this set will be saved as a draft and can be resumed from Today. Ratings already submitted will not be withdrawn.'],
    'exit.desc.exam': ['退出会暂存草稿，你可以在宽限期内续考；超过宽限期服务端将按已暂存内容收卷。', 'Leaving saves a draft. You can resume within the grace period; after that the server collects what was saved.'],
    'exit.desc.import': ['离开后导入任务会继续，并显示在题库的导入记录里。', 'The import keeps running and will appear in the bank’s import history.'],
    'exit.desc.task': ['退出后当前进度会保存，可以稍后继续。', 'Your progress will be saved and you can continue later.'],
    'exit.keep': ['继续当前任务', 'Keep going'],
    'exit.stash': ['退出并暂存', 'Leave and save draft'],
    'exit.leave': ['退出', 'Leave'],
    'nav.back': ['返回上一级', 'Back'],
    'nav.exit': ['退出当前任务', 'Leave task'],
    'account.menu': ['账户菜单', 'Account menu']
  };
  function t2(key) {
    var pair = COPY[key];
    if (!pair) return '';
    return pair[lang() === 'en' ? 1 : 0];
  }
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function currentFile() {
    var p = location.pathname.split('/');
    return (p[p.length - 1] || '').toLowerCase();
  }
  /* 屏幕目录里的路由是裸文件名；规范页（/pages/components.html）要加 screens/。 */
  function resolveHref(href) {
    if (!href) return href;
    if (/^(?:[a-z]+:|\/|#)/i.test(href)) return href;
    if (/^(?:screens\/|\.\.?\/)/i.test(href)) return href;
    if (/\/pages\/[^\/]+$/.test(location.pathname)) return 'screens/' + href;
    return href;
  }

  var SHELL = {
    theme: function () { return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'; },
    lang: lang,
    routes: function () {
      /* 命令面板只列出与当前用户相关的入口（CR-12）：实例管理对普通用户不出现 */
      if (window.eeNav && window.eeNav.visibleRoutes) return window.eeNav.visibleRoutes();
      if (window.eeNav && window.eeNav.routes) return window.eeNav.routes;
      /* 规范页没有 nav.js 时的最小页面清单（不复制产品路由表） */
      if (/\/pages\/[^\/]+$/.test(location.pathname)) {
        return { '控件库': './components.html', '状态与外壳': './states.html', '设计令牌': './tokens.html' };
      }
      return {};
    },
    setTheme: setTheme,
    setLang: setLang,
    openPalette: openPalette,
    closePalette: closePalette,
    signOut: doSignout,
    exitTask: exitTask,
    searchItems: searchItems,
    refreshAccountMenus: ensureAccountMenus
  };
  window.eeShell = SHELL;

  /* 菜单按可用空间展开：默认落在触发器的静态位置（CSS 绝对定位），
     超出视口时用位移把它推回可见区——用 transform 而不是改 left/bottom，
     因为后两者会改变绝对定位的原点，反而把菜单甩到别处。 */
  function placeMenu(menu, trig) {
    menu.style.transform = '';
    menu.style.maxHeight = '';
    menu.style.overflowY = '';
    var tr = trig.getBoundingClientRect();
    var mr = menu.getBoundingClientRect();
    var vw = window.innerWidth, vh = window.innerHeight;
    var pad = 8, dx = 0, dy = 0;
    if (mr.bottom > vh - pad) dy = (vh - pad) - mr.bottom;
    if (mr.top + dy < pad) dy = pad - mr.top;
    if (mr.right > vw - pad) dx = (vw - pad) - mr.right;
    if (mr.left + dx < pad) dx = pad - mr.left;
    if (dx || dy) menu.style.transform = 'translate(' + Math.round(dx) + 'px,' + Math.round(dy) + 'px)';
    var after = menu.getBoundingClientRect();
    if (after.height > vh - pad * 2) {
      menu.style.maxHeight = (vh - pad * 2) + 'px';
      menu.style.overflowY = 'auto';
    }
  }

  /* ---------- 明暗 ---------- */
  function syncThemeButtons() {
    var dark = SHELL.theme() === 'dark';
    document.querySelectorAll('[data-ee-shell="theme"]').forEach(function (b) {
      var use = b.querySelector('use');
      if (use) use.setAttribute('href', dark ? '#i-moon' : '#i-sun');
      var label = dark ? t('shell.tb.theme.toLight') : t('shell.tb.theme.toDark');
      if (label) { b.title = label; b.setAttribute('aria-label', label); }
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
    var en = lang() === 'en';
    document.documentElement.setAttribute('lang', en ? 'en' : 'zh-CN');
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var pair = DICT[el.getAttribute('data-i18n')];
      if (!pair) return;                       /* 页面自己的词典：不动 */
      var value = pair[en ? 1 : 0];
      if (value == null) return;
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
    syncPaletteCopy();
    if (typeof window.eeShellLangChanged === 'function') window.eeShellLangChanged(next);
    if (announce) window.eeToast(next === 'en' ? 'Interface language: English' : '界面语言：简体中文');
  }

  /* ======================================================================
     命令面板：页面 / 题库 / 题目 / 资料 四类对象
     ----------------------------------------------------------------------
     页面来自 nav.js 的唯一路由契约；题库 / 题目 / 资料来自 eeStore。
     跳转目标用稳定 id：workspace.html?bank=<id>、question.html?id=<id>、
     notes.html?note=<id>。
     ====================================================================== */
  var palette = null;

  function searchItems(query) {
    var q = String(query || '').trim().toLowerCase();
    var list = [];
    var store = window.eeStore;
    function titleScore(title) {
      if (!q) return 0;
      var i = title.toLowerCase().indexOf(q);
      return i === 0 ? 0 : (i > 0 ? 1 : 3);
    }
    function push(group, title, meta, href, icon, extra) {
      if (!title) return;
      var hay = (title + ' ' + (meta || '') + ' ' + (extra || '')).toLowerCase();
      if (q && hay.indexOf(q) < 0) return;
      list.push({ group: group, title: title, meta: meta || '', href: resolveHref(href), icon: icon, score: titleScore(title), seq: list.length });
    }
    /* 页面：同一路由的中英两条只保留当前语言的一条；没有对应语言时保留原文 */
    var routes = SHELL.routes();
    var byHref = {};
    var enUI = lang() === 'en';
    Object.keys(routes).forEach(function (label) {
      if (label === '完整产品原型' || label === '命令面板' || label === 'Command palette') return;
      var href = routes[label];
      var isEn = /^[A-Za-z]/.test(label);
      var cur = byHref[href];
      if (!cur || (isEn === enUI && cur.isEn !== enUI)) byHref[href] = { label: label, isEn: isEn };
    });
    Object.keys(byHref).forEach(function (href) {
      push('page', byHref[href].label, '', href, 'arrow-right', byHref[href].label);
    });
    if (store) {
      /* 题库：只索引未归档的；已归档题库不应从全局搜索里被当成可打开对象 */
      store.banks({ archived: false }).forEach(function (b) {
        var count = t2('cmd.count').replace('{n}', b.count || 0);
        push('bank', b.name, count + (b.shared ? ' · ' + t2('cmd.shared') : ''), 'workspace.html?bank=' + encodeURIComponent(b.id), 'library', (b.category || '') + ' ' + (b.desc || ''));
      });
      /* 题目：题干、章节、题型、标签都可搜 */
      store.questions().forEach(function (q2) {
        if (q2.archived) return;
        var bank = store.bankName ? store.bankName(q2.bankId) : '';
        push('question', q2.stem, bank + ' · ' + (q2.type || '题目'), 'question.html?id=' + encodeURIComponent(q2.id), 'exam', (q2.chapter || '') + ' ' + ((q2.tags || []).join(' ')));
      });
      /* 资料：标题、标签、正文（store 里没有正文时正文腿自然为空） */
      store.notes().forEach(function (n) {
        var bank = store.bankName ? store.bankName(n.bankId) : '';
        push('note', n.title, bank, 'notes.html?note=' + encodeURIComponent(n.id), 'note', ((n.tags || []).join(' ')) + ' ' + (n.body || ''));
      });
    }
    var order = { page: 0, bank: 1, question: 2, note: 3 };
    list.sort(function (a, b) {
      if (order[a.group] !== order[b.group]) return order[a.group] - order[b.group];
      if (a.score !== b.score) return a.score - b.score;
      return a.seq - b.seq;
    });
    var limit = { page: 99, bank: 8, question: 8, note: 8 };
    var used = {};
    return list.filter(function (it) {
      used[it.group] = (used[it.group] || 0) + 1;
      return used[it.group] <= limit[it.group];
    });
  }

  function groupLabel(group) {
    if (group === 'page') return t2('cmd.group.page');
    if (group === 'bank') return t2('cmd.group.bank');
    if (group === 'question') return t2('cmd.group.question');
    return t2('cmd.group.note');
  }

  function buildPalette() {
    if (palette) return palette;
    var host = document.createElement('div');
    host.className = 'cmd-host';
    host.hidden = true;
    host.innerHTML =
      '<div class="cmd-scrim" data-act="close-palette"></div>' +
      '<div class="cmd-panel" role="dialog" aria-modal="true">' +
      '<div class="cmd-input-row">' + ico('search', '15px') +
      '<input class="cmd-input" type="text" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="ee-cmd-list">' +
      '<kbd class="cmd-kbd">Esc</kbd></div>' +
      '<ul class="cmd-list" id="ee-cmd-list" role="listbox"></ul>' +
      '<div class="cmd-foot"></div>' +
      '</div>';
    document.body.appendChild(host);
    palette = host;
    var input = host.querySelector('.cmd-input');
    var list = host.querySelector('.cmd-list');
    var foot = host.querySelector('.cmd-foot');
    var panel = host.querySelector('.cmd-panel');
    var active = 0;
    var items = [];

    function syncCopy() {
      panel.setAttribute('aria-label', t2('cmd.title'));
      input.setAttribute('aria-label', t2('cmd.title'));
      input.setAttribute('placeholder', t2('cmd.placeholder'));
      foot.textContent = t2('cmd.foot');
    }
    function render() {
      var q = input.value.trim();
      items = searchItems(q);
      active = 0;
      if (!items.length) {
        var msg = q ? t2('cmd.empty').replace('{q}', q) : t2('cmd.noData');
        list.innerHTML = '<li class="cmd-empty">' + escHtml(msg) + '</li>' +
          (q ? '<li class="cmd-empty" style="padding-top:0">' + escHtml(t2('cmd.emptyHint')) + '</li>' : '');
        return;
      }
      var html = '';
      var last = '';
      items.forEach(function (it, i) {
        if (it.group !== last) {
          last = it.group;
          html += '<li class="cmd-group rule-label" role="presentation" style="padding:var(--sp-3) var(--sp-4) var(--sp-1)">' +
            escHtml(groupLabel(it.group)) + '</li>';
        }
        html += '<li class="cmd-item' + (i === 0 ? ' is-on' : '') + '" role="option" aria-selected="' + (i === 0) + '" data-index="' + i + '" data-href="' + escHtml(it.href) + '">' +
          ico(it.icon, '14px') +
          '<span style="flex:1 1 auto;min-width:0;display:block">' +
          '<span style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + escHtml(it.title) + '</span>' +
          (it.meta ? '<span class="hint" style="display:block;margin:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + escHtml(it.meta) + '</span>' : '') +
          '</span></li>';
      });
      list.innerHTML = html;
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
    function go(i) {
      var it = items[i];
      if (!it) return;
      closePalette();
      location.href = it.href;
    }
    input.addEventListener('input', render);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); go(active); }
      else if (e.key === 'Escape') { e.preventDefault(); closePalette(); }
    });
    list.addEventListener('click', function (e) {
      var item = e.target.closest ? e.target.closest('.cmd-item') : null;
      if (!item) return;
      go(Number(item.getAttribute('data-index')));
    });
    host.querySelector('[data-act="close-palette"]').addEventListener('click', closePalette);
    palette._render = render;
    palette._input = input;
    palette._syncCopy = syncCopy;
    return palette;
  }
  function syncPaletteCopy() {
    if (palette && palette._syncCopy) palette._syncCopy();
  }
  function openPalette() {
    var p = buildPalette();
    p._trigger = document.activeElement;
    p.hidden = false;
    p._syncCopy();
    p._render();
    setTimeout(function () { p._input.focus(); p._input.select(); }, 20);
  }
  function closePalette() {
    if (!palette || palette.hidden) return;
    palette.hidden = true;
    var t0 = palette._trigger;
    if (t0 && t0.isConnected && t0 !== document.body) t0.focus();
  }

  /* ======================================================================
     账户菜单：唯一实现（13 个屏同一形态）
     ----------------------------------------------------------------------
     头像按钮 → 设置 / 账户资料 / 实例管理（仅相关时）/ 分隔线 / 退出登录。
     页面已有的菜单会被重建为这一套；设置页的页内分区索引（.set-rail）
     不在这里，保持原样。
     ====================================================================== */
  function accountMenuHtml() {
    var showInst = !window.eeStore || !window.eeStore.relevant || window.eeStore.relevant('instance.manage');
    var settingsLabel = t('shell.menu.settings') || '设置';
    var profileLabel = t('shell.menu.profile') || '账户资料';
    var instanceLabel = t('shell.menu.instance') || '实例管理';
    var logoutLabel = t('shell.menu.logout') || '退出登录';
    return '<a class="menu-item" role="menuitem" href="' + resolveHref('settings.html') + '" data-act="menu-settings">' +
        ico('settings') + '<span data-i18n="shell.menu.settings">' + escHtml(settingsLabel) + '</span></a>' +
      '<a class="menu-item" role="menuitem" href="' + resolveHref('settings.html#account') + '" data-act="menu-profile">' +
        ico('user') + '<span data-i18n="shell.menu.profile">' + escHtml(profileLabel) + '</span></a>' +
      '<a class="menu-item" role="menuitem" href="' + resolveHref('instance.html') + '" data-ee-instance-item' + (showInst ? '' : ' hidden') + '>' +
        ico('users') + '<span data-i18n="shell.menu.instance">' + escHtml(instanceLabel) + '</span></a>' +
      '<div class="menu-sep" role="separator" data-ee-instance-sep' + (showInst ? '' : ' hidden') + '></div>' +
      '<button class="menu-item is-danger" type="button" role="menuitem" data-act="signout" data-ee-signout>' +
        ico('logout') + '<span data-i18n="shell.menu.logout">' + escHtml(logoutLabel) + '</span></button>';
  }

  function ensureAccountMenus() {
    document.querySelectorAll('.topbar .user-mini, .mobile-top .user-mini, .topbar [data-ee-shell="account"], .mobile-top [data-ee-shell="account"]').forEach(function (btn) {
      if (btn.tagName !== 'BUTTON') {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = btn.className;
        b.textContent = (btn.textContent || '').trim() || 'A';
        Array.prototype.forEach.call(btn.attributes, function (attr) {
          if (attr.name === 'class' || attr.name === 'type') return;
          try { b.setAttribute(attr.name, attr.value); } catch (e) {}
        });
        if (btn.parentNode) btn.parentNode.replaceChild(b, btn);
        btn = b;
      }
      if (!btn.getAttribute('type')) btn.type = 'button';
      if (!btn.getAttribute('aria-label')) btn.setAttribute('aria-label', t2('account.menu'));
      if (!btn.getAttribute('title')) btn.title = t2('account.menu');
      btn.setAttribute('data-ee-shell', 'account');
      btn.setAttribute('data-act', 'account-menu');
      btn.setAttribute('data-menu-trigger', '');
      btn.setAttribute('aria-haspopup', 'menu');
      if (!btn.hasAttribute('aria-expanded')) btn.setAttribute('aria-expanded', 'false');
      var anchor = btn.closest('.menu-anchor');
      if (!anchor) {
        anchor = document.createElement('div');
        anchor.className = 'menu-anchor';
        if (btn.parentNode) { btn.parentNode.insertBefore(anchor, btn); anchor.appendChild(btn); }
      }
      var menu = anchor.querySelector('[role="menu"]');
      if (!menu) {
        menu = document.createElement('div');
        anchor.appendChild(menu);
      }
      menu.className = 'menu';
      menu.setAttribute('role', 'menu');
      menu.hidden = true;
      menu.innerHTML = accountMenuHtml();
    });
    syncAccountMenus();
  }

  /* 角色可能在本页切换（演示壳 / 设置页），账户菜单要跟着相关性重算：
     实例管理只对实例管理员有意义，普通用户整项不出现（CR-12）。 */
  function syncAccountMenus() {
    var store = window.eeStore;
    if (!store || !store.relevant) return;
    var show = store.relevant('instance.manage');
    document.querySelectorAll('[data-ee-instance-item]').forEach(function (el) { el.hidden = !show; });
    document.querySelectorAll('[data-ee-instance-sep]').forEach(function (el) { el.hidden = !show; });
  }

  function doSignout() {
    if (window.eeStore) window.eeStore.logout();
    if (window.eeToast) window.eeToast(t('shell.menu.logout') || '已退出登录');
    setTimeout(function () { location.href = resolveHref('login.html'); }, 120);
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
      '<p class="dlg-eyebrow" data-i18n="shell.menu.logout">' + escHtml(t('shell.menu.logout') || '退出登录') + '</p>' +
      '<h2 class="dlg-title" id="ee-dlg-signout-t" data-i18n="shell.signout.title">' + escHtml(t('shell.signout.title') || '退出登录') + '</h2></div>' +
      '<button class="icon-btn" type="button" aria-label="关闭" data-dlg-close>' + ico('x', '15px') + '</button></div>' +
      '<div class="dlg-body"><p class="dlg-p" data-i18n="shell.signout.desc">' + escHtml(t('shell.signout.desc') || '') + '</p></div>' +
      '<div class="dlg-foot">' +
      '<button class="btn btn-quiet" type="button" data-dlg-close data-autofocus data-i18n="shell.signout.cancel">' + escHtml(t('shell.signout.cancel') || '取消') + '</button>' +
      '<button class="btn btn-danger-solid" type="button" id="ee-dlg-signout-go" data-i18n="shell.signout.ok">' + escHtml(t('shell.signout.ok') || '退出登录') + '</button>' +
      '</div>';
    document.body.appendChild(d);
    d.querySelector('#ee-dlg-signout-go').addEventListener('click', function () {
      window.eeDialog.close(d);
      doSignout();
    });
  }

  /* ---------- 退出当前任务：统一的 data-act="exit-task" ---------- */
  function ensureExitDialog() {
    var d = document.getElementById('ee-dlg-exit-task');
    if (d) return d;
    d = document.createElement('dialog');
    d.className = 'dlg narrow';
    d.id = 'ee-dlg-exit-task';
    d.setAttribute('data-dlg-noguard', '');
    d.setAttribute('aria-labelledby', 'ee-dlg-exit-t');
    d.innerHTML =
      '<div class="dlg-head"><div class="dlg-head-text">' +
      '<p class="dlg-eyebrow">' + escHtml(t2('nav.exit')) + '</p>' +
      '<h2 class="dlg-title" id="ee-dlg-exit-t">' + escHtml(t2('exit.title')) + '</h2></div>' +
      '<button class="icon-btn" type="button" aria-label="关闭" data-dlg-close>' + ico('x', '15px') + '</button></div>' +
      '<div class="dlg-body"><p class="dlg-p" id="ee-dlg-exit-desc"></p></div>' +
      '<div class="dlg-foot">' +
      '<button class="btn btn-quiet" type="button" data-dlg-close data-autofocus>' + escHtml(t2('exit.keep')) + '</button>' +
      '<button class="btn btn-primary" type="button" id="ee-dlg-exit-go">' + escHtml(t2('exit.leave')) + '</button>' +
      '</div>';
    document.body.appendChild(d);
    d.querySelector('#ee-dlg-exit-go').addEventListener('click', function () {
      var to = d._eeExitTo;
      window.eeDialog.close(d);
      if (to) location.href = to;
      else if (history.length > 1) history.back();
    });
    return d;
  }
  function exitTask(el) {
    var dlgId = el.getAttribute('data-exit-dialog');
    if (dlgId && document.getElementById(dlgId)) {
      window.eeDialog.open(dlgId, el);
      return;
    }
    var kind = el.getAttribute('data-exit-kind') || 'task';
    var d = ensureExitDialog();
    d._eeExitTo = resolveHref(el.getAttribute('data-exit-to') || el.getAttribute('href') || '');
    d.querySelector('.dlg-eyebrow').textContent = t2('nav.exit');
    d.querySelector('.dlg-title').textContent = t2('exit.title');
    d.querySelector('[data-autofocus]').textContent = t2('exit.keep');
    d.querySelector('#ee-dlg-exit-desc').textContent = t2('exit.desc.' + kind) || t2('exit.desc.task');
    d.querySelector('#ee-dlg-exit-go').textContent = kind === 'exam' ? t2('exit.stash') : t2('exit.leave');
    window.eeDialog.open(d.id, el);
  }

  /* ======================================================================
     归一化：旧 class / onclick 只在这里读一次
     ====================================================================== */
  function normalizeShell() {
    /* 1) 顶栏 / 移动顶栏里带搜索图标的按钮 → 全局搜索入口（捕获阶段接管） */
    document.querySelectorAll('.topbar .icon-btn, .mobile-top .icon-btn').forEach(function (b) {
      if (b.querySelector('use[href="#i-search"]') && !b.hasAttribute('data-ee-shell')) {
        b.setAttribute('data-ee-shell', 'search');
        b.setAttribute('data-act', 'open-search');
      }
    });
    /* 旧式顶栏搜索框 → 行为属性；之后只按 data-ee-shell="search-input" 绑定 */
    document.querySelectorAll('.tb-search input').forEach(function (inp) {
      if (!inp.getAttribute('data-ee-shell')) inp.setAttribute('data-ee-shell', 'search-input');
    });
    /* 2) 退出类 onclick → data-act="exit-task"（保留页面自己的确认对话框） */
    document.querySelectorAll('[onclick]').forEach(function (el) {
      if (el.closest('dialog') || el.closest('.cmd-list')) return;
      var oc = el.getAttribute('onclick') || '';
      var m = /eeDialog\.open\(\s*['"]([^'"]+)['"]/.exec(oc);
      if (m && /(dlg-exit|ex-dlg-exit|dlg-leave)/.test(m[1])) {
        el.setAttribute('data-act', 'exit-task');
        el.setAttribute('data-exit-dialog', m[1]);
        el.removeAttribute('onclick');
        return;
      }
      if (/EErun\.exit\s*\(/.test(oc)) {
        el.setAttribute('data-act', 'exit-task');
        el.setAttribute('data-exit-dialog', 'dlg-exit');
        el.removeAttribute('onclick');
        return;
      }
      if (/EEexam\.exit\s*\(/.test(oc)) {
        el.setAttribute('data-act', 'exit-task');
        el.setAttribute('data-exit-dialog', 'ex-dlg-exit');
        el.removeAttribute('onclick');
        return;
      }
      /* 3) 退出登录 → 统一确认对话框与跳转目标 */
      if (/dlg-logout/.test(oc)) {
        el.setAttribute('data-act', 'signout');
        el.removeAttribute('onclick');
      }
    });
    /* 4) 分段 / 页签 / 菜单：语义属性补齐 */
    document.querySelectorAll('.segmented').forEach(function (g) {
      g.setAttribute('data-act', 'segmented');
      g.querySelectorAll('.segment').forEach(function (s) { s.setAttribute('data-act', 'segment'); });
    });
    document.querySelectorAll('.tabs').forEach(function (g) {
      g.setAttribute('data-act', 'tabs');
      g.querySelectorAll('.tab').forEach(function (t) { t.setAttribute('data-act', 'tab'); });
    });
    document.querySelectorAll('.menu').forEach(function (m) {
      if (!m.getAttribute('role')) m.setAttribute('role', 'menu');
    });
    document.querySelectorAll('.menu-item').forEach(function (mi) {
      if (!mi.getAttribute('role')) mi.setAttribute('role', 'menuitem');
    });
    /* 5) 导航语义三类动作：返回父页面 / 切换一级页面 / 退出当前任务 */
    document.querySelectorAll('.page-back').forEach(function (el) {
      el.setAttribute('data-nav-kind', 'back-parent');
      if (!el.getAttribute('aria-label') && !(el.textContent || '').trim()) el.setAttribute('aria-label', t2('nav.back'));
    });
    document.querySelectorAll('[data-act="nav"]').forEach(function (el) {
      el.setAttribute('data-nav-kind', 'switch-page');
    });
    document.querySelectorAll('[data-act="exit-task"]').forEach(function (el) {
      el.setAttribute('data-nav-kind', 'exit-task');
      if (!el.getAttribute('aria-label') && !(el.textContent || '').trim()) el.setAttribute('aria-label', t2('nav.exit'));
    });
    /* 6) 整行可点：只给「没有页面专属动作」的 data-row-href 行补语义；
       已有 data-act="open-question" 等页面动作的行由页面自己处理，不抢。 */
    document.querySelectorAll('[data-row-href]').forEach(function (row) {
      if (row.getAttribute('data-act') && row.getAttribute('data-act') !== 'open-row') return;
      if (!row.getAttribute('role')) row.setAttribute('role', 'link');
      if (!row.hasAttribute('tabindex')) row.setAttribute('tabindex', '0');
      if (!row.getAttribute('data-act')) row.setAttribute('data-act', 'open-row');
    });
    document.querySelectorAll('[data-act="open-row"]').forEach(function (row) {
      if (!row.getAttribute('role')) row.setAttribute('role', 'link');
      if (!row.hasAttribute('tabindex')) row.setAttribute('tabindex', '0');
    });
  }

  /* ======================================================================
     全局动作委托（捕获阶段，页面自带监听不会重复执行）
     ====================================================================== */
  /* 搜索入口：先于页面自己的 focusSearch 生效 */
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-ee-shell="search"], [data-act="open-search"]') : null;
    if (!b || b.closest('.cmd-host')) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    openPalette();
  }, true);

  /* 退出登录：唯一确认对话框 + 唯一跳转目标 */
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-act="signout"], [data-ee-signout], [data-logout]') : null;
    if (!b || b.closest('.cmd-list')) return;
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    var menu = b.closest('[role="menu"]');
    if (menu) menu.hidden = true;
    /* 页面自己的退出对话框已经确认过 → 直接执行，不再二次确认 */
    if (b.hasAttribute('data-logout') && b.closest('dialog')) {
      var dlg = b.closest('dialog');
      window.eeDialog.close(dlg);
      doSignout();
      return;
    }
    window.eeDialog.open('ee-dlg-signout', b);
  }, true);

  /* 退出当前任务：页面给了 data-exit-dialog 就用页面对话框，否则用统一确认框 */
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-act="exit-task"]') : null;
    if (!b) return;
    if (b.hasAttribute('data-exit-dialog')) return;   /* 交给捕获分支 */
    e.preventDefault();
    exitTask(b);
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('[data-act="exit-task"][data-exit-dialog]') : null;
    if (!b) return;
    e.preventDefault();
    exitTask(b);
  }, true);

  /* 整行可点：行主体跳转；行内按钮 / 链接 / 其它动作不触发。
     已有页面专属动作（data-act="open-question" 等）的行由页面自己处理。 */
  function openRowOf(target) {
    var row = target.closest ? target.closest('[data-act="open-row"], [data-row-href]') : null;
    if (!row) return null;
    if (row.getAttribute('data-act') && row.getAttribute('data-act') !== 'open-row') return null;
    return row;
  }
  document.addEventListener('click', function (e) {
    var row = openRowOf(e.target);
    if (!row) return;
    if (row.getAttribute('aria-disabled') === 'true') return;
    var inner = e.target.closest('a, button, input, select, textarea, label, [role="button"], [data-act]:not([data-act="open-row"])');
    if (inner && inner !== row && row.contains(inner)) return;
    var href = row.getAttribute('data-row-href') || row.getAttribute('data-href');
    if (!href) return;
    e.preventDefault();
    location.href = resolveHref(href);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var row = openRowOf(e.target);
    if (!row || e.target !== row) return;
    if (row.getAttribute('aria-disabled') === 'true') return;
    var href = row.getAttribute('data-row-href') || row.getAttribute('data-href');
    if (!href) return;
    e.preventDefault();
    location.href = resolveHref(href);
  });

  /* 禁用原因：不能只在 hover 里。点击时把可见说明 / data 属性读成 toast。 */
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[aria-disabled="true"]') : null;
    if (!el || el.closest('.cmd-list')) return;
    e.preventDefault();
    e.stopPropagation();
    var reason = '';
    var ids = (el.getAttribute('aria-describedby') || '').split(/\s+/);
    ids.forEach(function (id) {
      var n = id && document.getElementById(id);
      if (n) reason += ' ' + (n.textContent || '').trim();
    });
    if (!reason.trim()) reason = el.getAttribute('data-disabled-reason') || '';
    if (!reason.trim()) reason = t2('disabled.reason');
    if (window.eeToast) window.eeToast(reason.trim(), 'bad');
  }, true);

  /* ---------- 绑定 ---------- */
  function wireShell() {
    normalizeShell();
    ensureAccountMenus();
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
      b.addEventListener('click', function () { setLang(lang() === 'en' ? 'zh' : 'en', true); });
    });
    /* 顶栏搜索框：聚焦即打开命令面板（只按行为属性绑定） */
    document.querySelectorAll('[data-ee-shell="search-input"]').forEach(function (inp) {
      if (inp._eeShellSearch) return;
      inp._eeShellSearch = true;
      inp.addEventListener('focus', function () { inp.blur(); openPalette(); });
    });
    /* Ctrl/⌘+K：与顶栏搜索同一入口 */
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K') && !e.isComposing) {
        e.preventDefault();
        if (palette && !palette.hidden) closePalette();
        else openPalette();
      }
      if (e.key === 'Escape' && palette && !palette.hidden) {
        e.preventDefault();
        closePalette();
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wireShell);
  else wireShell();

  /* ======================================================================
     软键盘占位（手机端输入不被遮挡的唯一机制）
     ----------------------------------------------------------------------
     原生 --kb-inset 只有声明没有更新方，输入框聚焦弹出软键盘后，
     .focus-foot 仍按 bottom:0 贴在被键盘盖住的位置，主操作点不到。
     这里用 visualViewport 的视口差实时写 --kb-inset，键盘收起归零。
     同时给 <html> 打 data-kb，让页面可按需收起源码里的次要区域。
     ====================================================================== */
  (function wireKeyboardInset() {
    var root = document.documentElement;
    function apply() {
      var vv = window.visualViewport;
      if (!vv) return;
      var inset = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop));
      if (inset < 40) inset = 0;              /* 地址栏收缩一类的小抖动不算键盘 */
      root.style.setProperty('--kb-inset', inset + 'px');
      if (inset > 0) root.setAttribute('data-kb', '1');
      else root.removeAttribute('data-kb');
    }
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', apply);
      window.visualViewport.addEventListener('scroll', apply);
    }
    window.addEventListener('orientationchange', function () { setTimeout(apply, 250); });
    apply();
  })();
  /* ---------- 侧栏学习状态：全产品唯一一份数字 ----------
     之前 11 个页面各写一段同步，四个页面还留着写死的「到期 12 / 错题 8 / 本周新增 46」。
     这里统一按 store 算，页面只负责渲染外壳片段的 HTML，不再各自维护口径。 */
  function sideNumbers() {
    var S = window.eeStore;
    if (!S) return null;
    var killed = function (r) { return S.reviewKilled ? S.reviewKilled(r) : !!r.killed_at; };
    var alive = function (rows) { return rows.filter(function (r) { return !killed(r); }); };
    var sessions = (S.sessions ? S.sessions() : []).filter(function (s) {
      /* 题库被删的孤儿会话不算「未完成」：它在选择器里也打不开，只会在数字上虚高。 */
      return !s.bankId || !!S.bank(s.bankId);
    });
    return {
      due: S.executableReview ? S.executableReview().length : 0,
      mistakes: alive(S.reviewQueue ? S.reviewQueue(null, 'mistakes') : []).length,
      weak: alive(S.reviewQueue ? S.reviewQueue(null, 'weak') : []).length,
      killedN: (S.reviewQueue ? S.reviewQueue() : []).filter(killed).length,
      sessions: sessions.length
    };
  }
  function syncSideStudy() {
    var n = sideNumbers();
    if (!n) return;
    var map = { 'side-due': n.due, 'side-mistakes': n.mistakes, 'side-weak': n.weak, 'side-sessions': n.sessions };
    Object.keys(map).forEach(function (id) {
      Array.prototype.forEach.call(document.querySelectorAll('#' + id), function (el) {
        el.textContent = String(map[id]);
        var row = el.closest ? el.closest('.side-study-row') : null;
        if (row) row.hidden = false;
      });
    });
    /* 覆盖写死的演示数字：任何仍在侧栏里的纯文字行都从这份数据取值。
       页面上还写着「本周新增」的，说明它没有被本轮改造覆盖到——直接移除，
       不把一个无来源的数字继续摆在侧栏。 */
    Array.prototype.forEach.call(document.querySelectorAll('.side-study-row'), function (row) {
      var label = row.querySelector('span');
      var txt = label ? label.textContent.trim() : '';
      if (/本周新增/.test(txt)) row.remove();
    });
  }
  window.eeSyncSideStudy = syncSideStudy;
  syncSideStudy();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', syncSideStudy);
  window.addEventListener('load', function () { setTimeout(syncSideStudy, 0); });

  /* 其他页改了设置（storage 事件）→ 同步外壳 */
  window.addEventListener('storage', function (e) {
    if (e.key && e.key.indexOf('eeStore') === 0) {
      setTimeout(function () { applyI18n(); syncThemeButtons(); syncAccountMenus(); syncSideStudy(); }, 30);
    }
  });
  /* 本页改了角色 / 实例角色 → 账户菜单与命令面板的相关性要立刻重算 */
  if (window.eeStore && window.eeStore.subscribe) {
    window.eeStore.subscribe(function (state, evt) {
      syncAccountMenus();
      syncSideStudy();
      /* 主题变化（含系统明暗跟随）要同步顶栏图标与 aria-label */
      if (!evt || evt.type === 'theme' || evt.type === 'external' || evt.type === 'settings') syncThemeButtons();
    });
  }
})();
