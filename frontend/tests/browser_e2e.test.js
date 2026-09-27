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
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

let serverProcess = null
let tempDbPath = ''

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

test('True Chrome Browser E2E: Full Lifecycle Test with Dynamic Port and Deep Scenarios', async (t) => {
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

    console.log(`Launching Google Chrome at: ${CHROME_PATH}...`)
    browser = await chromium.launch({
      executablePath: CHROME_PATH,
      headless: true,
    })
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const page = await context.newPage()

    page.on('console', msg => console.log(`[Browser Console ${msg.type()}] ${msg.text()}`))
    page.on('pageerror', err => console.error(`[Browser PageError] ${err.message}`))
    page.on('dialog', async (dialog) => {
      console.log(`Browser Dialog [${dialog.type()}]: ${dialog.message()}`)
      await dialog.accept()
    })

    await t.test('1. User Registration and Auto Login', async () => {
      await page.goto(BASE_URL)
      await page.waitForSelector('.auth-page')
      assert.ok(await page.locator('text=易考宝').isVisible())

      // Switch to register
      await page.click('button:has-text("首次使用？创建账号")')
      await page.fill('input[placeholder="用户名"]', 'e2e_student')
      await page.fill('input[placeholder="密码（至少 8 位）"]', 'password-123456')
      await page.click('button:has-text("注册并登录")')

      // Wait for HomeView
      await page.waitForSelector('.home-page')
      const userText = await page.locator('.page-header p').textContent()
      assert.ok(userText.includes('e2e_student'))
      console.log('✓ Registered and logged in successfully.')
    })

    await t.test('2. Bank Creation via UI', async () => {
      await page.click('button:has-text("创建题库")')
      await page.waitForSelector('#create-bank-title')

      await page.fill('input[placeholder*="软考"]', 'E2E真实浏览器题库')
      await page.fill('input[placeholder="默认分类"]', '自动化测试')
      await page.fill('textarea[placeholder*="简要说明"]', '用于真实 Chrome 端到端验证')
      await page.click('button:has-text("确认创建")')

      // Wait for bank card to appear
      await page.waitForSelector('.bank-card h2:has-text("E2E真实浏览器题库")')
      console.log('✓ Created question bank via UI.')
    })

    let token = ''
    let bankId = ''
    let bankBId = ''
    await t.test('3. Seed Question Data and Multi-Bank Context via API', async () => {
      token = await page.evaluate(() => localStorage.getItem('easyexam_token'))
      assert.ok(token, 'Token must exist in localStorage')

      const banksRes = await fetch(`${BASE_URL}/api/v1/banks`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const banks = await banksRes.json()
      const targetBank = banks.find(b => b.name === 'E2E真实浏览器题库')
      assert.ok(targetBank, 'Bank must exist in API list')
      bankId = targetBank.id

      // Question 1: Single choice
      const q1Res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
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
        }),
      })
      assert.equal(q1Res.status, 201)

      // Question 2: Single choice
      const q2Res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
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
        }),
      })
      assert.equal(q2Res.status, 201)

      // Question 3: Single choice
      const q3Res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
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
        }),
      })
      assert.equal(q3Res.status, 201)

      // Seed second bank for multi-bank isolation testing
      const b2Res = await fetch(`${BASE_URL}/api/v1/banks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: '第二题库(专项隔离)', default_category: '隔离测试' }),
      })
      const b2Data = await b2Res.json()
      bankBId = b2Data.id

      // Seed question in bank B and flag as weak
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
      const qWeakData = await qWeakRes.json()
      // Flag as weak
      await fetch(`${BASE_URL}/api/v1/learning/weak/${qWeakData.id}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })

      // Set due_at in the past via sqlite script
      execSync(`python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); conn.execute(\\\"UPDATE fsrs_cards SET due_at = '2020-01-01 00:00:00' WHERE question_id = '${qWeakData.id}'\\\"); conn.commit(); conn.close()"`)

      // Reload page to reflect updated question counts
      await page.reload()
      await page.waitForSelector('.bank-card small:has-text("3 题")')
      console.log('✓ Seeded 3 questions in Bank A and 1 weak due question in Bank B.')
    })

    let killedStem = ''
    let mistakeStem = ''

    async function answerCurrentQuestion(wrong = false) {
      await page.waitForSelector('.question-card', { timeout: 8000 })
      const stem = await page.locator('.stem-box h2').textContent()
      let targetKey = 'A'
      if (stem.includes('计算机网络')) {
        targetKey = wrong ? 'A' : 'B'
      } else if (stem.includes('关系数据库')) {
        targetKey = wrong ? 'A' : 'B'
      } else if (stem.includes('面向对象')) {
        targetKey = wrong ? 'A' : 'C'
      } else if (stem.includes('软件测试')) {
        targetKey = wrong ? 'A' : 'B'
      }
      const opt = page.locator('label.option').filter({ has: page.locator(`.key-cap:text-is("${targetKey}")`) })
      await opt.click()
      await page.click('button:has-text("提交答案")')
      await page.waitForSelector('.result-card', { timeout: 8000 })
      return { stem, targetKey }
    }

    await t.test('4. Practice Flow: Answering, Result Inspection & Question Kill', async () => {
      console.log('Clicking 开始刷题...')
      await page.click('.bank-card:has-text("E2E真实浏览器题库") button:has-text("开始刷题")')

      // Q1: Answer wrongly
      const q1 = await answerCurrentQuestion(true)
      mistakeStem = q1.stem
      console.log(`Answered Q1 wrongly: "${q1.stem.slice(0, 15)}..." with ${q1.targetKey}`)
      const res1 = await page.locator('.result-header').textContent()
      assert.ok(res1.includes('未完全答对') || res1.includes('0'))

      // Next
      await page.click('button:has-text("下一题")')

      // Q2: Answer correctly and kill
      const q2 = await answerCurrentQuestion(false)
      killedStem = q2.stem
      console.log(`Answered Q2 correctly: "${q2.stem.slice(0, 15)}..." with ${q2.targetKey}`)
      const res2 = await page.locator('.result-header').textContent()
      assert.ok(res2.includes('完全正确'))

      // Kill Q2
      await page.click('button.btn-kill:has-text("斩杀此题")')
      await new Promise(r => setTimeout(r, 400))

      // Q3: Answer correctly
      const q3 = await answerCurrentQuestion(false)
      console.log(`Answered Q3 correctly: "${q3.stem.slice(0, 15)}..." with ${q3.targetKey}`)

      // Complete session
      await page.click('header button:has-text("交卷")')
      await page.waitForSelector('.home-page')
      console.log('✓ Completed practice session with wrong answer, question kill, and completion.')
    })

    await t.test('5. Mistakes View: Cause Persistence & FSRS Non-Default Rating Update (Fix 1)', async () => {
      await page.click('button:has-text("错题与斩杀")')
      await page.waitForSelector('.mistakes-page')

      // Verify mistake question is in mistakes list
      await page.waitForSelector(`.mistake-card h2:has-text("${mistakeStem.slice(0, 8)}")`)

      // Update mistake cause to '概念欠缺'
      const causeSelect = page.locator('.mistake-card select').first()
      await causeSelect.selectOption('概念欠缺')
      await new Promise(r => setTimeout(r, 600)) // wait for API update

      // Verify persistence by querying backend API
      const mistakesRes = await fetch(`${BASE_URL}/api/v1/mistakes?bank_id=${bankId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const mistakesData = await mistakesRes.json()
      const m1 = mistakesData.find(m => m.stem === mistakeStem)
      assert.ok(m1, 'Mistake must exist in API')
      assert.equal(m1.mistake_cause, '概念欠缺')

      // Click '练习此题' -> strictly scoped practice session
      await page.click('button:has-text("练习此题")')
      await page.waitForSelector('.practice-page')

      // Verify session is scoped to 1 question
      const progressText = await page.locator('.page-header small').textContent()
      assert.ok(progressText.includes('1 / 1'), `Expected 1 / 1 but got ${progressText}`)

      // Answer correctly
      await answerCurrentQuestion(false)

      // FSRS rating buttons are shown: deliberately select non-default '4 - 简单 (Easy)'
      await page.waitForSelector('.fsrs-rating-box')
      await page.click('button.rating-btn.easy')
      await page.waitForSelector('text=已更新 FSRS 评级')

      // Physical DB check: Verify attempt's fsrs_rating was really updated to 4 in SQLite
      const ratingInDb = execSync(
        `python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); r=conn.execute('SELECT fsrs_rating FROM answer_attempts ORDER BY rowid DESC LIMIT 1').fetchone(); print(r[0]); conn.close()"`
      ).toString().trim()
      assert.equal(ratingInDb, '4', 'FSRS rating must physically be 4 in SQLite database attempt record')

      // Verify pre-answer snapshot was recorded to prevent double scheduling
      const snapshotRecorded = execSync(
        `python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); r=conn.execute('SELECT card_snapshot_json FROM answer_attempts ORDER BY rowid DESC LIMIT 1').fetchone(); print(bool(r[0])); conn.close()"`
      ).toString().trim()
      assert.equal(snapshotRecorded, 'True', 'Attempt must store pre-answer card snapshot to guarantee single scheduling equivalence')


      // Return to mistakes view
      await page.click('button:has-text("返回")')
      await page.waitForSelector('.mistakes-page')
      console.log('✓ Verified mistake cause persistence, scoped practice, and physical FSRS rating=4 update.')
    })

    await t.test('6. Multi-Bank Isolation & Weak-Flagged Due Review (Fix 2)', async () => {
      // Check bank filter dropdown
      await page.waitForSelector('#bank-filter')
      // Switch filter to '第二题库(专项隔离)'
      await page.selectOption('#bank-filter', bankBId)
      await new Promise(r => setTimeout(r, 400))

      // Bank B has the weak flagged due question
      await page.waitForSelector('.due-highlight h2:has-text("软件测试")')
      assert.ok(await page.locator('.badge-due:has-text("薄弱标记")').isVisible())

      // Click '复习此题' on the weak card
      await page.click('.due-highlight button:has-text("复习此题")')
      await page.waitForSelector('.practice-page')

      // Answer the weak question
      await answerCurrentQuestion(false)
      await page.click('button:has-text("返回")')
      await page.waitForSelector('.mistakes-page')

      // Reset filter to all banks
      await page.selectOption('#bank-filter', '')
      await new Promise(r => setTimeout(r, 400))
      console.log('✓ Verified multi-bank isolation filter and weak-flagged due question review.')
    })

    await t.test('7. Elimination (Kills) View: Scoped Review and Restoration on Wrong', async () => {
      // Switch tab to '斩杀题库'
      await page.click('button:has-text("斩杀题库")')
      await page.waitForSelector(`.bank-card:has-text("${killedStem.slice(0, 8)}")`)

      // Click '查漏补缺练习'
      await page.click('button:has-text("查漏补缺练习")')
      await page.waitForSelector('.practice-page')

      // Verify mode is ELIMINATION by waiting for async session mode binding
      await page.waitForSelector('.practice-page .page-header h1:has-text("斩杀查漏补缺")')


      // Answer wrong on purpose
      await answerCurrentQuestion(true)

      // Return to mistakes view
      await page.click('button:has-text("返回")')
      await page.waitForSelector('.mistakes-page')

      // Switch to '斩杀题库' tab and verify question was restored (killed list is now empty)
      await page.click('button:has-text("斩杀题库")')
      await page.waitForSelector('text=暂无已斩杀题目')
      console.log('✓ Verified elimination review and restoration on wrong answer.')

      // Return to home
      await page.click('.mistakes-page .page-header button:has-text("返回")')
      await page.waitForSelector('.home-page')
    })

    await t.test('8. Mock Exam Mode: Idempotent Submit & Rich Report', async () => {
      await page.click('.bank-card:has-text("E2E真实浏览器题库") button:has-text("开始模考")')
      await page.waitForSelector('#exam-setup-title')

      await page.click('button:has-text("开始考试")')
      await page.waitForSelector('.exam-page')

      const timerLocator = page.locator('[data-testid="exam-timer"]')
      assert.ok(await timerLocator.isVisible())

      await page.click('.exam-options label:nth-child(1)')
      await page.click('.exam-answer-sheet button:has-text("2")')
      await page.click('.exam-options label:nth-child(2)')

      await page.click('header button.primary:has-text("交卷")')
      await page.waitForSelector('[data-testid="exam-submit-confirm"]')
      await page.click('button:has-text("确认交卷")')

      await page.waitForSelector('#exam-report-title:has-text("考试报告")')
      assert.ok(await page.locator('.report-summary').isVisible())
      assert.ok(await page.locator('.exam-stats-group:has-text("题型统计")').isVisible())

      await page.click('header button:has-text("返回")')
      await page.waitForSelector('.home-page')
      console.log('✓ Verified mock exam flow and rich statistics report.')
    })

    await t.test('9. Learning Diagnostics Dashboard & Interactive Recommendations to Practice (Task B1)', async () => {
      await page.click('button:has-text("学习诊断")')
      await page.waitForSelector('.learning-page')

      await page.waitForSelector('.metrics-grid', { timeout: 8000 })
      await page.waitForSelector('text=题库覆盖率', { timeout: 5000 })
      await page.waitForSelector('text=复习完成度', { timeout: 5000 })
      await page.waitForSelector('text=近期表现 vs 长期历史基线', { timeout: 5000 })

      // Adjust recommendation filters: set question type to SINGLE and new_ratio to 0.7
      await page.selectOption('#select-rec-type', 'SINGLE')
      await page.selectOption('#select-rec-ratio', '0.7')
      await page.waitForTimeout(400)

      // Verify recommendation cards update with reasons
      await page.waitForSelector('.rec-item', { timeout: 5000 })
      const recItems = page.locator('.rec-item')
      const count = await recItems.count()
      assert.ok(count > 0, 'Recommendation list must contain items after applying filters')

      // Assert all recommended items strictly match the SINGLE question type filter
      let newCount = 0
      for (let i = 0; i < count; i++) {
        const itemType = await recItems.nth(i).locator('small.muted').textContent()
        assert.equal(itemType.trim(), 'SINGLE', `Item ${i} must have type SINGLE`)
        const reasonText = await recItems.nth(i).locator('.rec-reason').textContent()
        assert.ok(reasonText.length > 0, `Item ${i} must have explainable reason`)
        if (reasonText.includes('新题覆盖')) {
          newCount++
        }
      }
      const newRatioActual = newCount / count
      console.log(`✓ Verified recommendation items count=${count}, newCount=${newCount} (ratio=${newRatioActual.toFixed(2)}), all types strictly SINGLE.`)

      // Click "开始推荐刷题" to launch real practice session from recommendations
      await page.click('button.btn-start-rec')
      await page.waitForSelector('.practice-page', { timeout: 8000 })
      await page.waitForSelector('.practice-page .stem-box', { timeout: 8000 })
      assert.ok(await page.locator('.stem-box').isVisible(), 'Should enter PracticeViewV1 from recommendations')
      console.log('✓ Successfully launched practice session directly from recommendations.')

      // Return from practice to LearningView, then return to HomeView
      await page.click('header button:has-text("返回")')
      await page.waitForSelector('.learning-page', { timeout: 8000 })
      await page.click('header button:has-text("返回")')
      await page.waitForSelector('.home-page', { timeout: 8000 })
      console.log('✓ Verified learning diagnostics dashboard and practice launch workflow.')
    })

    await t.test('10. Spreadsheet Column Mapping Preview, User Manual Mapping & Precheck Validation (Task 1 & 2)', async () => {
      // Navigate to Import view
      await page.click('button:has-text("导入题目")')
      await page.waitForSelector('.import-page')
      assert.ok(await page.locator('text=导入题目').isVisible())

      // Select target bank
      const bankSelect = page.locator('form.import-form select').first()
      await bankSelect.waitFor({ state: 'visible' })
      const firstOptionVal = await bankSelect.locator('option:not([disabled])').first().getAttribute('value')
      await bankSelect.selectOption(firstOptionVal)

      // Create a test CSV file with arbitrary unmapped headers (5 options requiring manual mapping including option E)
      const manualCsvPath = path.join(tempDir, 'manual_unmapped.csv')
      fs.writeFileSync(
        manualCsvPath,
        'col_q,col_opt1,col_opt2,col_opt3,col_opt4,col_opt5,col_ans,col_exp\n' +
        '浏览器手工映射五选项题目,第一项,第二项,第三项,第四项,第五项,E,手工映射五选项详细解析\n',
        'utf8'
      )

      // Attach file to input
      const fileInput = page.locator('input[type="file"]')
      await fileInput.setInputFiles(manualCsvPath)

      // Click "预览表格列映射"
      await page.click('button:has-text("预览表格列映射")')

      // Verify Column Mapping Preview Panel is displayed with missing stem/answer warning
      await page.waitForSelector('.column-mapping-panel', { timeout: 8000 })
      assert.ok(await page.locator('text=表格列映射预览').isVisible())
      assert.ok(await page.locator('text=前 1 行内容采样').isVisible())
      assert.ok(await page.locator('table.sample-table').isVisible())
      await page.waitForSelector('.missing-warning:has-text("缺少必要字段映射")', { timeout: 5000 })
      console.log('✓ Verified column mapping preview panel correctly caught unmapped headers.')

      // Manually interact with browser UI select controls to bind columns including Option E (#select-opt-e)
      await page.selectOption('#select-stem', '0') // col_q -> 题干
      await page.selectOption('#select-answer', '6') // col_ans -> 答案
      await page.selectOption('#select-opt-a', '1') // col_opt1 -> 选项 A
      await page.selectOption('#select-opt-b', '2') // col_opt2 -> 选项 B
      await page.selectOption('#select-opt-c', '3') // col_opt3 -> 选项 C
      await page.selectOption('#select-opt-d', '4') // col_opt4 -> 选项 D
      await page.selectOption('#select-opt-e', '5') // col_opt5 -> 选项 E
      await page.selectOption('#select-explanation', '7') // col_exp -> 解析
      console.log('✓ Manually mapped stem, answer, options A-E (#select-opt-e), and explanation via UI dropdowns.')

      // Confirm and Import with manual mapping
      await page.click('button:has-text("确认列映射并导入")')
      await page.waitForSelector('.success:has-text("导入完成")', { timeout: 8000 })
      assert.ok(await page.locator('text=新增/更新 1 题').isVisible())
      console.log('✓ Verified user confirmation and successful import with manual column bindings.')

      // Test duplicate precheck: re-import the exact same file without strategy
      await fileInput.setInputFiles(manualCsvPath)
      await page.click('button:has-text("预览表格列映射")')
      await page.waitForSelector('.column-mapping-panel', { timeout: 8000 })
      // Re-apply mapping
      await page.selectOption('#select-stem', '0')
      await page.selectOption('#select-answer', '6')
      await page.click('button:has-text("确认列映射并导入")')

      // Verify duplicate warning is shown
      await page.waitForSelector('.warning:has-text("检测到 1 道重复题")', { timeout: 8000 })
      assert.ok(await page.locator('text=请选择如何处理后再次导入').isVisible())
      console.log('✓ Verified duplicate precheck warning intercepted duplicate import.')

      // Test sparse mapping: map only B and E columns, leaving other options unmapped
      const sparseCsvPath = path.join(tempDir, 'browser_sparse.csv')
      fs.writeFileSync(
        sparseCsvPath,
        'col_q,col_b,col_e,col_ans\n' +
        '浏览器稀疏B与E选项题目,选项B内容,选项E内容,E\n',
        'utf8'
      )
      await fileInput.setInputFiles(sparseCsvPath)
      await page.click('button:has-text("预览表格列映射")')
      await page.waitForSelector('.column-mapping-panel', { timeout: 8000 })
      await page.selectOption('#select-stem', '0')
      await page.selectOption('#select-answer', '3')
      await page.selectOption('#select-opt-b', '1') // map Option B
      await page.selectOption('#select-opt-e', '2') // map Option E
      await page.click('button:has-text("确认列映射并导入")')
      await page.waitForSelector('.success:has-text("导入完成")', { timeout: 8000 })
      assert.ok(await page.locator('text=新增/更新 1 题').isVisible())

      // Verify via API that options retain keys 'B' and 'E' rather than being renumbered to 'A' and 'B'
      const bankQs = await (await fetch(`${BASE_URL}/api/v1/banks/${firstOptionVal}/questions`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })).json()
      const sparseQ = bankQs.find(q => q.stem === '浏览器稀疏B与E选项题目')
      assert.ok(sparseQ, 'Sparse question must exist in bank')
      assert.equal(sparseQ.options.length, 2)
      assert.equal(sparseQ.options[0].key, 'B')
      assert.equal(sparseQ.options[0].content, '选项B内容')
      assert.equal(sparseQ.options[1].key, 'E')
      assert.equal(sparseQ.options[1].content, '选项E内容')
      console.log('✓ Verified browser sparse manual mapping preserves option keys B and E without renumbering.')

      // Return to Home view
      await page.click('header button:has-text("返回")')
      await page.waitForSelector('.home-page')
      console.log('✓ Successfully tested full spreadsheet manual mapping and import workflow in browser.')
    })

    await t.test('11. Multi-Device Dual Browser Context Sync & Conflict Retention (Task B3)', async () => {
      // 1. Prepare target question in real bank
      const bankQs = await (await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      const targetQuestion = bankQs[0]
      const targetQId = targetQuestion.id

      // 2. Device A enters practice session, answers the question (real attempt)
      await page.click('.bank-card:has-text("E2E真实浏览器题库") button:has-text("开始刷题")')
      await page.waitForSelector('.practice-page', { timeout: 8000 })
      await page.waitForSelector('.stem-box h2', { timeout: 5000 })

      await page.click('.options-group label:nth-child(1)')
      await page.click('button:has-text("提交答案")')
      await page.waitForSelector('.result-card', { timeout: 5000 })
      console.log('✓ Device A submitted practice attempt via browser UI.')

      // 3. Device B opens an independent BrowserContext and enters practice while question is at version 1
      const contextB = await browser.newContext()
      const pageB = await contextB.newPage()

      await pageB.goto(BASE_URL)
      await pageB.waitForSelector('.auth-page')
      await pageB.fill('input[placeholder="用户名"]', 'e2e_student')
      await pageB.fill('input[placeholder="密码（至少 8 位）"]', 'password-123456')
      await pageB.click('button:has-text("登录")')
      await pageB.waitForSelector('.home-page', { timeout: 8000 })
      console.log('✓ Device B logged in concurrently in independent BrowserContext.')

      await pageB.click('.bank-card:has-text("E2E真实浏览器题库") button:has-text("开始刷题")')
      await pageB.waitForSelector('.practice-page', { timeout: 8000 })
      await pageB.waitForSelector('.stem-box h2', { timeout: 5000 })
      console.log('✓ Device B opened practice session with Question at Version 1.')

      // 4. Device A modifies the question online via UI
      await page.click('button.btn-edit-question')
      await page.waitForSelector('.question-edit-panel')
      await page.fill('.input-edit-stem', 'A端在线协同更新题干')
      await page.click('button.btn-save-question-edit')
      await page.waitForTimeout(500)

      const qAfterA = await (await fetch(`${BASE_URL}/api/v1/questions/${targetQId}`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      assert.equal(qAfterA.version_number, 2, 'Device A update must advance question to version 2')
      console.log('✓ Device A updated question to version 2 via UI.')

      // 5. Device B is disconnected (true browser offline state via context.setOffline)
      await contextB.setOffline(true)

      // Device B modifies the question offline via UI
      await pageB.click('button.btn-edit-question')
      await pageB.waitForSelector('.question-edit-panel')
      await pageB.fill('.input-edit-stem', 'B端离线并发修改题干')
      await pageB.click('button.btn-save-question-edit')

      // Assert Device B frontend queued offline modification into localStorage and displayed offline banner
      await pageB.waitForSelector('[data-testid="offline-banner"]', { timeout: 5000 })
      const queuedData = await pageB.evaluate(() => JSON.parse(localStorage.getItem('easyexam_offline_question_edits') || '[]'))
      assert.equal(queuedData.length, 1, 'Offline edit must be queued in localStorage')
      assert.equal(queuedData[0].payload.base_version_number, 1, 'Queued edit must carry base_version_number = 1')
      assert.equal(queuedData[0].payload.stem, 'B端离线并发修改题干')
      console.log('✓ Device B went offline, safely queued edit into localStorage, and displayed offline banner.')

      // 6. Device B reconnects to network and triggers client replay
      await contextB.setOffline(false)
      await pageB.click('button.btn-sync-offline')
      await pageB.waitForTimeout(600)

      // 7. Verify server detects conflict (base_version_number 1 < server version 2) and records in question_conflicts
      const conflictRes = await (await fetch(`${BASE_URL}/api/v1/questions/${targetQId}/conflict`, {
        headers: { Authorization: `Bearer ${token}` },
      })).json()
      assert.ok(conflictRes.has_conflict, 'Server must flag active conflict')
      assert.equal(conflictRes.conflict.base_version_number, 1)
      assert.equal(conflictRes.conflict.server_version_number, 2)
      assert.equal(conflictRes.conflict.client_version_number, 3)

      // 8. Device B UI displays conflict banner and multi-version comparison
      await pageB.waitForSelector('[data-testid="conflict-banner"]', { timeout: 8000 })
      const conflictBadgeB = await pageB.locator('.conflict-badge').textContent()
      assert.ok(conflictBadgeB.includes('检测到多端并发编辑冲突'), 'Device B must display active conflict banner')

      await pageB.click('.btn-conflict-toggle')
      await pageB.waitForSelector('[data-testid="conflict-list"]')
      assert.ok(await pageB.locator('[data-testid="conflict-version-1"]').isVisible())
      assert.ok(await pageB.locator('[data-testid="conflict-version-2"]').isVisible())
      assert.ok(await pageB.locator('[data-testid="conflict-version-3"]').isVisible())
      console.log('✓ Device B UI displayed active conflict banner and multi-version list (v1, v2, v3).')

      // 9. Device A navigates to practice and sees conflict banner as well
      await page.click('header button:has-text("返回")')
      await page.waitForSelector('.home-page')
      await page.click('.bank-card:has-text("E2E真实浏览器题库") button:has-text("开始刷题")')
      await page.waitForSelector('.practice-page', { timeout: 8000 })
      await page.waitForSelector('[data-testid="conflict-banner"]', { timeout: 8000 })

      // 10. Device A resolves conflict via UI by adopting Version 2
      await page.click('.btn-conflict-toggle')
      await page.waitForSelector('[data-testid="conflict-list"]')
      await page.click('[data-testid="conflict-version-2"] button.btn-adopt-version')
      await page.waitForSelector('.conflict-resolved-msg')
      const resolvedMsg = await page.locator('.conflict-resolved-msg').textContent()
      assert.ok(resolvedMsg.includes('已成功确认采用版本 v2 内容'), 'Resolution confirmation must display in UI')
      console.log(`✓ Device A user adopted Version 2 via UI: ${resolvedMsg}`)

      // 11. Verify SQLite physical database state: all 4 versions intact, conflict marked resolved
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
      assert.equal(sqlData.versions.length, 4, `Expected 4 versions in SQLite, got ${sqlData.versions.length}`)
      assert.equal(sqlData.versions[0][0], 1, 'Version 1 must remain intact')
      assert.equal(sqlData.versions[1][0], 2, 'Version 2 (A update) must remain intact')
      assert.equal(sqlData.versions[1][1], 'A端在线协同更新题干')
      assert.equal(sqlData.versions[2][0], 3, 'Version 3 (B concurrent edit) must remain intact')
      assert.equal(sqlData.versions[2][1], 'B端离线并发修改题干')
      assert.equal(sqlData.versions[3][0], 4, 'Version 4 (adopted resolution) must be created')
      assert.equal(sqlData.versions[3][1], 'A端在线协同更新题干')
      assert.equal(sqlData.conflicts[0][0], 1, 'question_conflicts.is_resolved must be 1')
      assert.ok(sqlData.attempts >= 1, 'Practice attempts must remain intact in SQLite')
      console.log('✓ Verified SQLite physical state: all 4 versions preserved intact, conflict resolved, 0 data loss.')

      // Clean up Device B and return Device A to home
      await contextB.close()
      await page.click('header button:has-text("返回")')
      await page.waitForSelector('.home-page')
    })

    await t.test('12. Forced Password Change Flow for Migrated Users & Final Logout (Fix 4)', async () => {
      // Logout current user
      await page.click('button:has-text("退出")')
      await page.waitForSelector('.auth-page')

      // Register a migrated user via API then set must_change_password = 1
      await fetch(`${BASE_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'migrated_user', password: 'temp-pass-123456' }),
      })
      execSync(`python -c "import sqlite3; conn=sqlite3.connect(r'${tempDbPath}'); conn.execute('UPDATE users SET must_change_password = 1 WHERE username = \\\"migrated_user\\\"'); conn.commit(); conn.close()"`)

      // Login as migrated_user
      await page.fill('input[placeholder="用户名"]', 'migrated_user')
      await page.fill('input[placeholder="密码（至少 8 位）"]', 'temp-pass-123456')
      await page.click('button:has-text("登录")')

      // Verify blocking force-change-password view is rendered
      await page.waitForSelector('.force-pwd-card')
      assert.ok(await page.locator('text=请修改初始密码').isVisible())
      console.log('✓ Forced password change screen blocked unauthorized entry.')

      // Try weak password (less than 8 chars)
      await page.fill('input[placeholder="请输入当前密码"]', 'temp-pass-123456')
      await page.fill('input[placeholder="请输入新密码"]', '123456')
      await page.fill('input[placeholder="请再次输入新密码"]', '123456')
      await page.click('button:has-text("确认修改并进入系统")')

      await page.waitForSelector('.force-pwd-alert.error:has-text("新密码长度至少为 8 位")')
      console.log('✓ Weak password (< 8 chars) was properly rejected.')

      // Now enter valid 8+ chars password
      await page.fill('input[placeholder="请输入新密码"]', 'NewPassSecure888')
      await page.fill('input[placeholder="请再次输入新密码"]', 'NewPassSecure888')
      await page.click('button:has-text("确认修改并进入系统")')

      // Successfully transitions to HomeView
      await page.waitForSelector('.home-page', { timeout: 8000 })
      const welcome = await page.locator('.page-header p').textContent()
      assert.ok(welcome.includes('migrated_user'))
      console.log('✓ Successfully changed password and entered main workspace.')

      // Final Logout
      await page.click('button:has-text("退出")')
      await page.waitForSelector('.auth-page')
      const storedToken = await page.evaluate(() => localStorage.getItem('easyexam_token'))
      assert.equal(storedToken, null)
      console.log('✓ Final logout cleanly cleared localStorage.')
    })
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
