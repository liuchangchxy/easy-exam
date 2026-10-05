import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import net from 'node:net'
import crypto from 'node:crypto'
import assert from 'node:assert'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')
const FIXTURE_PATH = path.resolve(__dirname, 'fixtures/mobile_interaction_questions.md')
const SCREENSHOT_DIR = path.resolve(repoRoot, 'screenshots/mobile')
const ARTIFACT_DIR = path.resolve(repoRoot, 'screenshots/mobile')

function getFreePort() {
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

// The progress pill renders as "N / M 📑 答题卡" (spaces around the slash, see
// PracticeViewV1.vue `.btn-sheet-trigger-pill`). Assert on the numbers rather than a
// literal substring so this tracks the DOM instead of a hand-copied format string.
const PROGRESS_RE = /(?:^|\D)(\d+)\s*\/\s*(\d+)/

function assertProgress(text, expectedN, label) {
  const raw = (text || '').trim()
  const m = PROGRESS_RE.exec(raw)
  assert(m, `${label}: pill did not contain an "N / M" progress value, read "${raw}"`)
  assert.strictEqual(
    Number(m[1]),
    expectedN,
    `${label}: expected progress "${expectedN} / M" but pill read "${raw}"`
  )
}

// The action bar swaps its primary slot by state (see PracticeViewV1.vue):
//   answered  -> .btn-next-question  ("下一题 →")
//   unanswered -> .btn-skip-unanswered ("跳过 →")
// Both call next(). Tests must click whichever is actually present for the state
// under test, instead of assuming "下一题" always exists.
async function advance(page) {
  const nextBtn = page.locator('.btn-next-question')
  if (await nextBtn.count() && await nextBtn.isVisible()) {
    await nextBtn.click()
    return 'next'
  }
  const skipBtn = page.locator('.btn-skip-unanswered')
  if (await skipBtn.count() && await skipBtn.isVisible()) {
    await skipBtn.click()
    return 'skip'
  }
  throw new Error('no forward control (.btn-next-question / .btn-skip-unanswered) is visible')
}

async function goBack(page) {
  await page.locator('.btn-prev-question').click()
}

async function run() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fnexam-mobile-check-'))
  const tempDbPath = path.join(tempDir, 'mobile_check.db')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const BASE_URL = `http://127.0.0.1:${port}`

  console.log(`Starting FastAPI on port ${port}...`)
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
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )
  server.stderr.on('data', (d) => {
    const text = d.toString()
    if (!text.includes('INFO:')) process.stderr.write(`[Server Error] ${text}`)
  })

  let browser = null
  try {
    await waitForServer(BASE_URL, instanceToken)
    console.log('Server ready. Launching mobile viewport in Playwright...')
    browser = await chromium.launch({
      headless: true,
    })
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    })
    const page = await context.newPage()

    // --- Register through the real UI (not the API: this is the user path) ---
    await page.goto(BASE_URL)
    await page.click('button:has-text("首次使用？创建账号")')
    await page.fill('input[placeholder="用户名"]', `mobile_suite_${Date.now()}`)
    await page.fill('input[placeholder="密码（至少 8 位）"]', 'password-123456')
    await page.click('button:has-text("注册并登录")')
    await page.waitForSelector('.home-page')

    // Check 1: login persisted for offline/token reuse
    const cached = await page.evaluate(() => localStorage.getItem('easyexam_user'))
    console.log('[Check 1] easyexam_user in localStorage:', cached ? 'YES' : 'NO')
    assert(cached !== null, 'easyexam_user must be persisted in localStorage')

    const token = await page.evaluate(() => localStorage.getItem('easyexam_token'))
    const createBankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: '移动端校验题库', description: 'mobile suite' }),
    })
    const bank = await createBankRes.json()

    const mdContent = fs.readFileSync(FIXTURE_PATH, 'utf-8')
    const importRes = await fetch(`${BASE_URL}/api/v1/imports/banks/${bank.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ format: 'markdown', content: mdContent, duplicate_strategy: 'merge' }),
    })
    assert(importRes.ok, `Failed to import fixture questions: ${importRes.status}`)

    await page.reload()
    await page.waitForSelector('.bank-card')
    await page.click('button:has-text("开始刷题")')
    await page.waitForSelector('.question-card')
    console.log('[Check 2] Question card loaded')

    await page.click('.option:first-child')
    await page.waitForTimeout(200)
    await page.click('button:has-text("提交答案")')
    await page.waitForTimeout(600)

    // Check 3: single-choice verdict wording
    const verdictBanner = await page.textContent('.verdict-status-title')
    console.log('[Check 3] Single choice verdict text:', verdictBanner.trim())
    assert(!verdictBanner.includes('未完全答对'), 'Single choice must never show 未完全答对')
    assert(
      verdictBanner.includes('回答正确') || verdictBanner.includes('回答错误'),
      'Verdict should be either 回答正确 or 回答错误'
    )

    await advance(page)
    await page.waitForTimeout(400)
    const q2Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 4] Progress after next:', q2Progress.trim())
    assertProgress(q2Progress, 2, 'Should have navigated to Q2')

    // Check 5: skipping an unanswered question must be allowed (non-blocking navigation)
    await advance(page)
    await page.waitForTimeout(400)
    const q3Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 5] Skip unanswered question to Q3:', q3Progress.trim())
    assertProgress(q3Progress, 3, 'Should have skipped to Q3 without answering Q2')

    // Check 6: navigate back to Q1
    await goBack(page)
    await page.waitForTimeout(300)
    await goBack(page)
    await page.waitForTimeout(400)
    const backToQ1Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 6] Back to Q1:', backToQ1Progress.trim())
    assertProgress(backToQ1Progress, 1, 'Should be back at Q1')

    // Check 7: going back must not clear the earlier answer/verdict
    const q1PreservedVerdict = await page.textContent('.verdict-status-title')
    console.log('[Check 7] Q1 preserved verdict after navigating back:', q1PreservedVerdict.trim())
    assert(
      q1PreservedVerdict &&
        (q1PreservedVerdict.includes('回答正确') || q1PreservedVerdict.includes('回答错误')),
      'Q1 answer/result must NOT be reset when going back!'
    )

    // Check 8: question palette drawer
    await page.click('.btn-sheet-trigger-pill')
    await page.waitForSelector('.sheet-modal-drawer')
    const isDrawerOpen = await page.isVisible('.sheet-modal-drawer')
    console.log('[Check 8] Question palette drawer opened:', isDrawerOpen)
    assert(isDrawerOpen, 'Question palette drawer should be open')

    const q1PaletteClass = await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.sheet-num-btn'))
      return items[0]?.className || ''
    })
    console.log('[Check 9] Q1 palette class:', q1PaletteClass)
    assert(
      q1PaletteClass.includes('correct') || q1PaletteClass.includes('incorrect'),
      'Q1 in palette should be marked answered (correct/incorrect)'
    )

    // Check 10: jump to Q10 via the palette
    const jumpTarget = await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.sheet-num-btn'))
      const t = items.find((el) => el.textContent.trim() === '10')
      if (t) t.click()
      return Boolean(t)
    })
    assert(jumpTarget, 'palette should expose a Q10 button')
    await page.waitForTimeout(500)
    const q10Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 10] Jumped to Q10:', q10Progress.trim())
    assertProgress(q10Progress, 10, 'Should jump to Q10')

    // Check 11: horizontal swipe advances one question.
    // The handler reads e.touches / e.changedTouches (PracticeViewV1.vue
    // handleTouchStart/handleTouchEnd), so a mouse drag never reaches it — real
    // touch events must be dispatched via CDP Input.dispatchTouchEvent.
    const box = await page.locator('.practice-page').boundingBox()
    const cy = box.y + box.height / 2
    const cdp = await context.newCDPSession(page)
    // Start beyond the 25px iOS-back edge guard (isSwipeGestureValid).
    const startX = box.x + box.width - 40
    const endX = box.x + 40
    await cdp.send('Input.dispatchTouchEvent', {
      type: 'touchStart',
      touchPoints: [{ x: startX, y: cy }],
    })
    for (let i = 1; i <= 8; i++) {
      const x = startX + ((endX - startX) * i) / 8
      await cdp.send('Input.dispatchTouchEvent', {
        type: 'touchMove',
        touchPoints: [{ x, y: cy }],
      })
    }
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await page.waitForTimeout(800)
    const q11Progress = await page.textContent('.btn-sheet-trigger-pill')
    console.log('[Check 11] After swipe:', q11Progress.trim())
    assertProgress(q11Progress, 11, 'Should have swiped to Q11')

    console.log('\nAll mobile interaction checks passed.')
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'mobile_suite_final.png') })
  } finally {
    if (browser) await browser.close()
    server.kill()
  }
}

run().catch((err) => {
  console.error('Test Failed:', err)
  process.exit(1)
})
