/* ==========================================================================
   report.js — 成绩报告的三级结构与逐题明细（共用组件）
   --------------------------------------------------------------------------
   一份报告从上到下只有三级：

   1. 核心成绩：`得分 / 满分` 同一行大数字，下面一行小字
      「得分率 · 正确率 · 总用时」。不再拆成四张平级统计卡。
   2. 学习分析：答题结果分布（一条堆叠条 + 图例与数量）、按题型表现
      （共享轨道的紧凑条形）、薄弱章节（得分率升序 Top 3–5）。
   3. 详细信息：逐题明细（可筛选、批量展开、答题卡定位）、完整统计表、
      判分版本、交卷信息；统计表与交卷信息默认收在折叠区里。

   交卷当次报告、练习归档报告、模考交卷报告与模考归档回看都用这一套
   `reportHtml / blockHtml / bind / locate`，字段顺序、展开交互与文案一致。
   历史报告只读：汇总数字来自交卷时存下的字段，没有逐题明细时明说缺什么，
   不拿演示数据填充；分布与章节分析只聚合交卷时存下的判定，不重新判分。

   每条 item 的字段（B 域已定，消费方不改语义）：
     qid / bankId / type / chapter / score / subjective / answered / multi
     correctness  CORRECT | PARTIAL | INCORRECT | UNGRADED | BLANK
     ratio        客观题得分率 0 / 1 / 1/3…；主观题为 null
     stem / mine / answer / missed / extra / explain
     rating / ratingDue
     ver / verAt              判分所依据的题目版本快照
     cur / curAt / curNote    当前版本（与 ver 不同时说明改了什么）

   opts:
     withVer   true 时在明细里渲染判分版本（历史报告必须为 true）
     qPrefix   题目详情页相对前缀（flows/ 传 '../screens/'）
     rPrefix   复习/错题页相对前缀
     bankId    题库 id，item 上没带 bankId 时用它补
     scope     同一页有多份列表时的作用域后缀，保证 aria-controls 唯一
     at / mode / bank / viaText / note / extraFacts  报告头的交卷信息

   对外 API：
     reportHtml(rep, items, opts)     整份报告（核心成绩 + 学习分析 + 详细信息）
     coreHtml(rep, items, opts)       只有核心成绩
     analysisHtml(rep, items, opts)   只有学习分析
     blockHtml(items, withVer, opts)  逐题明细（工具栏 + 列表 + 空状态）
     sheetHtml(items, opts)           答题卡格子（固定 36/32，不随容器放大）
     bindSheet(host, list, onMiss)    答题卡点击 → 定位并展开对应明细
     bind(node)                       委托展开、筛选、全部展开 / 收起
     locate(node, index)              展开并滚到第 index 题（0 起），返回是否命中
   ========================================================================== */
