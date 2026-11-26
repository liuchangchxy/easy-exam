/* ==========================================================================
   report.js — 逐题明细共享组件（ee.css §15 .rep-*）
   --------------------------------------------------------------------------
   交卷当次的报告、练习的历史归档报告、模考的归档成绩报告共用这一套渲染与
   展开交互：同一道题在三处的呈现、字段顺序、版本提示、回看入口完全一致
   （CONTRACT §3.3 / BR-109 / CR-25）。

   每条 item 的字段：
     qid        题目 id（可选，缺省时不带「查看该题当前版本」链接）
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
     withVer   true 时渲染判分版本快照条（历史归档报告必须为 true）
     qPrefix   题目详情页相对前缀（flows/ 传 '../screens/'）
     rPrefix   复习/错题页相对前缀
   ========================================================================== */
window.eeReport = (function () {
  var VERDICT = {
    CORRECT: { tag: 'ok', text: '回答正确' },
    PARTIAL: { tag: 'warn', text: '部分正确' },
    INCORRECT: { tag: 'bad', text: '回答错误' },
    UNGRADED: { tag: 'plain', text: '未判分' },
    BLANK: { tag: '', text: '未作答' }
  };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function itemHtml(it, i, withVer, opts) {
    opts = opts || {};
    var v = VERDICT[it.correctness] || VERDICT.BLANK;
    var bodyId = 'rep-item-' + i + '-' + (withVer ? 'v' : 'l') + '-' + (opts.scope || 'x');
    var head = '<button type="button" class="rep-item-head" aria-expanded="false" aria-controls="' + bodyId + '">' +
      '<span class="rep-item-n">' + (i + 1) + '</span>' +
      '<span class="rep-item-type">' + esc(it.type) + '</span>' +
      '<span class="tag ' + v.tag + '">' + v.text + '</span>' +
      '<span class="rep-item-spacer"></span>' +
      (withVer
        ? '<span class="tag plain mono">判分 ' + esc(it.ver) + '</span>' + (it.cur ? '<span class="tag warn">有新版</span>' : '')
        : '') +
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
    if (it.bankId) qp.push('bank=' + encodeURIComponent(it.bankId));
    var href = (opts.qPrefix || '') + 'question.html' + (qp.length ? '?' + qp.join('&') : '');
    var body = '<div class="rep-item-body" id="' + bodyId + '" hidden>';
    if (withVer) {
      body += '<div class="rep-ver">' +
        '<span class="rep-ver-tags">' +
        '<span class="tag plain">判分版本 ' + esc(it.ver) + '</span>' +
        '<span class="mono muted">' + esc(it.verAt) + ' 保存</span>' +
        (it.cur ? '<span class="tag warn">当前 ' + esc(it.cur) + '</span>' : '<span class="tag">与当前版本一致</span>') +
        '</span>' +
        '<p class="rep-ver-note">' + (it.cur
          ? '题目在 ' + esc(it.curAt) + ' 改过：' + esc(it.curNote) + '这份报告仍按 ' + esc(it.ver) + ' 判分，不会变。'
          : '这道题交卷后没有再改过。') + '</p>' +
        '</div>';
    }
    body += '<p class="rep-stem">' + esc(it.stem) + '</p>' +
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
      '<a class="btn btn-sm btn-quiet" href="' + href + '">查看该题当前版本</a>' +
      ((v.tag === 'bad' || v.tag === 'warn') ? '<a class="btn btn-sm btn-quiet" href="' + (opts.rPrefix || '') + 'review.html?tab=mistakes">在错题里打开</a>' : '') +
      '</div></div>';
    return '<div class="rep-item">' + head + body + '</div>';
  }
  function itemsHtml(items, withVer, opts) {
    opts = opts || {};
    opts.scope = opts.scope || 'r';
    return (items || []).map(function (it, i) { return itemHtml(it, i, withVer, opts); }).join('');
  }
  /* 展开 / 收起：委托给容器，报告重渲染后重复调用即可。
     接受单个选择器字符串、单个 Element、Element 数组或 NodeList。 */
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
          var head = e.target && e.target.closest ? e.target.closest('.rep-item-head') : null;
          if (!head || !box.contains(head)) return;
          var item = head.closest('.rep-item');
          var body = document.getElementById(head.getAttribute('aria-controls'));
          var open = item.classList.toggle('is-open');
          head.setAttribute('aria-expanded', open ? 'true' : 'false');
          if (body) body.hidden = !open;
        });
      })(nodes[n]);
    }
  }
  return { VERDICT: VERDICT, esc: esc, itemHtml: itemHtml, itemsHtml: itemsHtml, bind: bind };
})();
