import { spawn } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import net from 'node:net'
import crypto from 'node:crypto'
import assert from 'node:assert'
import { chromium } from 'playwright'

const repoRoot = path.resolve(process.cwd())
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

async function getFreePort() {
  return new Promise((resolve) => {
    const srv = net.createServer()
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port
      srv.close(() => resolve(port))
    })
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
          throw new Error('Token mismatch')
        }
        return true
      }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 300))
  }
  throw new Error(`Server at ${url} failed to start`)
}

async function run() {
  console.log('Starting Mobile Interaction E2E Verification...')
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fnexam-mobile-suite-'))
  const tempDbPath = path.join(tempDir, 'mobile_test.db')
  const port = await getFreePort()
  const BASE_URL = `http://127.0.0.1:${port}`

  console.log(`Starting FastAPI on port ${port}...`)
  const instanceToken = crypto.randomUUID()
  const server = spawn(
    'python',
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        DB_PATH: tempDbPath,
        INSTANCE_TOKEN: instanceToken,
        EASYEXAM_SECRET_KEY: 'mobile-secret-key-32bytes-ci!!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  server.stderr.on('data', d => {
    const text = d.toString()
    if (!text.includes('GET /') && !text.includes('POST /')) {
      console.error('[Server Error]', text)
    }
  })

  await waitForServer(BASE_URL, instanceToken)
  console.log('Server ready. Launching mobile viewport in Playwright...')

  const browser = await chromium.launch({
    headless: true,
    executablePath: fs.existsSync(CHROME_PATH) ? CHROME_PATH : undefined,
  })

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    hasTouch: true,
    isMobile: true,
  })

  const page = await context.newPage()

  try {
    // 1. Visit Login
    await page.goto(BASE_URL)
    await page.waitForSelector('.auth-page')

    // Register user
    await page.click('button:has-text("首次使用？创建账号")')
    await page.fill('input[placeholder="用户名"]', 'mobile_suite_tester')
    await page.fill('input[placeholder="密码（至少 8 位）"]', 'REDACTED_TEST_PASSWORD')
    await page.click('button:has-text("注册并登录")')
    await page.waitForSelector('.home-page')

    // Verify localStorage has easyexam_token AND easyexam_user (Login persistence fix)
    const storedUser = await page.evaluate(() => localStorage.getItem('easyexam_user'))
    console.log('[Check 1] easyexam_user in localStorage:', storedUser ? 'YES' : 'NO')
    assert(storedUser !== null, 'easyexam_user must be persisted in localStorage')

    // Create Bank and Seed Questions
    const token = await page.evaluate(() => localStorage.getItem('easyexam_token'))
    const createBankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: '系统集成项目管理真题',
        category: '软考',
        description: '系统集成历年真题精选'
      })
    })
    const bank = await createBankRes.json()

    // Import questions
    const mdContent = fs.readFileSync(path.join(repoRoot, 'data', 'ruankao_system_integration_142.md'), 'utf-8')
    await fetch(`${BASE_URL}/api/v1/imports/banks/${bank.id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        format: 'markdown',
        content: mdContent.slice(0, 10000),
        duplicate_strategy: 'merge'
      })
    })

    // Reload home page and enter practice
    await page.reload()
    await page.waitForSelector('.bank-card')
    await page.click('button:has-text("开始刷题")')
    await page.waitForSelector('.question-card')
    console.log('[Check 2] Question card loaded')

    // Click option A and Submit
    await page.click('.option:first-child')
    await page.waitForTimeout(200)
    await page.click('button:has-text("提交答案")')
    await page.waitForTimeout(600)

    // Verify submit verdict text: should NEVER be "未完全答对" for single choice
    const verdictBanner = await page.textContent('.verdict-status-title')
    console.log('[Check 3] Single choice verdict text:', verdictBanner.trim())
    assert(!verdictBanner.includes('未完全答对'), 'Single choice must never show 未完全答对')
    assert(verdictBanner.includes('回答正确') || verdictBanner.includes('回答错误'), 'Verdict should be either 回答正确 or 回答错误')

    // Click Next button to go to Q2
    await page.click('.btn-next-question')
    await page.waitForTimeout(400)

    const q2Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 4] Progress after next:', q2Progress.trim())
    assert(q2Progress.includes('2/'), 'Should have navigated to Q2')

    // Test: Q2 is UNANSWERED. Can we still click "Next" to skip to Q3?
    await page.click('.btn-next-question')
    await page.waitForTimeout(400)

    const q3Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 5] Skip unanswered question to Q3:', q3Progress.trim())
    assert(q3Progress.includes('3/'), 'Should have skipped to Q3 without answering Q2')

    // Test: Go back to Q1 (prev -> prev)
    await page.click('.btn-prev-question')
    await page.waitForTimeout(300)
    await page.click('.btn-prev-question')
    await page.waitForTimeout(400)

    const backToQ1Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 6] Back to Q1:', backToQ1Progress.trim())
    assert(backToQ1Progress.includes('1/'), 'Should be back at Q1')

    // Check if Q1 answer and result are STILL PRESERVED (Fix: Previous button cleared answer)
    const q1PreservedVerdict = await page.textContent('.verdict-status-title')
    console.log('[Check 7] Q1 preserved verdict after navigating back:', q1PreservedVerdict.trim())
    assert(q1PreservedVerdict && (q1PreservedVerdict.includes('回答正确') || q1PreservedVerdict.includes('回答错误')), 'Q1 answer/result must NOT be reset when going back!')

    // Test: Question Palette (答题卡)
    // Click progress badge to open palette
    await page.click('.btn-sheet-trigger-pill')
    await page.waitForSelector('.sheet-modal-drawer')

    const isDrawerOpen = await page.isVisible('.sheet-modal-drawer')
    console.log('[Check 8] Question palette drawer opened:', isDrawerOpen)
    assert(isDrawerOpen, 'Question palette drawer should be open')

    // Check palette item 1 state: should have class 'incorrect' or 'correct'
    const q1PaletteClass = await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.sheet-num-btn'))
      return items[0]?.className
    })
    console.log('[Check 9] Palette item 1 class:', q1PaletteClass)
    assert(q1PaletteClass.includes('correct') || q1PaletteClass.includes('incorrect'), 'Q1 in palette should be marked answered (correct/incorrect)')

    // Jump to Question 10 from palette
    await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.sheet-num-btn'))
      items[9].click()
    })
    await page.waitForTimeout(400)

    const q10Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 10] Jumped to Q10 from palette:', q10Progress.trim())
    assert(q10Progress.includes('10/'), 'Should jump to Q10')

    // Test: Swipe gesture (Swipe left to go to Q11)
    await page.evaluate(() => {
      const container = document.querySelector('.practice-page') || document.body
      const touchStart = new Touch({
        identifier: Date.now(),
        target: container,
        clientX: 300,
        clientY: 300
      })
      const touchEnd = new Touch({
        identifier: Date.now(),
        target: container,
        clientX: 100,
        clientY: 300
      })
      container.dispatchEvent(new TouchEvent('touchstart', { touches: [touchStart], changedTouches: [touchStart], bubbles: true }))
      container.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [touchEnd], bubbles: true }))
    })
    await page.waitForTimeout(600)

    const q11Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 11] Navigated to Q11 via Swipe Left:', q11Progress.trim())
    assert(q11Progress.includes('11/'), 'Should have swiped to Q11')

    console.log('\n=============================================')
    console.log(' ALL 11 MOBILE INTERACTION CHECKS PASSED! ')
    console.log('=============================================\n')

  } finally {
    await browser.close()
    server.kill()
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
}

run().catch(err => {
  console.error('Test Failed:', err)
  process.exit(1)
})
