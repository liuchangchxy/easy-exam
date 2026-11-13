// Final acceptance walkthrough: one real instance, three real viewports, the
// flows a person actually walks through.
//
// This is the closing evidence for the Core UX redesign rather than another
// regression suite: it bootstraps an empty instance, puts real content in it,
// and then drives Home -> Banks -> bank workspace -> practice -> review ->
// settings -> instance admin at 1280, 768 and 375 with a real Chromium. Every
// screen is screenshotted, horizontal scrolling is checked on each one, and any
// native dialog or uncaught page error fails the run.
//
// Run: node tests/final_acceptance_walkthrough.mjs
// Screenshots: tests/screenshots/acceptance/<viewport>-<screen>.png (git-ignored)
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
const shotDir = path.join(__dirname, 'screenshots', 'acceptance')

const VIEWPORTS = [
  { name: 'desktop-1280', width: 1280, height: 900 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'phone-375', width: 375, height: 812, isMobile: true, hasTouch: true },
]

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
  const expectedFingerprint = crypto.createHash('sha256').update(expectedToken).digest('hex').slice(0, 16)
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${url}/api/v1/health`)
      if (res.ok) {
        const body = await res.json()
        if (body.instance_fingerprint !== expectedFingerprint) {
          throw new Error(`Instance fingerprint mismatch: ${body.instance_fingerprint}`)
        }
        return true
      }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 300))
  }
  throw new Error(`Server at ${url} failed to start`)
}

function api(baseUrl, token) {
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const call = async (method, url, body) => {
    const res = await fetch(`${baseUrl}${url}`, {
      method,
      headers: body ? { ...headers, 'Content-Type': 'application/json' } : headers,
      body: body ? JSON.stringify(body) : undefined,
    })
    const text = await res.text()
    let json = null
    try { json = text ? JSON.parse(text) : null } catch (_) { json = null }
    return { status: res.status, body: json, text }
  }
  return {
    get: url => call('GET', url),
    post: (url, body) => call('POST', url, body),
    patch: (url, body) => call('PATCH', url, body),
    del: url => call('DELETE', url),
  }
}

async function login(page, baseUrl, username, password) {
  await page.goto(baseUrl)
  await page.waitForSelector('.auth-layout', { timeout: 15000 })
  await page.fill('#login-username', username)
  await page.fill('#login-password', password)
  await page.click('.auth-submit')
  await page.waitForSelector('.today', { timeout: 20000 })
}

const failures = []
const shots = []

async function visit(page, viewportName, screen, hash, readySelector) {
  const url = `${page.__baseUrl}/#${hash}`
  await page.goto(url)
  // Hash-to-hash navigation keeps the component alive; reload so each screen is
  // entered the way a returning user would enter it.
  await page.reload()
  if (readySelector) await page.waitForSelector(readySelector, { timeout: 20000 })
  await page.waitForTimeout(250)
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }))
  if (overflow.scrollWidth > overflow.innerWidth + 1) {
    failures.push(
      `${viewportName} ${screen}: horizontal overflow ${overflow.scrollWidth} > ${overflow.innerWidth}`
    )
  }
  const file = path.join(shotDir, `${viewportName}-${screen}.png`)
  await page.screenshot({ path: file, fullPage: false })
  shots.push(file)
  return page
}

async function startPractice(page, bankName) {
  await page.goto(`${page.__baseUrl}/#/banks`)
  await page.waitForSelector('.banks-page', { timeout: 15000 })
  const row = page.locator('.banks-row').filter({ hasText: bankName }).first()
  await row.waitFor({ state: 'visible', timeout: 15000 })
  await row.locator('.btn-sm').first().click()
  const panel = page.locator('[data-testid="start-study-panel"]')
  await Promise.race([
    page.waitForSelector('.focus-mode', { timeout: 15000 }),
    panel.waitFor({ state: 'visible', timeout: 15000 }),
  ])
  if (await panel.isVisible()) {
    await panel.locator('[data-testid="start-study-continue"]').click()
  }
  await page.waitForSelector('.focus-mode .q-stem', { timeout: 15000 })
}

async function answerOne(page) {
  await page.locator('.opt').first().click()
  await page.locator('.focus-actionbar .btn-primary').click()
  await page.waitForSelector('.verdict-line', { timeout: 10000 })
}

async function exitPractice(page) {
  await page.locator('.focus-exit').click()
  const dialog = page.locator('[data-testid="exit-confirm-modal"]')
  await dialog.waitFor({ state: 'visible', timeout: 8000 })
  await dialog.locator('.btn-primary').click()
  await page.waitForSelector('.focus-mode', { state: 'detached', timeout: 10000 })
}

