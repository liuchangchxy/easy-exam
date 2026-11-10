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

async function login(page, baseUrl, username, password) {
  await page.goto(baseUrl)
  await page.waitForSelector('.auth-layout')
  await page.fill('#login-username', username)
  await page.fill('#login-password', password)
  await page.click('.auth-submit')
  await page.waitForSelector('.today', { timeout: 15000 })
}

test('Fast UI Interaction: mobile nav, review page, practice tools and finish', async () => {
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
    // Mobile: bottom navigation reaches the library
    // -------------------------------------------------------------
    const mobileContext = await browser.newContext({
      viewport: { width: 375, height: 812 },
      isMobile: true,
      hasTouch: true,
    })
    const mobilePage = await mobileContext.newPage()
    await login(mobilePage, BASE_URL, username, password)

    await mobilePage.waitForSelector('.bottomnav')
    const navItems = mobilePage.locator('.bottomnav .bn-item')
    assert.equal(await navItems.count(), 5, 'Bottom navigation must expose five destinations')
    await navItems.nth(4).click()
    await mobilePage.waitForSelector('.library-page', { timeout: 8000 })
    assert.ok(await mobilePage.locator('.library-page').isVisible(), 'Library page should open from mobile nav')
    await mobileContext.close()

    // -------------------------------------------------------------
    // Desktop: sidebar navigation and review tabs
    // -------------------------------------------------------------
    const desktopContext = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const desktopPage = await desktopContext.newPage()
    await login(desktopPage, BASE_URL, username, password)

    await desktopPage.waitForSelector('.sidebar')
    const sideItems = desktopPage.locator('.sidebar .nav-item')
    await sideItems.nth(2).click()
    await desktopPage.waitForSelector('.review-page', { timeout: 8000 })
    const tabs = desktopPage.locator('.review-page .tabs .tab')
    assert.ok(await tabs.count() >= 4, 'Review page must expose due, mistakes, killed and diagnosis tabs')
    await tabs.nth(1).click()
    await desktopPage.waitForSelector('.review-page .tabs .tab.is-active')

    // -------------------------------------------------------------
    // Practice: start from Today, open tools, finish to report
    // -------------------------------------------------------------
    await desktopPage.locator('.sidebar .nav-item').nth(0).click()
    await desktopPage.waitForSelector('.today')
    await desktopPage.locator('.masthead .btn-primary').click()
    await desktopPage.waitForSelector('.focus-mode', { timeout: 12000 })

    await desktopPage.waitForSelector('.btn-more-menu', { timeout: 12000 })
    const practiceMoreBtn = desktopPage.locator('.btn-more-menu')
    assert.ok(await practiceMoreBtn.isVisible(), 'Practice more menu button should be visible')
    assert.equal(await desktopPage.locator('.focus-menu').count(), 0, 'Menu should initially be closed')
    await practiceMoreBtn.click()
    await desktopPage.waitForSelector('.focus-menu')
    assert.equal(await desktopPage.locator('.focus-menu .focus-menu-item').count(), 2, 'Menu should expose edit and kill actions')
    await practiceMoreBtn.click()

    await desktopPage.locator('.focus-finish').click()
    const confirmDialog = desktopPage.locator('.confirm-dialog')
    if (await confirmDialog.count()) {
      await confirmDialog.locator('.btn-primary').click()
    }
    await desktopPage.waitForSelector('[data-testid="practice-report-modal"]', { timeout: 12000 })
    assert.ok(await desktopPage.locator('[data-testid="practice-report-modal"]').isVisible(), 'Completing practice should show the report')

    await desktopContext.close()
  } finally {
    if (browser) await browser.close()
    serverProcess.kill()
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
})
