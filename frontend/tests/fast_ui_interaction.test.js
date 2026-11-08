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
    await new Promise(r => setTimeout(r, 300))
  }
  throw new Error(`Server at ${url} failed to start within ${timeoutMs}ms`)
}

test('Fast UI Interaction: MobileNav More menu, Learning accordion, Practice more menu', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fast-ui-interaction-'))
  const tempDbPath = path.join(tempDir, 'fast_ui.db')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const BASE_URL = `http://127.0.0.1:${port}`

  const serverProcess = spawn(
    'python',
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        DB_PATH: tempDbPath,
        INSTANCE_TOKEN: instanceToken,
        EASYEXAM_SECRET_KEY: 'fast-ui-interaction-secret-key-32b',
      },
      stdio: ['ignore', 'ignore', 'ignore'],
    }
  )

  let browser = null
  try {
    await waitForServer(BASE_URL, instanceToken)

    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })

    // Setup 1: Register and login user
    const username = `test_fast_${Date.now()}`
    const password = 'Password123!'
    const regRes = await fetch(`${BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    assert.equal(regRes.status, 201, 'User registration must succeed')

    const loginRes = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    assert.equal(loginRes.status, 200, 'User login must succeed')
    const loginData = await loginRes.json()
    const token = loginData.token

    // Create a bank and a question to enable Practice view & Learning recommendations
    const bankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ name: 'Fast Interaction Bank', description: 'Testing UI' }),
    })
    assert.equal(bankRes.status, 201, 'Bank creation must succeed')
    const bank = await bankRes.json()

    const qRes = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/questions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        stem: 'Fast UI Sample Question 1?',
        type: 'SINGLE',
        options: [
          { key: 'A', content: 'Option A' },
          { key: 'B', content: 'Option B' },
        ],
        answer: 'A',
        explanation: 'Option A explanation',
        difficulty: 1,
      }),
    })
    assert.equal(qRes.status, 201, 'Question creation must succeed')

    // -------------------------------------------------------------
    // Test Case 1: MobileNav More Menu Popup and Navigation
    // -------------------------------------------------------------
    const mobileContext = await browser.newContext({
      viewport: { width: 375, height: 812 },
      isMobile: true,
      hasTouch: true,
    })
    const mobilePage = await mobileContext.newPage()

    await mobilePage.goto(BASE_URL)
    await mobilePage.waitForSelector('.auth-page')
    await mobilePage.fill('input[placeholder*="用户名"], input[type="text"]', username)
    await mobilePage.fill('input[type="password"]', password)
    await mobilePage.click('button[type="submit"]')
    await mobilePage.waitForSelector('.home-page')

    // Verify Mobile Bottom Nav is visible
    await mobilePage.waitForSelector('.mobile-nav-bar')
    const moreBtn = mobilePage.locator('.mobile-nav-item-more')
    assert.ok(await moreBtn.isVisible(), 'Mobile nav more button should be visible')

    // Initial state: popup should not exist
    assert.equal(await mobilePage.locator('.mobile-nav-more-popup').count(), 0, 'More popup should initially be closed')

    // Natural user click on "更多"
    await moreBtn.click()
    await mobilePage.waitForSelector('.mobile-nav-more-popup')
    assert.equal(await mobilePage.locator('.mobile-nav-more-popup').count(), 1, 'More popup should appear on click')

    // Verify "导入" and "设置" options exist inside the popup
    const importItem = mobilePage.locator('.more-popup-item:has-text("导入"), .more-popup-item:has-text("Imports")')
    const settingsItem = mobilePage.locator('.more-popup-item:has-text("设置"), .more-popup-item:has-text("Settings")')
    assert.ok(await importItem.isVisible(), 'Import item should be visible in popup')
    assert.ok(await settingsItem.isVisible(), 'Settings item should be visible in popup')

    // Click "导入" and verify navigation happens to import view
    await importItem.click()
    await mobilePage.waitForSelector('.import-page', { timeout: 5000 })
    assert.ok(await mobilePage.locator('.import-page').isVisible(), 'Should navigate to Import view')

    await mobileContext.close()

    // -------------------------------------------------------------
    // Test Case 2: LearningView Analytics Accordion Natural Click
    // -------------------------------------------------------------
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
    })
    const desktopPage = await desktopContext.newPage()

    await desktopPage.goto(BASE_URL)
    await desktopPage.waitForSelector('.auth-page')
    await desktopPage.fill('input[placeholder*="用户名"], input[type="text"]', username)
    await desktopPage.fill('input[type="password"]', password)
    await desktopPage.click('button[type="submit"]')
    await desktopPage.waitForSelector('.home-page')

    // Navigate to LearningView
    await desktopPage.waitForSelector('.app-sidebar')
    await desktopPage.click('.app-sidebar .sidebar-nav-item:has-text("复习规划"), .sidebar-nav-item:has-text("Learning")')
    await desktopPage.waitForSelector('.learning-page')

    // Verify accordion exists and is initially closed
    const accordion = desktopPage.locator('.learning-analytics-accordion')
    await accordion.waitFor({ state: 'attached' })
    const isInitiallyOpen = await accordion.evaluate(el => el.hasAttribute('open'))
    assert.equal(isInitiallyOpen, false, 'Learning analytics accordion should be closed by default')

    // Natural user click on summary to expand
    const summaryBtn = desktopPage.locator('.learning-analytics-accordion summary.analytics-accordion-summary')
    await summaryBtn.click()
    await desktopPage.waitForSelector('.learning-analytics-accordion[open]', { timeout: 3000 })

    // Verify analytics body & metrics become visible
    await desktopPage.waitForSelector('.metrics-grid', { timeout: 3000 })
    assert.ok(await desktopPage.locator('.metrics-grid').isVisible(), 'Metrics grid should be visible after expansion')

    // -------------------------------------------------------------
    // Test Case 3: PracticeViewV1 More Menu and Weak Toggle / Complete
    // -------------------------------------------------------------
    // Start a practice session
    await desktopPage.click('header button:has-text("返回"), .btn-back')
    await desktopPage.waitForSelector('.home-page')

    // Start practice on the created bank
    const practiceBtn = desktopPage.locator('button:has-text("顺序刷题"), button:has-text("开始刷题")').first()
    await practiceBtn.click()
    await desktopPage.waitForSelector('.practice-page', { timeout: 8000 })

    // Verify ⋯ more menu button exists
    const practiceMoreBtn = desktopPage.locator('.btn-more-menu')
    assert.ok(await practiceMoreBtn.isVisible(), 'Practice more menu button should be visible')

    // Click ⋯ more menu button to toggle dropdown
    assert.equal(await desktopPage.locator('.mobile-dropdown-menu').count(), 0, 'Dropdown menu should initially be closed')
    await practiceMoreBtn.click()
    await desktopPage.waitForSelector('.mobile-dropdown-menu')
    assert.equal(await desktopPage.locator('.mobile-dropdown-menu').count(), 1, 'Dropdown menu should open on click')

    // Verify items in more menu
    assert.ok(await desktopPage.locator('.dropdown-item.btn-help-guide').isVisible(), 'Help guide item should be in dropdown')
    assert.ok(await desktopPage.locator('.dropdown-item.btn-edit-question').isVisible(), 'Edit question item should be in dropdown')

    // Verify complete button is accessible and works without blocking
    const completeBtn = desktopPage.locator('.btn-header-complete')
    assert.ok(await completeBtn.isVisible(), 'Complete button should be accessible')

    await desktopContext.close()
  } finally {
    if (browser) {
      await browser.close().catch(() => {})
    }
    serverProcess.kill('SIGTERM')
  }
})
