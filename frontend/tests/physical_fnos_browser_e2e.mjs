import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { chromium } from 'playwright'

// Physical browser acceptance run against a deployed fnOS instance.
//   FNOS_BASE_URL=http://<NAS_IP>:3000 FNOS_E2E_EXPECTED_SHA=<revision> \
//     node frontend/tests/physical_fnos_browser_e2e.mjs
//
// FNOS_BASE_URL is required: this script must never silently point at localhost
// or at someone else's NAS. FNOS_E2E_EXPECTED_SHA is required and must equal the
// commit_sha the instance reports, so the run is attributable to one revision.
// Set CHROME_PATH only to use a specific Chrome build; otherwise Playwright's
// bundled Chromium is used.
const BASE_URL = (process.env.FNOS_BASE_URL || '').trim().replace(/\/+$/, '')
const CHROME_PATH = (process.env.CHROME_PATH || '').trim()
const PASSWORD = process.env.FNOS_E2E_PASSWORD || `Fn0sE2E!${Date.now()}`

// The revision the deployed instance is expected to run. A run whose target
// revision is unverified cannot serve as acceptance evidence for a specific
// build, so the instance's reported commit_sha must equal this value.
const EXPECTED_SHA = (process.env.FNOS_E2E_EXPECTED_SHA || '').trim().toLowerCase()

async function assertRunningRevision() {
  if (!EXPECTED_SHA) {
    throw new Error('FNOS_E2E_EXPECTED_SHA is required: set it to the revision this build was made from, '
      + 'otherwise the result cannot be attributed to that revision')
  }
  const res = await fetch(`${BASE_URL}/api/v1/health`)
  assert.equal(res.status, 200, 'health endpoint must answer 200')
  const health = await res.json()
  const running = String(health.commit_sha || '').trim().toLowerCase()
  console.log(`[revision] target=${EXPECTED_SHA} running=${running || '<empty>'}`)
  assert.equal(running, EXPECTED_SHA,
    `deployed revision ${JSON.stringify(running)} is not the target revision ${JSON.stringify(EXPECTED_SHA)}`)
}

