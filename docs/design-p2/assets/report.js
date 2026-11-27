/* ==========================================================================
   report.js — 逐题明细共享组件（ee.css §15 .rep-*）
   --------------------------------------------------------------------------
   交卷当次的报告、练习的历史归档报告、模考的归档成绩报告共用这一套渲染与
   展开交互：同一道题在三处的呈现、字段顺序、版本提示、回看入口完全一致
   （CONTRACT §3.3 / BR-109 / CR-25）。

   每条 item 的字段：
     qid        题目 id（可选，缺省时不带「查看该题当前版本」链接）
     bankId     题库 id（可选，缺省时取 opts.bankId）
     type       题型名
     subjective 是否主观题（不自动判分）
     answered   是否作答
     ratio      客观题得分率 0 / 1 / 1/3…；主观题为 null
     correctness CORRECT | PARTIAL | INCORRECT | UNGRADED | BLANK
     stem       题干
     mine       我的作答（未作答传「未作答」）
     answer     标准答案
     explain    解析
     missed / extra / multi   多选漏选与错选
     rating / ratingDue       FSRS 评级与下次到期
     ver / verAt              判分所依据的题目版本快照
     cur / curAt / curNote    当前版本（与 ver 不同时说明改了什么）
     ai        { text, src }   AI 解释（本期不提供 AI 建议标签，仅展示解释）

   opts:
     withVer   true 时渲染判分版本快照条（三处报告都传 true：交卷当次与
               过后回看必须是同一份内容）
     qPrefix   题目详情页相对前缀（flows/ 传 '../screens/'）
     rPrefix   复习/错题页相对前缀
     bankId    题库 id，item 上没带 bankId 时用它补
     scope     同一页有多份列表时的作用域后缀，保证 aria-controls 唯一

   对外 API：
     itemHtml(it, i, withVer, opts)   单题 HTML
     itemsHtml(items, withVer, opts)  列表 HTML（.rep-list 内部）
     toolbarHtml(items, opts)         筛选 / 展开工具栏 HTML
     blockHtml(items, withVer, opts)  工具栏 + 列表 + 空状态，一整块
     bind(node)                      委托展开、筛选、全部展开 / 收起
   ========================================================================== */
