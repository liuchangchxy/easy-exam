// Navigation contract acceptance (P1): back is history-first, every page
// survives a refresh, and list state lives in the URL. Runs against a real
// FastAPI instance and a real Chromium, because these are exactly the paths
// component tests cannot prove (document reload, hash history, deep links).
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

const hash = locatorPage => locatorPage.evaluate(() => location.hash)

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'navigation-contract-'))
  const tempDbPath = path.join(tempDir, 'navigation.db')
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
        EASYEXAM_SECRET_KEY: 'navigation-contract-secret-key-32b',
      },
      stdio: ['ignore', 'ignore', 'ignore'],
    }
  )

  let browser = null
  try {
    await waitForServer(baseUrl, instanceToken)

    const username = `nav_contract_${Date.now()}`
    const password = 'Password123!'
    const regRes = await fetch(`${baseUrl}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    assert.equal(regRes.status, 201, 'User registration must succeed')

    const loginData = await (await fetch(`${baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })).json()
    const token = loginData.token

    const bank = await (await fetch(`${baseUrl}/api/v1/banks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: '导航验收题库', description: 'navigation contract' }),
    })).json()
    const question = await (await fetch(`${baseUrl}/api/v1/banks/${bank.id}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        stem: '导航契约样题？',
        type: 'SINGLE',
        options: [{ key: 'A', content: '甲' }, { key: 'B', content: '乙' }],
        answer: 'A',
        explanation: '甲',
        difficulty: 1,
      }),
    })).json()

    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    await login(page, baseUrl, username, password)

    // --- 1. Deep link: a fresh document has no in-app history, so back falls
    // back to the list and says so. ---
    const deepPage = await context.newPage()
    await deepPage.goto(`${baseUrl}/#/banks/${bank.id}`)
    await deepPage.waitForSelector('.manage-page', { timeout: 15000 })
    // The shell loads the bank list on its own; the crumb names the bank once
    // that list is in, not on the page's first paint.
    await deepPage.waitForFunction(
      () => document.querySelector('.crumb')?.textContent?.includes('导航验收题库'),
      null,
      { timeout: 8000 }
    )
    const crumb = await deepPage.locator('.crumb').innerText()
    assert.ok(crumb.includes('导航验收题库'), `Breadcrumb must name the bank, got "${crumb}"`)
    await deepPage.waitForFunction(() => document.title.startsWith('导航验收题库'), null, { timeout: 8000 })
    assert.equal(await deepPage.title(), '导航验收题库 · 易考宝', 'Document title must name the page')

    const deepBack = deepPage.locator('[data-testid="page-back"]')
    assert.equal(await deepBack.getAttribute('aria-label'), '返回题库', 'Deep link must announce the fallback destination')
    await deepBack.click()
    await deepPage.waitForSelector('.banks-page', { timeout: 8000 })
    assert.equal(await hash(deepPage), '#/banks', 'Fallback back must land on the bank list')
    await deepPage.close()

    // --- 2. In-app history: back returns where the user came from ---
    await page.goto(`${baseUrl}/#/banks`)
    await page.waitForSelector('.banks-page', { timeout: 8000 })
    await page.locator('.banks-row .bank-open').first().click()
    await page.waitForSelector('.manage-page', { timeout: 8000 })
    const historyBack = page.locator('[data-testid="page-back"]')
    assert.equal(await historyBack.getAttribute('aria-label'), '返回', 'In-app history must announce plain "back"')
    await historyBack.click()
    await page.waitForSelector('.banks-page', { timeout: 8000 })
    assert.equal(await hash(page), '#/banks', 'History back must return to the previous app page')

    // --- 2b. The bank workspace keeps its filters, sort and page in the address ---
    await page.goto(`${baseUrl}/#/banks/${bank.id}?q=${encodeURIComponent('样题')}&type=SINGLE&sort=id`)
    await page.waitForSelector('.manage-page .mtable-row', { timeout: 10000 })
    assert.equal(await page.inputValue('.manage-toolbar .search-box input'), '样题', 'Workspace keyword must open from the address')
    assert.equal(await page.inputValue('[data-testid="question-sort"]'), 'id', 'Workspace sort must open from the address')

    await page.reload()
    await page.waitForSelector('.manage-page .mtable-row', { timeout: 12000 })
    assert.equal(await page.inputValue('.manage-toolbar .search-box input'), '样题', 'Workspace keyword must survive a reload')
    assert.equal(await page.inputValue('[data-testid="question-sort"]'), 'id', 'Workspace sort must survive a reload')

    // --- 2c. A question is a page with its own address, not a drawer ---
    const questionPage = await context.newPage()
    await questionPage.goto(`${baseUrl}/#/banks/${bank.id}/q/${question.id}`)
    await questionPage.waitForSelector('.question-page .page-title', { timeout: 15000 })
    const questionCrumb = await questionPage.locator('.crumb').innerText()
    assert.ok(questionCrumb.includes('导航验收题库'), `Question crumb must name the bank, got "${questionCrumb}"`)
    assert.ok(questionCrumb.includes('题目'), `Question crumb must name the question page, got "${questionCrumb}"`)
    assert.ok((await questionPage.title()).includes('题目'), 'Question document title must name the page')
    await questionPage.waitForSelector('.question-page .qp-stem', { timeout: 8000 })
    assert.match(await questionPage.locator('.question-page .qp-stem').innerText(), /导航契约样题/, 'Question page must render the current version')

    // Archiving is a reversible state, not a delete: the same page flips the
    // action and shows the badge without navigation.
    await questionPage.locator('[data-testid="question-archive"]').click()
    await questionPage.waitForSelector('.question-page .tag.bad', { timeout: 8000 })
    assert.equal(await hash(questionPage), `#/banks/${bank.id}/q/${question.id}`, 'Archiving must not navigate away')
    assert.ok(await questionPage.locator('.practice-one-btn').isDisabled(), 'An archived question cannot be practised')
    await questionPage.locator('[data-testid="question-archive"]').click()
    await questionPage.waitForFunction(
      () => !document.querySelector('.question-page .tag.bad'),
      null,
      { timeout: 8000 }
    )

    await questionPage.locator('[data-testid="page-back"]').click()
    await questionPage.waitForSelector('.manage-page', { timeout: 8000 })
    assert.equal(await hash(questionPage), `#/banks/${bank.id}`, 'Question back must land on the bank workspace')
    await questionPage.close()

    // --- 2d. Archived questions leave the working list and come back from it ---
    await page.goto(`${baseUrl}/#/banks/${bank.id}`)
    await page.waitForSelector('.manage-page .mtable-row', { timeout: 10000 })
    await page.locator('.mtable-row [data-testid="row-archive"]').first().click()
    await page.waitForFunction(
      () => document.querySelectorAll('.manage-page .mtable-row').length === 0,
      null,
      { timeout: 8000 }
    )

    await page.goto(`${baseUrl}/#/banks/${bank.id}?archived=1`)
    await page.waitForSelector('.manage-page .mtable-row', { timeout: 10000 })
    const archivedBadges = await page.locator('.manage-page .mtable-row .tag:has-text("归档")').count()
    assert.equal(archivedBadges, 1, 'The archived view must show the archived question with its badge')
    await page.locator('.mtable-row [data-testid="row-archive"]').first().click()
    await page.waitForFunction(
      () => ![...document.querySelectorAll('.manage-page .mtable-row .tag')].some(el => el.textContent.includes('归档')),
      null,
      { timeout: 8000 }
    )
    await page.goto(`${baseUrl}/#/banks/${bank.id}`)
    await page.waitForSelector('.manage-page .mtable-row', { timeout: 10000 })

    // --- 3. Review tab survives reload, and a tab change keeps other filters ---
    await page.goto(`${baseUrl}/#/review?tab=killed&bank=${bank.id}`)
    await page.waitForSelector('.review-page', { timeout: 8000 })
    const reviewTabs = page.locator('.review-page .tabs .tab')
    assert.ok(await reviewTabs.nth(2).evaluate(el => el.classList.contains('is-active')), 'Killed tab must open from the address')
    await page.reload()
    await page.waitForSelector('.review-page', { timeout: 10000 })
    assert.ok(await reviewTabs.nth(2).evaluate(el => el.classList.contains('is-active')), 'Killed tab must survive a reload')

    await reviewTabs.nth(1).click()
    await page.waitForFunction(() => location.hash.includes('tab=mistakes'))
    assert.ok((await hash(page)).includes(`bank=${bank.id}`), 'Changing the tab must keep the bank filter')

    // --- 4. Library search and type filter live in the address ---
    await page.goto(`${baseUrl}/#/notes`)
    await page.waitForSelector('.library-page', { timeout: 8000 })
    await page.fill('.library-page .search-box input', '甲')
    await page.waitForFunction(() => location.hash.includes('q='))
    await page.locator('.library-tabs .tab').nth(2).click()
    await page.waitForFunction(() => location.hash.includes('type='))
    const notesHash = await hash(page)
    assert.ok(notesHash.includes('q=') && notesHash.includes('type=MISTAKE_SUMMARY'), `Library state must be addressable, got ${notesHash}`)

    await page.reload()
    await page.waitForSelector('.library-page', { timeout: 10000 })
    assert.equal(await page.inputValue('.library-page .search-box input'), '甲', 'Search keyword must survive a reload')
    assert.ok(await page.locator('.library-tabs .tab').nth(2).evaluate(el => el.classList.contains('is-active')), 'Type filter must survive a reload')

    await context.close()
    console.log('All navigation contract checks passed.')
  } finally {
    if (browser) await browser.close()
    server.kill()
  }
}

main().catch(error => {
  console.error(error)
  process.exit(1)
})
