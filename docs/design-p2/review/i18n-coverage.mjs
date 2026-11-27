#!/usr/bin/env node
/* ==========================================================================
   EasyExam P2 · 国际化覆盖率检查（域 C）
   --------------------------------------------------------------------------
   用法：node review/i18n-coverage.mjs [baseUrl]
   默认 baseUrl = http://127.0.0.1:8787/

   做什么
     1. 以产品模式（无 ?spec=1）打开 21 个产品页面；
     2. 收集「应翻译」的界面文本与四类属性（排除 [data-no-i18n]、[data-spec]、
        .spec-*、code/pre/.mono，以及题目/选项/解析/笔记等数据内容）；
     3. 切到英文 → 收集仍未翻译的中文（漏译）；再切回中文 → 收集未还原的英文；
     4. 额外验证动态插入节点与 toast 是否跟随目标语言；
     5. 输出每页覆盖率与剩余条目清单。

   退出码：有漏译或未还原时为 1。
   ========================================================================== */
import { chromium } from 'file:///C:/Users/chang/Desktop/code/飞牛刷题软件/frontend/node_modules/playwright/index.mjs';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const BASE = (process.argv[2] || 'http://127.0.0.1:8787/').replace(/\/?$/, '/');
const EXE = 'C:/Users/chang/AppData/Local/ms-playwright/chromium-1254/chrome-win64/chrome.exe';

const PAGES = [
  'pages/screens/home.html', 'pages/screens/review.html', 'pages/screens/banks.html',
  'pages/screens/workspace.html', 'pages/screens/question.html', 'pages/screens/practice.html',
  'pages/screens/exam.html', 'pages/screens/exams.html', 'pages/screens/diagnosis.html',
  'pages/screens/settings.html', 'pages/screens/notes.html', 'pages/screens/import.html',
  'pages/screens/instance.html', 'pages/screens/login.html', 'pages/screens/forbidden.html',
  'pages/screens/palette.html',
  'pages/flows/collab.html', 'pages/flows/exam.html', 'pages/flows/import.html',
  'pages/flows/practice.html', 'pages/flows/review.html'
];

const SKIP = 'script,style,code,pre,.mono,textarea,[contenteditable="true"],[data-spec],[data-no-i18n],noscript,template,' +
             '.spec-section,.spec-bar,.drawer-demo-note';
/* 数据内容容器：题目、选项、解析、笔记正文、用户名、文件名等 */
const CONTENT_SEL = '[data-no-i18n],.q-stem,.opt-text,.explain-body,.note-body,.note-title,' +
                    '.ee-stem,.list-title,.rep-stem,.rep-parse,.ee-reader-body,.ee-fu-bubble,' +
                    '.ai-body,.chat-body,.doc-body,.file-name,.user-name,' +
                    /* 数据值：题库分类副标题、跳转面板里的题库名、知识点标签下拉项 */
                    '.sheet-sub,.cmd-item[data-group="banks"] .cmd-item-title,#rc-tag option';

function isContentText(t, storeStrings) {
  if (!t) return false;
  /* 只有「纯日期 / 纯时间」才算数据；日期开头的界面摘要仍按 UI 统计 */
  if (/^\d{4}[-/年]\d{1,2}([-/月]\d{1,2}日?)?(\s+\d{1,2}:\d{2})?$/.test(t)) return true;
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(t)) return true; /* 时间 */
  if (/^[A-Za-z0-9_.@-]+$/.test(t)) return true;    /* id / 用户名 / 文件名 */
  const n = t.replace(/\s+/g, '');
  for (const s of storeStrings) {
    const sn = s.replace(/\s+/g, '');
    if (n === sn) return true;
    if (sn.length > 4 && n.includes(sn)) return true;
  }
  return false;
}