async function runBrowserE2E() {
  if (!BASE_URL) {
    console.error('FNOS_BASE_URL is required, e.g. FNOS_BASE_URL=http://<NAS_IP>:3000')
    process.exit(2)
  }

  console.log('============================================================')
  console.log('PHYSICAL BROWSER E2E TEST RUNNER')
  console.log(`Target: ${BASE_URL}`)
  console.log(`Browser: ${CHROME_PATH || 'bundled chromium'}`)
  console.log('============================================================\n')

  const browser = await chromium.launch({
    ...(CHROME_PATH ? { executablePath: CHROME_PATH } : {}),
    headless: true,
  })

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  })
  const page = await context.newPage()

  const goHome = async () => {
    await page.click('.page-header button:has-text("返回")')
    const exitModal = page.locator('[data-testid="exit-confirm-modal"], .confirm-submit-dialog')
    if (await exitModal.count()) {
      await exitModal.locator('button.btn-confirm-exit, button.primary').first().click()
    }
    await page.waitForSelector('.home-page', { timeout: 8000 })
  }

  try {
    // 0. Refuse to run against an unverified revision
    await assertRunningRevision()

    // 1. Visit Login Page
    console.log('[STEP 1] Navigating to fnOS web shell...')
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 })
    const title = await page.title()
    console.log(`  -> Page Title: "${title}"`)
    assert(title.length > 0, 'Deployed shell must return a document title')

    // 2. Register new test user
    const username = `fn_e2e_${Date.now()}`
    console.log(`[STEP 2] Registering user: ${username}...`)

    // Clear storage to ensure fresh login page
    await page.evaluate(() => localStorage.clear())
    await page.reload({ waitUntil: 'networkidle' })

    // Toggle to register tab
    await page.click('button:has-text("创建账号")')
    await page.fill('input[autocomplete="username"]', username)
    const passwordFields = page.locator('input[autocomplete="new-password"]')
    await passwordFields.nth(0).fill(PASSWORD)
    await passwordFields.nth(1).fill(PASSWORD)
    await page.click('button[type="submit"]')

    // Wait for login/home
    await page.waitForSelector('.home-page', { timeout: 15000 })
    const userDisplay = await page.locator('.page-header p').textContent()
    console.log(`  -> Logged in successfully as: ${userDisplay?.trim()}`)
    assert(userDisplay?.toLowerCase().includes(username.toLowerCase()), 'Username not displayed in header')

    // 3. Create Bank
    console.log('[STEP 3] Creating new question bank...')
    await page.click('button:has-text("创建题库")')
    await page.waitForSelector('.exam-setup-dialog', { timeout: 5000 })
    const bankName = `E2E Bank ${Date.now()}`
    await page.fill('.exam-setup-dialog input', bankName)
    await page.click('.exam-setup-dialog button[type="submit"]')
    await page.waitForSelector(`.bank-card:has-text("${bankName}")`, { timeout: 8000 })
    console.log(`  -> Created bank: "${bankName}"`)

    // 4. Import questions via file upload
    console.log('[STEP 4] Importing questions into bank via file upload...')
    await page.click('.sidebar-nav-item:has-text("导入题库")')
    await page.waitForSelector('.import-page', { timeout: 8000 })

    // Select our new bank
    await page.selectOption('.import-page select', { label: bankName })

    // Prepare import text file
    const importText = `1. (单选) HTTP状态码404表示什么？
A. 服务器错误
B. 资源未找到
C. 请求成功
D. 禁止访问
答案：B
解析：404 Not Found表示请求的资源在服务器上未找到。
标签：网络, HTTP

2. (单选) TCP协议属于哪一层？
A. 应用层
B. 传输层
C. 网络层
D. 物理层
答案：B
解析：TCP属于传输层。
标签：网络, 传输层`

    const tempFilePath = path.join(os.tmpdir(), `e2e_import_${Date.now()}.txt`)
    fs.writeFileSync(tempFilePath, importText, 'utf-8')

    await page.setInputFiles('.import-page input[type="file"]', tempFilePath)
    await page.click('.import-page button[type="submit"]')

    // Wait for import result
    await page.waitForSelector('.import-page p.success', { timeout: 10000 })
    const resultMsg = await page.locator('.import-page p.success').textContent()
    console.log(`  -> Import Result: ${resultMsg?.trim()}`)
    assert(resultMsg?.includes('导入完成：新增/更新 2 题'), 'Expected 2 questions imported')

    // Clean up temp file
    try { fs.unlinkSync(tempFilePath) } catch (_) {}

    // Return to home
    await page.click('.import-page .btn-back')
    await page.waitForSelector('.home-page', { timeout: 8000 })

    // 5. Practice Mode (Ergonomics verification)
    console.log('[STEP 5] Testing Practice Mode & Ergonomic Fixed Action Bar...')
    const targetCard = page.locator(`.bank-card:has-text("${bankName}")`)
    await targetCard.locator('button:has-text("开始刷题")').click()
    await page.waitForSelector('.practice-page .question-card', { timeout: 10000 })
    const cardHtml = await page.locator('.practice-page .question-card').innerHTML()
    console.log(`  -> Card HTML snippet: ${cardHtml.slice(0, 300)}...`)

    // Verify keycap badges rendered
    const keycaps = await page.locator('.key-cap').allTextContents()
    console.log(`  -> Keycap badges verified: ${JSON.stringify(keycaps)}`)
    assert(keycaps.length >= 4, 'Option keycap badges must be visible')

    // Use keyboard shortcut 'B' to answer
    console.log('  -> Pressing keyboard "B" to select option...')
    await page.keyboard.press('KeyB')
    await page.waitForTimeout(300)

    // Verify Option B selected
    const selectedOpt = await page.locator('.option.selected').textContent()
    console.log(`  -> Selected option text: "${selectedOpt?.trim()}"`)
    assert(selectedOpt !== null && selectedOpt.includes('B'), 'Option B must be selected')

    // Use keyboard Enter to submit
    console.log('  -> Pressing Enter to submit answer...')
    await page.keyboard.press('Enter')
    await page.waitForSelector('.result-card', { timeout: 5000 })

    // Verify Ergonomic Action Bar is FIXED AT BOTTOM (bottom: 0)
    const fixedBarBox = await page.locator('.ergonomic-action-bar').boundingBox()
    const viewport = page.viewportSize()
    console.log(`  -> Fixed action bar position: y=${fixedBarBox?.y}, height=${fixedBarBox?.height}, viewport_height=${viewport?.height}`)
    assert(fixedBarBox && fixedBarBox.y + fixedBarBox.height >= viewport.height - 2, 'Action bar MUST be fixed at viewport bottom!')

    // Next question via Space key
    console.log('  -> Pressing Space to advance to next question...')
    await page.keyboard.press('Space')
    await page.waitForTimeout(500)

    // Now on Question 2
    const q2Text = await page.locator('.stem-box h2').textContent()
    console.log(`  -> Question 2 stem: "${q2Text?.trim()}"`)

    // Select wrong answer 'A' to create a mistake record
    console.log('  -> Answering Question 2 wrongly (A) to generate mistake record...')
    await page.keyboard.press('KeyA')
    await page.waitForTimeout(300)
    await page.keyboard.press('Enter')
    await page.waitForSelector('.result-card', { timeout: 5000 })

    // Return to home
    await goHome()

    // 6. Mistakes & Kill View Verification
    console.log('[STEP 6] Testing Mistakes Book & Kill System...')
    await page.click('.sidebar-nav-item:has-text("错题攻克")')
    await page.waitForSelector('.mistakes-page', { timeout: 8000 })

    // Select our bank in mistakes filter
    await page.selectOption('#bank-filter', { label: bankName })
    await page.waitForTimeout(500)

    const mistakeCards = await page.locator('.mistake-card').count()
    console.log(`  -> Verified mistake cards count in bank: ${mistakeCards}`)
    assert(mistakeCards >= 1, 'Question 2 must appear in mistakes book')

    // Test Kill Question
    console.log('  -> Killing mistake question...')
    await page.click('.mistake-card button:has-text("斩杀此题")')
    await page.waitForTimeout(600)
    if (await page.locator('.confirm-submit-dialog').count()) {
      await page.locator('.confirm-submit-dialog button.primary').click()
      await page.waitForTimeout(600)
    }

    // Switch to Kills Tab
    await page.click('.mistakes-page button:has-text("斩杀题库")')
    await page.waitForSelector('.killed-card', { timeout: 8000 })
    const killedCards = await page.locator('.killed-card').count()
    console.log(`  -> Verified killed cards count: ${killedCards}`)
    assert(killedCards >= 1, 'Question must appear in killed tab')

    // Test Unkill (Restore)
    console.log('  -> Restoring (unkilling) question back to active pool...')
    await page.click('.killed-card button:has-text("恢复 (解除斩杀)")')
    await page.waitForTimeout(800)

    // Return to home
    await page.click('.page-header button:has-text("返回")')
    await page.waitForSelector('.home-page', { timeout: 8000 })

    // 7. Mock Exam Verification
    console.log('[STEP 7] Testing Mock Exam Full Lifecycle...')
    const examCard = page.locator(`.bank-card:has-text("${bankName}")`)
    await examCard.locator('button:has-text("开始模考")').click()
    await page.waitForSelector('.exam-setup-dialog', { timeout: 5000 })
    await page.click('.exam-setup-dialog button[type="submit"]')

    // Wait for the exam view. ``.exam-page`` is rendered before the session's
    // questions arrive, so wait for the answer sheet's buttons themselves;
    // counting on ``.exam-page`` alone reads an empty grid.
    await page.waitForSelector('.exam-page', { timeout: 8000 })
    await page.waitForSelector('.answer-grid button', { timeout: 8000 })
    const examQuestionsCount = await page.locator('.answer-grid button').count()
    console.log(`  -> Exam started with ${examQuestionsCount} questions on answer sheet`)
    assert(examQuestionsCount === 2, 'Exam sheet must display 2 questions')

    // Answer Q1
    await page.click('.exam-option:has(.key-cap:has-text("B"))')
    // Answer Q2 via answer sheet navigation
    await page.click('.answer-grid button:has-text("2")')
    await page.waitForTimeout(300)
    await page.click('.exam-option:has(.key-cap:has-text("B"))')

    // Submit Exam
    console.log('  -> Submitting exam...')
    await page.click('.exam-header button:has-text("交卷")')
    await page.waitForSelector('.exam-confirm-dialog', { timeout: 5000 })
    await page.click('.exam-confirm-dialog button.primary:has-text("确认交卷")')

    // Wait for Report
    await page.waitForSelector('.exam-report', { timeout: 8000 })
    const finalScore = await page.locator('.report-summary strong').first().textContent()
    console.log(`  -> Mock Exam Completed! Final Score: ${finalScore?.trim()}`)
    assert(finalScore !== null && finalScore !== '', 'Exam report score must be present')

    // Return to home from exam
    await page.click('.exam-report button:has-text("返回题库")')
    await page.waitForSelector('.home-page', { timeout: 8000 })

    // 8. Learning Trends & Recommendations Verification
    console.log('[STEP 8] Testing Learning Diagnostics View...')
    await page.click('.sidebar-nav-item:has-text("复习中心")')
    await page.waitForSelector('.learning-page .stat-box', { timeout: 10000 })

    const statBoxes = await page.locator('.stat-box').count()
    console.log(`  -> Verified diagnostic metrics cards: ${statBoxes}`)
    assert(statBoxes >= 4, 'Must have at least 4 diagnostic metric boxes')

    console.log('\n============================================================')
    console.log('ALL PHYSICAL BROWSER E2E TESTS PASSED ON REAL FNOS!')
    console.log('============================================================')
  } finally {
    await browser.close()
  }
}

runBrowserE2E().catch(err => {
  console.error('\n[BROWSER E2E FAILED]:', err)
  process.exit(1)
})
