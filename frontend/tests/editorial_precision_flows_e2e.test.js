/**
 * PR 90 — independent real-browser regression flows.
 *
 * Scope (deliberately separate from browser_e2e.test.js):
 *   1. 4 palettes x light/dark x 1440/1024/768/390/375/320 (48 combinations)
 *   2. Offline practice answer -> pending queue -> online auto-sync -> reload
 *      with exactly one persisted attempt
 *   3. Notes create/edit/save + real PDF upload/preview/download
 *   4. PDF import preview + duplicate strategies skip / new / merge
 *   5. Blueprint create/edit/save persistence
 *   6. Exam flag / answer sheet / unanswered / submit report
 *
 * Every product assertion is driven through Chromium. The backend is a real
 * uvicorn process on an isolated temp SQLite database. API/DB reads are used
 * only as physical corroboration of what the browser did, never as a
 * substitute for the browser interaction itself.
 *
 * Run (after `npm --prefix frontend run build`):
 *   node frontend/tests/editorial_precision_flows_e2e.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { spawn, spawnSync, execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import net from 'node:net'
import crypto from 'node:crypto'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')
const fixturePdf = path.join(__dirname, 'fixtures', 'editorial_precision_questions.pdf')

const PALETTES = [
  { id: 'editorial', light: '#f5f2ea', dark: '#121512' },
  { id: 'gruvbox', light: '#fbf1c7', dark: '#282828' },
  { id: 'everforest', light: '#fdf6e3', dark: '#2d353b' },
  { id: 'catppuccin', light: '#eff1f5', dark: '#1e1e2e' },
]
const WIDTHS = [1440, 1024, 768, 390, 375, 320]

let serverProcess = null
let tempDbPath = ''
let tempDbScript = ''
let baseUrl = ''
let navCounter = 0

/**
 * Full-document navigation. A hash-only `page.goto` on the current route does
 * not reload the SPA, so component state (e.g. an open drawer) would leak into
 * the next flow. The cache-busting query forces a fresh document while keeping
 * the same origin/localStorage.
 */
async function gotoFresh(page, route) {
  navCounter += 1
  await page.goto(`${baseUrl}/?pr90nav=${navCounter}#${route}`)
  await page.waitForLoadState('load')
}

function hexToRgbString(hex) {
  const value = hex.replace('#', '')
  const r = parseInt(value.slice(0, 2), 16)
  const g = parseInt(value.slice(2, 4), 16)
  const b = parseInt(value.slice(4, 6), 16)
  return `rgb(${r}, ${g}, ${b})`
}

async function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer()
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port
      srv.close(() => resolve(port))
    })
    srv.on('error', reject)
  })
}

async function waitForServer(url, expectedToken, timeoutMs = 30000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${url}/api/v1/health`)
      if (res.ok) {
        const body = await res.json()
        const expectedFingerprint = expectedToken
          ? crypto.createHash('sha256').update(expectedToken).digest('hex').slice(0, 16)
          : ''
        if (expectedFingerprint && body.instance_fingerprint !== expectedFingerprint) {
          throw new Error(`Instance fingerprint mismatch: expected ${expectedFingerprint} but got ${body.instance_fingerprint}`)
        }
        return true
      }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 400))
  }
  throw new Error(`Server at ${url} failed to start within ${timeoutMs}ms`)
}

/**
 * Physical DB reads go through the repo's Python runtime (the same one that
 * runs the backend) instead of `node:sqlite`, which CI's Node 20 lacks.
 */
function dbAll(sql, params = []) {
  const result = spawnSync('python', [tempDbScript, tempDbPath, sql, JSON.stringify(params)], {
    encoding: 'utf8',
    maxBuffer: 8 * 1024 * 1024,
  })
  if (result.status !== 0) {
    throw new Error(`DB query failed (${result.status}): ${result.stderr || result.error?.message || ''}`)
  }
  const output = String(result.stdout || '').trim()
  return output ? JSON.parse(output) : []
}

function dbCount(sql, params = []) {
  const rows = dbAll(sql, params)
  return Number(rows[0]?.c ?? 0)
}

async function api(token, method, apiPath, body) {
  const res = await fetch(`${baseUrl}${apiPath}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  const text = await res.text()
  let parsed = null
  try { parsed = text ? JSON.parse(text) : null } catch (_) { parsed = text }
  return { status: res.status, body: parsed }
}

async function apiGet(token, apiPath) {
  const res = await api(token, 'GET', apiPath)
  assert.equal(res.status, 200, `GET ${apiPath} -> ${res.status}: ${JSON.stringify(res.body)}`)
  return res.body
}