window.eeReport = (function () {
  /* ---------- 组件自带样式（.rpt-* 作用域，仅本组件使用） ---------- */
  var STYLE_ID = 'ee-report-css';
  var CSS =
    '.rpt-report{display:flex;flex-direction:column;gap:var(--sp-8);min-width:0}' +
    '.rpt-core{display:flex;flex-direction:column;gap:var(--sp-3)}' +
    '.rpt-scoreline{display:flex;align-items:baseline;gap:.16em;font-family:var(--font-mono);font-size:var(--text-5xl);font-weight:500;line-height:1.05;font-variant-numeric:tabular-nums}' +
    '.rpt-scoreline .sep{color:var(--ink-4);font-weight:400}' +
    '.rpt-scoreline .full{color:var(--ink-2)}' +
    '.rpt-scoreline .unit{font-family:var(--font-sans);font-size:var(--text-sm);color:var(--ink-3);margin-left:var(--sp-1)}' +
    '.rpt-score-cap{font-family:var(--font-sans);font-size:var(--text-sm);color:var(--ink-3);margin-left:var(--sp-2)}' +
    '.rpt-metrics{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--sp-1) var(--sp-3);margin:0;font-size:var(--text-sm);color:var(--ink-2)}' +
    '.rpt-metrics b{font-family:var(--font-mono);font-weight:500;color:var(--ink);font-variant-numeric:tabular-nums}' +
    '.rpt-metrics .dot{color:var(--ink-4)}' +
    '.rpt-note{margin:0;font-size:var(--text-sm);color:var(--ink-3);line-height:var(--text-sm-lh);max-width:var(--measure)}' +
    '.rpt-sec{display:flex;flex-direction:column;gap:var(--sp-5);min-width:0}' +
    '.rpt-sec-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--sp-2) var(--sp-3);padding-bottom:var(--sp-3);border-bottom:1px solid var(--line-strong)}' +
    '.rpt-sec-title{font-family:var(--font-serif);font-size:var(--text-xl);font-weight:500;line-height:1.4;margin:0}' +
    '.rpt-sec-note{font-size:var(--text-xs);color:var(--ink-3);margin-left:auto;font-variant-numeric:tabular-nums}' +
    '.rpt-sub{display:flex;flex-direction:column;gap:var(--sp-3);min-width:0}' +
    '.rpt-sub-title{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--sp-2);margin:0;font-size:var(--text-sm);font-weight:500;color:var(--ink)}' +
    '.rpt-sub-title span{font-weight:400;font-size:var(--text-xs);color:var(--ink-3)}' +
    '.rpt-cols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--sp-6);align-items:start}' +
    '.rpt-distbar{display:flex;height:14px;gap:2px;background:var(--surface-3);border-radius:var(--r-xs);overflow:hidden}' +
    '.rpt-distbar > i{display:block;height:100%;min-width:2px}' +
    '.rpt-seg-correct{background:var(--ok)}' +
    '.rpt-seg-partial{background:var(--warn)}' +
    '.rpt-seg-wrong{background:var(--bad)}' +
    '.rpt-seg-blank{background:var(--line)}' +
    '.rpt-seg-ungraded{background:var(--ink-3)}' +
    '.rpt-legend{display:flex;flex-wrap:wrap;gap:var(--sp-2) var(--sp-5);font-size:var(--text-sm);color:var(--ink-2)}' +
    '.rpt-key{display:inline-flex;align-items:center;gap:var(--sp-2)}' +
    '.rpt-key b{font-family:var(--font-mono);font-weight:500;color:var(--ink);font-variant-numeric:tabular-nums}' +
    '.rpt-key .cap{font-size:var(--text-xs);color:var(--ink-3)}' +
    '.rpt-sw{width:10px;height:10px;border-radius:2px;flex:none}' +
    '.rpt-sw.correct{background:var(--ok)} .rpt-sw.partial{background:var(--warn)} .rpt-sw.wrong{background:var(--bad)}' +
    '.rpt-sw.blank{background:var(--line);border:1px solid var(--line-strong)} .rpt-sw.ungraded{background:var(--ink-3)}' +
    '.rpt-glyph{font-family:var(--font-mono);font-size:var(--text-xs);color:var(--ink-3);width:1ch;text-align:center}' +
    '.rpt-bar-sub{color:var(--ink-3);font-size:var(--text-xs);margin-left:4px;font-family:var(--font-mono)}' +
    '.rpt-empty-line{margin:0;font-size:var(--text-sm);color:var(--ink-3);line-height:var(--text-sm-lh)}' +
    '.rpt-items{min-width:0}' +
    '.rpt-ver-line{margin:0;font-size:var(--text-xs);color:var(--ink-3);line-height:var(--text-xs-lh);font-variant-numeric:tabular-nums}' +
    '.rpt-ver-alert{display:flex;align-items:flex-start;gap:var(--sp-3);padding:var(--sp-3) var(--sp-4);background:var(--warn-soft);border-left:3px solid var(--warn);border-radius:var(--r-sm);font-size:var(--text-sm);color:var(--ink-2);line-height:var(--text-sm-lh)}' +
    '.rpt-ver-alert .od-icon{--od-icon-size:16px;margin-top:2px;flex:none;color:var(--warn)}' +
    '.rpt-ver-alert b{color:var(--ink);font-weight:500}' +
    '.rpt-fold{border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface-2)}' +
    '.rpt-fold > summary{display:flex;align-items:center;gap:var(--sp-2);min-height:36px;padding:var(--sp-2) var(--sp-4);font-size:var(--text-sm);color:var(--ink-2);cursor:pointer;list-style:none}' +
    '.rpt-fold > summary::-webkit-details-marker{display:none}' +
    '.rpt-fold > summary:hover{color:var(--ink)}' +
    '.rpt-fold > summary:focus-visible{outline:2px solid var(--brand);outline-offset:-2px}' +
    '.rpt-fold > summary .rep-help-caret{flex:none;transition:transform var(--dur-fast) ease}' +
    '.rpt-fold[open] > summary .rep-help-caret{transform:rotate(180deg)}' +
    '.rpt-fold-body{display:flex;flex-direction:column;gap:var(--sp-4);padding:var(--sp-2) var(--sp-4) var(--sp-4);font-size:var(--text-sm);color:var(--ink-2);line-height:var(--text-base-lh)}' +
    '.rpt-fold-body p{margin:0;max-width:var(--measure)}' +
    '.rpt-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:var(--sp-3) var(--sp-5);margin:0}' +
    '.rpt-facts dt{font-size:var(--text-xs);color:var(--ink-3)}' +
    '.rpt-facts dd{margin:2px 0 0;font-size:var(--text-sm);color:var(--ink);font-variant-numeric:tabular-nums}' +
    '.rpt-facts dd.mono{font-family:var(--font-mono)}' +
    '.rpt-table-wrap{overflow:auto;scrollbar-width:thin}' +
    '.rpt-report .dtable tr.is-total td{border-top:1px solid var(--line-strong);font-weight:500}' +
    '.rpt-vglyph{font-family:var(--font-mono);font-size:var(--text-xs);margin-right:3px;opacity:.9}' +
    '.rpt-sheet-block{display:flex;flex-direction:column;gap:var(--sp-3);min-width:0}' +
    '.sheet-cell.rpt-cell-correct{background:var(--ok-soft);border-color:var(--ok-line);color:var(--ok)}' +
    '.sheet-cell.rpt-cell-partial{background:var(--warn-soft);border-color:var(--warn-line);color:var(--warn)}' +
    '.sheet-cell.rpt-cell-wrong{background:var(--bad-soft);border-color:var(--bad-line);color:var(--bad)}' +
    '.sheet-cell.rpt-cell-blank{background:var(--surface);color:var(--ink-3)}' +
    '.sheet-cell.rpt-cell-ungraded{background:var(--surface-2);color:var(--ink-3);border-style:dashed}' +
    '.rpt-sheet-legend{display:flex;flex-wrap:wrap;gap:var(--sp-2) var(--sp-4);font-size:var(--text-xs);color:var(--ink-3)}' +
    '.rpt-sheet-legend span{display:inline-flex;align-items:center;gap:var(--sp-1)}' +
    '.rpt-sheet-legend i{width:10px;height:10px;border-radius:2px;border:1px solid var(--line-strong);flex:none}' +
    '.rpt-sheet-legend i.correct{background:var(--ok-soft);border-color:var(--ok-line)}' +
    '.rpt-sheet-legend i.partial{background:var(--warn-soft);border-color:var(--warn-line)}' +
    '.rpt-sheet-legend i.wrong{background:var(--bad-soft);border-color:var(--bad-line)}' +
    '.rpt-sheet-legend i.ungraded{background:var(--surface-2);border-style:dashed}' +
    '@media (max-width:900px){.rpt-cols{grid-template-columns:minmax(0,1fr)}}' +
    '@media (max-width:640px){.rpt-scoreline{font-size:var(--text-4xl)}.rpt-score-cap{display:block;margin:var(--sp-1) 0 0}.rpt-scoreline{flex-wrap:wrap}}';

  function injectStyles() {
    if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }
  injectStyles();

  var VERDICT = {
    CORRECT: { tag: 'ok', text: '回答正确', key: 'correct', glyph: '✓' },
    PARTIAL: { tag: 'warn', text: '部分正确', key: 'partial', glyph: '◐' },
    INCORRECT: { tag: 'bad', text: '回答错误', key: 'wrong', glyph: '✕' },
    UNGRADED: { tag: 'plain', text: '未判分', key: 'ungraded', glyph: '＝' },
    BLANK: { tag: '', text: '未作答', key: 'blank', glyph: '○' }
  };
  /* 快速筛选档位：与 VERDICT 的 correctness 对齐，未判分不在快速筛选里
     （主观题恒定未判分，筛它没有决策价值）。 */
  var FILTERS = [
    { key: 'all', label: '全部' },
    { key: 'INCORRECT', label: '错误' },
    { key: 'PARTIAL', label: '部分正确' },
    { key: 'BLANK', label: '未答' }
  ];
  var ORDER = ['correct', 'partial', 'wrong', 'blank', 'ungraded'];
  var DIST_KEY = { correct: 'CORRECT', partial: 'PARTIAL', wrong: 'INCORRECT', blank: 'BLANK', ungraded: 'UNGRADED' };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function num(v, d) {
    var n = parseFloat(v);
    return isNaN(n) ? (d == null ? 0 : d) : n;
  }
  function fmt(v) {
    if (v == null || isNaN(v)) return '—';
    var n = Math.round(Number(v) * 10) / 10;
    return String(n);
  }
  function pct(v) { return v == null ? '暂无数据' : Math.round(v) + '%'; }
  function verdictOf(it) { return VERDICT[it.correctness] || VERDICT.BLANK; }

  /* ---------- 汇总（优先用交卷时存下的字段，缺字段时才从明细聚合） ---------- */
  function countsOf(rep, items) {
    var c = { correct: 0, partial: 0, wrong: 0, blank: 0, ungraded: 0 };
    if (items && items.length) {
      items.forEach(function (it) {
        var v = it.correctness || (it.answered ? 'UNGRADED' : 'BLANK');
        if (v === 'CORRECT') c.correct++;
        else if (v === 'PARTIAL') c.partial++;
        else if (v === 'INCORRECT') c.wrong++;
        else if (v === 'UNGRADED') c.ungraded++;
        else c.blank++;
      });
      return c;
    }
    c.correct = num(rep && rep.correct);
    c.partial = num(rep && rep.partial);
    c.wrong = num(rep && rep.wrong);
    c.blank = num(rep && rep.unanswered);
    c.ungraded = num(rep && rep.ungraded);
    return c;
  }
  function fullOf(rep, items) {
    if (rep) {
      if (rep.full != null) return num(rep.full);
      if (rep.objectiveFull != null) return num(rep.objectiveFull);
    }
    if (items && items.length) {
      var n = 0, has = false;
      items.forEach(function (it) { if (!it.subjective) { n += it.score == null ? 1 : num(it.score); has = true; } });
      if (has) return n;
    }
    return null;
  }
  function scoreOf(rep, items) {
    if (rep) {
      if (rep.full != null && rep.score != null) return num(rep.score);
      if (rep.objectiveFull != null && rep.objectiveScore != null) return num(rep.objectiveScore);
      if (rep.full != null && rep.objectiveScore != null) return num(rep.objectiveScore);
    }
    if (items && items.length) {
      var n = 0, has = false;
      items.forEach(function (it) {
        if (it.subjective) return;
        has = true;
        n += (it.ratio == null ? 0 : num(it.ratio)) * (it.score == null ? 1 : num(it.score));
      });
      if (has) return Math.round(n * 10) / 10;
    }
    return null;
  }
  function rateOf(rep, items) {
    if (rep && rep.rate != null) return num(rep.rate);
    var full = fullOf(rep, items), score = scoreOf(rep, items);
    if (full && score != null) return Math.round(score / full * 100);
    return null;
  }
  function accOf(rep, items) {
    if (rep && rep.accObj != null) return num(rep.accObj);
    if (rep && rep.answeredObj) return Math.round(num(rep.answeredObjCorrect) / num(rep.answeredObj) * 100);
    if (items && items.length) {
      var answered = 0, ok = 0;
      items.forEach(function (it) {
        if (it.subjective) return;
        if (it.correctness && it.correctness !== 'BLANK') { answered++; if (it.correctness === 'CORRECT') ok++; }
      });
      if (answered) return Math.round(ok / answered * 100);
    }
    return null;
  }

  /* ---------- 核心成绩 ---------- */
  function coreHtml(rep, items, opts) {
    rep = rep || {};
    var full = fullOf(rep, items);
    var score = scoreOf(rep, items);
    var rate = rateOf(rep, items);
    var acc = accOf(rep, items);
    var minutes = rep.minutes == null ? null : num(rep.minutes);
    var legacy = full == null;
    var metrics = '<span>得分率 <b>' + (legacy ? (rep.score != null && rep.rate == null ? num(rep.score) + '%' : pct(rate)) : pct(rate)) + '</b></span>' +
      '<span class="dot" aria-hidden="true">·</span>' +
      '<span>正确率 <b>' + pct(acc) + '</b></span>' +
      '<span class="dot" aria-hidden="true">·</span>' +
      '<span>总用时 <b>' + (minutes == null ? '—' : minutes + ' 分钟') + '</b></span>';
    return '<section class="rpt-core" aria-label="核心成绩">' +
      '<div class="rpt-scoreline">' +
      '<span class="score">' + (score == null ? '—' : fmt(score)) + '</span>' +
      '<span class="sep" aria-hidden="true">/</span>' +
      '<span class="full">' + (full == null ? '—' : fmt(full)) + '</span>' +
      '<span class="unit">分</span>' +
      '<span class="rpt-score-cap">客观题得分 / 满分</span>' +
      '</div>' +
      '<p class="rpt-metrics">' + metrics + '</p>' +
      (legacy ? '<p class="rpt-note">这是一份早期报告：交卷时没有记录满分口径，得分与满分显示「—」，两个率照交卷时的记录显示。</p>' : '') +
      (opts && opts.note ? '<p class="rpt-note">' + esc(opts.note) + '</p>' : '') +
      '</section>';
  }

  /* ---------- 学习分析 ---------- */
  function distHtml(rep, items) {
    var c = countsOf(rep, items);
    var total = c.correct + c.partial + c.wrong + c.blank + c.ungraded;
    if (!total) return '<p class="rpt-empty-line">这一场还没有可统计的作答结果。</p>';
    var segs = ORDER.map(function (k) {
      if (!c[k]) return '';
      var w = Math.round(c[k] / total * 1000) / 10;
      return '<i class="rpt-seg-' + k + '" style="width:' + w + '%" title="' + VERDICT[DIST_KEY[k]].text + ' ' + c[k] + ' 题"></i>';
    }).join('');
    var legend = ORDER.map(function (k) {
      var v = VERDICT[DIST_KEY[k]];
      return '<span class="rpt-key"><i class="rpt-sw ' + k + '" aria-hidden="true"></i>' +
        '<span class="rpt-glyph" aria-hidden="true">' + v.glyph + '</span>' +
        '<span>' + v.text + '</span><b>' + c[k] + '</b><span class="cap">题</span></span>';
    }).join('');
    return '<div class="rpt-sub">' +
      '<h3 class="rpt-sub-title">答题结果分布 <span>共 ' + total + ' 题</span></h3>' +
      '<div class="rpt-distbar" role="img" aria-label="正确 ' + c.correct + ' 题，部分正确 ' + c.partial + ' 题，错误 ' + c.wrong + ' 题，未答 ' + c.blank + ' 题，未判分 ' + c.ungraded + ' 题">' + segs + '</div>' +
      '<div class="rpt-legend">' + legend + '</div>' +
      '</div>';
  }
  function typeStats(items) {
    var order = [], map = {};
    (items || []).forEach(function (it) {
      var t = it.type || '其他';
      if (!map[t]) { map[t] = { type: t, n: 0, objN: 0, answered: 0, correct: 0, subjective: 0 }; order.push(t); }
      var g = map[t]; g.n++;
      if (it.subjective) { g.subjective++; return; }
      g.objN++;
      if (it.correctness && it.correctness !== 'BLANK') g.answered++;
      if (it.correctness === 'CORRECT') g.correct++;
    });
    return order.map(function (k) { return map[k]; });
  }
  function barClass(rate) {
    if (rate == null) return 'line';
    if (rate >= 80) return 'ok';
    if (rate >= 50) return 'warn';
    return 'bad';
  }
  function typesHtml(items) {
    if (!items || !items.length) return '<p class="rpt-empty-line">这一场没有留下逐题明细，无法按题型统计。</p>';
    var rows = typeStats(items).map(function (g) {
      if (!g.objN) {
        return '<div class="bar-row"><span class="bar-label">' + esc(g.type) + '<span class="rpt-bar-sub">' + g.n + ' 题</span></span>' +
          '<span class="bar-track" aria-hidden="true"></span>' +
          '<span class="bar-val">未判分</span></div>';
      }
      var rate = g.answered ? Math.round(g.correct / g.answered * 100) : null;
      var label = rate == null ? '暂无数据' : rate + '%';
      return '<div class="bar-row"><span class="bar-label">' + esc(g.type) + '<span class="rpt-bar-sub">' + g.n + ' 题</span></span>' +
        '<span class="bar-track"><i class="bar-fill ' + barClass(rate) + '" style="width:' + (rate == null ? 0 : rate) + '%"></i></span>' +
        '<span class="bar-val">' + label + '</span></div>';
    }).join('');
    return '<div class="rpt-sub">' +
      '<h3 class="rpt-sub-title">按题型表现 <span>正确率 = 答对 ÷ 已答客观题</span></h3>' +
      '<div class="bar-group">' + rows + '</div>' +
      '</div>';
  }
  function chapterStats(items) {
    var order = [], map = {};
    (items || []).forEach(function (it) {
      if (it.subjective) return;
      var k = it.chapter || '未分章';
      if (!map[k]) { map[k] = { chapter: k, n: 0, full: 0, earned: 0 }; order.push(k); }
      var g = map[k], sc = it.score == null ? 1 : num(it.score);
      g.n++; g.full += sc;
      g.earned += (it.ratio == null ? 0 : num(it.ratio)) * sc;
    });
    return order.map(function (k) { return map[k]; })
      .filter(function (g) { return g.full > 0; })
      .map(function (g) { return { chapter: g.chapter, n: g.n, rate: Math.round(g.earned / g.full * 100) }; })
      .sort(function (a, b) { return a.rate - b.rate || a.chapter.localeCompare(b.chapter); });
  }
  function chaptersHtml(items) {
    if (!items || !items.length) return '<p class="rpt-empty-line">这一场没有留下逐题明细，无法按章节统计。</p>';
    var all = chapterStats(items);
    if (!all.length) return '<p class="rpt-empty-line">这一场的客观题没有章节标记，暂时按题型看更准。</p>';
    var rows = all.slice(0, 5).map(function (g) {
      return '<div class="bar-row"><span class="bar-label">' + esc(g.chapter) + '<span class="rpt-bar-sub">' + g.n + ' 题</span></span>' +
        '<span class="bar-track"><i class="bar-fill ' + barClass(g.rate) + '" style="width:' + g.rate + '%"></i></span>' +
        '<span class="bar-val">' + g.rate + '%</span></div>';
    }).join('');
    return '<div class="rpt-sub">' +
      '<h3 class="rpt-sub-title">薄弱章节 <span>' + (all.length > 5 ? '得分率最低的 5 个' : '共 ' + all.length + ' 个章节') + '</span></h3>' +
      '<div class="bar-group">' + rows + '</div>' +
      '</div>';
  }
  function analysisHtml(rep, items, opts) {
    rep = rep || {};
    var hasItems = !!(items && items.length);
    return '<section class="rpt-sec" aria-label="学习分析">' +
      '<div class="rpt-sec-head"><h2 class="rpt-sec-title">学习分析</h2>' +
      '<span class="rpt-sec-note">' + (hasItems ? '分布、题型与章节都来自这场交卷时的判定' : '缺少逐题明细，只显示交卷时记下的分布') + '</span></div>' +
      distHtml(rep, items) +
      '<div class="rpt-cols">' + typesHtml(items) + chaptersHtml(items) + '</div>' +
      '</section>';
  }

  /* ---------- 完整统计表（列宽由 ee.css 的 .dtable .col-* 统一给） ---------- */
  function statsTableHtml(items) {
    if (!items || !items.length) return '';
    var order = [], map = {};
    items.forEach(function (it) {
      var t = it.type || '其他';
      if (!map[t]) { map[t] = { type: t, n: 0, answered: 0, correct: 0, partial: 0, wrong: 0, blank: 0, score: 0, full: 0, subj: 0 }; order.push(t); }
      var g = map[t]; g.n++;
      if (it.subjective) { g.subj++; return; }
      var sc = it.score == null ? 1 : num(it.score);
      g.full += sc;
      if (it.correctness === 'BLANK' || !it.correctness) { g.blank++; return; }
      g.answered++;
      if (it.correctness === 'CORRECT') { g.correct++; g.score += sc; }
      else if (it.correctness === 'PARTIAL') { g.partial++; g.score += sc * (it.ratio == null ? 0.5 : num(it.ratio)); }
      else g.wrong++;
    });
    var total = { n: 0, answered: 0, correct: 0, partial: 0, wrong: 0, blank: 0, score: 0, full: 0 };
    var rows = order.map(function (t) {
      var g = map[t];
      total.n += g.n; total.answered += g.answered; total.correct += g.correct; total.partial += g.partial;
      total.wrong += g.wrong; total.blank += g.blank; total.score += g.score; total.full += g.full;
      var rate = g.full ? Math.round(g.score / g.full * 100) + '%' : '未判分';
      return '<tr><td class="col-name">' + esc(g.type) + '</td>' +
        '<td class="col-num">' + g.n + '</td>' +
        '<td class="col-num">' + g.answered + '</td>' +
        '<td class="col-num">' + (g.subj && !g.full ? '未判分' : g.correct) + '</td>' +
        '<td class="col-num">' + (g.subj && !g.full ? '不计入' : fmt(g.score)) + '</td>' +
        '<td class="col-num">' + (g.subj && !g.full ? '不计入' : fmt(g.full)) + '</td>' +
        '<td class="col-num">' + (g.subj && !g.full ? '暂无数据' : rate) + '</td></tr>';
    }).join('');
    rows += '<tr class="is-total"><td class="col-name">合计</td>' +
      '<td class="col-num">' + total.n + '</td><td class="col-num">' + total.answered + '</td>' +
      '<td class="col-num">' + total.correct + '</td><td class="col-num">' + fmt(total.score) + '</td>' +
      '<td class="col-num">' + fmt(total.full) + '</td>' +
      '<td class="col-num">' + (total.full ? Math.round(total.score / total.full * 100) + '%' : '暂无数据') + '</td></tr>';
    return '<div class="dtable-wrap"><table class="dtable">' +
      '<thead><tr><th class="col-name">题型</th><th class="col-num">题数</th><th class="col-num">已答</th><th class="col-num">答对</th><th class="col-num">得分</th><th class="col-num">满分</th><th class="col-num">得分率</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>';
  }

  /* ---------- 判分版本：只在真的改过题时突出 ---------- */
  function versionHtml(rep, items) {
    rep = rep || {};
    var changed = (items || []).filter(function (it) { return it && it.cur && it.cur !== it.ver; });
    if (changed.length) {
      var c0 = changed[0];
      var no = items.indexOf(c0) + 1;
      return '<div class="rpt-ver-alert" role="status">' +
        '<svg class="od-icon" aria-hidden="true"><use href="#i-alert-triangle"/></svg>' +
        '<div><b>' + changed.length + ' 题在交卷后被改过。</b>本报告仍按交卷时的版本判分，不会变。' +
        '例如第 ' + no + ' 题：判分版本 ' + esc(c0.ver || '—') + ' → 当前 ' + esc(c0.cur) + '。展开逐题明细可看每题版本。</div></div>';
    }
    var ver = rep.version || (items && items.length ? items[0].ver : null);
    return '<p class="rpt-ver-line">判分依据：交卷当时的题目版本' + (ver ? ' ' + esc(ver) : '') + ' · 交卷后没有题目被改动</p>';
  }

  /* ---------- 交卷信息 ---------- */
  function factsHtml(rep, opts) {
    rep = rep || {}; opts = opts || {};
    var rows = [];
    if (opts.at || rep.at) rows.push(['交卷时间', esc(opts.at || rep.at)]);
    if (opts.viaText || rep.via) rows.push(['交卷来源', esc(opts.viaText || rep.via)]);
    if (opts.bank) rows.push(['题库', esc(opts.bank)]);
    if (rep.minutes != null) rows.push(['总用时', num(rep.minutes) + ' 分钟']);
    if (rep.unanswered != null) rows.push(['未答（含主观题）', num(rep.unanswered) + ' 题']);
    if (rep.ungraded != null) rows.push(['未判分（主观题）', num(rep.ungraded) + ' 题']);
    rows.push(['判分依据', '交卷当时的题目版本']);
    (opts.extraFacts || []).forEach(function (r) { rows.push([r[0], r[1]]); });
    return '<dl class="rpt-facts">' + rows.map(function (r) {
      return '<div><dt>' + esc(r[0]) + '</dt><dd>' + r[1] + '</dd></div>';
    }).join('') + '</dl>';
  }

  /* ---------- 逐题明细 ---------- */
  function itemHtml(it, i, withVer, opts) {
    opts = opts || {};
    it = it || {};
    var v = verdictOf(it);
    var bodyId = 'rep-item-' + i + '-' + (withVer ? 'v' : 'l') + '-' + (opts.scope || 'x');
    var stem = esc(it.stem);
    var diffVer = !!(it.cur && it.cur !== it.ver);
    /* 折叠态：序号 + 题型 + 题干摘要（一行截断，全文放 title）+ 判定；
       版本只在真的改过题时出现，避免 100 行里 99 行都是「与交卷时一致」。 */
    var head = '<button type="button" class="rep-item-head" aria-expanded="false" aria-controls="' + bodyId + '">' +
      '<span class="rep-item-n">' + (i + 1) + '</span>' +
      '<span class="rep-item-type">' + esc(it.type) + '</span>' +
      '<span class="rep-item-stem" title="' + stem + '">' + stem + '</span>' +
      '<span class="tag ' + v.tag + '"><span class="rpt-vglyph" aria-hidden="true">' + v.glyph + '</span>' + v.text + '</span>' +
      (withVer && diffVer ? verHead(it) : '') +
      '<svg class="od-icon rep-item-caret" viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 9.5 12 15l5.5-5.5"/></svg>' +
      '</button>';
    var scoreTxt = it.subjective
      ? '不计入客观题得分'
      : (it.answered ? '得分率 ' + Math.round((it.ratio == null ? 0 : it.ratio) * 100) + '%' : '未作答 · 按 0 分计分，仍占满分');
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
       而不是只把用户丢到错题列表页顶部。
       bankId 写的是复习队列行所属题库（item 自带的 bankId，或 opts.bankId）；
       报告的题库与当前题库不同时，用错题库去 review.html 只会命中不了行——宁可不带 bank 也不带错 bank。 */
    var rq = [];
    if (it.qid) rq.push('qid=' + encodeURIComponent(it.qid));
    if (bank) rq.push('bank=' + encodeURIComponent(bank));
    /* 题干是第三重定位依据：报告快照里的题目 id 与复习队列的行 id 是两套编号，
       只带 qid 会在两套编号对不上时退化成「跳到错题列表页」。带上归一化题干，
       review.html 才能在两套编号之间架桥，真正落到那一行。归一化由 store.js 统一提供。 */
    var norm = window.eeStore && window.eeStore.normStem;
    if (it.stem && norm) rq.push('stem=' + encodeURIComponent(norm(it.stem)));
    var rHref = (opts.rPrefix || '') + 'review.html?tab=mistakes' + (rq.length ? '&' + rq.join('&') : '');
    var body = '<div class="rep-item-body" id="' + bodyId + '" hidden>';
    body += '<p class="rep-stem">' + stem + '</p>' +
      '<dl class="rep-kv">' +
      '<dt>我的作答</dt><dd' + (it.subjective ? '' : ' class="mono"') + '>' + esc(it.mine) + '</dd>' +
      '<dt>标准答案</dt><dd class="mono">' + esc(it.answer) + '</dd>' +
      '<dt>判定结果</dt><dd><span class="tag ' + v.tag + '"><span class="rpt-vglyph" aria-hidden="true">' + v.glyph + '</span>' + v.text + '</span>　' + esc(scoreTxt) + '</dd>' +
      '<dt>评级</dt><dd>' + rating + '</dd>' +
      '</dl>' + gap +
      '<div><div class="rule-label">' + (it.subjective ? '参考解析' : '官方解析') + '</div><p class="rep-parse">' + esc(it.explain) + '</p></div>';
    if (it.ai) {
      body += '<div><div class="rule-label">AI 解释</div><p class="rep-parse">' + esc(it.ai.text) + '</p>' +
        '<div class="ai-src ee-mt-4"><span class="tag brand">AI</span><span>' + esc(it.ai.src) + '</span></div></div>';
    }
    body += '<div class="rep-item-acts">' +
      /* qid 缺省时不给「查看该题当前版本」：没有 id 的 question.html 只能落到空页。 */
      (it.qid ? '<a class="btn btn-sm btn-quiet" href="' + href + '">查看该题当前版本</a>' : '') +
      ((v.tag === 'bad' || v.tag === 'warn') ? '<a class="btn btn-sm btn-quiet" href="' + rHref + '">在错题里打开</a>' : '') +
      '</div>';
    /* 版本：改过题时给出警示块，没改过就是一行弱化文字。 */
    if (withVer) {
      if (diffVer) {
        body += '<div class="rpt-ver-alert" role="status">' +
          '<svg class="od-icon" aria-hidden="true"><use href="#i-alert-triangle"/></svg>' +
          '<div><b>这道题交卷后改过：判分版本 ' + esc(it.ver) + ' → 当前 ' + esc(it.cur) + '。</b>' +
          '题目在 ' + esc(it.curAt) + ' 改过：' + esc(it.curNote) + '本报告仍按交卷时的 ' + esc(it.ver) + ' 判分，不会变。</div></div>';
      } else {
        body += '<p class="rpt-ver-line">判分版本 ' + esc(it.ver) + (it.verAt ? ' · ' + esc(it.verAt) + ' 保存' : '') + ' · 交卷后未改过</p>';
      }
    }
    body += '</div>';
    return '<div class="rep-item" data-rep-index="' + i + '" data-correctness="' + (it.correctness || 'BLANK') + '">' + head + body + '</div>';
  }
  /* 行头版本指示：只有判分版本与当前版本真的不同时才出现，且只占一个小标签。 */
  function verHead(it) {
    return '<span class="rep-item-ver is-diff" title="判分版本 ' + esc(it.ver) + '，当前已是 ' + esc(it.cur) + '">' +
      esc(it.ver) + ' → ' + esc(it.cur) + '</span>';
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
     复用既有 chip / btn，当前条件由 chip 的 is-on 与 aria-pressed 表达。 */
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
  function blockHtml(items, withVer, opts) {
    opts = opts || {};
    return '<div class="rep-block">' + toolbarHtml(items, opts) +
      '<div class="rep-list">' + itemsHtml(items, withVer, opts) + '</div>' +
      '<div class="rep-empty" hidden>' +
      '<p class="rep-empty-txt">没有符合当前条件的题目。</p>' +
      '<button type="button" class="btn btn-sm btn-quiet" data-rep-clear>清除筛选</button>' +
      '</div></div>';
  }

  /* ---------- 答题卡 ---------- */
  function sheetHtml(items, opts) {
    opts = opts || {};
    return (items || []).map(function (it, i) {
      var v = verdictOf(it);
      return '<button type="button" class="sheet-cell rpt-cell-' + v.key + '" data-locate="' + i + '"' +
        ' aria-label="第 ' + (i + 1) + ' 题，' + v.text + '，定位到逐题明细">' + (i + 1) + '</button>';
    }).join('');
  }
  function sheetLegendHtml() {
    return '<span><i class="correct" aria-hidden="true"></i>正确</span>' +
      '<span><i class="partial" aria-hidden="true"></i>部分</span>' +
      '<span><i class="wrong" aria-hidden="true"></i>错误</span>' +
      '<span><i class="blank" aria-hidden="true"></i>未答</span>' +
      '<span><i class="ungraded" aria-hidden="true"></i>未判分</span>';
  }
  function bindSheet(host, list, onMiss) {
    if (!host || !list) return;
    host.onclick = function (e) {
      var b = e.target.closest ? e.target.closest('[data-locate]') : null;
      if (!b) return;
      var index = parseInt(b.getAttribute('data-locate'), 10);
      var ok = locate(list, index);
      if (!ok) {
        if (onMiss) onMiss(index);
        return;
      }
      var item = list.querySelector ? list.querySelector('.rep-item[data-rep-index="' + index + '"]') : null;
      var head = item ? item.querySelector('.rep-item-head') : null;
      if (head) head.focus({ preventScroll: true });
    };
  }

  /* ---------- 整份报告 ---------- */
  function reportHtml(rep, items, opts) {
    opts = opts || {};
    items = items || [];
    rep = rep || {};
    var hasItems = items.length > 0;
    var counts = countsOf(rep, items);
    var totalN = counts.correct + counts.partial + counts.wrong + counts.blank + counts.ungraded;
    var wrongN = counts.wrong + counts.partial + counts.blank;
    var detailNote = hasItems
      ? '共 ' + totalN + ' 题 · 答错与未答 ' + wrongN + ' 题 · 点开看作答、判定、解析与判分版本'
      : '这一场交卷时没有记录逐题明细';
    var detailInner = hasItems
      ? '<div class="rpt-items">' + blockHtml(items, opts.withVer !== false, opts) + '</div>'
      : '<div class="rep-empty"><p class="rep-empty-txt">' +
        (opts.emptyItemsText || '这一场交卷时没有记录逐题明细，因此没有可回看的题目。上面的汇总计数是当时记下来的部分。') +
        '</p></div>';
    return '<div class="rpt-report">' +
      coreHtml(rep, items, opts) +
      analysisHtml(rep, items, opts) +
      '<section class="rpt-sec" aria-label="详细信息">' +
      '<div class="rpt-sec-head"><h2 class="rpt-sec-title">逐题明细</h2><span class="rpt-sec-note">' + detailNote + '</span></div>' +
      detailInner +
      versionHtml(rep, items) +
      '<details class="rpt-fold"><summary><svg class="od-icon rep-help-caret" viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 9.5 12 15l5.5-5.5"/></svg>怎么算的：两个率与未答、未判分的口径</summary>' +
      '<div class="rpt-fold-body"><p>得分只看客观题：未作答的客观题按 0 分计分，但仍占满分；已作答的主观题显示「未判分」，计入已答、不计入得分，也不算未答。得分率的分母是客观题满分；正确率只统计你实际答过的客观题，两者分母不同，数值不同是正常结果。</p>' +
      '<p>薄弱章节按得分率从低到高取前 5 个；题型表现按「答对 ÷ 已答客观题」计算，主观题单独标注未判分。所有分析只聚合交卷时存下的判定，不重新判分。</p></div></details>' +
      '<details class="rpt-fold"><summary><svg class="od-icon rep-help-caret" viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 9.5 12 15l5.5-5.5"/></svg>完整统计表与交卷信息</summary>' +
      '<div class="rpt-fold-body">' +
      (statsTableHtml(items) || '<p>这一场没有记录逐题明细，无法给出完整统计表。</p>') +
      factsHtml(rep, opts) +
      '</div></details>' +
      '</section>' +
      '</div>';
  }

  /* ---------- 绑定与定位 ---------- */
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
  /* 展开 / 收起 / 筛选 / 定位：委托给容器，报告重渲染后重复调用即可。
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
  /* 定位并展开某一题（报告答题卡格子 → 对应明细）。
     契约：调用方给出容器与题号，本组件负责
       ① 若该题被当前筛选挡住，先把筛选恢复为「全部」；
       ② 展开该题的 .rep-item 并同步 aria-expanded / hidden；
       ③ 用 scrollIntoView({block:'center'}) 滚到它，并加 .is-target 高亮。
     返回 true 表示真的落到了某一题；找不到就返回 false，调用方据此给出准确反馈
     （不静默停在列表顶部）。 */
  function locate(box, index) {
    var node = typeof box === 'string' ? document.querySelector(box) : box;
    if (!node) return false;
    var block = node.classList && node.classList.contains('rep-block') ? node : (node.querySelector ? node.querySelector('.rep-block') : null);
    var host = block || node;
    var items = host.querySelectorAll('.rep-item');
    if (!items.length) return false;
    var want = parseInt(index, 10);
    if (isNaN(want) || want < 0 || want >= items.length) return false;
    var item = items[want];
    /* ① 被筛选挡住时先解除筛选，否则「定位」只会得到一个隐藏节点 */
    if (item.hidden) applyFilter(block || host, 'all');
    for (var i = 0; i < items.length; i++) items[i].classList.remove('is-target');
    /* ② 展开并同步无障碍状态 */
    setOpen(item, true);
    /* ③ 滚动到行并高亮 */
    item.classList.add('is-target');
    if (item.scrollIntoView) item.scrollIntoView({ block: 'center', behavior: 'smooth' });
    var head = item.querySelector('.rep-item-head');
    if (head && head.focus) { if (!head.hasAttribute('tabindex')) head.setAttribute('tabindex', '-1'); head.focus({ preventScroll: true }); }
    return true;
  }

  return {
    VERDICT: VERDICT, esc: esc, num: num, fmt: fmt, pct: pct,
    countsOf: countsOf, fullOf: fullOf, scoreOf: scoreOf, rateOf: rateOf, accOf: accOf,
    coreHtml: coreHtml, analysisHtml: analysisHtml, reportHtml: reportHtml,
    statsTableHtml: statsTableHtml, versionHtml: versionHtml, factsHtml: factsHtml,
    itemHtml: itemHtml, itemsHtml: itemsHtml, toolbarHtml: toolbarHtml, blockHtml: blockHtml,
    sheetHtml: sheetHtml, sheetLegendHtml: sheetLegendHtml, bindSheet: bindSheet,
    bind: bind, locate: locate, FILTERS: FILTERS
  };
})();
