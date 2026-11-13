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
const captureDir = path.join(repoRoot, 'docs/screenshots/bank-management-20261112')
fs.mkdirSync(captureDir, { recursive: true })

async function capture(page, name) {
  await page.screenshot({ path: path.join(captureDir, `${name}.png`), fullPage: true })
  console.log(`✓ Captured ${name}.png`)
}

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

test('Bank management completion E2E: multi-bank list, settings, structure, members, imports, questions, recycle bin', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bank-completion-e2e-'))
  const tempDbPath = path.join(tempDir, 'bank_completion.db')
  const port = await getFreePort()
  const BASE_URL = `http://127.0.0.1:${port}`
  const instanceToken = crypto.randomUUID()

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

    const api = async (method, pathname, token, body) => {
      const res = await fetch(`${BASE_URL}/api/v1${pathname}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      })
      return res
    }

    const register = async username => {
      const res = await api('POST', '/auth/register', null, { username, password: 'Password123!' })
      assert.equal(res.status, 201, `register ${username}`)
      const login = await api('POST', '/auth/login', null, { username, password: 'Password123!' })
      return (await login.json()).token
    }

    const adminToken = await register('completion_admin')
    await register('completion_member')

    const bankA = await (await api('POST', '/banks', adminToken, {
      name: 'Alpha Bank', category: 'Alpha', description: 'first bank',
    })).json()
    const bankB = await (await api('POST', '/banks', adminToken, {
      name: 'Beta Bank', category: 'Beta', description: 'second bank',
    })).json()

    await api('POST', `/banks/${bankA.id}/members`, adminToken, { username: 'completion_member', role: 'EDITOR' })

    const rootChapter = await (await api('POST', `/banks/${bankA.id}/chapters`, adminToken, { name: 'Root' })).json()
    const childChapter = await (await api('POST', `/banks/${bankA.id}/chapters`, adminToken, {
      name: 'Child', parent_id: rootChapter.id,
    })).json()

    const createQuestion = async (index, type = 'SINGLE') => {
      const payload = type === 'FILL'
        ? { stem: `Fill question ${index}`, type: 'FILL', options: [], answer: '答案', difficulty: 2, tags: ['alpha'], chapter_id: childChapter.id }
        : {
            stem: `Question number ${index}`,
            type: 'SINGLE',
            options: [{ key: 'A', content: 'one' }, { key: 'B', content: 'two' }],
            answer: 'A',
            explanation: 'because',
            difficulty: (index % 5) + 1,
            tags: ['alpha', `tag-${index % 3}`],
            chapter_id: childChapter.id,
          }
      const res = await api('POST', `/banks/${bankA.id}/questions`, adminToken, payload)
      assert.equal(res.status, 201, 'create question')
      return res.json()
    }

    const questions = []
    for (let i = 1; i <= 31; i += 1) questions.push(await createQuestion(i))
    const fillQuestion = await createQuestion(32, 'FILL')

    browser = await chromium.launch({
      ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
      headless: true,
    })
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'zh-CN', acceptDownloads: true })
    const page = await context.newPage()
    page.on('dialog', dialog => dialog.accept())

    await page.goto(BASE_URL)
    await page.waitForSelector('.auth-layout', { timeout: 10000 })
    await page.fill('#login-username', 'completion_admin')
    await page.fill('#login-password', 'Password123!')
    await page.click('.auth-submit')
    await page.waitForSelector('.today', { timeout: 10000 })

    // ---------------------------------------------------------------- bank list
    await page.goto(`${BASE_URL}/#/banks`)
    await page.waitForSelector('.banks-row', { timeout: 10000 })
    assert.equal(await page.locator('.banks-row').count(), 2, 'both banks must render')
    assert.equal(await page.locator('.banks-row').first().locator('.bank-actions-cell button').count(), 2)
    assert.equal(await page.locator('.banks-row').first().locator('button button').count(), 0)

    await page.locator('[data-testid="bank-sort"]').selectOption('name')
    await page.waitForTimeout(200)
    assert.match(await page.locator('.banks-row').first().innerText(), /Alpha Bank/)

    const betaRow = page.locator('.banks-row').filter({ hasText: 'Beta Bank' }).first()
    await betaRow.locator('[data-testid="bank-menu-trigger"]').click()
    await betaRow.locator('[data-testid="bank-menu"]').getByText('编辑资料').click()
    await page.waitForSelector('#bank-edit-name', { timeout: 5000 })
    await page.locator('#bank-edit-name').fill('Beta Renamed')
    await page.locator('button[form="bank-edit-form"]').click()
    await page.waitForSelector('.banks-row:has-text("Beta Renamed")', { timeout: 8000 })

    const rows = page.locator('.banks-row')
    await rows.nth(0).locator('.bank-select-cell input').check()
    await rows.nth(1).locator('.bank-select-cell input').check()
    await page.waitForSelector('.bank-batch-bar', { timeout: 5000 })
    await page.locator('.bank-batch-bar .input').fill('Unified')
    await page.locator('.bank-batch-bar').getByText('设置分类').click()
    await page.waitForSelector('.banks-row .bank-meta:has-text("Unified")', { timeout: 8000 })

    await page.locator('[data-testid="bank-category-manage"]').click()
    await page.waitForSelector('.category-row', { timeout: 5000 })
    const categoryRow = page.locator('.category-row').first()
    await categoryRow.locator('.input').fill('Renamed Category')
    await categoryRow.getByText('重命名').click()
    await page.waitForSelector('.banks-row .bank-meta:has-text("Renamed Category")', { timeout: 8000 })
    console.log('✓ Bank list menu, rename, batch category and category manager work.')

    // --------------------------------------------------------------- manage page
    await page.goto(`${BASE_URL}/#/banks/${bankA.id}/manage`)
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    assert.equal(await page.locator('.mtable-row').count(), 25, 'client pagination shows the first page')
    assert.match(await page.locator('.mtable-foot').innerText(), /1 \/ 2/)
    await page.locator('.mtable-foot .list-side .btn').last().click()
    await page.waitForTimeout(200)
    assert.equal(await page.locator('.mtable-row').count(), 7, 'second page shows the remaining questions')
    assert.match(await page.locator('.mtable-row').last().innerText(), /Fill question 32/, 'FILL question lands on the second page')

    const pageSize = page.locator('[data-testid="page-size"]')
    assert.equal(await pageSize.count(), 1, 'page-size selector is rendered in the footer')
    await pageSize.selectOption('50')
    await page.waitForTimeout(200)
    assert.equal(await page.locator('.mtable-row').count(), 32, 'page size 50 shows every question on one page')
    assert.match(await page.locator('.mtable-foot').innerText(), /1 \/ 1/)
    await pageSize.selectOption('25')
    await page.waitForTimeout(200)

    // Import after the pagination checks so the bank holds exactly 32 questions
    // for these assertions; later loadData() calls surface the job in Imports.
    const importRes = await api('POST', `/imports/banks/${bankA.id}`, adminToken, {
      format: 'text', content: '1. 1+1=?\nA. 1\nB. 2\n【答案】B', duplicate_strategy: 'skip',
    })
    assert.equal(importRes.status, 201, 'text import')

    const search = page.locator('.manage-toolbar .search-box input')
    await search.fill(fillQuestion.id.slice(0, 8))
    await page.waitForTimeout(250)
    assert.equal(await page.locator('.mtable-row').count(), 1, 'id search narrows to one row')
    await page.locator('.manage-toolbar').getByText('清除筛选').click()
    await page.waitForTimeout(250)

    await page.locator('.manage-toolbar select').first().selectOption('FILL')
    await page.waitForTimeout(250)
    assert.equal(await page.locator('.mtable-row').count(), 1, 'FILL filter isolates the fill question')
    assert.match(await page.locator('.mtable-row').first().innerText(), /Fill question 32/)
    await page.locator('.manage-toolbar').getByText('清除筛选').click()
    await page.waitForTimeout(250)

    await search.fill(questions[0].id.slice(0, 8))
    await page.waitForTimeout(300)
    assert.equal(await page.locator('.mtable-row').count(), 1)
    await page.locator('.mtable-row [data-testid="row-archive"]').click()
    await page.waitForTimeout(500)
    assert.equal(await page.locator('.mtable-row').count(), 0, 'archived question leaves the default view')
    await page.locator('[data-testid="show-archived"]').check()
    await page.waitForTimeout(500)
    assert.equal(await page.locator('.mtable-row').count(), 1)
    await page.locator('.mtable-row [data-testid="row-archive"]').click()
    await page.waitForTimeout(500)
    assert.equal(await page.locator('.mtable-row .tag:has-text("已归档")').count(), 0, 'restored question is active again')
    await page.locator('[data-testid="show-archived"]').uncheck()
    await page.waitForTimeout(500)
    await page.locator('.manage-toolbar').getByText('清除筛选').click()
    await page.waitForTimeout(300)

    // Settings: update metadata, verify audit list, export a download.
    await page.locator('.manage-tabs .tab').nth(5).click()
    await page.waitForSelector('.settings-form', { timeout: 5000 })
    assert.match(page.url(), /[?&]tab=settings/, 'active tab is reflected in the URL query')
    await page.locator('.settings-form .input').first().fill('Alpha Updated')
    await page.locator('.settings-form button[type="submit"]').click()
    await page.waitForSelector('.audit-row[data-action="BANK_UPDATED"]', { timeout: 8000 })
    assert.match(
      await page.locator('.audit-row[data-action="BANK_UPDATED"]').first().innerText(),
      /题库已更新/,
      'audit action enums render as localised labels',
    )
    assert.match(await page.locator('.page-title').innerText(), /Alpha Updated/)
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 8000 }),
      page.locator('[data-testid="export-json"]').click(),
    ])
    assert.match(download.suggestedFilename(), /\.json$/)
    console.log('✓ Pagination, id search, FILL filter, single archive/restore, settings, audit and export work.')

    // Structure: add a second root, move it, rename a tag.
    await page.locator('.manage-tabs .tab').nth(1).click()
    await page.waitForSelector('.chapter-row', { timeout: 5000 })
    assert.equal(await page.locator('.chapter-row').count(), 2)
    await page.locator('.chapter-add .input[placeholder="章节名称"]').fill('Second Root')
    await page.getByRole('button', { name: '新增章节' }).click()
    await page.waitForTimeout(400)
    assert.equal(await page.locator('.chapter-row').count(), 3)
    const secondRoot = page.locator('.chapter-row').filter({ hasText: 'Second Root' }).first()
    await secondRoot.getByText('上移').click()
    await page.waitForTimeout(400)
    assert.match(await page.locator('.chapter-row').first().innerText(), /Second Root/)

    const tagRow = page.locator('.tag-row').first()
    await tagRow.getByText('重命名').click()
    await tagRow.locator('input.tag-row-input').fill('renamed-tag')
    await tagRow.locator('[data-testid="tag-save"]').click()
    await page.waitForTimeout(500)
    const tagValues = await page.locator('.tag-row .tag-name').allInnerTexts()
    assert.ok(tagValues.includes('renamed-tag'), `tag rename must persist, got ${tagValues.join(', ')}`)
    console.log('✓ Chapter tree add/move and tag rename work.')

    // Members: role change + leave visibility.
    await page.locator('.manage-tabs .tab').nth(2).click()
    await page.waitForSelector('.member-actions select', { timeout: 5000 })
    await page.locator('.member-actions select').selectOption('MEMBER')
    await page.waitForTimeout(500)
    const members = await (await api('GET', `/banks/${bankA.id}/members`, adminToken)).json()
    const member = members.find(item => item.username === 'completion_member')
    assert.equal(member.role, 'MEMBER')
    assert.equal(await page.locator('.member-leave').count(), 0, 'owner cannot leave')
    console.log('✓ Member role change persists and owner cannot leave.')

    // Imports: job history table.
    await page.locator('.manage-tabs .tab').nth(3).click()
    await page.waitForSelector('.import-table', { timeout: 5000 })
    const importedTag = page.locator('.import-table [data-status="IMPORTED"]')
    assert.equal(await importedTag.count(), 1, 'imported job keeps its status for styling')
    assert.match(await importedTag.first().innerText(), /已导入/, 'import status renders as a localised label')
    assert.match(await page.locator('.import-table').innerText(), /text/)
    console.log('✓ Import history table lists real jobs.')

    // Danger zone → recycle bin → restore.
    await page.locator('.manage-tabs .tab').nth(5).click()
    await page.waitForSelector('[data-testid="bank-archive"]', { timeout: 5000 })
    await page.locator('[data-testid="bank-archive"]').click()
    await page.waitForSelector('.banks-row', { timeout: 10000 })
    assert.equal(await page.locator('.banks-row:has-text("Alpha Updated")').count(), 0, 'archived bank leaves the list')

    await page.locator('[data-testid="bank-recycle-toggle"]').click()
    await page.waitForSelector('.banks-row:has-text("Alpha Updated")', { timeout: 8000 })
    const recycled = page.locator('.banks-row').filter({ hasText: 'Alpha Updated' }).first()
    await recycled.locator('[data-testid="row-restore"]').click()
    await page.waitForTimeout(500)
    assert.equal(await page.locator('.banks-row:has-text("Alpha Updated")').count(), 0, 'restored bank leaves the recycle bin')
    await page.locator('[data-testid="bank-recycle-toggle"]').click()
    await page.waitForSelector('.banks-row:has-text("Alpha Updated")', { timeout: 8000 })
    console.log('✓ Archive, recycle bin listing and restore work.')

    // --------------------------------------------------------- 1280px evidence
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto(`${BASE_URL}/#/banks`)
    await page.waitForSelector('.banks-row', { timeout: 10000 })
    await capture(page, '1280-bank-list')

    await page.goto(`${BASE_URL}/#/banks/${bankA.id}/manage`)
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    await capture(page, '1280-manage-questions')
    await page.locator('.manage-tabs .tab').nth(1).click()
    await page.waitForSelector('.chapter-row', { timeout: 5000 })
    await capture(page, '1280-manage-structure')
    await page.locator('.manage-tabs .tab').nth(5).click()
    await page.waitForSelector('.settings-form', { timeout: 5000 })
    await capture(page, '1280-manage-settings')

    // --------------------------------------------------------------- 375px
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`${BASE_URL}/#/banks`)
    await page.waitForSelector('.banks-row', { timeout: 10000 })
    const listOverflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }))
    assert.ok(listOverflow.scrollWidth <= listOverflow.innerWidth + 1, 'bank list must not overflow at 375px')
    await capture(page, '375-bank-list')

    await page.goto(`${BASE_URL}/#/banks/${bankA.id}/manage`)
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    await page.locator('.manage-tabs .tab').first().click()
    await page.waitForSelector('.mtable-row', { timeout: 10000 })
    const manageOverflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }))
    assert.ok(manageOverflow.scrollWidth <= manageOverflow.innerWidth + 1, 'manage page must not overflow at 375px')
    const tallTargets = await page.evaluate(() => [...document.querySelectorAll('.manage-tabs .tab')]
      .map(el => el.getBoundingClientRect().height)
      .filter(height => height > 0 && height < 24))
    assert.deepEqual(tallTargets, [], 'tab touch targets stay at least 24px high')
    await capture(page, '375-manage-questions')
    console.log('✓ 375px list and manage layouts have no horizontal overflow.')
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
