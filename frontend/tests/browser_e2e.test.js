import test from 'node:test'
import assert from 'node:assert/strict'
import { spawn, execSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import net from 'node:net'
import crypto from 'node:crypto'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')

let serverProcess = null
let tempDbPath = ''

function parseRgb(str, parentRgb = [255, 255, 255]) {
  if (!str) return parentRgb
  str = str.trim()
  if (str.startsWith('color(srgb')) {
    const parts = str.slice(10, -1).trim().split(/[\s/]+/).map(Number)
    const r = Math.round(parts[0] * 255)
    const g = Math.round(parts[1] * 255)
    const b = Math.round(parts[2] * 255)
    const a = parts.length > 3 ? parts[3] : 1
    if (a < 1) {
      return [
        Math.round(r * a + parentRgb[0] * (1 - a)),
        Math.round(g * a + parentRgb[1] * (1 - a)),
        Math.round(b * a + parentRgb[2] * (1 - a)),
      ]
    }
    return [r, g, b]
  }
  const m = str.match(/rgba?\(([^)]+)\)/)
  if (m) {
    const parts = m[1].split(/[\s,]+/).filter(Boolean).map(Number)
    const r = parts[0], g = parts[1], b = parts[2]
    const a = parts.length > 3 ? parts[3] : 1
    if (a < 1) {
      return [
        Math.round(r * a + parentRgb[0] * (1 - a)),
        Math.round(g * a + parentRgb[1] * (1 - a)),
        Math.round(b * a + parentRgb[2] * (1 - a)),
      ]
    }
    return [r, g, b]
  }
  const digits = (str || '').match(/\d+/g)
  if (digits && digits.length >= 3) {
    return [Number(digits[0]), Number(digits[1]), Number(digits[2])]
  }
  return [15, 23, 42]
}