async function main() {
  fs.mkdirSync(shotDir, { recursive: true })

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'final-accept-'))
  const tempDbPath = path.join(tempDir, 'accept.db')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const baseUrl = `http://127.0.0.1:${port}`

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
        EASYEXAM_SECRET_KEY: 'final-acceptance-secret-key-32-bytes',
      },
      stdio: ['ignore', 'ignore', 'ignore'],
    }
  )

  let browser = null
  try {
    await waitForServer(baseUrl, instanceToken)

    // ------------------------------------------------------- seed the instance
    const stamp = Date.now()
    const adminName = `accept_admin_${stamp}`.slice(0, 40)
    const password = 'Password123!'
    const anon = api(baseUrl)
    const registered = await anon.post('/api/v1/auth/register', { username: adminName, password })
    assert.equal(registered.status, 201, registered.text)
    assert.equal(registered.body.is_admin, true, 'The first account owns the instance')
    const token = (await anon.post('/api/v1/auth/login', { username: adminName, password })).body.token
    const asAdmin = api(baseUrl, token)

    const bankName = `验收题库 ${stamp}`
    const bank = await asAdmin.post('/api/v1/banks', { name: bankName })
    assert.equal(bank.status, 201, bank.text)
    const bankId = bank.body.id

    const questions = [
      { stem: 'Vue 3 的响应式系统默认基于什么机制？', answer: 'A', options: [['A', 'Proxy'], ['B', 'Object.defineProperty'], ['C', '脏检查']] },
      { stem: 'HTTP 状态码 404 表示什么？', answer: 'B', options: [['A', '服务器内部错误'], ['B', '资源不存在'], ['C', '请求超时']] },
      { stem: 'SQLite 默认的写入并发模型是什么？', answer: 'A', options: [['A', '单写者'], ['B', '多写者'], ['C', '无锁']] },
    ]
    for (const q of questions) {
      const created = await asAdmin.post(`/api/v1/banks/${bankId}/questions`, {
        stem: q.stem,
        type: 'SINGLE',
        answer: q.answer,
        options: q.options.map(([key, content]) => ({ key, content })),
      })
      assert.equal(created.status, 201, created.text)
    }

    browser = await chromium.launch({ headless: true })

    for (const viewport of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        isMobile: !!viewport.isMobile,
        hasTouch: !!viewport.hasTouch,
      })
      const page = await context.newPage()
      page.__baseUrl = baseUrl
      page.on('dialog', async dialog => {
        failures.push(`${viewport.name}: native ${dialog.type()} dialog appeared: ${dialog.message()}`)
        await dialog.dismiss().catch(() => {})
      })
      page.on('pageerror', err => {
        failures.push(`${viewport.name}: uncaught page error: ${err.message}`)
      })

      await login(page, baseUrl, adminName, password)
      await visit(page, viewport.name, 'home', '/', '.today')
      await visit(page, viewport.name, 'banks', '/banks', '.banks-page')
      await visit(page, viewport.name, 'bank-workspace', `/banks/${bankId}`, '.manage-page')
      await visit(page, viewport.name, 'review', '/review?source=all', '.review-page')
      // /mistakes is a redirect into the review workspace's mistakes tab.
      await visit(page, viewport.name, 'mistakes', '/review?tab=mistakes', '.review-page')
      await visit(page, viewport.name, 'notes', '/notes', '.notes-page')
      await visit(page, viewport.name, 'settings', '/settings?section=ai', '.settings-section')
      await visit(page, viewport.name, 'exams', '/exams', '.exam-center')

      // The core loop: start a session from the bank list, answer, read the
      // verdict, leave. This is the flow the whole redesign exists to protect.
      await startPractice(page, bankName)
      await page.screenshot({
        path: path.join(shotDir, `${viewport.name}-practice-question.png`),
      })
      shots.push(path.join(shotDir, `${viewport.name}-practice-question.png`))
      await answerOne(page)
      assert.ok(await page.locator('.verdict-line').isVisible())
      await page.screenshot({
        path: path.join(shotDir, `${viewport.name}-practice-verdict.png`),
      })
      shots.push(path.join(shotDir, `${viewport.name}-practice-verdict.png`))
      await exitPractice(page)

      if (viewport.name === 'desktop-1280') {
        await visit(page, viewport.name, 'instance', '/instance', '.instance-admin-page')
      }

      await context.close()
    }

    if (failures.length) {
      throw new Error(`Acceptance failures:\n${failures.join('\n')}`)
    }
    console.log(`\nAcceptance walkthrough passed at ${VIEWPORTS.map(v => v.width).join(', ')} px.`)
    console.log(`Screenshots (${shots.length}) written to ${shotDir}`)
  } finally {
    if (browser) await browser.close().catch(() => {})
    server.kill()
    await new Promise(resolve => {
      if (server.exitCode !== null) return resolve()
      server.once('exit', resolve)
      setTimeout(resolve, 3000)
    })
    try {
      fs.rmSync(tempDir, { recursive: true, force: true })
    } catch (_) {}
  }
}

main().then(
  () => process.exit(0),
  err => {
    console.error(err)
    process.exit(1)
  }
)
