import test from 'node:test'
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import net from 'node:net'
import crypto from 'node:crypto'
import { chromium } from 'playwright'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')

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

async function waitForServer(url, timeoutMs = 20000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${url}/api/v1/health`)
      if (res.ok) return true
    } catch (_) {}
    await new Promise(r => setTimeout(r, 300))
  }
  throw new Error(`Server at ${url} failed to start within ${timeoutMs}ms`)
}

test('Bank Content Management E2E: Full Lifecycle, Killed Retention, Active Exam Lock, Mobile 375px', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bank-manage-e2e-'))
  const tempDbPath = path.join(tempDir, 'bank_manage.db')
  const port = await getFreePort()
  const BASE_URL = `http://127.0.0.1:${port}`

  console.log(`[E2E] Spawning backend server on ${BASE_URL}...`)
  const serverProcess = spawn(
    'python',
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        DB_PATH: tempDbPath,
        EASYEXAM_SECRET_KEY: 'e2e-secret-key-32bytes-ci-safe!!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  const screenshotsDir = path.resolve(repoRoot, 'tests/visual_smoke')
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true })
  }

  let browser = null

  try {
    await waitForServer(BASE_URL)
    console.log('[E2E] Backend server healthy.')

    // Setup initial data via API
    // 1. Admin user registration & login
    const adminRegRes = await fetch(`${BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin_e2e', password: 'Password123!' }),
    })
    assert.equal(adminRegRes.status, 201)

    const adminLoginRes = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin_e2e', password: 'Password123!' }),
    })
    const adminLoginBody = await adminLoginRes.json()
    const adminToken = adminLoginBody.token

    // 2. Member user registration
    const memberRegRes = await fetch(`${BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'member_e2e', password: 'Password123!' }),
    })
    assert.equal(memberRegRes.status, 201)

    // 3. Create question bank
    const createBankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        name: 'Computer Networks Bank',
        category: 'CS Core',
        description: 'Comprehensive networking exam bank',
      }),
    })
    assert.equal(createBankRes.status, 201)
    const bank = await createBankRes.json()
    const bankId = bank.id

    // 4. Add member_e2e as MEMBER
    await fetch(`${BASE_URL}/api/v1/banks/${bankId}/members`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({ username: 'member_e2e', role: 'MEMBER' }),
    })

    // 5. Add chapter
    const chapRes = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/chapters`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({ name: 'Transport Layer' }),
    })
    const chapter = await chapRes.json()

    // 6. Create 3 questions
    // Q1 (will be killed by admin)
    const q1Res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        stem: 'What layer of the OSI model does IP belong to?',
        type: 'SINGLE',
        options: [{ key: 'A', content: 'Network' }, { key: 'B', content: 'Transport' }],
        answer: 'A',
        explanation: 'IP is network layer (Layer 3).',
        difficulty: 2,
        tags: ['network', 'osi'],
        chapter_id: chapter.id,
      }),
    })
    const q1 = await q1Res.json()

    // Q2 (multi-choice)
    const q2Res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        stem: 'Which protocols run on TCP?',
        type: 'MULTI',
        options: [
          { key: 'A', content: 'HTTP' },
          { key: 'B', content: 'FTP' },
          { key: 'C', content: 'UDP' },
        ],
        answer: 'AB',
        explanation: 'HTTP and FTP use TCP connection.',
        difficulty: 3,
        tags: ['protocol', 'tcp'],
        chapter_id: chapter.id,
      }),
    })
    const q2 = await q2Res.json()

    // Q3 (judge question)
    const q3Res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        stem: 'Is UDP a connection-oriented protocol?',
        type: 'JUDGE',
        options: [{ key: 'T', content: 'True' }, { key: 'F', content: 'False' }],
        answer: 'F',
        explanation: 'UDP is connectionless.',
        difficulty: 1,
        tags: ['udp', 'basics'],
        chapter_id: chapter.id,
      }),
    })
    const q3 = await q3Res.json()

    // 7. Kill Question 1
    const killRes = await fetch(`${BASE_URL}/api/v1/kills/${q1.id}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    assert.equal(killRes.status, 201)
    console.log('[E2E] Seeded 3 questions and killed Q1.')

    // Launch Playwright Chromium
    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
    const page = await context.newPage()

    // Step A: Login as admin via LoginView UI
    await page.goto(BASE_URL)
    await page.waitForSelector('.auth-page', { timeout: 10000 })
    await page.fill('input[autocomplete="username"]', 'admin_e2e')
    await page.fill('input[type="password"]', 'Password123!')
    await page.click('button[type="submit"]')
    await page.waitForSelector('.home-page', { timeout: 10000 })
    console.log('[E2E] Logged into HomeView.')

    // Step B: Home bank card has "管理题目" button
    const manageBtn = page.locator(`[data-testid="manage-bank-${bankId}"]`)
    await manageBtn.waitFor({ state: 'visible', timeout: 5000 })
    await manageBtn.click()

    // Step C: URL is now #/banks/:bankId
    await page.waitForURL(`**/banks/${bankId}`, { timeout: 5000 })
    await page.waitForSelector('.bank-manage-page', { timeout: 5000 })
    console.log('[E2E] Entered BankManageView.')

    // Step D: Acceptance Criterion 3 - Wait for questions to load and verify Killed question 1 MUST be in the content list!
    await page.waitForSelector(`[data-testid="question-card-${q1.id}"]`, { timeout: 5000 })
    await page.waitForSelector(`[data-testid="question-card-${q2.id}"]`, { timeout: 5000 })
    await page.waitForSelector(`[data-testid="question-card-${q3.id}"]`, { timeout: 5000 })
    console.log('[E2E] Confirmed questions loaded and killed question Q1 is present in management list.')

    // Step E: Header verification
    const titleText = await page.locator('.bank-title-text').innerText()
    assert.equal(titleText, 'Computer Networks Bank')
    const rolePill = await page.locator('.role-pill').innerText()
    assert.ok(rolePill.includes('管理员') || rolePill.includes('Admin'))

    // Visual Capture 1: 1280px full bank manage page (with questions loaded)
    await page.screenshot({ path: path.join(screenshotsDir, 'bank_manage_1280_full.png'), fullPage: false })

    // Step F: Keyword Search
    await page.fill('.search-input', 'TCP')
    await page.waitForTimeout(300)
    assert.equal(await page.locator(`[data-testid="question-card-${q2.id}"]`).isVisible(), true)
    assert.equal(await page.locator(`[data-testid="question-card-${q1.id}"]`).isVisible(), false)
    assert.equal(await page.locator(`[data-testid="question-card-${q3.id}"]`).isVisible(), false)

    // Visual Capture 2: 1280px search + multi-filter state
    await page.screenshot({ path: path.join(screenshotsDir, 'bank_manage_1280_filtered.png') })

    // Clear search
    await page.click('.btn-clear-search')
    await page.waitForTimeout(200)

    // Step G: Type and Difficulty filter
    const typeSelect = page.locator('.filter-select').first()
    await typeSelect.selectOption('JUDGE')
    await page.waitForTimeout(200)
    assert.equal(await page.locator(`[data-testid="question-card-${q3.id}"]`).isVisible(), true)
    assert.equal(await page.locator(`[data-testid="question-card-${q2.id}"]`).isVisible(), false)

    // Reset filters
    await page.click('.btn-reset-filters')
    await page.waitForTimeout(200)
    assert.equal(await page.locator(`[data-testid="question-card-${q1.id}"]`).isVisible(), true)
    assert.equal(await page.locator(`[data-testid="question-card-${q2.id}"]`).isVisible(), true)

    // Step H: Versioned Question Editing
    const editBtnQ3 = page.locator(`[data-testid="edit-btn-${q3.id}"]`)
    await editBtnQ3.click()
    await page.waitForSelector('.question-edit-dialog', { timeout: 5000 })
    await page.waitForTimeout(300)

    // Visual Capture 3: 1280px edit modal
    await page.screenshot({ path: path.join(screenshotsDir, 'bank_manage_1280_edit_modal.png') })

    // Edit stem
    const stemInput = page.locator('#edit-stem')
    await stemInput.fill('Is UDP a connection-oriented protocol or connectionless?')
    await page.click('.btn-submit-edit')

    // Toast appears
    await page.waitForSelector('.toast-success-banner', { timeout: 5000 })
    console.log('[E2E] Question edited and saved.')

    // Card should now display v2
    const q3Card = page.locator(`[data-testid="question-card-${q3.id}"]`)
    const q3VersionText = await q3Card.locator('.version-badge').innerText()
    assert.ok(q3VersionText.includes('v2'))

    // Reload page and check persistence
    await page.reload()
    await page.waitForSelector(`[data-testid="question-card-${q3.id}"]`, { timeout: 5000 })
    const reloadedStem = await page.locator(`[data-testid="question-card-${q3.id}"] .card-stem-text`).innerText()
    assert.ok(reloadedStem.includes('connectionless'))
    const reloadedVer = await page.locator(`[data-testid="question-card-${q3.id}"] .version-badge`).innerText()
    assert.ok(reloadedVer.includes('v2'))
    console.log('[E2E] Persistence and version increment v2 verified after reload.')

    // Step I: Mobile 375px responsive testing
    await page.setViewportSize({ width: 375, height: 812 })
    await page.waitForTimeout(300)

    // Check no horizontal overflow
    const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth)
    const bodyClientWidth = await page.evaluate(() => document.body.clientWidth)
    assert.ok(bodyScrollWidth <= bodyClientWidth + 1, `Horizontal overflow detected: scrollWidth=${bodyScrollWidth}, clientWidth=${bodyClientWidth}`)

    // Visual Capture 4: 375px mobile list
    await page.screenshot({ path: path.join(screenshotsDir, 'bank_manage_375_list.png') })

    // Open edit modal on mobile
    await page.locator(`[data-testid="edit-btn-${q3.id}"]`).click()
    await page.waitForSelector('.question-edit-dialog', { timeout: 5000 })
    await page.waitForTimeout(300)

    // Visual Capture 5: 375px mobile edit modal
    await page.screenshot({ path: path.join(screenshotsDir, 'bank_manage_375_edit_modal.png') })

    await page.click('.modal-footer .secondary-btn')
    await page.waitForTimeout(200)

    // Test back button on mobile
    await page.click('.btn-back-home')
    await page.waitForURL(`**/`, { timeout: 5000 })
    console.log('[E2E] Mobile 375px responsiveness and navigation verified.')

    // Step J: Active Exam Protection & Masking Verification
    // Start active exam with Q2
    const startExamRes = await fetch(`${BASE_URL}/api/v1/practice/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        bank_id: bankId,
        mode: 'EXAM',
        total_questions: 1,
        question_ids: [q2.id],
      }),
    })
    assert.equal(startExamRes.status, 201)
    const examSession = await startExamRes.json()

    // Assert backend API masks answer and explanation during active exam
    const contentCheckRes = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    const contentQuestions = await contentCheckRes.json()
    const q2Content = contentQuestions.find(q => q.id === q2.id)
    assert.equal(q2Content.answer, '', 'Backend API must mask question answer during active exam')
    assert.equal(q2Content.explanation, '', 'Backend API must mask question explanation during active exam')

    // Re-visit bank manage page
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto(`${BASE_URL}/#/banks/${bankId}`)
    await page.waitForSelector('.bank-manage-page', { timeout: 5000 })

    // Active exam banner must be visible
    const examAlert = page.locator('[data-testid="active-exam-alert"]')
    await examAlert.waitFor({ state: 'visible', timeout: 5000 })
    console.log('[E2E] Active exam warning banner verified.')

    // Edit button must be replaced by view button
    const editBtnsCount = await page.locator('.btn-action-edit').count()
    assert.equal(editBtnsCount, 0, 'Edit buttons must not be present during active exam')
    const viewBtn = page.locator(`[data-testid="view-btn-${q2.id}"]`)
    assert.equal(await viewBtn.isVisible(), true)

    // Clicking view opens modal in readOnly mode
    await viewBtn.click()
    await page.waitForSelector('.question-edit-dialog', { timeout: 5000 })
    const saveBtnVisible = await page.locator('.btn-submit-edit').isVisible()
    assert.equal(saveBtnVisible, false, 'Save button must not exist in read-only modal')

    // Assert DOM input fields are masked in the modal
    const ansVal = await page.inputValue('#edit-answer')
    assert.equal(ansVal, '', 'DOM input #edit-answer must be empty (masked) during active exam')
    const expVal = await page.inputValue('#edit-explanation')
    assert.equal(expVal, '', 'DOM textarea #edit-explanation must be empty (masked) during active exam')

    await page.click('.btn-close-modal')
    console.log('[E2E] Active exam safety verified: answers masked in API and DOM, view-only mode enforced.')

    // Step K: Concurrent Conflict Detection Verification
    // Complete the exam session first so editing is re-enabled
    await fetch(`${BASE_URL}/api/v1/practice/sessions/${examSession.id}/complete`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}` },
    })

    // Advance Q3 to version 3 on backend directly
    await fetch(`${BASE_URL}/api/v1/questions/${q3.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        stem: 'Is UDP connectionless? (Intermediary edit v3)',
        type: 'JUDGE',
        options: [{ key: 'T', content: 'True' }, { key: 'F', content: 'False' }],
        answer: 'F',
        base_version_number: 2,
      }),
    })

    // Reload bank manage page so UI has latest data
    await page.reload()
    await page.waitForSelector(`[data-testid="edit-btn-${q3.id}"]`, { timeout: 5000 })

    // Simulate concurrent client editing based on outdated base_version_number=1
    // (by calling PUT with base_version_number: 1 directly or via mock)
    const conflictPutRes = await fetch(`${BASE_URL}/api/v1/questions/${q3.id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${adminToken}`,
      },
      body: JSON.stringify({
        stem: 'Outdated client concurrent update',
        type: 'JUDGE',
        options: [{ key: 'T', content: 'True' }, { key: 'F', content: 'False' }],
        answer: 'F',
        base_version_number: 1,
      }),
    })
    assert.equal(conflictPutRes.status, 200)

    // Check conflict endpoint
    const conflictRes = await fetch(`${BASE_URL}/api/v1/questions/${q3.id}/conflict`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    const confJson = await conflictRes.json()
    assert.equal(confJson.has_conflict, true, 'Conflict endpoint must report has_conflict=true')
    assert.equal(confJson.conflict.base_version_number, 1)
    console.log('[E2E] Concurrent conflict tracking verified.')

    console.log('[E2E] All browser E2E acceptance criteria successfully passed!')
  } finally {
    if (browser) await browser.close()
    if (serverProcess) {
      serverProcess.kill('SIGTERM')
    }
    if (fs.existsSync(tempDir)) {
      fs.rmSync(tempDir, { recursive: true, force: true })
    }
  }
})
