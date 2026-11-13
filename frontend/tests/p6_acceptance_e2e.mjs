// P6 acceptance: the responsive, touch, dialog, toast and keyboard promises.
//
// P6 is the "it works in the hand" phase. This drives the built app in a real
// Chromium against a fresh server/database and proves: no page scrolls
// sideways at phone/tablet/desktop widths, coarse-pointer controls are 44px or
// carry an expanded hit area, destructive confirms go through the editorial app
// dialog instead of window.confirm, transient saves surface a real toast, the
// practice bar consumes --kb-inset, and the shared start panel stops a second
// practice session from being stacked on top of an unfinished one.
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
  const expectedFingerprint = expectedToken
    ? crypto.createHash('sha256').update(expectedToken).digest('hex').slice(0, 16)
    : ''
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${url}/api/v1/health`)
      if (res.ok) {
        const body = await res.json()
        if (expectedFingerprint && body.instance_fingerprint !== expectedFingerprint) {
          throw new Error(`Instance fingerprint mismatch: expected ${expectedFingerprint} but got ${body.instance_fingerprint}`)
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
    put: (url, body) => call('PUT', url, body),
    del: url => call('DELETE', url),
  }
}

async function waitUntil(check, label, timeoutMs = 10000, intervalMs = 150) {
  const start = Date.now()
  let last
  while (Date.now() - start < timeoutMs) {
    try {
      last = await check()
      if (last) return last
    } catch (err) {
      last = err
    }
    await new Promise(r => setTimeout(r, intervalMs))
  }
  throw new Error(`${label} did not happen within ${timeoutMs}ms${last instanceof Error ? `: ${last.message}` : ''}`)
}

async function assertNoSidewaysScroll(page, label) {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }))
  assert.ok(
    scrollWidth <= innerWidth + 1,
    `${label}: page scrolls sideways (documentElement.scrollWidth=${scrollWidth}, innerWidth=${innerWidth})`
  )
}

// A rendered target passes when it is at least 44x44, or when its ::after hit
// area is. Icon-only controls legitimately use the latter (style.css @media
// (pointer: coarse) grows an invisible 44px ::after box).
async function measureHitTargets(page, selector, label) {
  const boxes = await page.$$eval(selector, (els) => els.map((el) => {
    const rect = el.getBoundingClientRect()
    const style = getComputedStyle(el)
    const after = getComputedStyle(el, '::after')
    return {
      width: rect.width,
      height: rect.height,
      afterWidth: Number.parseFloat(after.width) || 0,
      afterHeight: Number.parseFloat(after.height) || 0,
      visible: rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden',
      text: (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 24),
    }
  }).filter(box => box.visible))

  assert.ok(boxes.length > 0, `${label}: no visible targets matched "${selector}"`)
  for (const box of boxes) {
    const wide = box.width >= 44 || box.afterWidth >= 44
    const tall = box.height >= 44 || box.afterHeight >= 44
    assert.ok(
      wide && tall,
      `${label}: "${box.text}" is ${box.width.toFixed(1)}x${box.height.toFixed(1)} ` +
      `(::after ${box.afterWidth}x${box.afterHeight}) — expected >=44 or an expanded hit area`
    )
  }
  return boxes.length
}

async function main() {
  const runStarted = Date.now()
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'p6-acceptance-'))
  const tempDbPath = path.join(tempDir, 'p6.db')
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
        EASYEXAM_SECRET_KEY: 'p6-acceptance-secret-key-32-bytes',
      },
      stdio: ['ignore', 'ignore', 'ignore'],
    }
  )

  let browser = null
  try {
    await waitForServer(baseUrl, instanceToken)

    const stamp = Date.now()
    const username = `p6_user_${stamp}`.slice(0, 40)
    const password = 'Password123!'
    const mainBankName = `P6 主题库 ${stamp}`
    const archiveBankName = `P6 待归档题库 ${stamp}`
    const anon = api(baseUrl)

    // ------------------------------------------------------- seed through API
    const registration = await anon.post('/api/v1/auth/register', { username, password })
    assert.equal(registration.status, 201, registration.text)
    const ownerToken = (await anon.post('/api/v1/auth/login', { username, password })).body.token
    assert.ok(ownerToken, 'Login must return a token')
    const asOwner = api(baseUrl, ownerToken)

    const mainBank = await asOwner.post('/api/v1/banks', { name: mainBankName })
    assert.equal(mainBank.status, 201, mainBank.text)
    const mainBankId = mainBank.body.id

    for (let i = 1; i <= 3; i += 1) {
      const question = await asOwner.post(`/api/v1/banks/${mainBankId}/questions`, {
        stem: `P6 移动端验收题 ${i}：三个选项里选一个`,
        type: 'SINGLE',
        answer: 'A',
        options: [
          { key: 'A', content: '选项甲' },
          { key: 'B', content: '选项乙' },
          { key: 'C', content: '选项丙' },
        ],
      })
      assert.equal(question.status, 201, question.text)
    }

    const archiveBank = await asOwner.post('/api/v1/banks', { name: archiveBankName })
    assert.equal(archiveBank.status, 201, archiveBank.text)
    const archiveBankId = archiveBank.body.id

    // One active practice session exists for sections 1, 5 and 6. It is seeded
    // directly so the start-panel test can prove a row click is *blocked* by it.
    const practice = await asOwner.post('/api/v1/practice/sessions', {
      bank_id: mainBankId,
      mode: 'PRACTICE',
    })
    assert.equal(practice.status, 201, practice.text)
    const practiceSessionId = practice.body.id
    assert.ok(practiceSessionId, 'A practice session id is required')

    // ------------------------------------------------------- browser: desktop
    browser = await chromium.launch({ headless: true })
    const desktop = await browser.newContext({ viewport: { width: 1280, height: 900 } })
    const page = await desktop.newPage()
    await login(page, baseUrl, username, password)

    // ------------------------------------------------- 1. responsive layouts
    const viewports = [
      { width: 375, height: 812, label: '375x812' },
      { width: 768, height: 1024, label: '768x1024' },
      { width: 1280, height: 900, label: '1280x900' },
    ]
    const routes = [
      { url: '/#/', root: '.today', label: 'today' },
      { url: '/#/banks', root: '.banks-page', label: 'banks' },
      { url: `/#/banks/${mainBankId}`, root: '.manage-page', label: 'bank workspace' },
      { url: '/#/review?source=all', root: '.review-page', label: 'review' },
      { url: '/#/settings', root: '.settings-page', label: 'settings' },
      { url: `/#/practice/${practiceSessionId}`, root: '.focus-mode', label: 'practice focus' },
    ]

    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height })
      await page.waitForTimeout(120)
      for (const route of routes) {
        await page.goto(`${baseUrl}${route.url}`)
        await page.waitForSelector(route.root, { timeout: 15000 })
        if (route.label === 'practice focus') {
          await page.waitForSelector('.focus-actionbar', { timeout: 15000 })
        }
        if (route.label === 'bank workspace') {
          // The question table is allowed to be wider than the page only if it
          // owns the scroll: the wrapper must exist and be the scroller.
          await page.waitForSelector('.mtable-wrap', { timeout: 15000 })
          const overflow = await page.locator('.mtable-wrap').first().evaluate(
            el => getComputedStyle(el).overflowX
          )
          assert.equal(overflow, 'auto', `${route.label} @ ${viewport.label}: the table wrapper must scroll, not the page`)
        }
        await page.waitForTimeout(60)
        await assertNoSidewaysScroll(page, `${route.label} @ ${viewport.label}`)
      }
    }
    console.log('✓ 1. No sideways page scroll at 375/768/1280; wide tables scroll inside .mtable-wrap.')
    await page.goto(`${baseUrl}/#/banks`)
    await page.waitForSelector('.banks-page')

    // ------------------------------------------------- 2. touch targets @375
    const mobile = await browser.newContext({
      viewport: { width: 375, height: 812 },
      hasTouch: true,
      isMobile: true,
      storageState: await desktop.storageState(),
    })
    const mobilePage = await mobile.newPage()

    await mobilePage.goto(`${baseUrl}/#/banks`)
    await mobilePage.waitForSelector('.banks-page', { timeout: 15000 })
    await mobilePage.waitForSelector('.bottomnav .bn-item', { timeout: 10000 })
    const navTargets = await measureHitTargets(mobilePage, '.bottomnav .bn-item', 'bottom navigation')

    await mobilePage.goto(`${baseUrl}/#/practice/${practiceSessionId}`)
    await mobilePage.waitForSelector('.focus-actionbar', { timeout: 15000 })
    const barTargets = await measureHitTargets(mobilePage, '.focus-actionbar .btn', 'practice action bar')

    // The exam answer cells are cheap: start an exam session, open its mobile
    // answer-sheet drawer and measure the numbered cells.
    const exam = await asOwner.post('/api/v1/practice/sessions', {
      bank_id: mainBankId,
      mode: 'EXAM',
    })
    assert.equal(exam.status, 201, exam.text)
    const examSessionId = exam.body.id
    await mobilePage.goto(`${baseUrl}/#/exam/${examSessionId}`)
    await mobilePage.waitForSelector('.exam-mode', { timeout: 15000 })
    // The trigger only renders once the session/question finished loading.
    await mobilePage.waitForSelector('.exam-sheet-trigger', { state: 'visible', timeout: 15000 })
    await mobilePage.locator('.exam-sheet-trigger').click()
    await mobilePage.waitForSelector('.exam-sheet-drawer .answer-cell', { state: 'visible', timeout: 10000 })
    const answerTargets = await measureHitTargets(
      mobilePage,
      '.exam-sheet-drawer .answer-cell',
      'exam answer cells'
    )
    // Leave no stray EXAM session blocking later bank mutations.
    await asOwner.post(`/api/v1/practice/sessions/${examSessionId}/abandon`)
    await mobile.close()
    console.log(`✓ 2. Touch targets >=44 at 375 (${navTargets} nav, ${barTargets} action-bar, ${answerTargets} exam cells).`)

    // ------------------------------------------- 3. app dialog, never native
    let nativeDialogSeen = null
    page.on('dialog', async (dialog) => {
      nativeDialogSeen = dialog.message()
      await dialog.dismiss().catch(() => {})
    })

    const activeBankIds = async () => {
      const res = await asOwner.get('/api/v1/banks')
      assert.equal(res.status, 200, res.text)
      return (res.body || []).map(row => row.id)
    }

    await page.goto(`${baseUrl}/#/banks`)
    await page.waitForSelector('.banks-page', { timeout: 15000 })
    const archiveRow = page.locator('.banks-row').filter({ hasText: archiveBankName }).first()
    await archiveRow.waitFor({ state: 'visible', timeout: 10000 })
    await archiveRow.locator('.bank-select-cell input[type="checkbox"]').check()
    const batchArchive = page.locator('[data-testid="bank-batch-archive"]')
    await batchArchive.waitFor({ state: 'visible', timeout: 8000 })
    await batchArchive.click()

    const confirmPanel = page.locator('.app-dialog-panel[data-testid="confirm-dialog"]')
    await confirmPanel.waitFor({ state: 'visible', timeout: 8000 })
    assert.equal(await page.locator('.app-dialog-panel.confirm-dialog').count(), 1, 'Confirm must render the app dialog')
    await page.locator('[data-testid="confirm-cancel"]').click()
    await confirmPanel.waitFor({ state: 'detached', timeout: 8000 })
    assert.equal(nativeDialogSeen, null, `A native window.confirm/alert appeared: ${nativeDialogSeen}`)
    assert.ok((await activeBankIds()).includes(archiveBankId), 'Cancelling the app dialog must not archive the bank')

    await batchArchive.click()
    await confirmPanel.waitFor({ state: 'visible', timeout: 8000 })
    await page.locator('[data-testid="confirm-ok"]').click()
    await waitUntil(
      async () => !(await activeBankIds()).includes(archiveBankId),
      'batch archive through the app confirm',
      10000
    )
    const deleted = await asOwner.get('/api/v1/banks?deleted=1')
    assert.equal(deleted.status, 200, deleted.text)
    assert.ok((deleted.body || []).some(row => row.id === archiveBankId), 'Archived bank belongs in the recycle list')
    assert.equal(nativeDialogSeen, null, `A native window.confirm/alert appeared: ${nativeDialogSeen}`)
    console.log('✓ 3. Destructive batch-archive uses .app-dialog-panel; cancel keeps data, confirm archives.')

    // --------------------------------------------------------- 4. toast channel
    await page.goto(`${baseUrl}/#/settings?section=ai`)
    await page.waitForSelector('[data-testid="ai-test"]', { timeout: 10000 })
    const modelInput = page.locator('.settings-section input[placeholder="gpt-4o-mini"]')
    await modelInput.waitFor({ state: 'visible', timeout: 10000 })
    const savedModel = `p6-toast-${stamp}`
    await modelInput.fill(savedModel)
    await modelInput.blur()

    const toast = page.locator('#toast-root .toast[role="status"]')
    await toast.waitFor({ state: 'visible', timeout: 8000 })
    assert.ok(
      await toast.evaluate(el => Boolean(el.closest('#toast-root'))),
      'The toast must live inside #toast-root'
    )
    await waitUntil(
      async () => {
        const config = await asOwner.get('/api/v1/ai/config')
        return config.body?.ai_model === savedModel
      },
      'saved AI model to persist',
      8000
    )
    const toastShownAt = Date.now()
    await toast.waitFor({ state: 'detached', timeout: 6000 })
    const toastLifetime = Date.now() - toastShownAt
    assert.ok(toastLifetime < 6000, `Toast stayed visible for ${toastLifetime}ms (expected < 6000ms)`)
    console.log(`✓ 4. A persisted settings save shows a role="status" toast and it leaves in ${toastLifetime}ms.`)

    // --------------------------------------------------- 5. keyboard inset
    await page.goto(`${baseUrl}/#/practice/${practiceSessionId}`)
    await page.waitForSelector('.focus-actionbar', { timeout: 15000 })
    const insetAtRest = await page.evaluate(
      () => getComputedStyle(document.documentElement).getPropertyValue('--kb-inset').trim()
    )
    assert.equal(insetAtRest, '0px', `--kb-inset must be present and 0px at rest, saw "${insetAtRest}"`)

    const readBar = () => page.evaluate(() => {
      const bar = document.querySelector('.focus-actionbar')
      const style = getComputedStyle(bar)
      const rect = bar.getBoundingClientRect()
      return {
        bottom: style.bottom,
        paddingBottom: style.paddingBottom,
        rectBottom: rect.bottom,
        innerHeight: window.innerHeight,
        inset: getComputedStyle(document.documentElement).getPropertyValue('--kb-inset').trim(),
      }
    })
    const barAtRest = await readBar()
    const basePadding = Number.parseFloat(barAtRest.paddingBottom)
    assert.ok(basePadding > 0, 'The action bar must already carry a non-zero safe-area/base padding-bottom')

    const barAt120 = await page.evaluate(() => {
      document.documentElement.style.setProperty('--kb-inset', '120px')
      const bar = document.querySelector('.focus-actionbar')
      const style = getComputedStyle(bar)
      const rect = bar.getBoundingClientRect()
      return {
        bottom: style.bottom,
        paddingBottom: style.paddingBottom,
        rectBottom: rect.bottom,
        inset: getComputedStyle(document.documentElement).getPropertyValue('--kb-inset').trim(),
      }
    })
    assert.equal(barAt120.inset, '120px')
    const bottomConsumed = Number.parseFloat(barAt120.bottom) >= 119
    const paddingConsumed = Number.parseFloat(barAt120.paddingBottom) - basePadding >= 119
    const rectLifted = barAtRest.rectBottom - barAt120.rectBottom >= 119
    assert.ok(
      bottomConsumed || paddingConsumed || rectLifted,
      `The fixed .focus-actionbar did not consume --kb-inset: bottom=${barAt120.bottom}, ` +
      `padding-bottom=${barAt120.paddingBottom} (rest ${barAtRest.paddingBottom}), ` +
      `rect.bottom ${barAtRest.rectBottom} -> ${barAt120.rectBottom}`
    )
    console.log(
      `✓ 5. --kb-inset is 0px at rest and the action bar consumes 120px ` +
      `(${bottomConsumed ? 'via bottom' : paddingConsumed ? 'via padding' : 'via layout shift'}).`
    )

    // ------------------------------------------------- 6. one start panel
    const activeBefore = await asOwner.get('/api/v1/practice/sessions/active?mode=PRACTICE')
    assert.equal(activeBefore.status, 200, activeBefore.text)
    assert.equal(activeBefore.body.length, 1, 'Exactly one unfinished practice session is seeded')

    await page.goto(`${baseUrl}/#/banks`)
    await page.waitForSelector('.banks-page', { timeout: 15000 })
    const mainRow = page.locator('.banks-row').filter({ hasText: mainBankName }).first()
    await mainRow.waitFor({ state: 'visible', timeout: 10000 })
    await mainRow.locator('.bank-practice-btn').click()

    const startPanel = page.locator('.start-study-dialog[data-testid="start-study-panel"]')
    await startPanel.waitFor({ state: 'visible', timeout: 10000 })
    assert.match(await startPanel.innerText(), /PRACTICE|练习|进行中|未完成/, 'The shared panel must explain the blocking session')
    await page.locator('[data-testid="start-study-cancel"]').click()
    await startPanel.waitFor({ state: 'detached', timeout: 8000 })

    const activeAfter = await asOwner.get('/api/v1/practice/sessions/active?mode=PRACTICE')
    assert.equal(activeAfter.status, 200, activeAfter.text)
    assert.equal(activeAfter.body.length, 1, 'Cancelling the start panel must not create a second session')
    assert.match(await page.evaluate(() => location.hash), /^#\/banks/, 'Cancelling must stay on the bank list')
    console.log('✓ 6. A bank-row start with unfinished work opens the shared panel; cancel leaves one session.')

    console.log(`\nAll P6 acceptance checks passed in ${((Date.now() - runStarted) / 1000).toFixed(1)}s.`)
  } finally {
    if (browser) await browser.close().catch(() => {})
    server.kill()
    // Windows keeps the SQLite handle open until the child actually exits, so
    // wait for it before deleting; and never let cleanup hide a real failure.
    await new Promise(resolve => {
      if (server.exitCode !== null) return resolve()
      server.once('exit', resolve)
      setTimeout(resolve, 3000)
    })
    try {
      fs.rmSync(tempDir, { recursive: true, force: true })
    } catch (_) {
      // A leftover temp directory must not fail an otherwise passing run.
    }
  }
}

main().then(
  () => process.exit(0),
  err => {
    console.error('\nP6 acceptance failed:')
    console.error(err)
    process.exit(1)
  }
)
