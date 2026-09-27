import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { chromium } from 'playwright'

const NAS_URL = 'http://192.168.x.x:3000'
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

async function runBrowserE2E() {
  console.log('============================================================')
  console.log('PHYSICAL CHROME BROWSER E2E TEST RUNNER')
  console.log(`Target: ${NAS_URL}`)
  console.log('============================================================\n')

  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    headless: true,
  })

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  })
  const page = await context.newPage()

  try {
    // 1. Visit Login Page
    console.log('[STEP 1] Navigating to fnOS web shell...')
    await page.goto(NAS_URL, { waitUntil: 'networkidle', timeout: 15000 })
    const title = await page.title()
    console.log(`  -> Page Title: "${title}"`)

    // 2. Register new test user
    const username = `fn_e2e_${Date.now()}`
    const password = 'Password123!'
    console.log(`[STEP 2] Registering user: ${username}...`)

    // Clear storage to ensure fresh login page
    await page.evaluate(() => localStorage.clear())
    await page.reload({ waitUntil: 'networkidle' })

    // Toggle to register tab
    await page.click('button:has-text("创建账号")')
    await page.fill('input[autocomplete="username"]', username)
    await page.fill('input[type="password"]', password)
    await page.click('button:has-text("注册并登录")')

    // Wait for login/home
    await page.waitForSelector('.home-page', { timeout: 10000 })
    const userDisplay = await page.locator('.page-header p').textContent()
    console.log(`  -> Logged in successfully as: ${userDisplay?.trim()}`)
    assert(userDisplay?.toLowerCase().includes(username.toLowerCase()), 'Username not displayed in header')

    // 3. Create Bank
    console.log('[STEP 3] Creating new question bank...')
    await page.click('button:has-text("创建题库")')
    await page.waitForSelector('.exam-setup-dialog', { timeout: 5000 })
    const bankName = `E2E Bank ${Date.now()}`
    await page.fill('input[placeholder*="历年真题"]', bankName)
    await page.click('.exam-setup-dialog button[type="submit"]')
    await page.waitForSelector(`.bank-card:has-text("${bankName}")`, { timeout: 5000 })
    console.log(`  -> Created bank: "${bankName}"`)

    // 4. Import questions via file upload
    console.log('[STEP 4] Importing questions into bank via file upload...')
    await page.click('button:has-text("导入题目")')
    await page.waitForSelector('.import-page', { timeout: 5000 })

    // Select our new bank
    await page.selectOption('label:has-text("目标题库") select', { label: bankName })

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

    await page.setInputFiles('input[type="file"]', tempFilePath)
    await page.click('button:has-text("检查并导入")')

    // Wait for import result
    await page.waitForSelector('.import-page p.success', { timeout: 10000 })
    const resultMsg = await page.locator('.import-page p.success').textContent()
    console.log(`  -> Import Result: ${resultMsg?.trim()}`)
    assert(resultMsg?.includes('导入完成：新增/更新 2 题'), 'Expected 2 questions imported')

    // Clean up temp file
    try { fs.unlinkSync(tempFilePath) } catch (_) {}

    // Return to home
    await page.click('.page-header button:has-text("返回")')
    await page.waitForSelector('.home-page', { timeout: 5000 })

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
    await page.click('.page-header button:has-text("返回")')
    await page.waitForSelector('.home-page', { timeout: 5000 })

    // 6. Mistakes & Kill View Verification
    console.log('[STEP 6] Testing Mistakes Book & Kill System...')
    await page.click('button:has-text("错题与斩杀")')
    await page.waitForSelector('.mistakes-page', { timeout: 5000 })

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

    // Switch to Kills Tab
    await page.click('button:has-text("斩杀题库")')
    await page.waitForSelector('.killed-card', { timeout: 5000 })
    const killedCards = await page.locator('.killed-card').count()
    console.log(`  -> Verified killed cards count: ${killedCards}`)
    assert(killedCards >= 1, 'Question must appear in killed tab')

    // Test Unkill (Restore)
    console.log('  -> Restoring (unkilling) question back to active pool...')
    await page.click('.killed-card button:has-text("恢复 (解除斩杀)")')
    await page.waitForTimeout(800)

    // Return to home
    await page.click('.page-header button:has-text("返回")')
    await page.waitForSelector('.home-page', { timeout: 5000 })

    // 7. Mock Exam Verification
    console.log('[STEP 7] Testing Mock Exam Full Lifecycle...')
    const examCard = page.locator(`.bank-card:has-text("${bankName}")`)
    await examCard.locator('button:has-text("开始模考")').click()
    await page.waitForSelector('.exam-setup-dialog', { timeout: 5000 })
    await page.click('.exam-setup-dialog button[type="submit"]')

    // Wait for exam view
    await page.waitForSelector('.exam-page', { timeout: 8000 })
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
    await page.waitForSelector('.home-page', { timeout: 5000 })

    // 8. Learning Trends & Recommendations Verification
    console.log('[STEP 8] Testing Learning Diagnostics View...')
    await page.click('button:has-text("学习诊断")')
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
