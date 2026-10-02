import assert from 'node:assert/strict'
import test from 'node:test'
import { spawn, execFileSync } from 'node:child_process'
import { chromium } from 'playwright'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import net from 'node:net'

const repoRoot = path.resolve(import.meta.dirname, '../..')

async function getFreePort() {
  const server = net.createServer()
  await new Promise((resolve, reject) => server.listen(0, '127.0.0.1', resolve).once('error', reject))
  const port = server.address().port
  await new Promise(resolve => server.close(resolve))
  return port
}

async function waitForServer(url, timeoutMs = 25000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${url}/api/v1/health`)
      if (response.ok) return
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 250))
  }
  throw new Error(`EasyExam did not start at ${url}`)
}

test('real browser bilingual login, localized API error, and persisted language switch', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'easyexam-locale-e2e-'))
  const databasePath = path.join(tempDir, 'locale-e2e.db')
  const port = await getFreePort()
  const baseUrl = `http://127.0.0.1:${port}`
  const server = spawn('python', ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONPATH: repoRoot,
      DB_PATH: databasePath,
      EASYEXAM_SECRET_KEY: process.env.EASYEXAM_SECRET_KEY || 'easyexam-locale-e2e-secret-key-32bytes',
    },
    stdio: ['ignore', 'ignore', 'pipe'],
  })
  let browser
  let startupErrors = ''
  try {
    server.stderr.on('data', chunk => { startupErrors += chunk.toString() })
    await waitForServer(baseUrl)
    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })
    const context = await browser.newContext({ locale: 'zh-CN', viewport: { width: 1280, height: 800 } })
    const page = await context.newPage()
    const loginRequests = []
    page.on('request', request => {
      if (request.url().endsWith('/api/v1/auth/login')) {
        loginRequests.push(request.headers()['accept-language'])
      }
    })

    await page.goto(baseUrl)
    await page.waitForSelector('.auth-page')
    assert.equal(await page.locator('html').getAttribute('lang'), 'zh-CN')
    assert.equal(await page.locator('.auth-brand h1').innerText(), '飞牛刷题')
    assert.equal(await page.locator('button[type="submit"]').innerText(), '登录')

    await page.locator('input[autocomplete="username"]').fill('missing-locale-user')
    await page.locator('input[autocomplete="current-password"]').fill('incorrect-password-123')
    await page.locator('button[type="submit"]').click()
    await page.locator('.error-banner').waitFor({ state: 'visible' })
    await assert.doesNotReject(() => page.locator('.error-text').getByText('账号或密码错误', { exact: true }).waitFor())
    assert.match(loginRequests.at(-1) || '', /^zh-CN/)

    await page.locator('.locale-toggle').click()
    assert.equal(await page.locator('html').getAttribute('lang'), 'en-US')
    assert.equal(await page.evaluate(() => localStorage.getItem('easyexam_locale')), 'en-US')
    assert.equal(await page.locator('.auth-brand h1').innerText(), 'EasyExam')
    assert.equal(await page.locator('button[type="submit"]').innerText(), 'Sign in')
    assert.equal(await page.locator('.error-text').innerText(), 'Invalid username or password')

    const englishLoginResponse = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/login'))
    await page.locator('button[type="submit"]').click()
    await englishLoginResponse
    assert.match(loginRequests.at(-1) || '', /^en-US/)
    assert.equal(await page.locator('.error-text').innerText(), 'Invalid username or password')

    await page.reload()
    await page.waitForSelector('.auth-page')
    assert.equal(await page.locator('html').getAttribute('lang'), 'en-US')
    assert.equal(await page.locator('button[type="submit"]').innerText(), 'Sign in')

    await page.locator('.auth-footer-toggle .link-button').click()
    await page.locator('input[autocomplete="username"]').fill(`locale_student_${Date.now()}`)
    await page.locator('input[placeholder="Password (at least 8 characters)"]').fill('locale-pass-123456')
    await page.locator('input[placeholder="Please enter your password again to confirm"]').fill('locale-pass-123456')
    await page.locator('button[type="submit"]').click()
    await page.waitForSelector('.home-page')

    const assertEnglishSurface = async selector => {
      const text = await page.locator(selector).innerText()
      assert.doesNotMatch(text, /[\u4e00-\u9fff]/u, `${selector} leaked Chinese system copy in English mode`)
    }
    await assertEnglishSurface('.home-page')
    await page.locator('.sidebar-nav-item').nth(1).click()
    await page.waitForSelector('.mistakes-page')
    assert.match(await page.locator('.mistakes-page h1').innerText(), /Mistake/)
    await assertEnglishSurface('.mistakes-page')
    await page.locator('.sidebar-nav-item').nth(2).click()
    await page.waitForSelector('.learning-page')
    await assertEnglishSurface('.learning-page')
    await page.locator('.sidebar-nav-item').nth(3).click()
    await page.waitForSelector('.import-page')
    await assertEnglishSurface('.import-page')

    await page.locator('.locale-toggle').click()
    assert.equal(await page.locator('html').getAttribute('lang'), 'zh-CN')
    await assert.doesNotReject(() => page.getByText('导入题库', { exact: true }).first().waitFor())
  } catch (error) {
    if (!browser && startupErrors) error.message += `\nBackend startup output:\n${startupErrors}`
    throw error
  } finally {
    if (browser) await browser.close().catch(() => {})
    if (server.pid) {
      try { execFileSync('taskkill', ['/pid', String(server.pid), '/T', '/F'], { stdio: 'ignore' }) }
      catch { server.kill('SIGKILL') }
    }
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
})