async function collect(page) {
  return await page.evaluate(({ SKIP, CONTENT_SEL }) => {
    const store = window.eeStore ? window.eeStore.get() : {};
    const strings = new Set();
    (function walk(v) {
      if (typeof v === 'string') { if (/[\u4e00-\u9fff]/.test(v)) strings.add(v.replace(/\s+/g, ' ').trim()); }
      else if (Array.isArray(v)) v.forEach(walk);
      else if (v && typeof v === 'object') Object.values(v).forEach(walk);
    })(store);
    const storeStrings = [...strings];
    const out = { text: [], attrs: [], content: [], noI18n: 0, spec: 0 };
    const seen = new Set();
    const isContentEl = el => !!(el && el.closest && el.closest(CONTENT_SEL));
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let n;
    while ((n = walker.nextNode())) {
      const p = n.parentElement;
      if (!p) continue;
      if (p.closest(SKIP)) { if (p.closest('[data-no-i18n]')) out.noI18n++; if (p.closest('[data-spec],.spec-section,.spec-bar')) out.spec++; continue; }
      /* 规格状态演示：只有隐藏的规格工具条能切到的面板，属于设计文档，不是产品 UI */
      const panel = p.closest('[data-tab-panel]');
      if (panel && panel.hidden) {
        const scope = panel.closest('[data-tab-scope]');
        if (scope && scope.querySelector('.spec-bar')) { out.spec++; continue; }
      }
      const raw = n.nodeValue;
      if (!raw || !/[\u4e00-\u9fff]/.test(raw)) continue;
      const t = raw.replace(/\s+/g, ' ').trim();
      if (!t) continue;
      if (isContentEl(p)) { out.content.push(t); continue; }
      out.text.push(t);
    }
    const A = ['title', 'aria-label', 'placeholder', 'alt'];
    document.querySelectorAll('*').forEach(el => {
      if (el.closest(SKIP)) return;
      A.forEach(a => {
        const v = el.getAttribute(a);
        if (v && /[\u4e00-\u9fff]/.test(v)) {
          const t = v.trim();
          /* \u9898\u9762\u4f5c\u4e3a title\uff08\u9898\u76ee\u5217\u8868\u7684\u5b8c\u6574\u9898\u5e72\u63d0\u793a\uff09\u5c5e\u5185\u5bb9\u6570\u636e */
          if (a === 'title' && t.length > 12 && /[\uff08(]/.test(t)) { out.content.push(t); return; }
          if (a === 'title' && t.length > 20 && /\u3002$/.test(t)) { out.content.push(t); return; }
          if (isContentEl(el)) out.content.push(t); else out.attrs.push(a + '=' + t);
        }
      });
    });
    return { ...out, storeStrings };
  }, { SKIP, CONTENT_SEL });
}

function classify(list, storeStrings, seenContent) {
  const ui = new Set(), content = new Set();
  for (const raw of list) {
    const t = raw.replace(/^[a-z-]+=/, '');
    if (isContentText(t, storeStrings) || seenContent.has(t)) content.add(raw);
    else ui.add(raw);
  }
  return { ui: [...ui], content: [...content] };
}

/* 译文模板保留的数据：去掉引号内片段后不再有中文，说明模板已翻译、引号内是题库/标签等数据。
   例：3 questions · add tag “易错”  /  Filter “信息安全” in recommendations */
function translatedWithData(t) {
  const rest = t
    .replace(/「[^」]*」/g, '')
    .replace(/“[^”]*”/g, '')
    .replace(/"[^"]*"/g, '')
    .replace(/‘[^’]*’/g, '')
    .replace(/'[^']*'/g, '');
  return !/[一-鿿]/.test(rest);
}

const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const report = { base: BASE, pages: {}, totals: { ui: 0, miss: 0, content: 0, notRestored: 0 } };
let failed = false;

for (const rel of PAGES) {
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(BASE + rel, { waitUntil: 'load' });
  await page.waitForTimeout(450);

  const before = await collect(page);
  const contentSet = new Set(before.content);
  const cls = classify(before.text.concat(before.attrs), before.storeStrings, contentSet);

  /* 切到英文：走真实设置通道，再强制应用一次 */
  await page.evaluate(() => {
    if (window.eeStore) window.eeStore.setSetting('lang', 'en');
    if (window.eeApplyI18N) window.eeApplyI18N(document.body);
  });
  await page.waitForTimeout(350);
  await page.evaluate(() => { if (window.eeApplyI18N) window.eeApplyI18N(document.body); });
  await page.waitForTimeout(120);

  const afterEn = await collect(page);
  const missCls = classify(afterEn.text.concat(afterEn.attrs), before.storeStrings, contentSet);

  /* 动态插入节点 + toast 是否跟随目标语言 */
  const dynamic = await page.evaluate(() => {
    const d = document.createElement('div');
    d.id = 'ee-i18n-probe';
    d.innerHTML = '<span>取消</span><button aria-label="关闭提示">关闭</button>';
    document.body.appendChild(d);
    if (window.eeToast) window.eeToast('已切换为深色');
    return new Promise(resolve => setTimeout(() => {
      const span = d.querySelector('span');
      const btn = d.querySelector('button');
      const toast = document.querySelector('.toast span');
      resolve({
        text: span ? span.textContent.trim() : '',
        aria: btn ? btn.getAttribute('aria-label') : '',
        toast: toast ? toast.textContent.trim() : ''
      });
    }, 120));
  });

  /* 切回中文：检查英文界面文案是否还原 */
  await page.evaluate(() => {
    if (window.eeStore) window.eeStore.setSetting('lang', 'zh');
    if (window.eeApplyI18N) window.eeApplyI18N(document.body);
  });
  await page.waitForTimeout(300);
  const notRestored = await page.evaluate(() => {
    const en = new Set();
    Object.keys(window.eeI18N || {}).forEach(k => {
      const v = window.eeI18N[k];
      const s = Array.isArray(v) ? v[1] : v;
      if (typeof s === 'string' && /[A-Za-z]{2}/.test(s)) en.add(s);
    });
    const out = [];
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let n;
    while ((n = w.nextNode())) {
      const p = n.parentElement;
      if (!p || p.closest('script,style,code,pre,.mono,[data-spec],[data-no-i18n],.spec-section,.spec-bar')) continue;
      const t = n.nodeValue.replace(/\s+/g, ' ').trim();
      if (t && en.has(t)) out.push(t);
    }
    return [...new Set(out)];
  });

  const pageMiss = missCls.ui.filter(t => !/^\d+$/.test(t) && !translatedWithData(t));
  const keptContent = [...new Set([...cls.content, ...before.content])];
  const ok = pageMiss.length === 0 && notRestored.length === 0 &&
             dynamic.text === 'Cancel' && dynamic.aria === 'Close notification' && dynamic.toast === 'Switched to dark';
  if (!ok) failed = true;
  const uiTotal = cls.ui.length;
  const coverage = uiTotal ? ((uiTotal - pageMiss.length) / uiTotal * 100) : 100;
  report.pages[rel] = {
    uiStrings: uiTotal,
    translated: uiTotal - pageMiss.length,
    coverage: Number(coverage.toFixed(1)),
    missing: pageMiss,
    notRestored,
    contentKept: keptContent.length,
    contentSample: keptContent.slice(0, 6),
    dynamic,
    errors
  };
  report.totals.ui += uiTotal;
  report.totals.miss += pageMiss.length;
  report.totals.content += keptContent.length;
  report.totals.notRestored += notRestored.length;
  await page.close();
}
await browser.close();

report.totals.coverage = report.totals.ui
  ? Number(((report.totals.ui - report.totals.miss) / report.totals.ui * 100).toFixed(1))
  : 100;

const outDir = path.dirname(fileURLToPath(import.meta.url));
fs.writeFileSync(path.join(outDir, 'i18n-coverage-report.json'), JSON.stringify(report, null, 2));

console.log('\n=== i18n coverage ===');
console.log('base:', report.base);
for (const [rel, r] of Object.entries(report.pages)) {
  console.log(`\n${rel}  UI ${r.uiStrings} · translated ${r.translated} · ${r.coverage}% · content kept ${r.contentKept}`);
  if (r.missing.length) console.log('  missing:', r.missing.slice(0, 40).join(' | '), r.missing.length > 40 ? `…(+${r.missing.length - 40})` : '');
  if (r.notRestored.length) console.log('  not restored:', r.notRestored.slice(0, 20).join(' | '));
  if (r.dynamic.text !== 'Cancel' || r.dynamic.aria !== 'Close notification' || r.dynamic.toast !== 'Switched to dark')
    console.log('  dynamic probe:', JSON.stringify(r.dynamic));
  if (r.errors.length) console.log('  pageerrors:', r.errors.slice(0, 3));
}
console.log('\nTOTAL UI', report.totals.ui, '· translated', report.totals.ui - report.totals.miss,
  `· coverage ${report.totals.coverage}% · missing ${report.totals.miss} · content kept ${report.totals.content} · not restored ${report.totals.notRestored}`);
process.exit(failed ? 1 : 0);