window.eeReport = (function () {
  var VERDICT = {
    CORRECT: { tag: 'ok', text: '回答正确' },
    PARTIAL: { tag: 'warn', text: '部分正确' },
    INCORRECT: { tag: 'bad', text: '回答错误' },
    UNGRADED: { tag: 'plain', text: '未判分' },
    BLANK: { tag: '', text: '未作答' }
  };
  /* 快速筛选档位：与 VERDICT 的 correctness 对齐，未判分不在快速筛选里
     （主观题恒定未判分，筛它没有决策价值）。 */
  var FILTERS = [
    { key: 'all', label: '全部' },
    { key: 'INCORRECT', label: '错题' },
    { key: 'PARTIAL', label: '部分正确' },
    { key: 'BLANK', label: '未作答' }
  ];
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function itemHtml(it, i, withVer, opts) {
    opts = opts || {};
    it = it || {};
    var v = VERDICT[it.correctness] || VERDICT.BLANK;
    var bodyId = 'rep-item-' + i + '-' + (withVer ? 'v' : 'l') + '-' + (opts.scope || 'x');
    /* 折叠态题干摘要：一行截断，全文放 title。裸 overflow:hidden 会把题干
       切成看不出内容的碎片，所以必须配 text-overflow 与 title。 */
    var stem = esc(it.stem);
    var head = '<button type="button" class="rep-item-head" aria-expanded="false" aria-controls="' + bodyId + '">' +
      '<span class="rep-item-n">' + (i + 1) + '</span>' +
      '<span class="rep-item-type">' + esc(it.type) + '</span>' +
      '<span class="tag ' + v.tag + '">' + v.text + '</span>' +
      '<span class="rep-item-stem" title="' + stem + '">' + stem + '</span>' +
      '<span class="rep-item-spacer"></span>' +
      (withVer ? verHead(it) : '') +
      '<svg class="od-icon rep-item-caret" viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 9.5 12 15l5.5-5.5"/></svg>' +
      '</button>';
    var scoreTxt = it.subjective
      ? '不计入客观题得分'
      : (it.answered ? '得分率 ' + Math.round(it.ratio * 100) + '%' : '未作答 · 按 0 分计分，仍占满分');
    var rating = it.rating
      ? '<span class="tag brand">' + esc(it.rating) + '</span> <span class="muted">下次到期 ' + esc(it.ratingDue || '未调度') + '</span>'
      : (it.subjective ? '<span class="muted">主观题不参与评级</span>' : '<span class="muted">未评级</span>');
    var gap = '';
    if ((it.missed && it.missed.length) || (it.extra && it.extra.length)) {
      var extraLabel = it.multi ? '多选 ' : '错选 ';
      gap = '<div><div class="rule-label">差距</div><div class="od-cluster ee-mt-4">' +
        (it.extra || []).map(function (x) { return '<span class="tag bad">' + extraLabel + esc(x) + '</span>'; }).join('') +
        (it.missed || []).map(function (x) { return '<span class="tag warn">漏选 ' + esc(x) + '</span>'; }).join('') +
        '</div></div>';
    }
    var qp = [];
    if (it.qid) qp.push('id=' + encodeURIComponent(it.qid));
    var bank = it.bankId || opts.bankId;
    if (bank) qp.push('bank=' + encodeURIComponent(bank));
    var href = (opts.qPrefix || '') + 'question.html' + (qp.length ? '?' + qp.join('&') : '');
    /* 复习页定位：带上题目 id 与题库 id，让复习页能定位并高亮这一题，
       而不是只把用户丢到错题列表页顶部。 */
    var rq = [];
    if (it.qid) rq.push('qid=' + encodeURIComponent(it.qid));
    if (bank) rq.push('bank=' + encodeURIComponent(bank));
    /* 题干是第三重定位依据。报告快照里的题目 id 与复习队列的行 id 是两套编号
       （报告存交卷当时的题目快照 id，复习队列有自己的行 id），只带 qid 会在两套
       编号对不上时退化成「跳到错题列表页」——那正是要消除的行为。带上题干，
       review.html 才能在两套编号之间架桥，真正落到那一行。
       归一化函数由 store.js 统一提供（S.normStem），两端必须同一个实现才谈得上
       比对；store.js 缺失（组件演示页）时退化成只带 qid + bank，定位能力降级
       但不报错。 */
    var norm = window.eeStore && window.eeStore.normStem;
    if (it.stem && norm) rq.push('stem=' + encodeURIComponent(norm(it.stem)));
    var rHref = (opts.rPrefix || '') + 'review.html?tab=mistakes' + (rq.length ? '&' + rq.join('&') : '');
    var body = '<div class="rep-item-body" id="' + bodyId + '" hidden>';
    if (withVer) {
      body += '<div class="rep-ver">' +
        '<span class="rep-ver-tags">' +
        '<span class="tag plain">判分版本 ' + esc(it.ver) + '</span>' +
        '<span class="mono muted">' + esc(it.verAt) + ' 保存</span>' +
        (it.cur && it.cur !== it.ver ? '<span class="tag warn">当前 ' + esc(it.cur) + '</span>' : '<span class="tag">与当前版本一致</span>') +
        '</span>' +
        '<p class="rep-ver-note">' + (it.cur && it.cur !== it.ver
          ? '题目在 ' + esc(it.curAt) + ' 改过：' + esc(it.curNote) + '本报告仍按交卷时的 ' + esc(it.ver) + ' 判分，不会变。'
          : '这道题交卷后没有再改过。') + '</p>' +
        '</div>';
    }
    body += '<p class="rep-stem">' + stem + '</p>' +
      '<dl class="rep-kv">' +
      '<dt>我的作答</dt><dd' + (it.subjective ? '' : ' class="mono"') + '>' + esc(it.mine) + '</dd>' +
      '<dt>标准答案</dt><dd class="mono">' + esc(it.answer) + '</dd>' +
      '<dt>判定结果</dt><dd><span class="tag ' + v.tag + '">' + v.text + '</span>　' + esc(scoreTxt) + '</dd>' +
      '<dt>评级</dt><dd>' + rating + '</dd>' +
      '</dl>' + gap +
      '<div><div class="rule-label">' + (it.subjective ? '参考解析' : '官方解析') + '</div><p class="rep-parse">' + esc(it.explain) + '</p></div>';
    if (it.ai) {
      body += '<div><div class="rule-label">AI 解释</div><p class="rep-parse">' + esc(it.ai.text) + '</p>' +
        '<div class="ai-src ee-mt-4"><span class="tag brand">AI</span><span>' + esc(it.ai.src) + '</span></div></div>';
    }
    body += '<div class="rep-item-acts">' +
      /* qid 缺省时不给「查看该题当前版本」：没有 id 的 question.html 只能落到「未选择题目」
         状态，那是一个把用户导向空页的死入口。宁可不给按钮（本文件头部的字段说明即此契约）。 */
      (it.qid ? '<a class="btn btn-sm btn-quiet" href="' + href + '">查看该题当前版本</a>' : '') +
      ((v.tag === 'bad' || v.tag === 'warn') ? '<a class="btn btn-sm btn-quiet" href="' + rHref + '">在错题里打开</a>' : '') +
      '</div></div>';
    return '<div class="rep-item" data-correctness="' + (it.correctness || 'BLANK') + '">' + head + body + '</div>';
  }
  /* 行头版本指示：只有一个低权重元素。判分版本与当前版本真的不同时才提亮，
     否则一行小字说明「与交卷时一致」——版本信息不该是行头最抢眼的东西。 */
  function verHead(it) {
    var same = !it.cur || it.cur === it.ver;
    var hint = same
      ? '判分版本 ' + it.ver + '，与交卷时一致'
      : '判分版本 ' + it.ver + '，当前已是 ' + it.cur;
    return '<span class="rep-item-ver' + (same ? '' : ' is-diff') + '" title="' + esc(hint) + '">' +
      esc(it.ver) + (same ? ' · 与交卷时一致' : ' → ' + esc(it.cur)) + '</span>';
  }
  function itemsHtml(items, withVer, opts) {
    opts = opts || {};
    opts.scope = opts.scope || 'r';
    return (items || []).map(function (it, i) { return itemHtml(it, i, withVer, opts); }).join('');
  }
  function countOf(items, key) {
    if (key === 'all') return (items || []).length;
    return (items || []).filter(function (it) { return it && it.correctness === key; }).length;
  }
  /* 工具栏：快速筛选 + 结果计数 + 批量展开 / 收起。
     复用既有 chip / btn，不新造控件；当前条件由 chip 的 is-on 与 aria-pressed
     表达，清除方式就是点「全部」，空结果里再给一颗显式的「清除筛选」。 */
  function toolbarHtml(items, opts) {
    opts = opts || {};
    var total = (items || []).length;
    var chips = FILTERS.map(function (f) {
      var n = countOf(items, f.key);
      var on = f.key === 'all';
      return '<button type="button" class="chip' + (on ? ' is-on' : '') + '" data-rep-filter="' + f.key + '"' +
        ' aria-pressed="' + (on ? 'true' : 'false') + '">' + f.label +
        '<span class="count">' + n + '</span></button>';
    }).join('');
    return '<div class="rep-tool">' +
      '<div class="chip-row" role="group" aria-label="逐题明细筛选">' + chips + '</div>' +
      '<div class="rep-tool-acts">' +
      '<span class="rep-tool-count" aria-live="polite">显示 ' + total + ' / ' + total + ' 题</span>' +
      '<button type="button" class="btn btn-sm btn-quiet" data-rep-clear hidden>清除筛选</button>' +
      '<button type="button" class="btn btn-sm btn-quiet" data-rep-expand="1">全部展开</button>' +
      '<button type="button" class="btn btn-sm btn-quiet" data-rep-expand="0">全部收起</button>' +
      '</div>' +
      '</div>';
  }
  /* 一整块：工具栏 + 列表 + 空状态，最外层是 .rep-block。
     调用方把这一整块塞进容器，再 bind 这个 .rep-block（每次渲染都是新节点，
     所以重复渲染后重复 bind 是安全的）。 */
  function blockHtml(items, withVer, opts) {
    opts = opts || {};
    return '<div class="rep-block">' + toolbarHtml(items, opts) +
      '<div class="rep-list">' + itemsHtml(items, withVer, opts) + '</div>' +
      '<div class="rep-empty" hidden>' +
      '<p class="rep-empty-txt">没有符合当前条件的题目。</p>' +
      '<button type="button" class="btn btn-sm btn-quiet" data-rep-clear>清除筛选</button>' +
      '</div></div>';
  }
  function listOf(box) {
    if (!box) return null;
    if (box.classList && box.classList.contains('rep-list')) return box;
    return box.querySelector ? box.querySelector('.rep-list') : null;
  }
  function applyFilter(box, key) {
    var list = listOf(box);
    var items = list ? list.querySelectorAll('.rep-item') : [];
    var shown = 0;
    for (var i = 0; i < items.length; i++) {
      var hit = key === 'all' || items[i].getAttribute('data-correctness') === key;
      items[i].hidden = !hit;
      if (hit) shown++;
      /* 换条件时先全部收起：留着上一批的展开态会让人以为筛选没生效 */
      setOpen(items[i], false);
    }
    var label = '';
    FILTERS.forEach(function (f) { if (f.key === key) label = f.label; });
    var chips = box.querySelectorAll('[data-rep-filter]');
    for (var c = 0; c < chips.length; c++) {
      var on = chips[c].getAttribute('data-rep-filter') === key;
      chips[c].classList.toggle('is-on', on);
      chips[c].setAttribute('aria-pressed', on ? 'true' : 'false');
    }
    var count = box.querySelector('.rep-tool-count');
    if (count) count.textContent = '显示 ' + shown + ' / ' + items.length + ' 题' + (key === 'all' ? '' : ' · 只看' + label);
    var clears = box.querySelectorAll('[data-rep-clear]');
    for (var k = 0; k < clears.length; k++) clears[k].hidden = key === 'all';
    var empty = box.querySelector('.rep-empty');
    if (empty) empty.hidden = shown > 0;
  }
  function setOpen(item, open) {
    var head = item.querySelector('.rep-item-head');
    var body = head ? document.getElementById(head.getAttribute('aria-controls')) : null;
    item.classList.toggle('is-open', !!open);
    if (head) head.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (body) body.hidden = !open;
  }
  /* 展开 / 收起 / 筛选：委托给容器，报告重渲染后重复调用即可。
     接受单个选择器字符串、单个 Element、Element 数组或 NodeList。
     容器可以是 .rep-block（含工具栏），也可以是单个 .rep-list。 */
  function bind(selector) {
    var nodes;
    if (!selector) return;
    if (typeof selector === 'string') nodes = Array.prototype.slice.call(document.querySelectorAll(selector));
    else if (selector.nodeType === 1) nodes = [selector];
    else nodes = Array.prototype.slice.call(selector);
    for (var n = 0; n < nodes.length; n++) {
      (function (box) {
        if (!box || box.getAttribute('data-rep-bound') === '1') return;
        box.setAttribute('data-rep-bound', '1');
        box.addEventListener('click', function (e) {
          var t = e.target;
          if (!t || !t.closest) return;
          var expand = t.closest('[data-rep-expand]');
          if (expand && box.contains(expand)) {
            var open = expand.getAttribute('data-rep-expand') === '1';
            var list = listOf(box);
            var its = list ? list.querySelectorAll('.rep-item') : [];
            for (var i = 0; i < its.length; i++) if (!its[i].hidden) setOpen(its[i], open);
            return;
          }
          if (t.closest('[data-rep-clear]') && box.contains(t.closest('[data-rep-clear]'))) {
            applyFilter(box, 'all');
            return;
          }
          var chip = t.closest('[data-rep-filter]');
          if (chip && box.contains(chip)) {
            applyFilter(box, chip.getAttribute('data-rep-filter'));
            return;
          }
          var head = t.closest('.rep-item-head');
          if (!head || !box.contains(head)) return;
          var item = head.closest('.rep-item');
          var body = document.getElementById(head.getAttribute('aria-controls'));
          var now = item.classList.toggle('is-open');
          head.setAttribute('aria-expanded', now ? 'true' : 'false');
          if (body) body.hidden = !now;
        });
      })(nodes[n]);
    }
  }
  return {
    VERDICT: VERDICT, esc: esc, itemHtml: itemHtml, itemsHtml: itemsHtml,
    toolbarHtml: toolbarHtml, blockHtml: blockHtml, bind: bind, FILTERS: FILTERS
  };
})();
