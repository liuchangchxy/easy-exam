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

test('Bank Management E2E: Editorial Table, Filtering, Edit, Active Exam Lock and 375px', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bank-manage-e2e-'))
  const tempDbPath = path.join(tempDir, 'bank_manage.db')
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
      body: JSON.stringify({ username: 'admin_e2e', password: 'Password123!' }),
    })
    assert.equal(adminRegRes.status, 201)

    const adminLoginRes = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin_e2e', password: 'Password123!' }),
    })
    const adminToken = (await adminLoginRes.json()).token

    const memberRegRes = await fetch(`${BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'member_e2e', password: 'Password123!' }),
    })
    assert.equal(memberRegRes.status, 201)

    const createBankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify({
        name: 'Computer Networks Bank',
        category: 'CS Core',
        description: 'Comprehensive networking exam bank',
      }),
    })
    assert.equal(createBankRes.status, 201)
    const bank = await createBankRes.json()
    const bankId = bank.id

    const addMemberRes = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify({ username: 'member_e2e', role: 'MEMBER' }),
    })
    assert.equal(addMemberRes.status, 201)

    const chapRes = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/chapters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify({ name: 'Transport Layer' }),
    })
    const chapter = await chapRes.json()

    const createQuestion = async payload => {
      const res = await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${adminToken}` },
        body: JSON.stringify(payload),
      })
      assert.equal(res.status, 201)
      return res.json()
    }

    const q1 = await createQuestion({
      stem: 'What layer of the OSI model does IP belong to?',
      type: 'SINGLE',
      options: [{ key: 'A', content: 'Network' }, { key: 'B', content: 'Transport' }],
      answer: 'A',
      explanation: 'IP is network layer (Layer 3).',
      difficulty: 2,
      tags: ['network', 'osi'],
      chapter_id: chapter.id,
    })
    const q2 = await createQuestion({
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
    })
    const q3 = await createQuestion({
      stem: 'Is UDP a connection-oriented protocol?',
      type: 'JUDGE',
      options: [{ key: 'T', content: 'True' }, { key: 'F', content: 'False' }],
      answer: 'F',
      explanation: 'UDP is connectionless.',
      difficulty: 1,
      tags: ['udp', 'basics'],
      chapter_id: chapter.id,
    })

    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN' })
    const page = await context.newPage()
    page.on('dialog', dialog => dialog.accept())

    await page.goto(BASE_URL)
    await page.waitForSelector('.auth-layout', { timeout: 10000 })
    await page.fill('#login-username', 'admin_e2e')
    await page.fill('#login-password', 'Password123!')
    await page.click('.auth-submit')
    await page.waitForSelector('.today', { timeout: 10000 })

    await page.goto(`${BASE_URL}/#/banks/${bankId}/manage`)
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    assert.equal(await page.locator('.mtable-row').count(), 3, 'Management table must list all three questions')
    assert.match(await page.locator('.page-title').innerText(), /Computer Networks Bank/)

    await page.locator('.manage-toolbar .input').fill('UDP')
    await page.waitForTimeout(250)
    assert.equal(await page.locator('.mtable-row').count(), 1, 'Keyword search must narrow the table')
    assert.match(await page.locator('.mtable-row').first().innerText(), /UDP/)

    await page.locator('.manage-toolbar .btn-quiet').click()
    await page.waitForTimeout(250)
    assert.equal(await page.locator('.mtable-row').count(), 3)

    await page.locator('.manage-toolbar select').first().selectOption('JUDGE')
    await page.waitForTimeout(250)
    assert.equal(await page.locator('.mtable-row').count(), 1, 'Type filter must isolate JUDGE questions')
    assert.match(await page.locator('.mtable-row').first().innerText(), /UDP/)
    await page.locator('.manage-toolbar .btn-quiet').click()
    await page.waitForTimeout(250)

    const q3Row = page.locator('.mtable-row').filter({ hasText: 'Is UDP a connection-oriented protocol?' }).first()
    await q3Row.locator('[data-testid="row-edit"]').click()
    await page.waitForSelector('.question-edit-dialog', { timeout: 5000 })
    await page.locator('#edit-stem').fill('Is UDP a connectionless protocol?')
    await page.locator('.btn-submit-edit').click()
    await page.waitForSelector('.notice.ok.manage-notice', { timeout: 8000 })
    await page.waitForSelector('.mtable-row:has-text("Is UDP a connectionless protocol?")', { timeout: 8000 })
    const versionText = await page.locator('.mtable-row:has-text("Is UDP a connectionless protocol?")').innerText()
    assert.match(versionText, /v2/, 'Edited question must advance to version 2')

    await page.reload()
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    await page.waitForSelector('.mtable-row:has-text("Is UDP a connectionless protocol?")', { timeout: 10000 })
    console.log('✓ Verified table, search, type filter and versioned inline edit.')

    const memberLoginRes = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'member_e2e', password: 'Password123!' }),
    })
    const memberToken = (await memberLoginRes.json()).token
    const examRes = await fetch(`${BASE_URL}/api/v1/practice/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${memberToken}` },
      body: JSON.stringify({ bank_id: bankId, mode: 'EXAM', total_questions: 1, question_ids: [q1.id] }),
    })
    assert.equal(examRes.status, 201)
    const examSession = await examRes.json()

    await page.reload()
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    const lockNotice = page.locator('.notice.warn.manage-notice')
    await lockNotice.waitFor({ state: 'visible', timeout: 10000 })
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    assert.match(await lockNotice.innerText(), /模考/)
    assert.ok(await page.locator('.mtable-row .tag.warn').count() > 0, 'Locked questions must carry an active-exam tag')

    await page.locator('.mtable-row').filter({ hasText: 'Is UDP a connectionless protocol?' }).first().locator('[data-testid="row-edit"]').click()
    await page.waitForSelector('.question-edit-dialog', { timeout: 5000 })
    assert.equal(await page.locator('#edit-stem').isDisabled(), true, 'Active exam must force read-only editing')
    assert.equal(await page.locator('.btn-submit-edit').count(), 0, 'Read-only modal must not expose save')
    await page.locator('.question-edit-dialog .modal-footer .btn').first().click()
    await page.waitForSelector('.question-edit-dialog', { state: 'detached', timeout: 5000 })

    const completeExam = await fetch(`${BASE_URL}/api/v1/practice/sessions/${examSession.id}/complete`, {
      method: 'POST', headers: { Authorization: `Bearer ${memberToken}` },
    })
    assert.equal(completeExam.status, 200)

    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`${BASE_URL}/#/banks/${bankId}/manage`)
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    const mobile = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
      tableWidth: document.querySelector('.mtable-wrap')?.getBoundingClientRect().width || 0,
      titleWidth: document.querySelector('.page-title')?.getBoundingClientRect().width || 0,
    }))
    assert.ok(mobile.scrollWidth <= mobile.innerWidth + 1, 'Manage page must not overflow horizontally at 375px')
    assert.ok(mobile.tableWidth > 0 && mobile.titleWidth > 0)
    console.log('✓ Verified active-exam read-only lock and 375px management layout.')

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
