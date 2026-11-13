import test from 'node:test'
import assert from 'node:assert/strict'
import { spawn, execSync } from 'node:child_process'
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

test('Bank Batch E2E: select, batch chapter, copy, archive and restore', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bank-batch-e2e-'))
  const tempDbPath = path.join(tempDir, 'bank_batch.db')
  const port = await getFreePort()
  const BASE_URL = `http://127.0.0.1:${port}`
  const instanceToken = crypto.randomUUID()

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
        INSTANCE_TOKEN: instanceToken,
        EASYEXAM_SECRET_KEY: 'e2e-secret-key-32bytes-ci-safe!!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  let browser = null
  try {
    await waitForServer(BASE_URL)
    console.log('[E2E] Backend server healthy.')

    const adminRegRes = await fetch(`${BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin_batch', password: 'Password123!' }),
    })
    assert.equal(adminRegRes.status, 201)

    const adminLoginRes = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin_batch', password: 'Password123!' }),
    })
    const adminToken = (await adminLoginRes.json()).token
    const authHeaders = { 'Content-Type': 'application/json', Authorization: `Bearer ${adminToken}` }

    const createBank = async name => {
      const res = await fetch(`${BASE_URL}/api/v1/banks`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ name, category: 'CS Core', description: `${name} description` }),
      })
      assert.equal(res.status, 201)
      return res.json()
    }

    const bank = await createBank('Batch Source Bank')
    const targetBank = await createBank('Batch Target Bank')

    const chapterRes = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/chapters`, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify({ name: 'Alpha Chapter' }),
    })
    assert.equal(chapterRes.status, 201)
    const chapter = await chapterRes.json()

    const createQuestion = async (payload) => {
      const res = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/questions`, {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify(payload),
      })
      assert.equal(res.status, 201)
      return res.json()
    }

    const q1 = await createQuestion({
      stem: 'Which layer does IP belong to?',
      type: 'SINGLE',
      options: [{ key: 'A', content: 'Network' }, { key: 'B', content: 'Transport' }],
      answer: 'A',
      explanation: 'IP is layer 3.',
      difficulty: 2,
      tags: ['network'],
    })
    const q2 = await createQuestion({
      stem: 'Which protocols use TCP?',
      type: 'MULTI',
      options: [{ key: 'A', content: 'HTTP' }, { key: 'B', content: 'FTP' }, { key: 'C', content: 'UDP' }],
      answer: 'AB',
      explanation: 'HTTP and FTP use TCP.',
      difficulty: 3,
      tags: ['protocol'],
    })
    const q3 = await createQuestion({
      stem: 'Is UDP connection oriented?',
      type: 'JUDGE',
      options: [{ key: 'T', content: 'True' }, { key: 'F', content: 'False' }],
      answer: 'F',
      explanation: 'UDP is connectionless.',
      difficulty: 1,
      tags: ['udp'],
    })

    const contentRes = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    assert.equal(contentRes.status, 200)
    const beforeBatch = await contentRes.json()
    assert.equal(beforeBatch.length, 3)

    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' })
    const page = await context.newPage()
    page.on('dialog', dialog => dialog.accept())

    await page.goto(BASE_URL)
    await page.waitForSelector('.auth-layout', { timeout: 10000 })
    await page.fill('#login-username', 'admin_batch')
    await page.fill('#login-password', 'Password123!')
    await page.click('.auth-submit')
    await page.waitForSelector('.today', { timeout: 10000 })

    await page.goto(`${BASE_URL}/#/banks/${bank.id}/manage`)
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    assert.equal(await page.locator('.mtable-row').count(), 3)

    // Select all and confirm the batch bar appears.
    await page.locator('[data-testid="select-all"]').check()
    await page.waitForSelector('.batch-bar', { timeout: 5000 })
    assert.equal(await page.locator('input.row-select:checked').count(), 3, 'Select all must check every visible row')

    // Batch chapter assignment.
    await page.locator('[data-testid="batch-chapter"]').selectOption(chapter.id)
    await page.locator('[data-testid="batch-apply-chapter"]').click()
    await page.waitForSelector('.notice.ok.manage-notice', { timeout: 8000 })
    await page.waitForTimeout(300)

    const afterChapterRes = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    const afterChapter = await afterChapterRes.json()
    assert.ok(
      afterChapter.every(q => q.chapter_id === chapter.id),
      'Every selected question must move into the batch chapter'
    )
    assert.ok(
      afterChapter.every(q => q.version_number === 1),
      'Batch chapter must not bump question versions'
    )

    // Batch copy into another bank.
    await page.locator('[data-testid="select-all"]').check()
    await page.waitForSelector('.batch-bar', { timeout: 5000 })
    await page.locator('[data-testid="batch-target"]').selectOption(targetBank.id)
    await page.locator('[data-testid="batch-copy"]').click()
    await page.waitForSelector('.notice.ok.manage-notice', { timeout: 8000 })
    await page.waitForTimeout(300)

    const targetContentRes = await fetch(`${BASE_URL}/api/v1/banks/${targetBank.id}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    assert.equal(targetContentRes.status, 200)
    const targetContent = await targetContentRes.json()
    assert.equal(targetContent.length, 3, 'Batch copy must clone all three questions into the target bank')

    const sourceAfterCopyRes = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    assert.equal((await sourceAfterCopyRes.json()).length, 3, 'Batch copy must leave the source bank intact')

    // Archive selected questions, then restore them from the archived view.
    await page.locator('[data-testid="select-all"]').check()
    await page.waitForSelector('.batch-bar', { timeout: 5000 })
    await page.locator('[data-testid="batch-archive"]').click()
    await page.waitForTimeout(600)
    await page.waitForFunction(
      () => document.querySelectorAll('.mtable-row').length === 0,
      null,
      { timeout: 8000 }
    )

    const archivedRes = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    assert.equal((await archivedRes.json()).length, 0, 'Archived questions must be hidden from the default content list')

    await page.locator('[data-testid="show-archived"]').check()
    await page.waitForSelector('.mtable-row', { timeout: 8000 })
    assert.equal(await page.locator('.mtable-row').count(), 3)
    assert.equal(await page.locator('.mtable-row .tag:has-text("归档")').count(), 3, 'Archived rows must carry a badge')

    await page.locator('[data-testid="select-all"]').check()
    await page.waitForSelector('.batch-bar', { timeout: 5000 })
    await page.locator('[data-testid="batch-restore"]').click()
    await page.waitForTimeout(800)
    await page.waitForFunction(
      () => ![...document.querySelectorAll('.mtable-row .tag')].some(el => el.textContent.includes('归档')),
      null,
      { timeout: 8000 }
    )

    const restoredRes = await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    const restored = await restoredRes.json()
    assert.equal(restored.length, 3, 'Restore must bring archived questions back')
    assert.ok(restored.every(q => q.archived === false), 'Restored questions must not stay archived')

    await page.locator('[data-testid="show-archived"]').uncheck()
    await page.waitForSelector('.mtable-row', { timeout: 8000 })
    assert.equal(await page.locator('.mtable-row').count(), 3)
    console.log('✓ Verified select-all, batch chapter, copy, archive and restore.')

    // Question page: version history must be reachable and copy must not need a UUID.
    await page.goto(`${BASE_URL}/#/banks/${bank.id}`)
    await page.waitForSelector('.manage-page .mtable-row', { timeout: 10000 })
    await page.locator('.mtable-row .stem-link').first().click()
    await page.waitForSelector('.question-page', { timeout: 8000 })
    await page.waitForSelector('.question-page .version-item', { timeout: 8000 })
    assert.ok((await page.locator('.question-page .version-item').count()) >= 1, 'Question page must expose question version history')

    await page.locator('.question-page .copy-select').selectOption(targetBank.id)
    await page.locator('.question-page .copy-form .btn').click()
    await page.waitForSelector('.question-page .copy-notice', { timeout: 8000 })
    assert.match(await page.locator('.question-page .copy-notice').innerText(), /Batch Target Bank/)

    const targetAfterDetailRes = await fetch(`${BASE_URL}/api/v1/banks/${targetBank.id}/content/questions`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    assert.equal(
      (await targetAfterDetailRes.json()).length,
      4,
      'Copying from the question page must add one question to the target bank'
    )
    console.log('✓ Verified question page version history and UUID-free copy entry.')

    // 375px layout with the batch bar open.
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`${BASE_URL}/#/banks/${bank.id}/manage`)
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    await page.locator('[data-testid="select-all"]').check()
    await page.waitForSelector('.batch-bar', { timeout: 5000 })
    const mobile = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
      batchWidth: document.querySelector('.batch-bar')?.getBoundingClientRect().width || 0,
    }))
    assert.ok(mobile.batchWidth > 0)
    assert.ok(
      mobile.scrollWidth <= mobile.innerWidth + 1,
      `Batch bar must not overflow horizontally at 375px (scrollWidth=${mobile.scrollWidth}, innerWidth=${mobile.innerWidth})`
    )
    console.log('✓ Verified 375px batch bar layout.')

    // 375px overflow guard for the other pages in this ownership area.
    const overflowAt375 = async (hash, readySelector) => {
      await page.goto(`${BASE_URL}/#${hash}`)
      await page.waitForSelector(readySelector, { timeout: 10000 })
      await page.waitForTimeout(300)
      const dims = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
      }))
      assert.ok(
        dims.scrollWidth <= dims.innerWidth + 1,
        `${hash} must not overflow horizontally at 375px (scrollWidth=${dims.scrollWidth}, innerWidth=${dims.innerWidth})`
      )
    }
    await overflowAt375('/banks', '.banks-page')
    await overflowAt375(`/banks/${bank.id}`, '.mtable-row')
    await overflowAt375('/import', '.import-page')
    console.log('✓ Verified 375px layout for banks, bank detail and import pages.')

    console.log(`[E2E] Covered questions ${q1.id}, ${q2.id}, ${q3.id}.`)
  } finally {
    if (browser) await browser.close().catch(() => {})
    if (serverProcess && serverProcess.pid) {
      try {
        execSync(`taskkill /pid ${serverProcess.pid} /T /F`, { stdio: 'ignore' })
      } catch (_) {
        serverProcess.kill('SIGKILL')
      }
    }
    if (tempDbPath && fs.existsSync(tempDbPath)) {
      try {
        fs.rmSync(path.dirname(tempDbPath), { recursive: true, force: true })
      } catch (_) {}
    }
  }
})