async function registerAndLogin(page, username, password) {
  await page.goto(baseUrl)
  await page.waitForSelector('.auth-layout', { timeout: 15000 })
  await page.locator('.auth-switch .link-btn').click()
  await page.fill('#login-username', username)
  await page.fill('#login-password', password)
  await page.fill('#login-confirm', password)
  await page.click('.auth-submit')
  await page.waitForSelector('.today', { timeout: 20000 })
}

async function openPracticeFromBank(page, bankName) {
  await gotoFresh(page, '/banks')
  await page.waitForSelector('.banks-page', { timeout: 15000 })
  const row = page.locator('.banks-row').filter({ hasText: bankName }).first()
  await row.waitFor({ state: 'visible', timeout: 10000 })
  await row.locator('.btn-sm').first().click()
  await page.waitForSelector('.focus-mode', { timeout: 15000 })
  await page.waitForSelector('.q-stem', { timeout: 10000 })
}

test('PR90 Editorial Precision independent real-browser flows', async (t) => {
  assert.ok(fs.existsSync(fixturePdf), `PDF fixture missing: ${fixturePdf}`)
  const fixtureBytes = fs.readFileSync(fixturePdf)
  const fixtureSha = crypto.createHash('sha256').update(fixtureBytes).digest('hex')

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fnexam-pr90-e2e-'))
  tempDbPath = path.join(tempDir, 'pr90_e2e.db')
  tempDbScript = path.join(tempDir, 'db_query.py')
  fs.writeFileSync(
    tempDbScript,
    [
      'import json',
      'import sqlite3',
      'import sys',
      '',
      'db_path, sql, params_json = sys.argv[1], sys.argv[2], sys.argv[3]',
      'params = json.loads(params_json)',
      'conn = sqlite3.connect(db_path)',
      'conn.row_factory = sqlite3.Row',
      'try:',
      '    rows = conn.execute(sql, params).fetchall()',
      '    print(json.dumps([dict(row) for row in rows], ensure_ascii=False))',
      'finally:',
      '    conn.close()',
      '',
    ].join('\n'),
    'utf8'
  )
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  baseUrl = `http://127.0.0.1:${port}`

  console.log(`[pr90] starting FastAPI on ${baseUrl} with isolated DB ${tempDbPath}`)
  serverProcess = spawn(
    'python',
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        DB_PATH: tempDbPath,
        INSTANCE_TOKEN: instanceToken,
        EASYEXAM_SECRET_KEY: process.env.EASYEXAM_SECRET_KEY || 'easyexam-e2e-secret-key-32bytes-ci!!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  let serverErrorOutput = ''
  // Uvicorn writes an access log line per request. A piped stdout that nobody
  // reads fills its OS buffer and blocks the server mid-suite, so drain it.
  serverProcess.stdout.on('data', () => {})
  serverProcess.stderr.on('data', chunk => { serverErrorOutput += chunk.toString() })

  let browser = null
  const USER = 'pr90_browser_student'
  const PASSWORD = 'password-123456'
  let token = ''
  let userKey = ''
  let seedBankId = ''
  let pdfBankId = ''
  let seedQuestions = []

  try {
    await waitForServer(baseUrl, instanceToken)
    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: 'zh-CN',
      acceptDownloads: true,
    })
    const page = await context.newPage()
    // Every browser action gets a hard ceiling. Without this, a locator that
    // never resolves can silently park the suite forever (Playwright's locator
    // helpers default to no timeout in some paths).
    context.setDefaultTimeout(20000)
    page.setDefaultNavigationTimeout(20000)
    page.on('pageerror', err => console.error(`[pr90][pageerror] ${err.message}`))
    page.on('dialog', dialog => dialog.accept().catch(() => {}))

    await t.test('1. Register and sign in through the editorial auth screen', async () => {
      await registerAndLogin(page, USER, PASSWORD)
      assert.match(await page.locator('.byline').innerText(), new RegExp(USER))
      token = await page.evaluate(() => localStorage.getItem('easyexam_token'))
      assert.ok(token, 'auth token must be persisted in localStorage')
      userKey = await page.evaluate(() => {
        const user = JSON.parse(localStorage.getItem('easyexam_user') || '{}')
        return String(user.id ?? user.username ?? '')
      })
      assert.ok(userKey, 'per-account offline queue scope must resolve')
      console.log('✓ auth screen registration/login')
    })

    await t.test('2. Seed isolated banks and questions through the real API', async () => {
      const bank = await api(token, 'POST', '/api/v1/banks', {
        name: 'PR90 Seed Bank',
        default_category: 'PR90 浏览器验证',
      })
      assert.equal(bank.status, 201, JSON.stringify(bank.body))
      seedBankId = bank.body.id

      const pdfBank = await api(token, 'POST', '/api/v1/banks', {
        name: 'PR90 PDF Import Bank',
        default_category: 'PR90 PDF 导入',
      })
      assert.equal(pdfBank.status, 201, JSON.stringify(pdfBank.body))
      pdfBankId = pdfBank.body.id

      const seeds = [
        { stem: 'PR90 浏览器流程题一：计算机网络中提供无连接数据报服务的协议是？', answer: 'B', tags: ['网络', 'PR90'] },
        { stem: 'PR90 浏览器流程题二：关系数据库主键必须满足的约束是？', answer: 'B', tags: ['数据库', 'PR90'] },
        { stem: 'PR90 浏览器流程题三：面向对象中用于实现代码复用的机制是？', answer: 'C', tags: ['面向对象', 'PR90'] },
        { stem: 'PR90 浏览器流程题四：软件测试中验证模块接口的测试属于？', answer: 'B', tags: ['软件测试', 'PR90'] },
      ]
      seedQuestions = []
      for (const seed of seeds) {
        const created = await api(token, 'POST', `/api/v1/banks/${seedBankId}/questions`, {
          stem: seed.stem,
          type: 'SINGLE',
          options: [
            { key: 'A', content: '选项 A' },
            { key: 'B', content: '选项 B' },
            { key: 'C', content: '选项 C' },
            { key: 'D', content: '选项 D' },
          ],
          answer: seed.answer,
          explanation: `解析：${seed.stem}`,
          tags: seed.tags,
        })
        assert.equal(created.status, 201, JSON.stringify(created.body))
        seedQuestions.push(created.body)
      }
      assert.equal(seedQuestions.length, 4)
      assert.equal(dbCount('SELECT COUNT(*) AS c FROM bank_question_items WHERE bank_id = ?', [seedBankId]), 4)
      console.log('✓ seeded 4 questions + empty PDF import bank')
    })

    await t.test('3. Palette x mode x width matrix: 4 x 2 x 6 = 48 real layouts', async () => {
      let combinations = 0
      for (const palette of PALETTES) {
        for (const mode of ['light', 'dark']) {
          await gotoFresh(page, '/settings')
          await page.waitForSelector('.settings-page', { timeout: 15000 })

          const paletteOption = page.locator(`.palette-option[data-palette="${palette.id}"]`)
          await paletteOption.waitFor({ state: 'visible', timeout: 8000 })
          await paletteOption.click()
          assert.equal(
            await page.evaluate(() => document.documentElement.getAttribute('data-theme-palette')),
            palette.id,
            `${palette.id}: palette attribute must apply immediately`
          )

          await page.locator('.settings-section .segmented .segment').nth(mode === 'light' ? 0 : 1).click()
          assert.equal(
            await page.evaluate(() => document.documentElement.getAttribute('data-theme')),
            mode,
            `${palette.id}/${mode}: theme attribute must apply immediately`
          )

          await gotoFresh(page, '/')
          await page.waitForSelector('.today', { timeout: 15000 })
          assert.equal(
            await page.evaluate(() => document.documentElement.getAttribute('data-theme-palette')),
            palette.id,
            `${palette.id}/${mode}: palette must survive a full navigation`
          )
          assert.equal(
            await page.evaluate(() => document.documentElement.getAttribute('data-theme')),
            mode,
            `${palette.id}/${mode}: mode must survive a full navigation`
          )

          for (const width of WIDTHS) {
            await page.setViewportSize({ width, height: width <= 390 ? 844 : 900 })
            const layout = await page.evaluate(() => {
              const style = el => (el ? getComputedStyle(el) : null)
              const title = document.querySelector('.masthead-title')
              const sidebar = document.querySelector('.sidebar')
              const bottomnav = document.querySelector('.bottomnav')
              return {
                bodyBg: getComputedStyle(document.body).backgroundColor,
                scrollWidth: document.documentElement.scrollWidth,
                innerWidth: window.innerWidth,
                titleWidth: title ? title.getBoundingClientRect().width : 0,
                sidebarDisplay: style(sidebar)?.display || 'missing',
                bottomnavDisplay: style(bottomnav)?.display || 'missing',
              }
            })
            assert.equal(
              layout.bodyBg,
              hexToRgbString(mode === 'light' ? palette.light : palette.dark),
              `${palette.id}/${mode}/${width}px: body must paint the palette paper colour`
            )
            assert.ok(
              layout.scrollWidth <= layout.innerWidth + 1,
              `${palette.id}/${mode}/${width}px: horizontal overflow ${layout.scrollWidth} > ${layout.innerWidth}`
            )
            assert.ok(layout.titleWidth > 0, `${palette.id}/${mode}/${width}px: masthead title must be laid out`)
            if (width >= 1024) {
              assert.notEqual(layout.sidebarDisplay, 'none', `${palette.id}/${mode}/${width}px: desktop sidebar must be visible`)
            } else {
              assert.notEqual(layout.bottomnavDisplay, 'none', `${palette.id}/${mode}/${width}px: mobile bottom nav must be visible`)
            }
            combinations += 1
          }
        }
      }
      assert.equal(combinations, PALETTES.length * 2 * WIDTHS.length)
      await page.setViewportSize({ width: 1440, height: 900 })
      console.log(`✓ ${combinations} palette/mode/width layouts without overflow`)
    })

    await t.test('4. Notes: create, edit, save, reload, real PDF upload/preview/download', async () => {
      await gotoFresh(page, '/notes')
      await page.waitForSelector('.library-page', { timeout: 15000 })

      // Create a note through the modal.
      await page.locator('.page-actions .btn-primary').click()
      const createDialog = page.locator('.library-dialog')
      await createDialog.waitFor({ state: 'visible', timeout: 8000 })
      await createDialog.locator('textarea').fill('PR90 note original content')
      await createDialog.locator('button[type="submit"]').click()
      await page.waitForSelector('.library-row:has-text("PR90 note original content")', { timeout: 10000 })

      // Edit and save through the reader.
      await page.locator('.library-row').filter({ hasText: 'PR90 note original content' }).first().click()
      await page.waitForSelector('.reader-foot .note-edit', { timeout: 8000 })
      await page.locator('.reader-foot .note-edit').click()
      await page.locator('.reader-edit-input').fill('PR90 note edited content v2')
      await page.locator('.reader-edit-actions .btn-primary').click()
      await page.waitForSelector('.notice.ok', { timeout: 10000 })
      assert.match(await page.locator('.notice.ok').innerText(), /笔记已保存/)
      await page.waitForSelector('.reader-title:has-text("PR90 note edited content v2")', { timeout: 8000 })

      // Reload proves the save reached the server, not just component state.
      await page.reload()
      await page.waitForSelector('.library-page', { timeout: 15000 })
      await page.locator('.library-row').filter({ hasText: 'PR90 note edited content v2' }).first().click()
      await page.waitForSelector('.reader-body:has-text("PR90 note edited content v2")', { timeout: 8000 })

      // Upload the real PDF fixture through the hidden file input.
      const uploadInput = page.locator('input[type="file"]')
      await uploadInput.setInputFiles(fixturePdf)
      // The row title is the extracted text; the filename itself is reduced to
      // its extension tag, so identify the row by the extracted question text.
      await page.waitForSelector('.library-row:has-text("Which protocol provides connectionless")', { timeout: 20000 })

      await page.locator('.library-row').filter({ hasText: 'Which protocol provides connectionless' }).first().click()
      await page.waitForSelector('.reader-file-name:has-text("editorial_precision_questions.pdf")', { timeout: 8000 })
      const extracted = await page.locator('.reader-body').innerText()
      assert.match(extracted, /Which protocol provides connectionless datagram delivery/)
      assert.match(extracted, /primary key uniquely identifies a row/)

      const assets = await apiGet(token, '/api/v1/assets')
      const pdfAsset = (Array.isArray(assets) ? assets : assets.assets || [])
        .find(item => item.file_name === 'editorial_precision_questions.pdf')
      assert.ok(pdfAsset, 'uploaded PDF asset must exist through the real API')

      // Preview: the browser opens the stored blob in a popup after fetching it.
      const popupPromise = page.waitForEvent('popup', { timeout: 15000 })
      const previewResponsePromise = page.waitForResponse(response => {
        const url = new URL(response.url())
        return response.request().method() === 'GET'
          && url.pathname === `/api/v1/assets/${pdfAsset.id}/file`
      }, { timeout: 15000 })
      await page.locator('.reader-file .file-preview').click()
      const [popup, previewResponse] = await Promise.all([popupPromise, previewResponsePromise])
      assert.equal(previewResponse.status(), 200)
      assert.match(previewResponse.headers()['content-type'] || '', /application\/pdf/i)
      // Corroborate the stored bytes independently of Playwright's response
      // capture (the page consumes the blob, so the captured body can be empty).
      const directRes = await fetch(`${baseUrl}/api/v1/assets/${pdfAsset.id}/file`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      assert.equal(directRes.status, 200)
      const directBytes = Buffer.from(await directRes.arrayBuffer())
      assert.equal(directBytes.length, fixtureBytes.length)
      assert.equal(crypto.createHash('sha256').update(directBytes).digest('hex'), fixtureSha)
      const previewBytes = await previewResponse.body()
      console.log(`[pr90] preview response body bytes: ${previewBytes.length}`)
      if (previewBytes.length) {
        assert.equal(crypto.createHash('sha256').update(previewBytes).digest('hex'), fixtureSha)
      }
      // Headless Chromium has no PDF viewer surface, so the popup navigation
      // can abort after the blob is fetched. Record the scheme without
      // pretending the viewer rendered; the fetch/bytes above are the
      // preview-path evidence.
      let popupScheme = 'unknown'
      try {
        await popup.waitForURL(/^blob:/, { timeout: 5000 })
        popupScheme = 'blob:'
      } catch (_) {
        try { popupScheme = popup.url() } catch (_) { popupScheme = 'popup closed after aborted PDF navigation' }
      }
      console.log(`[pr90] preview popup scheme: ${popupScheme}`)
      await popup.close().catch(() => {})

      // Download: the real anchor download must deliver the exact stored bytes.
      const downloadPromise = page.waitForEvent('download', { timeout: 15000 })
      await page.locator('.reader-file .file-download').click()
      const download = await downloadPromise
      assert.equal(download.suggestedFilename(), 'editorial_precision_questions.pdf')
      const downloadPath = path.join(tempDir, 'downloaded_fixture.pdf')
      await download.saveAs(downloadPath)
      const downloadedSha = crypto.createHash('sha256').update(fs.readFileSync(downloadPath)).digest('hex')
      assert.equal(downloadedSha, fixtureSha, 'downloaded PDF bytes must match the uploaded fixture')
      console.log('✓ note create/edit/save/reload + PDF upload/preview/download')
    })

    await t.test('5. PDF import preview and duplicate strategies skip / new / merge', async () => {
      const bankQuestionCount = () => dbCount(
        'SELECT COUNT(*) AS c FROM bank_question_items WHERE bank_id = ?', [pdfBankId]
      )
      const bankVersionCount = () => dbCount(
        `SELECT COUNT(*) AS c FROM question_versions qv
         JOIN bank_question_items bqi ON bqi.question_id = qv.question_id
         WHERE bqi.bank_id = ?`, [pdfBankId]
      )

      const startPdfPreview = async () => {
        // Chromium does not fire change when the same file path is selected
        // again on the same input, so clear it first to make the real
        // re-selection observable.
        await page.locator('input[type="file"]').setInputFiles([])
        await page.locator('input[type="file"]').setInputFiles(fixturePdf)
        const inspect = page.locator('.import-actions .btn-primary:not([disabled])')
        await inspect.waitFor({ state: 'visible', timeout: 10000 })
        await inspect.click()
        await page.waitForSelector('.pdf-list .pdf-card', { timeout: 20000 })
      }

      const resetAfterResult = async () => {
        await page.locator('.result-block .btn:not(.btn-primary)').click()
        await page.waitForSelector('.result-block', { state: 'detached', timeout: 8000 })
      }

      // The P5 wizard confirms *after* the duplicate step, so PDF corrections
      // are submitted from there rather than from the mapping step.
      const goToStrategyStep = async () => {
        await page.locator('[data-step="check"] .import-actions .btn-primary').click()
        await page.waitForSelector('[data-step="duplicates"]', { timeout: 10000 })
      }

      const confirmPdf = async () => {
        const confirm = page.locator('[data-step="duplicates"] .import-actions .btn-primary')
        await confirm.waitFor({ state: 'visible', timeout: 10000 })
        await confirm.click()
        await page.waitForSelector('.result-block', { timeout: 20000 })
      }

      await gotoFresh(page, '/import')
      await page.waitForSelector('.import-page', { timeout: 15000 })
      await page.locator('#import-bank').selectOption(pdfBankId)

      // First import: clean bank, two parsed candidates, no duplicate prompt.
      await startPdfPreview()
      assert.equal(await page.locator('.pdf-card').count(), 2, 'PDF preview must expose both candidates')
      await goToStrategyStep()
      assert.equal(await page.locator('[data-step="duplicates"] .dup-list').count(), 0, 'clean bank must not show duplicates')
      await confirmPdf()
      assert.match(await page.locator('.result-block .step-sub').innerText(), /2/)
      assert.equal(bankQuestionCount(), 2)

      // Second import: duplicates are detected and a strategy is mandatory.
      await resetAfterResult()
      await startPdfPreview()
      await goToStrategyStep()
      await page.waitForSelector('[data-step="duplicates"] .dup-list', { timeout: 10000 })
      assert.match(await page.locator('[data-step="duplicates"] .step-head').innerText(), /2/)
      const strategyStep = page.locator('[data-step="duplicates"] .import-actions .btn-primary')
      assert.equal(await strategyStep.isDisabled(), true,
        'confirm must stay disabled until a duplicate strategy is chosen')
      await page.locator('#import-strategy').selectOption('skip')
      assert.equal(await strategyStep.isDisabled(), false)
      await confirmPdf()
      assert.match(await page.locator('.result-block .step-sub').innerText(), /0/)
      assert.equal(bankQuestionCount(), 2, 'skip must not add questions')

      // Third import: "new" creates a second copy of each candidate.
      await resetAfterResult()
      await startPdfPreview()
      await goToStrategyStep()
      await page.waitForSelector('[data-step="duplicates"] .dup-list', { timeout: 10000 })
      await page.locator('#import-strategy').selectOption('new')
      await confirmPdf()
      assert.match(await page.locator('.result-block .step-sub').innerText(), /2/)
      assert.equal(bankQuestionCount(), 4, 'new strategy must import both candidates again')

      // Fourth import: "merge" updates existing questions as new versions.
      const versionsBeforeMerge = bankVersionCount()
      await resetAfterResult()
      await startPdfPreview()
      await goToStrategyStep()
      await page.waitForSelector('[data-step="duplicates"] .dup-list', { timeout: 10000 })
      await page.locator('#import-strategy').selectOption('merge')
      await confirmPdf()
      assert.match(await page.locator('.result-block .step-sub').innerText(), /2/)
      assert.equal(bankQuestionCount(), 4, 'merge must not create extra questions')
      assert.equal(bankVersionCount(), versionsBeforeMerge + 2, 'merge must create one new version per candidate')
      console.log('✓ PDF preview + skip/new/merge with physical question/version counts')
    })

    await t.test('6. Blueprint: create paper, add section, save and reload persistence', async () => {
      await gotoFresh(page, '/exams')
      await page.waitForSelector('.exam-center', { timeout: 15000 })

      const emptyCreate = page.locator('.empty-actions .btn').first()
      await emptyCreate.waitFor({ state: 'visible', timeout: 10000 })
      await emptyCreate.click()
      const createDialog = page.locator('.exam-setup-dialog')
      await createDialog.waitFor({ state: 'visible', timeout: 8000 })
      await createDialog.locator('input[type="text"]').first().fill('PR90 Blueprint Paper')
      await createDialog.locator('button[type="submit"]').click()
      await page.waitForSelector('.paper-row:has-text("PR90 Blueprint Paper")', { timeout: 15000 })

      const profiles = await apiGet(token, '/api/v1/exams/profiles')
      const profile = profiles.find(item => item.name === 'PR90 Blueprint Paper')
      assert.ok(profile, 'paper created through the UI must exist through the real API')

      // Creating a paper opens its blueprint drawer automatically.
      await page.waitForSelector('.drawer', { timeout: 10000 })
      await page.waitForSelector('.drawer-body', { timeout: 8000 })

      const addSection = page.locator('.drawer-body > button.btn.btn-sm')
      await addSection.waitFor({ state: 'visible', timeout: 8000 })
      await addSection.click()
      await page.waitForSelector('.bp-section', { timeout: 8000 })
      await page.locator('.bp-section .bp-count').fill('2')

      const saveResponsePromise = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/exams/profiles/${profile.id}/blueprint`)
        && response.request().method() === 'POST'
      , { timeout: 15000 })
      await page.locator('.drawer-foot .btn-primary').click()
      const saveResponse = await saveResponsePromise
      assert.equal(saveResponse.status(), 201)
      await page.waitForFunction(() => document.querySelector('.drawer-sub')?.textContent.includes('v1'), null, { timeout: 10000 })
      assert.equal(await page.locator('.drawer .error').count(), 0, 'blueprint save must not surface an error')

      const saved = await apiGet(token, `/api/v1/exams/profiles/${profile.id}/blueprint`)
      assert.equal(saved.blueprint.sections.length, 1)
      assert.equal(Number(saved.blueprint.sections[0].count), 2)

      // Close the drawer, then load a fresh document: the persisted count must
      // hydrate from the server rather than component state.
      await page.locator('.drawer .icon-btn').click()
      await page.waitForSelector('.drawer', { state: 'detached', timeout: 8000 })
      await gotoFresh(page, '/exams')
      await page.waitForSelector('.exam-center', { timeout: 15000 })
      const paperRow = page.locator('.paper-row').filter({ hasText: 'PR90 Blueprint Paper' }).first()
      await paperRow.waitFor({ state: 'visible', timeout: 10000 })
      assert.match(await paperRow.locator('.list-meta').innerText(), /1/)
      await paperRow.locator('.btn-quiet').click()
      await page.waitForSelector('.drawer .bp-section', { timeout: 10000 })
      assert.equal(await page.locator('.bp-section .bp-count').inputValue(), '2')
      await page.locator('.drawer-foot .btn-quiet').click()
      console.log('✓ blueprint create/save/reload persistence')
    })

    await t.test('7. Exam: flag, answer sheet, unanswered question, submit report', async () => {
      await gotoFresh(page, '/exams')
      await page.waitForSelector('.exam-center', { timeout: 15000 })
      await page.locator('.page-actions .btn-primary:not([disabled])').click()
      const setup = page.locator('.exam-setup-dialog')
      await setup.waitFor({ state: 'visible', timeout: 8000 })
      const bankSelect = setup.locator('select').first()
      const optionValue = await bankSelect.locator('option', { hasText: 'PR90 Seed Bank' }).first().getAttribute('value')
      assert.ok(optionValue, 'seed bank must be selectable in exam setup')
      await bankSelect.selectOption(optionValue)
      const numbers = setup.locator('input[type="number"]')
      await numbers.nth(0).fill('3')
      await numbers.nth(1).fill('30')
      await setup.locator('button[type="submit"]').click()
      await page.waitForSelector('.exam-mode', { timeout: 15000 })
      await page.waitForSelector('.exam-option', { timeout: 10000 })
      assert.equal(await page.locator('.exam-report').count(), 0, 'no report before submission')

      // Question 1: flag it, leave it unanswered. The flag is persisted by an
      // async API call, so wait for the server round-trip before asserting.
      const flagResponsePromise = page.waitForResponse(response =>
        response.url().endsWith('/toggle-flag') && response.request().method() === 'POST'
      , { timeout: 10000 })
      await page.locator('[data-testid="exam-flag-toggle"]').click()
      assert.equal((await flagResponsePromise).status(), 200)
      await page.waitForFunction(() =>
        document.querySelector('[data-testid="exam-flag-toggle"]')?.getAttribute('aria-pressed') === 'true'
      , null, { timeout: 10000 })
      assert.match(await page.locator('[data-testid="exam-answer-sheet"] .sheet-facts').innerText(), /标记\s*1/)

      // Question 2 and 3: answer both, leaving exactly one blank.
      await page.locator('[data-testid="exam-answer-sheet"] .answer-cell').nth(1).click()
      await page.locator('.exam-option').first().click()
      await page.locator('[data-testid="exam-answer-sheet"] .answer-cell').nth(2).click()
      await page.locator('.exam-option').first().click()

      const sheet = page.locator('[data-testid="exam-answer-sheet"]')
      assert.match(await sheet.locator('.sheet-count').innerText(), /2\s*\/\s*3/)
      assert.equal(await sheet.locator('.answer-cell.answered').count(), 2)
      assert.equal(await sheet.locator('.answer-cell.flagged').count(), 1)
      const facts = await sheet.locator('.sheet-facts').innerText()
      assert.match(facts, /已答\s*2/)
      assert.match(facts, /未答\s*1/)
      assert.match(facts, /标记\s*1/)

      await page.locator('.exam-submit').click()
      await page.locator('[data-testid="exam-submit-confirm"]').waitFor({ state: 'visible', timeout: 8000 })
      await page.locator('[data-testid="exam-submit-confirm"] .btn-primary').click()
      await page.waitForSelector('.exam-report', { timeout: 15000 })

      assert.ok(await page.locator('.report-score').isVisible())
      assert.match(await page.locator('.report-facts').innerText(), /2\s*\/\s*3/)
      assert.match(await page.locator('.report-counts').innerText(), /未答\s*1/)
      assert.ok(await page.locator('table.etable').first().isVisible(), 'type statistics table must render')
      const blankReview = page.locator('.exam-review .review-item .tag')
      await blankReview.first().waitFor({ state: 'visible', timeout: 8000 })
      assert.match(await blankReview.first().innerText(), /未答/)

      await page.locator('.report-actions .btn-primary').click()
      await page.waitForSelector('.exam-center', { timeout: 10000 })
      console.log('✓ exam flag/answer sheet/unanswered/report')
    })

    await t.test('8. Offline practice answer -> pending queue -> online auto-sync -> reload', async (t8) => {
      let question = null
      let chosenKey = ''
      let sessionId = ''
      const queueKey = `easyexam_offline_attempts_${userKey}`

      await t8.test('8a. Offline submit queues once and auto-sync persists exactly one attempt', async () => {
        await openPracticeFromBank(page, 'PR90 Seed Bank')
        const stem = await page.locator('.q-stem').first().innerText()
        question = seedQuestions.find(item => item.stem === stem)
        assert.ok(question, 'the first practice question must match a seeded question')

        await context.setOffline(true)
        const chosenOption = page.locator('.opt').first()
        chosenKey = (await chosenOption.locator('.opt-key').innerText()).trim()
        await chosenOption.click()
        await page.locator('.focus-actionbar .btn-primary').click()
        await page.waitForSelector('[data-testid="offline-banner"]', { timeout: 15000 })
        // Either the attempt-specific or the draft-flush notice may win the race;
        // both are the product's offline-kept state.
        assert.match(await page.locator('[data-testid="offline-banner"]').innerText(), /作答已暂存在本机|答案已保留/)

        // The submit retries twice before queueing; wait for the physical queue
        // entry instead of racing the banner.
        await page.waitForFunction(key => {
          try { return JSON.parse(localStorage.getItem(key) || '[]').length === 1 } catch (_) { return false }
        }, queueKey, { timeout: 20000 })
        const queued = await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]'), queueKey)
        assert.equal(queued.length, 1, 'offline answer must be queued exactly once')
        sessionId = queued[0].sessionId
        assert.ok(sessionId, 'queued attempt must carry the session id')
        assert.equal(
          dbCount('SELECT COUNT(*) AS c FROM answer_attempts WHERE session_id = ? AND question_id = ?',
            [sessionId, question.id]),
          0,
          'no attempt may reach the server while offline'
        )

        // Restore the network. The app's own online handler must drain the queue.
        await context.setOffline(false)
        await page.waitForFunction(key => {
          try { return JSON.parse(localStorage.getItem(key) || '[]').length === 0 } catch (_) { return false }
        }, queueKey, { timeout: 20000 })
        await page.locator('[data-testid="offline-banner"]').waitFor({ state: 'detached', timeout: 20000 })
        assert.equal(
          dbCount('SELECT COUNT(*) AS c FROM answer_attempts WHERE session_id = ? AND question_id = ?',
            [sessionId, question.id]),
          1,
          'online recovery must persist exactly one attempt'
        )
        console.log('✓ offline pending -> online auto-sync: exactly one attempt in SQLite')
      })

      await t8.test('8b. Reload keeps one attempt and rehydrates the submitted answer', async (t8b) => {
        assert.ok(sessionId && question, '8a must have established the offline session')
        await page.reload()
        await page.waitForSelector('.focus-mode', { timeout: 15000 })

        // Physical evidence first: a reload must never replay the drained attempt.
        assert.equal(
          dbCount('SELECT COUNT(*) AS c FROM answer_attempts WHERE session_id = ? AND question_id = ?',
            [sessionId, question.id]),
          1,
          'reload must not replay the drained attempt'
        )
        const queueAfterReload = await page.evaluate(key => JSON.parse(localStorage.getItem(key) || '[]'), queueKey)
        assert.equal(queueAfterReload.length, 0, 'offline queue must stay empty after reload')

        // `save_attempt` stores a rich answer object, but the app's online
        // recovery runs `drainPendingAttempts()` and `flushDraft()` without
        // ordering them. When the draft sync lands after the attempt, the
        // repository's `update_draft` replaces that object with the bare value
        // (`{"qid": "A"}`). Require the server-side scored record to survive.
        const sessionAfterReload = await apiGet(token, `/api/v1/practice/sessions/${sessionId}`)
        const savedEntry = sessionAfterReload.answers?.[question.id]
        const savedAnswer = savedEntry && typeof savedEntry === 'object' ? savedEntry.answer : savedEntry
        assert.equal(savedAnswer, chosenKey, 'server session must keep the drained answer value')
        assert.equal(typeof savedEntry, 'object', 'draft sync must preserve scored attempt metadata')

        await page.waitForSelector('.opt.is-selected', { timeout: 15000 })
        assert.equal(
          (await page.locator('.opt.is-selected .opt-key').first().innerText()).trim(),
          chosenKey,
          'the submitted option must still be selected after reload'
        )
        console.log('✓ reload: no duplicate attempt, answer retained, option rehydrated')
      })
    })

    await context.close()
  } catch (error) {
    if (serverErrorOutput && /Traceback|Error/.test(serverErrorOutput)) {
      console.error('[pr90] backend stderr tail:\n' + serverErrorOutput.slice(-5000))
    }
    throw error
  } finally {
    if (browser) await browser.close().catch(() => {})
    if (serverProcess && serverProcess.pid) {
      try {
        if (process.platform === 'win32') {
          execSync(`taskkill /pid ${serverProcess.pid} /T /F`, { stdio: 'ignore' })
        } else {
          serverProcess.kill('SIGKILL')
        }
      } catch (_) {
        try { serverProcess.kill('SIGKILL') } catch (_) {}
      }
    }
    if (tempDbPath && fs.existsSync(tempDbPath)) {
      const target = fs.realpathSync(path.dirname(tempDbPath))
      const tempRoot = fs.realpathSync(os.tmpdir())
      if (path.dirname(target) === tempRoot && path.basename(target).startsWith('fnexam-pr90-e2e-')) {
        try { fs.rmSync(target, { recursive: true, force: true }) } catch (_) {}
      }
    }
  }
})