function calcLum([r, g, b]) {
  const [lr, lg, lb] = [r, g, b].map(c => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb
}

function calcContrast(color1, color2, parentRgb = [255, 255, 255]) {
  const l1 = calcLum(Array.isArray(color1) ? color1 : parseRgb(color1, parentRgb))
  const l2 = calcLum(Array.isArray(color2) ? color2 : parseRgb(color2, parentRgb))
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
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

async function waitForServer(url, expectedToken, timeoutMs = 25000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${url}/api/v1/health`)
      if (res.ok) {
        const body = await res.json()
        if (expectedToken && body.instance_token !== expectedToken) {
          throw new Error(`Instance token mismatch: expected ${expectedToken} but got ${body.instance_token}`)
        }
        return true
      }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 400))
  }
  throw new Error(`Server at ${url} failed to start within ${timeoutMs}ms`)
}

async function login(page, baseUrl, username, password) {
  await page.goto(baseUrl)
  await page.waitForSelector('.auth-layout')
  await page.fill('#login-username', username)
  await page.fill('#login-password', password)
  await page.click('.auth-submit')
  await page.waitForSelector('.today', { timeout: 15000 })
}

async function logout(page) {
  await page.locator('.sidebar .user-mini').click()
  await page.locator('.account-menu .popover-action.is-danger').click()
  await page.waitForSelector('.auth-layout')
}

async function openBanks(page, baseUrl) {
  await page.goto(`${baseUrl}/#/banks`)
  await page.waitForSelector('.banks-page')
}

async function startBankPractice(page, baseUrl, bankName) {
  await openBanks(page, baseUrl)
  const row = page.locator('.banks-row').filter({ hasText: bankName }).first()
  await row.waitFor({ state: 'visible', timeout: 10000 })
  await row.locator('.btn-sm').first().click()
  await page.waitForSelector('.focus-mode', { timeout: 12000 })
  await page.waitForSelector('.q-stem', { timeout: 8000 })
}

function correctKeyFor(stem) {
  if (stem.includes('计算机网络')) return 'B'
  if (stem.includes('关系数据库')) return 'B'
  if (stem.includes('面向对象')) return 'C'
  if (stem.includes('软件测试')) return 'B'
  return 'A'
}

async function answerCurrent(page, wrong = false) {
  await page.waitForSelector('.focus-mode .q-stem', { timeout: 8000 })
  const stem = await page.locator('.q-stem').first().innerText()
  const correctKey = correctKeyFor(stem)
  const targetKey = wrong ? (correctKey === 'A' ? 'B' : 'A') : correctKey
  const option = page.locator('.opt').filter({ has: page.locator('.opt-key', { hasText: targetKey }) }).first()
  await option.click()
  await page.locator('.focus-actionbar .btn-primary').click()
  await page.waitForSelector('.verdict-line', { timeout: 8000 })
  return { stem, targetKey }
}

async function exitPractice(page) {
  await page.locator('.focus-exit').click()
  const dialog = page.locator('[data-testid="exit-confirm-modal"]')
  await dialog.waitFor({ state: 'visible', timeout: 5000 })
  await dialog.locator('.btn-primary').click()
  await page.waitForSelector('.focus-mode', { state: 'detached', timeout: 8000 })
}

async function nextQuestion(page) {
  await page.waitForSelector('.focus-actionbar .btn-primary', { timeout: 5000 })
  await page.locator('.focus-actionbar .btn-primary').click()
  await page.waitForTimeout(300)
}

async function currentStem(page) {
  await page.waitForSelector('.q-stem', { timeout: 8000 })
  return page.locator('.q-stem').first().innerText()
}

async function fillEditStem(page, value) {
  await page.locator('.edit-panel textarea').first().fill(value)
}

async function openQuestionEditor(page) {
  await page.locator('.btn-more-menu').click()
  await page.locator('.focus-menu-item').first().click()
  await page.waitForSelector('[data-testid="question-edit-panel"]', { timeout: 5000 })
}

async function startExamFromCenter(page, baseUrl, bankName, total = 3) {
  await page.goto(`${baseUrl}/#/exams`)
  await page.waitForSelector('.exam-center')
  await page.locator('.page-actions .btn-primary:not([disabled])').waitFor({ state: 'visible', timeout: 10000 })
  await page.locator('.page-actions .btn-primary:not([disabled])').click()
  const dialog = page.locator('.exam-setup-dialog')
  await dialog.waitFor({ state: 'visible', timeout: 5000 })
  const bankSelect = dialog.locator('select').first()
  const optionValue = await bankSelect.locator('option', { hasText: bankName }).first().getAttribute('value')
  assert.ok(optionValue, `Bank ${bankName} must be selectable in exam setup`)
  await bankSelect.selectOption(optionValue)
  const numbers = dialog.locator('input[type="number"]')
  await numbers.nth(0).fill(String(total))
  await numbers.nth(1).fill('30')
  await dialog.locator('button[type="submit"]').click()
  await page.waitForSelector('.exam-mode', { timeout: 12000 })
}

test('True Chrome Browser E2E: Editorial Precision Full Lifecycle', async (t) => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fnexam-e2e-'))
  tempDbPath = path.join(tempDir, 'browser_e2e.db')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const BASE_URL = `http://127.0.0.1:${port}`

  console.log(`Starting FastAPI on dynamic port ${port} with instance token ${instanceToken}...`)
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
  serverProcess.stderr.on('data', chunk => {
    serverErrorOutput += chunk.toString()
  })

  let browser = null
  try {
    await waitForServer(BASE_URL, instanceToken)
    console.log(`FastAPI server is up and verified with instance token on port ${port}.`)

    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' })
    const page = await context.newPage()
    page.__baseUrl = BASE_URL

    page.on('pageerror', err => console.error(`[Browser PageError] ${err.message}`))
    page.on('dialog', async dialog => {
      console.log(`Browser Dialog [${dialog.type()}]: ${dialog.message()}`)
      await dialog.accept()
    })

    await t.test('1. User Registration and Auto Login', async () => {
      await page.goto(BASE_URL)
      await page.waitForSelector('.auth-layout')
      await page.locator('.auth-switch .link-btn').click()
      await page.fill('#login-username', 'e2e_student')
      await page.fill('#login-password', 'password-123456')
      await page.fill('#login-confirm', 'password-123456')
      await page.click('.auth-submit')

      await page.waitForSelector('.today', { timeout: 15000 })
      const byline = await page.locator('.byline').innerText()
      assert.match(byline, /e2e_student/)
      console.log('✓ Registered and logged in through the editorial auth screen.')
    })

    await t.test('2. Bank Creation via the Banks Workspace', async () => {
      await openBanks(page, BASE_URL)
      await page.locator('.page-actions .btn-primary').click()
      const dialog = page.locator('.exam-setup-dialog')
      await dialog.waitFor({ state: 'visible', timeout: 5000 })
      const inputs = dialog.locator('input[type="text"]')
      await inputs.nth(0).fill('E2E真实浏览器题库')
      await inputs.nth(1).fill('自动化测试')
      await dialog.locator('textarea').fill('用于真实 Chrome 端到端验证')
      await dialog.locator('button[type="submit"]').click()
      await page.waitForTimeout(1000)
      await openBanks(page, BASE_URL)
      await page.waitForSelector('.banks-row:has-text("E2E真实浏览器题库")', { timeout: 10000 })
      await openBanks(page, BASE_URL)
      await page.waitForSelector('.banks-row:has-text("E2E真实浏览器题库")', { timeout: 10000 })
      console.log('✓ Created a question bank through the management-style banks page.')
    })

    let token = ''
    let bankId = ''
    let bankBId = ''

    await t.test('3. Seed Question Data, Weak Flag and Due Review via API', async () => {
      token = await page.evaluate(() => localStorage.getItem('easyexam_token'))
      assert.ok(token, 'Token must exist in localStorage')

      const banks = await (await fetch(`${BASE_URL}/api/v1/banks`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      const targetBank = banks.find(b => b.name === 'E2E真实浏览器题库')
      assert.ok(targetBank, 'Bank must exist in API list')
      bankId = targetBank.id

      const createQuestion = async payload => {
        const res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify(payload),
        })
        assert.equal(res.status, 201)
        return res.json()
      }

      await createQuestion({
        stem: '计算机网络中，提供无连接数据报传输服务的网络层协议是？',
        type: 'SINGLE',
        options: [
          { key: 'A', content: 'TCP' },
          { key: 'B', content: 'IP' },
          { key: 'C', content: 'HTTP' },
          { key: 'D', content: 'FTP' },
        ],
        answer: 'B',
        explanation: 'IP 协议工作在网络层，提供不可靠无连接的数据报传输。',
        tags: ['网络层', '计算机网络'],
      })
      await createQuestion({
        stem: '关系数据库中关于主键的约束，下列描述正确的是？',
        type: 'SINGLE',
        options: [
          { key: 'A', content: '可以包含 NULL 值' },
          { key: 'B', content: '必须唯一且非空' },
          { key: 'C', content: '每个表可以有多个主键' },
          { key: 'D', content: '必须是整型数值' },
        ],
        answer: 'B',
        explanation: '主键用于唯一标识表中的一条记录，必须满足唯一且非空。',
        tags: ['数据库', '主键'],
      })
      await createQuestion({
        stem: '面向对象程序设计的基本特征中，用于实现代码复用的是？',
        type: 'SINGLE',
        options: [
          { key: 'A', content: '多态' },
          { key: 'B', content: '封装' },
          { key: 'C', content: '继承' },
          { key: 'D', content: '重载' },
        ],
        answer: 'C',
        explanation: '继承机制允许子类获得父类的特征和行为，主要用于代码复用。',
        tags: ['面向对象'],
      })

      const b2Res = await fetch(`${BASE_URL}/api/v1/banks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: '第二题库(专项隔离)', default_category: '隔离测试' }),
      })
      assert.equal(b2Res.status, 201)
      bankBId = (await b2Res.json()).id

      const qWeakRes = await fetch(`${BASE_URL}/api/v1/banks/${bankBId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          stem: '软件测试中，用于验证模块接口的测试属于什么测试？',
          type: 'SINGLE',
          options: [
            { key: 'A', content: '单元测试' },
            { key: 'B', content: '集成测试' },
          ],
          answer: 'B',
          explanation: '集成测试重点检测模块之间的接口交互。',
        }),
      })
      assert.equal(qWeakRes.status, 201)
      const qWeak = await qWeakRes.json()
      await fetch(`${BASE_URL}/api/v1/learning/weak/${qWeak.id}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      execSync(`python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); conn.execute(\\"UPDATE fsrs_cards SET due_at = '2020-01-01 00:00:00' WHERE question_id = '${qWeak.id}'\\\"); conn.commit(); conn.close()"`)

      await openBanks(page, BASE_URL)
      await page.waitForSelector('.banks-row:has-text("E2E真实浏览器题库")')
      console.log('✓ Seeded 3 questions in Bank A and 1 weak due question in Bank B.')
    })

    let killedStem = ''
    let mistakeStem = ''

    await t.test('4. Learning Flow: Wrong Answer, Verdict, Kill and Report', async () => {
      await startBankPractice(page, BASE_URL, 'E2E真实浏览器题库')

      const q1 = await answerCurrent(page, true)
      mistakeStem = q1.stem
      const wrongVerdict = await page.locator('.verdict-line').innerText()
      assert.match(wrongVerdict, /回答错误/)
      assert.ok(await page.locator('.explain-block').isVisible(), 'Official explanation must be shown after answering')
      await nextQuestion(page)

      const q2 = await answerCurrent(page, false)
      killedStem = q2.stem
      const correctVerdict = await page.locator('.verdict-line').innerText()
      assert.match(correctVerdict, /回答正确/)

      await page.locator('.btn-more-menu').click()
      await page.locator('.focus-menu-item.is-danger').click()
      await page.waitForTimeout(400)

      const q3 = await answerCurrent(page, false)
      assert.ok(q3.stem)
      await page.locator('.focus-finish').click()
      await page.waitForSelector('.report-dialog', { timeout: 10000 })
      assert.ok(await page.locator('[data-testid="practice-report-modal"]').isVisible())
      await page.locator('.report-dialog .dialog-actions .btn').first().click()
      await page.waitForSelector('.banks-page', { timeout: 8000 })
      console.log('✓ Completed practice with a wrong answer, a killed question and the report dialog.')
    })

    await t.test('5. Mistakes: Cause Persistence, Scoped Practice and FSRS Rating', async () => {
      await page.locator('.sidebar .nav-item').nth(2).click()
      await page.waitForSelector('.review-page')
      await page.locator('.review-page .tabs .tab').nth(1).click()
      await page.waitForSelector('.mistake-row', { timeout: 10000 })

      const row = page.locator('.mistake-row').filter({ hasText: mistakeStem.slice(0, 8) }).first()
      await row.waitFor({ state: 'visible', timeout: 8000 })
      await row.locator('.cause-select').selectOption('概念欠缺')
      await page.waitForTimeout(600)

      const mistakes = await (await fetch(`${BASE_URL}/api/v1/mistakes?bank_id=${bankId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      const saved = mistakes.find(m => m.stem === mistakeStem)
      assert.ok(saved, 'Mistake must exist in API')
      assert.equal(saved.mistake_cause, '概念欠缺')

      await row.locator('.mistake-actions .btn').first().click()
      await page.waitForSelector('.focus-mode', { timeout: 10000 })
      const counter = await page.locator('.focus-actionbar .focus-counter').innerText()
      assert.match(counter, /1\s*\/\s*1/)

      await answerCurrent(page, false)
      await page.waitForSelector('.fsrs-block .fsrs-buttons .btn', { timeout: 5000 })

      const paper = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
      const ratingStyles = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('.fsrs-buttons .btn')).map(btn => {
          const cs = getComputedStyle(btn)
          return { text: btn.textContent.trim(), color: cs.color, bg: cs.backgroundColor }
        })
      })
      assert.equal(ratingStyles.length, 4, 'FSRS must expose four rating buttons')
      for (const style of ratingStyles) {
        const bg = style.bg === 'rgba(0, 0, 0, 0)' ? paper : style.bg
        const ratio = calcContrast(style.color, bg)
        assert.ok(ratio >= 4.5, `FSRS rating "${style.text}" contrast ${ratio.toFixed(2)}:1 must meet AA`)
      }

      const ratingResponse = page.waitForResponse(response => {
        if (!response.url().endsWith('/attempts') || response.request().method() !== 'POST') return false
        try { return response.request().postDataJSON()?.fsrs_rating === 4 } catch { return false }
      })
      await page.locator('.fsrs-buttons .btn').nth(3).click()
      assert.equal((await ratingResponse).status(), 201, 'FSRS rating request must succeed')
      await page.waitForSelector('.fsrs-block .hint', { timeout: 5000 })

      const ratingInDb = execSync(
        `python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); r=conn.execute('SELECT fsrs_rating FROM answer_attempts ORDER BY rowid DESC LIMIT 1').fetchone(); print(r[0]); conn.close()"`
      ).toString().trim()
      assert.equal(ratingInDb, '4', 'FSRS rating must physically be 4 in SQLite')

      const snapshotRecorded = execSync(
        `python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); r=conn.execute('SELECT card_snapshot_json FROM answer_attempts ORDER BY rowid DESC LIMIT 1').fetchone(); print(bool(r[0])); conn.close()"`
      ).toString().trim()
      assert.equal(snapshotRecorded, 'True', 'Attempt must store the pre-answer card snapshot')

      await page.locator('.focus-exit').click()
      const exitDialog = page.locator('[data-testid="exit-confirm-modal"]')
      await exitDialog.waitFor({ state: 'visible', timeout: 5000 })
      await exitDialog.locator('.dialog-actions .btn').first().click()
      assert.ok(await page.locator('.focus-mode').isVisible(), 'Cancelling exit must preserve the session')
      await page.locator('.focus-exit').click()
      await exitDialog.locator('.btn-primary').click()
      await page.waitForSelector('.review-page', { timeout: 8000 })
      console.log('✓ Verified mistake cause persistence, one-question practice and physical FSRS rating=4.')
    })

    await t.test('6. Multi-Bank Isolation and Weak-Flagged Due Review', async () => {
      await page.locator('.review-page .tabs .tab').nth(0).click()
      const dueRow = page.locator('.due-row').filter({ hasText: '软件测试' }).first()
      await dueRow.waitFor({ state: 'visible', timeout: 10000 })
      assert.ok(await dueRow.locator('.tag.brand').isVisible(), 'Weak question must carry the weak tag')

      await dueRow.locator('.btn').click()
      await page.waitForSelector('.focus-mode', { timeout: 10000 })
      await answerCurrent(page, false)
      await exitPractice(page)
      await page.waitForSelector('.review-page')
      console.log('✓ Verified bank-isolated weak due review.')
    })

    await t.test('7. Killed Questions: Scoped Review and Restoration on Wrong', async () => {
      await page.locator('.review-page .tabs .tab').nth(2).click()
      const killedRow = page.locator('.review-single .list-row').filter({ hasText: killedStem.slice(0, 8) }).first()
      await killedRow.waitFor({ state: 'visible', timeout: 8000 })

      await page.locator('.review-toolbar .btn').first().click()
      await page.waitForSelector('.focus-mode', { timeout: 10000 })
      const modeLabel = await page.locator('.focus-mode-label').innerText()
      assert.match(modeLabel, /斩杀/)

      await answerCurrent(page, true)
      await exitPractice(page)
      await page.waitForSelector('.review-page')
      await page.locator('.review-page .tabs .tab').nth(2).click()
      await page.waitForSelector('.review-single .empty-title', { timeout: 8000 })
      assert.match(await page.locator('.review-single .empty-title').innerText(), /没有斩杀题目/)
      console.log('✓ Verified elimination review restores a killed question after a wrong answer.')
    })

    await t.test('8. Mock Exam: Setup, Answer Sheet, Submit and Report', async () => {
      await page.locator('.sidebar .nav-item').nth(3).click()
      await page.waitForSelector('.exam-center')
      await page.locator('.page-actions .btn-primary').click()
      const dialog = page.locator('.exam-setup-dialog')
      await dialog.waitFor({ state: 'visible', timeout: 5000 })
      const bankSelect = dialog.locator('select').first()
      const val = await bankSelect.locator('option', { hasText: 'E2E真实浏览器题库' }).first().getAttribute('value')
      await bankSelect.selectOption(val)
      const numbers = dialog.locator('input[type="number"]')
      await numbers.nth(0).fill('3')
      await numbers.nth(1).fill('30')
      await dialog.locator('button[type="submit"]').click()

      await page.waitForSelector('.exam-mode', { timeout: 12000 })
      assert.ok(await page.locator('[data-testid="exam-timer"]').isVisible())
      assert.equal(await page.locator('.exam-report').count(), 0, 'No report or answers before submission')

      await page.locator('.exam-option').nth(0).click()
      await page.locator('.answer-cell').nth(1).click()
      await page.locator('.exam-option').nth(1).click()
      await page.locator('[data-testid="exam-flag-toggle"]').click()
      assert.match(await page.locator('[data-testid="exam-answer-sheet"]').innerText(), /2\s*\/\s*3/)

      await page.locator('.exam-submit').click()
      await page.locator('[data-testid="exam-submit-confirm"]').waitFor({ state: 'visible', timeout: 5000 })
      await page.locator('[data-testid="exam-submit-confirm"] .btn-primary').click()
      await page.waitForSelector('.exam-report', { timeout: 12000 })
      assert.ok(await page.locator('.report-score').isVisible())
      assert.ok(await page.locator('.report-counts').isVisible())
      assert.ok(await page.locator('table.etable').first().isVisible(), 'Type statistics table must render')

      await page.locator('.report-actions .btn-primary').click()
      await page.waitForSelector('.exam-center', { timeout: 8000 })
      console.log('✓ Verified exam setup, answer sheet, submit confirmation and the tabular report.')
    })

    await t.test('9. Diagnosis and Plan Recommendations Launch Practice', async () => {
      await page.locator('.sidebar .nav-item').nth(2).click()
      await page.waitForSelector('.review-page')
      await page.locator('.review-page .tabs .tab').nth(3).click()
      await page.waitForSelector('.diagnosis', { timeout: 10000 })
      assert.ok(await page.locator('.diagnosis .review-stats .stat').count() >= 4)
      await page.waitForSelector('.diagnosis .panel', { timeout: 5000 })

      const recRows = page.locator('.diagnosis .panel').last().locator('.list-row')
      await recRows.first().waitFor({ state: 'visible', timeout: 8000 })
      await recRows.first().locator('.btn').click()
      await page.waitForSelector('.focus-mode', { timeout: 10000 })
      await page.waitForSelector('.q-stem')
      await exitPractice(page)
      await page.waitForSelector('.review-page', { timeout: 8000 })
      console.log('✓ Verified diagnosis statistics and direct practice launch from recommendations.')
    })

    await t.test('10. Spreadsheet Mapping, Import, Duplicate Strategy and Sparse Keys', async () => {
      await page.goto(`${BASE_URL}/#/import`)
      await page.waitForSelector('.import-page')

      const bankSelect = page.locator('#import-bank')
      await bankSelect.selectOption(bankId)
      const fileInput = page.locator('input[type="file"]')

      const manualCsvPath = path.join(tempDir, 'manual_unmapped.csv')
      fs.writeFileSync(
        manualCsvPath,
        'col_q,col_opt1,col_opt2,col_opt3,col_opt4,col_opt5,col_ans,col_exp\n' +
        '浏览器手工映射五选项题目,第一项,第二项,第三项,第四项,第五项,E,手工映射五选项详细解析\n',
        'utf8'
      )
      await fileInput.setInputFiles(manualCsvPath)
      await page.locator('.import-actions .btn-primary').click()
      await page.waitForSelector('.mapping-grid', { timeout: 8000 })
      assert.match(await page.locator('.notice.warn').innerText(), /还没有对应/)
      assert.ok(await page.locator('table.sample-table').isVisible())

      const mapField = label => page.locator('.mapping-grid label').filter({ hasText: label }).locator('select')
      await mapField('题干').selectOption('0')
      await mapField('答案').selectOption('6')
      await mapField('选项 A').selectOption('1')
      await mapField('选项 B').selectOption('2')
      await mapField('选项 C').selectOption('3')
      await mapField('选项 D').selectOption('4')
      await mapField('选项 E').selectOption('5')
      await mapField('解析').selectOption('7')

      await page.locator('.import-actions .btn-primary').click()
      await page.waitForSelector('.result-block', { timeout: 10000 })
      assert.match(await page.locator('.result-block').innerText(), /导入完成/)

      // Re-import the same content under a new filename: duplicate detection is content based.
      await page.locator('.result-block button:has-text("再导入一批")').click()
      await page.waitForSelector('.result-block', { state: 'detached', timeout: 5000 })
      await page.locator('#import-bank').selectOption(bankId)
      const duplicateCsvPath = path.join(tempDir, 'manual_unmapped_again.csv')
      fs.copyFileSync(manualCsvPath, duplicateCsvPath)
      await page.locator('input[type="file"]').setInputFiles(duplicateCsvPath)
      await page.locator('.import-actions .btn-primary:not([disabled])').click()
      await page.waitForSelector('.mapping-grid', { timeout: 8000 })
      await mapField('题干').selectOption('0')
      await mapField('答案').selectOption('6')
      await page.locator('.mapping-grid ~ .import-actions .btn-primary:not([disabled])').click()
      await page.waitForSelector('.dup-list', { timeout: 10000 })
      assert.match(await page.locator('.dup-list').innerText(), /浏览器手工映射五选项题目/)
      await page.locator('.step-block select').last().selectOption('merge')
      await page.locator('.step-block .import-actions .btn-primary').last().click()
      await page.waitForSelector('.result-block', { timeout: 10000 })

      // Sparse mapping keeps the original option keys B and E.
      await page.locator('.result-block button:has-text("再导入一批")').click()
      await page.waitForSelector('.result-block', { state: 'detached', timeout: 5000 })
      await page.locator('#import-bank').selectOption(bankId)
      const sparseCsvPath = path.join(tempDir, 'browser_sparse.csv')
      fs.writeFileSync(
        sparseCsvPath,
        'col_q,col_b,col_e,col_ans\n' +
        '浏览器稀疏B与E选项题目,选项B内容,选项E内容,E\n',
        'utf8'
      )
      await page.locator('input[type="file"]').setInputFiles(sparseCsvPath)
      await page.locator('.import-actions .btn-primary:not([disabled])').click()
      await page.waitForSelector('.mapping-grid', { timeout: 8000 })
      await mapField('题干').selectOption('0')
      await mapField('答案').selectOption('3')
      await mapField('选项 B').selectOption('1')
      await mapField('选项 E').selectOption('2')
      await page.locator('.mapping-grid ~ .import-actions .btn-primary:not([disabled])').click()
      await page.waitForSelector('.result-block', { timeout: 10000 })

      const bankQs = await (await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      const sparseQ = bankQs.find(q => q.stem === '浏览器稀疏B与E选项题目')
      assert.ok(sparseQ, 'Sparse question must exist')
      assert.deepEqual(sparseQ.options.map(o => o.key), ['B', 'E'])
      console.log('✓ Verified mapping preview, duplicate strategy and sparse option-key preservation.')
    })

    await t.test('11. Dual-Device Conflict, Offline Queue, Active Exam Lock and Version Retention', async () => {
      const bankQs = await (await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()

      await startBankPractice(page, BASE_URL, 'E2E真实浏览器题库')
      const deviceAStem = await currentStem(page)
      const targetQuestion = bankQs.find(q => q.stem === deviceAStem)
      assert.ok(targetQuestion, 'The first practice question must match a seeded API question')
      const targetQId = targetQuestion.id

      await page.locator('.opt').first().click()
      await page.locator('.focus-actionbar .btn-primary').click()
      await page.waitForSelector('.verdict-line')

      const contextB = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'zh-CN' })
      const pageB = await contextB.newPage()
      pageB.on('dialog', dialog => dialog.accept())
      await login(pageB, BASE_URL, 'e2e_student', 'password-123456')
      await startBankPractice(pageB, BASE_URL, 'E2E真实浏览器题库')

      await openQuestionEditor(page)
      await fillEditStem(page, 'A端在线协同更新题干')
      const saveResponse = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/questions/${targetQId}`) && response.request().method() === 'PUT')
      await page.locator('.edit-panel-actions .btn-primary').click()
      const savedResponse = await saveResponse
      assert.equal(savedResponse.status(), 200, 'Device A inline edit must be accepted')
      await page.waitForSelector('[data-testid="question-edit-panel"]', { state: 'detached', timeout: 5000 })
      await page.waitForTimeout(400)
      const qAfterA = await (await fetch(`${BASE_URL}/api/v1/questions/${targetQId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      assert.equal(qAfterA.version_number, 2)

      await contextB.setOffline(true)
      await openQuestionEditor(pageB)
      await fillEditStem(pageB, 'B端离线并发修改题干')
      await pageB.locator('.edit-panel-actions .btn-primary').click()
      await pageB.waitForSelector('[data-testid="offline-banner"]', { timeout: 5000 })
      const queued = await pageB.evaluate(() => {
        const user = JSON.parse(sessionStorage.getItem('easyexam_user') || localStorage.getItem('easyexam_user') || '{}')
        const key = `easyexam_offline_question_edits_${user.id || user.username}`
        return JSON.parse(localStorage.getItem(key) || '[]')
      })
      assert.equal(queued.length, 1)
      assert.equal(queued[0].payload.base_version_number, 1)
      assert.equal(queued[0].payload.stem, 'B端离线并发修改题干')

      await contextB.setOffline(false)
      await pageB.waitForSelector('[data-testid="conflict-banner"]', { timeout: 8000 })

      const conflictRes = await (await fetch(`${BASE_URL}/api/v1/questions/${targetQId}/conflict`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      assert.ok(conflictRes.has_conflict)
      assert.equal(conflictRes.conflict.base_version_number, 1)
      assert.equal(conflictRes.conflict.server_version_number, 2)
      assert.equal(conflictRes.conflict.client_version_number, 3)

      await pageB.waitForSelector('[data-testid="conflict-banner"]', { timeout: 8000 })
      await pageB.locator('.conflict-head .btn').click()
      await pageB.waitForSelector('[data-testid="conflict-list"]')
      assert.equal(await pageB.locator('.conflict-version').count(), 3)

      await exitPractice(page)
      await startBankPractice(page, BASE_URL, 'E2E真实浏览器题库')
      await page.waitForSelector('[data-testid="conflict-banner"]', { timeout: 8000 })
      await page.locator('.conflict-head .btn').click()
      await page.waitForSelector('[data-testid="conflict-list"]')
      await page.locator('.conflict-version').nth(1).locator('.btn').click()
      await page.waitForSelector('.conflict-resolved', { timeout: 8000 })
      assert.match(await page.locator('.conflict-resolved').innerText(), /v2/)

      const crossExamUser = 'e2e_cross_exam'
      const crossExamPassword = 'password-123456'
      const crossExamRegister = await fetch(`${BASE_URL}/api/v1/auth/register`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: crossExamUser, password: crossExamPassword }),
      })
      assert.equal(crossExamRegister.status, 201)
      const crossExamLogin = await fetch(`${BASE_URL}/api/v1/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: crossExamUser, password: crossExamPassword }),
      })
      const crossExamToken = (await crossExamLogin.json()).token
      const addExamMember = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ username: crossExamUser, role: 'MEMBER' }),
      })
      assert.equal(addExamMember.status, 201)
      const crossExamStart = await fetch(`${BASE_URL}/api/v1/practice/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${crossExamToken}` },
        body: JSON.stringify({ bank_id: bankId, mode: 'EXAM', total_questions: 1, question_ids: [targetQId] }),
      })
      const crossExamSession = await crossExamStart.json()
      assert.equal(crossExamStart.status, 201, JSON.stringify(crossExamSession))

      await openQuestionEditor(page)
      await fillEditStem(page, '受保护考试中的拒绝修改')
      const activeExamRejection = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/questions/${targetQId}`) && response.request().method() === 'PUT')
      await page.locator('.edit-panel-actions .btn-primary').click()
      assert.equal((await activeExamRejection).status(), 403)
      await page.waitForSelector('[data-testid="question-edit-error"]')
      assert.match(await page.locator('[data-testid="question-edit-error"]').innerText(), /存在活动模拟考试/)
      assert.equal(await page.locator('[data-testid="question-edit-panel"]').isVisible(), true)
      assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('easyexam_offline_question_edits') || '[]').length), 0)

      await page.locator('.edit-grid select').first().selectOption('MULTI')
      await page.locator('.edit-grid input').first().fill('A')
      await fillEditStem(page, '无效答案修改')
      const validationRejection = page.waitForResponse(response =>
        response.url().endsWith(`/api/v1/questions/${targetQId}`) && response.request().method() === 'PUT')
      await page.locator('.edit-panel-actions .btn-primary').click()
      assert.equal((await validationRejection).status(), 400)
      await page.waitForFunction(() => document.querySelector('[data-testid="question-edit-error"]')?.textContent.includes('至少包含两个不同的正确答案'))
      assert.equal(await page.locator('[data-testid="question-edit-panel"]').isVisible(), true)

      await page.locator('.edit-panel-actions .btn').first().click()
      await context.setOffline(true)
      await openQuestionEditor(page)
      await fillEditStem(page, '离线暂存后被考试保护拒绝')
      await page.locator('.edit-panel-actions .btn-primary').click()
      await page.waitForSelector('[data-testid="offline-banner"]')
      await context.setOffline(false)
      await page.waitForSelector('[data-testid="question-edit-error"]')
      const rejectedQueue = await page.evaluate(() => {
        const user = JSON.parse(sessionStorage.getItem('easyexam_user') || localStorage.getItem('easyexam_user') || '{}')
        const key = `easyexam_offline_question_edits_${user.id || user.username}`
        return JSON.parse(localStorage.getItem(key) || '[]')
      })
      assert.equal(rejectedQueue.length, 1)
      assert.equal(rejectedQueue[0].blocked, true)
      assert.match(await page.locator('[data-testid="offline-banner"]').innerText(), /存在活动模拟考试/)
      assert.equal(await page.locator('[data-testid="offline-banner"] .btn').count(), 0)

      const completeCrossExam = await fetch(`${BASE_URL}/api/v1/practice/sessions/${crossExamSession.id}/complete`, {
        method: 'POST', headers: { Authorization: `Bearer ${crossExamToken}` },
      })
      assert.equal(completeCrossExam.status, 200)

      const sqlCheck = execSync(
        `python -c "import sqlite3, json; conn=sqlite3.connect(r'${tempDbPath}'); ` +
        `cur=conn.cursor(); ` +
        `cur.execute('SELECT version_number, stem FROM question_versions WHERE question_id = ? ORDER BY version_number ASC', ('${targetQId}',)); ` +
        `vers=cur.fetchall(); ` +
        `cur.execute('SELECT is_resolved, base_version_number, server_version_number, client_version_number FROM question_conflicts WHERE question_id = ?', ('${targetQId}',)); ` +
        `confs=cur.fetchall(); ` +
        `cur.execute('SELECT COUNT(*) FROM answer_attempts WHERE question_id = ?', ('${targetQId}',)); ` +
        `attempts_count=cur.fetchone()[0]; ` +
        `print(json.dumps({'versions': vers, 'conflicts': confs, 'attempts': attempts_count})); conn.close()"`,
        { encoding: 'utf8' }
      )
      const sqlData = JSON.parse(sqlCheck.trim())
      assert.equal(sqlData.versions.length, 4)
      assert.equal(sqlData.versions[1][1], 'A端在线协同更新题干')
      assert.equal(sqlData.versions[2][1], 'B端离线并发修改题干')
      assert.equal(sqlData.versions[3][1], 'A端在线协同更新题干')
      assert.equal(sqlData.conflicts[0][0], 1)
      assert.ok(sqlData.attempts >= 1)

      await contextB.close()
      await exitPractice(page)
      await page.waitForSelector('.banks-page', { timeout: 8000 })
      console.log('✓ Verified conflict retention, offline queue, active-exam lock and four preserved versions.')
    })

    await t.test('12. Forced Password Change and Logout', async () => {
      await logout(page)

      await fetch(`${BASE_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'migrated_user', password: 'temp-pass-123456' }),
      })
      execSync(`python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); conn.execute('UPDATE users SET must_change_password = 1 WHERE username = \\\"migrated_user\\\"'); conn.commit(); conn.close()"`)

      await page.fill('#login-username', 'migrated_user')
      await page.fill('#login-password', 'temp-pass-123456')
      await page.click('.auth-submit')
      await page.waitForSelector('.force-pwd-card', { timeout: 8000 })

      await page.fill('#force-old', 'temp-pass-123456')
      await page.fill('#force-new', '123456')
      await page.fill('#force-confirm', '123456')
      await page.locator('.force-pwd-actions .btn-primary').click()
      await page.waitForSelector('.force-pwd-card .notice.bad', { timeout: 5000 })
      assert.match(await page.locator('.force-pwd-card .notice.bad').innerText(), /至少 8 个字符/)

      await page.fill('#force-new', 'NewPassSecure888')
      await page.fill('#force-confirm', 'NewPassSecure888')
      await page.locator('.force-pwd-actions .btn-primary').click()
      await page.waitForSelector('.shell', { timeout: 10000 })
      await page.goto(`${BASE_URL}/#/`)
      await page.waitForSelector('.today', { timeout: 10000 })
      assert.match(await page.locator('.byline').innerText(), /migrated_user/)

      await logout(page)
      assert.equal(await page.evaluate(() => localStorage.getItem('easyexam_token')), null)
      console.log('✓ Verified the blocking password-change screen, weak-password rejection and clean logout.')
    })

    await t.test('13. Bilingual and Theme Toggle Lifecycle', async () => {
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('lang')), 'zh-CN')

      await page.locator('.auth-toggles button').first().click()
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('lang')), 'en-US')
      assert.equal(await page.evaluate(() => localStorage.getItem('easyexam_locale')), 'en-US')
      assert.match(await page.locator('.auth-submit').innerText(), /Sign in/)

      await page.reload()
      await page.waitForSelector('.auth-layout')
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('lang')), 'en-US')

      await page.locator('.auth-toggles button').nth(1).click()
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('data-theme')), 'dark')

      await page.locator('.auth-toggles button').first().click()
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('lang')), 'zh-CN')
      await page.locator('.auth-toggles button').nth(1).click()
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('data-theme')), 'light')
      console.log('✓ Verified locale and theme persistence and restoration on the auth screen.')
    })

    await t.test('14. Editorial Appearance System and Real Contrast', async () => {
      await login(page, BASE_URL, 'e2e_student', 'password-123456')
      await page.goto(`${BASE_URL}/#/settings`)
      await page.waitForSelector('.settings-page')

      const themeSegments = page.locator('.settings-section .segmented .segment')
      await themeSegments.nth(1).click()
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('data-theme')), 'dark')

      const auditActive = async label => {
        const styles = await page.evaluate(() => {
          const opaque = el => {
            let node = el
            while (node) {
              const bg = getComputedStyle(node).backgroundColor
              if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg
              node = node.parentElement
            }
            return getComputedStyle(document.body).backgroundColor
          }
          return ['.settings-nav-item.is-active', '.segment.is-active', '.accent-option.is-active .accent-name']
            .map(selector => {
              const el = document.querySelector(selector)
              if (!el) return null
              return { selector, color: getComputedStyle(el).color, bg: opaque(el) }
            })
            .filter(Boolean)
        })
        assert.ok(styles.length >= 2, `${label}: active editorial controls must be rendered`)
        for (const style of styles) {
          const ratio = calcContrast(style.color, style.bg)
          assert.ok(ratio >= 4.5, `${label}: ${style.selector} contrast ${ratio.toFixed(2)}:1 must meet AA`)
        }
      }
      await auditActive('dark / pine')

      const accentOptions = page.locator('.accent-option')
      assert.ok(await accentOptions.count() >= 4, 'Editorial accent presets must be available')
      for (let i = 1; i < 4; i++) {
        await accentOptions.nth(i).click()
        await page.waitForTimeout(150)
        await auditActive(`dark accent ${i}`)
      }
      await accentOptions.first().click()

      await themeSegments.nth(0).click()
      assert.equal(await page.evaluate(() => document.documentElement.getAttribute('data-theme')), 'light')
      await auditActive('light / pine')

      await page.evaluate(() => localStorage.removeItem('easyexam_custom_accent'))
      console.log('✓ Verified editorial light/dark surfaces and accent contrast.')
    })

    await t.test('15. Responsive Layout and Mobile Exam Usability', async () => {
      const widths = [1440, 1024, 768, 390, 375, 320]
      for (const width of widths) {
        await page.setViewportSize({ width, height: width <= 390 ? 844 : 900 })
        await page.goto(`${BASE_URL}/#/`)
        await page.waitForSelector('.today', { timeout: 10000 })
        const layout = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
          titleWidth: document.querySelector('.masthead-title')?.getBoundingClientRect().width || 0,
          sidebar: getComputedStyle(document.querySelector('.sidebar')).display,
          bottomnav: getComputedStyle(document.querySelector('.bottomnav')).display,
        }))
        assert.ok(layout.scrollWidth <= layout.innerWidth + 1, `${width}px: page must not scroll horizontally (${layout.scrollWidth} > ${layout.innerWidth})`)
        assert.ok(layout.titleWidth > 0, `${width}px: page title must be laid out`)
        if (width >= 1024) {
          assert.notEqual(layout.sidebar, 'none', `${width}px: desktop sidebar must be visible`)
        } else {
          assert.notEqual(layout.bottomnav, 'none', `${width}px: mobile navigation must be visible`)
        }
      }
      console.log('✓ Verified 1440 / 1024 / 768 / 390 / 375 / 320 px without horizontal overflow.')

      await page.setViewportSize({ width: 390, height: 844 })
      await startExamFromCenter(page, BASE_URL, 'E2E真实浏览器题库', 2)
      await page.waitForSelector('.exam-option', { timeout: 10000 })
      assert.ok(await page.locator('.exam-sheet-trigger').isVisible(), 'Mobile exam must expose the answer-sheet trigger')
      const paperWidth = await page.locator('.exam-paper').evaluate(el => el.getBoundingClientRect().width)
      assert.ok(paperWidth <= 390, 'Exam paper must fit the mobile viewport')

      await page.locator('.exam-option').first().click()
      await page.locator('.exam-sheet-trigger').click()
      await page.waitForSelector('.exam-sheet-drawer', { timeout: 5000 })
      await page.locator('.exam-sheet-drawer .answer-cell').nth(1).click()
      await page.waitForSelector('.exam-sheet-drawer', { state: 'detached', timeout: 5000 })
      const progress = await page.locator('.exam-sheet-trigger').innerText()
      assert.match(progress, /1\s*\/\s*2/)

      await page.locator('.exam-submit').click()
      await page.locator('[data-testid="exam-submit-confirm"] .btn-primary').click()
      await page.waitForSelector('.exam-report', { timeout: 12000 })
      const reportOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      assert.ok(reportOverflow <= 1, 'Mobile exam report must not overflow horizontally')
      await page.locator('.report-actions .btn-primary').click()
      await page.waitForSelector('.exam-center', { timeout: 8000 })
      console.log('✓ Verified mobile mock-exam answer sheet, progress and report at 390px.')
    })
  } catch (error) {
    if (serverErrorOutput && /Traceback|Error/.test(serverErrorOutput)) {
      console.error('Backend stderr tail:\n' + serverErrorOutput.slice(-4000))
    }
    throw error
  } finally {
    if (browser) {
      await browser.close().catch(() => {})
    }
    if (serverProcess && serverProcess.pid) {
      console.log('Stopping FastAPI server...')
      try {
        execSync(`taskkill /pid ${serverProcess.pid} /T /F`, { stdio: 'ignore' })
      } catch (_) {
        serverProcess.kill('SIGKILL')
      }
    }
    if (tempDbPath && fs.existsSync(tempDbPath)) {
      try {
        fs.rmSync(path.dirname(tempDbPath), { recursive: true, force: true })
      } catch (_) {}
    }
  }
})
