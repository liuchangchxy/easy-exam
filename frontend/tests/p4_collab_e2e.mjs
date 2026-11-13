// P4 acceptance: collaboration and instance administration on a real server.
//
// The exit condition for P4 is a multi-user walk-through, so this drives the
// actual HTTP surface and a real Chromium against a fresh database: one
// bootstrapped admin, a shared bank that a member can edit, a stranger who is
// refused at the page level, a registration switch that actually closes the
// door, and sessions that can be revoked from another device.
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

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'p4-collab-'))
  const tempDbPath = path.join(tempDir, 'p4.db')
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
        EASYEXAM_SECRET_KEY: 'p4-collab-secret-key-32-bytes-long',
      },
      stdio: ['ignore', 'ignore', 'ignore'],
    }
  )

  let browser = null
  try {
    await waitForServer(baseUrl, instanceToken)

    const stamp = Date.now()
    const ownerName = `p4_owner_${stamp}`.slice(0, 40)
    const editorName = `p4_editor_${stamp}`.slice(0, 40)
    const outsiderName = `p4_outsider_${stamp}`.slice(0, 40)
    const password = 'Password123!'

    // ---------------------------------------------------------- 1. bootstrap
    const anon = api(baseUrl)
    const regOwner = await anon.post('/api/v1/auth/register', { username: ownerName, password })
    assert.equal(regOwner.status, 201, regOwner.text)
    assert.equal(regOwner.body.is_admin, true, 'The first account of an empty instance must be the instance admin')
    for (const name of [editorName, outsiderName]) {
      const res = await anon.post('/api/v1/auth/register', { username: name, password })
      assert.equal(res.status, 201, res.text)
      assert.equal(res.body.is_admin, false, 'Later accounts must not be admins')
    }
    console.log('✓ First user is the instance admin; later users are plain members.')

    const ownerToken = (await anon.post('/api/v1/auth/login', { username: ownerName, password })).body.token
    const editorToken = (await anon.post('/api/v1/auth/login', { username: editorName, password })).body.token
    const outsiderToken = (await anon.post('/api/v1/auth/login', { username: outsiderName, password })).body.token
    const asOwner = api(baseUrl, ownerToken)
    const asEditor = api(baseUrl, editorToken)
    const asOutsider = api(baseUrl, outsiderToken)

    // ------------------------------------------------------ 2. shared bank
    const bank = await asOwner.post('/api/v1/banks', { name: `P4 共享题库 ${stamp}` })
    assert.equal(bank.status, 201, bank.text)
    const bankId = bank.body.id
    const question = await asOwner.post(`/api/v1/banks/${bankId}/questions`, {
      stem: 'P4 协作题：共享题库里的题目应能被编辑者修改',
      type: 'SINGLE',
      answer: 'A',
      options: [{ key: 'A', content: '对' }, { key: 'B', content: '错' }],
    })
    assert.equal(question.status, 201, question.text)

    const search = await asOwner.get(`/api/v1/users/search?q=${editorName.slice(0, 12)}`)
    assert.equal(search.status, 200, search.text)
    assert.ok(
      search.body.some(row => row.username === editorName),
      'The add-member combobox must find a registered user by prefix'
    )
    const editorId = search.body.find(row => row.username === editorName).id

    const add = await asOwner.post(`/api/v1/banks/${bankId}/members`, { username: editorName, role: 'EDITOR' })
    assert.equal(add.status, 201, add.text)
    const duplicate = await asOwner.post(`/api/v1/banks/${bankId}/members`, { username: editorName, role: 'MEMBER' })
    assert.equal(duplicate.status, 409, 'Re-adding a member must conflict, not silently rewrite their role')

    const members = await asOwner.get(`/api/v1/banks/${bankId}/members`)
    assert.equal(members.status, 200, members.text)
    assert.equal(members.body[0].role, 'ADMIN', 'The owner sorts first')
    const editorRow = members.body.find(row => row.user_id === editorId)
    assert.equal(editorRow.role, 'EDITOR')
    assert.ok(editorRow.joined_at, 'Members carry a joined_at for the member list')
    console.log('✓ Owner shares the bank; duplicate add conflicts; owner sorts first.')

    // ------------------------------------------- 3. member edits, outsider refused
    const editorBanks = await asEditor.get('/api/v1/banks')
    assert.equal(editorBanks.status, 200, editorBanks.text)
    const sharedRow = editorBanks.body.find(row => row.id === bankId)
    assert.ok(sharedRow, 'A shared bank must appear in the member list')
    assert.equal(sharedRow.role, 'EDITOR')

    const edit = await asEditor.post(`/api/v1/banks/${bankId}/questions`, {
      stem: '编辑者新增的题目',
      type: 'SINGLE',
      answer: 'A',
      options: [{ key: 'A', content: '对' }, { key: 'B', content: '错' }],
    })
    assert.equal(edit.status, 201, 'An editor may add content to the shared bank')
    const ownerOnly = await asEditor.patch(`/api/v1/banks/${bankId}/members/${editorId}`, { role: 'MEMBER' })
    assert.equal(ownerOnly.status, 403, 'An editor may not manage membership')

    // The API hides a bank the caller is not in rather than confirming it
    // exists (403 and 404 are both refusals here); the page turns either into
    // the same "you are not in this bank" state.
    assert.ok([403, 404].includes((await asOutsider.get(`/api/v1/banks/${bankId}`)).status))
    assert.ok([403, 404].includes((await asOutsider.get(`/api/v1/banks/${bankId}/questions`)).status))
    console.log('✓ Editor can edit; editor cannot manage members; outsider is refused by data.')

    // ---------------------------------------------- 4. browser: shared vs denied
    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
    const page = await context.newPage()

    await login(page, baseUrl, editorName, password)
    await page.goto(`${baseUrl}/#/banks`)
    await page.waitForSelector('.banks-page')
    const sharedRowLocator = page.locator('.banks-row').filter({ hasText: `P4 共享题库 ${stamp}` }).first()
    await sharedRowLocator.waitFor({ state: 'visible', timeout: 10000 })
    assert.ok(
      (await page.locator('.banks-page').innerText()).includes('共享给我'),
      'A bank somebody else owns belongs in the 共享给我 section'
    )
    await page.goto(`${baseUrl}/#/banks/${bankId}`)
    await page.waitForSelector('.manage-page', { timeout: 10000 })
    assert.equal(
      await page.locator('[data-testid="access-denied"]').count(),
      0,
      'The member may enter the workspace'
    )

    await context.clearCookies()
    await page.evaluate(() => localStorage.clear())
    await login(page, baseUrl, outsiderName, password)
    await page.goto(`${baseUrl}/#/banks/${bankId}`)
    await page.waitForSelector('[data-testid="access-denied"]', { timeout: 10000 })
    const deniedText = await page.locator('[data-testid="access-denied"]').innerText()
    assert.match(deniedText, /题库|权限|成员/, 'The denial is written for a person, not a raw backend error')
    // The way out of a denial is the bank list, not the home page: the shell
    // used to keep a fall-through "@back" listener that fired alongside the
    // page's own handler and sent the user to "/" instead.
    await page.locator('[data-testid="access-denied-back"]').click()
    await page.waitForSelector('.banks-page', { timeout: 8000 })
    assert.match(await page.evaluate(() => location.hash), /^#\/banks/)
    console.log('✓ Member enters the shared workspace; a stranger gets the page-level denial.')

    // -------------------------------------- 5. browser: member management UI
    // The owner adds the stranger through the workspace's member tab — search
    // by prefix, pick a role, add — and the person can then enter the bank.
    await context.clearCookies()
    await page.evaluate(() => localStorage.clear())
    await login(page, baseUrl, ownerName, password)
    await page.goto(`${baseUrl}/#/banks/${bankId}?tab=members`)
    await page.waitForSelector('[data-testid="member-search-input"]', { timeout: 10000 })
    const memberRows = page.locator('.member-row')
    await memberRows.first().waitFor({ state: 'visible', timeout: 8000 })
    assert.match(await memberRows.first().innerText(), new RegExp(ownerName), 'The owner sorts first')
    assert.equal(await page.locator('[data-testid="member-self-badge"]').count(), 1, 'Only the caller is marked 我')

    await page.locator('[data-testid="member-search-input"]').fill(outsiderName.slice(0, 12))
    await page.waitForSelector('#member-search-listbox .member-search-option', { timeout: 8000 })
    await page.locator('#member-search-listbox .member-search-option').filter({ hasText: outsiderName }).first().click()
    await page.locator('[data-testid="member-add-role"]').selectOption('MEMBER')
    await page.locator('[data-testid="member-add-submit"]').click()
    await page.waitForFunction(
      name => [...document.querySelectorAll('.member-row')].some(el => el.innerText.includes(name)),
      outsiderName,
      { timeout: 10000 }
    )
    assert.equal((await asOutsider.get(`/api/v1/banks/${bankId}`)).status, 200, 'The added member can now enter the bank')
    console.log('✓ The owner finds a user by prefix, adds them, and the new member gets access.')

    // ---------------------------------------------------- 5. registration gate
    assert.equal((await asOwner.get('/api/v1/admin/settings')).body.allow_registration, true)
    const closed = await asOwner.put('/api/v1/admin/settings', { allow_registration: false })
    assert.equal(closed.status, 200, closed.text)
    const blockedRegister = await anon.post('/api/v1/auth/register', {
      username: `p4_late_${stamp}`,
      password,
    })
    assert.equal(blockedRegister.status, 403, 'Registration must be closed once the switch is off')
    assert.equal((await asOwner.put('/api/v1/admin/settings', { allow_registration: true })).status, 200)
    assert.equal(
      (await anon.post('/api/v1/auth/register', { username: `p4_later_${stamp}`, password })).status,
      201
    )
    console.log('✓ The registration switch actually closes and reopens the door.')

    // ------------------------------------------------------- 6. admin guards
    assert.equal((await asEditor.get('/api/v1/admin/users')).status, 403)
    assert.equal((await asOwner.get('/api/v1/admin/users')).status, 200)
    const ownerMe = (await asOwner.get('/api/v1/auth/me')).body
    const ownerDisable = await asOwner.patch(`/api/v1/admin/users/${ownerMe.id}`, { is_active: false })
    assert.equal(ownerDisable.status, 400, 'An admin cannot lock themselves out')

    const reset = await asOwner.post(`/api/v1/admin/users/${editorId}/reset-password`)
    assert.equal(reset.status, 200, reset.text)
    assert.ok(reset.body.temporary_password.length >= 12)
    assert.equal(
      (await asEditor.get('/api/v1/banks')).status,
      401,
      'Resetting a password must end that user’s existing sessions'
    )
    const relogin = await anon.post('/api/v1/auth/login', {
      username: editorName,
      password: reset.body.temporary_password,
    })
    assert.equal(relogin.status, 200, relogin.text)
    assert.equal(relogin.body.user.must_change_password, true)
    console.log('✓ Admin surface is guarded; reset-password revokes sessions and forces a new one.')

    // ------------------------------------------- 6b. browser: admin surface
    // The decision "build a real instance-admin surface" is only real if a
    // person can operate it, so the panel itself is driven here: the user
    // table must list everyone, the registration switch must save explicitly,
    // and a non-admin must be refused at the page level.
    await context.clearCookies()
    await page.evaluate(() => localStorage.clear())
    await login(page, baseUrl, ownerName, password)
    await page.goto(`${baseUrl}/#/instance`)
    await page.waitForSelector('.instance-admin-page', { timeout: 10000 })
    await page.waitForSelector('.admin-users-table tbody tr', { timeout: 10000 })
    const adminRowCount = await page.locator('.admin-users-table tbody tr').count()
    assert.ok(adminRowCount >= 3, `The user table lists every account (saw ${adminRowCount})`)
    const adminTableText = await page.locator('.admin-users-table').innerText()
    assert.match(adminTableText, new RegExp(ownerName))
    assert.match(adminTableText, new RegExp(editorName))

    await page.locator('[data-testid="instance-tab-settings"]').click()
    const toggle = page.locator('[data-testid="allow-registration-toggle"]')
    await toggle.waitFor({ state: 'visible', timeout: 8000 })
    const waitForRegistration = async expected => {
      const start = Date.now()
      while (Date.now() - start < 10000) {
        const res = await asOwner.get('/api/v1/admin/settings')
        if (res.body?.allow_registration === expected) return
        await new Promise(r => setTimeout(r, 150))
      }
      throw new Error(`The registration switch never became ${expected}`)
    }
    await toggle.uncheck()
    await page.locator('[data-testid="save-instance-settings"]').click()
    await waitForRegistration(false)
    await toggle.check()
    await page.locator('[data-testid="save-instance-settings"]').click()
    await waitForRegistration(true)

    await context.clearCookies()
    await page.evaluate(() => localStorage.clear())
    await login(page, baseUrl, outsiderName, password)
    await page.goto(`${baseUrl}/#/instance`)
    await page.waitForSelector('[data-testid="access-denied"]', { timeout: 10000 })
    assert.match(await page.evaluate(() => location.hash), /forbidden/, 'Non-admins are routed to the denial page')
    console.log('✓ The instance-admin page lists users, saves the registration switch, and refuses non-admins.')

    // ---------------------------------------------------------- 7. sessions
    const deviceA = (await anon.post('/api/v1/auth/login', { username: ownerName, password })).body.token
    const deviceB = (await anon.post('/api/v1/auth/login', { username: ownerName, password })).body.token
    const sessions = await api(baseUrl, deviceB).get('/api/v1/auth/sessions')
    assert.equal(sessions.status, 200, sessions.text)
    assert.ok(sessions.body.length >= 2, 'Every device is listed')
    assert.equal(sessions.body.filter(row => row.current).length, 1, 'Exactly one row is "this device"')
    const revoked = await api(baseUrl, deviceB).del('/api/v1/auth/sessions')
    assert.equal(revoked.status, 200, revoked.text)
    assert.ok(revoked.body.revoked >= 1)
    assert.equal((await api(baseUrl, deviceA).get('/api/v1/auth/me')).status, 401, 'The other device is signed out')
    assert.equal((await api(baseUrl, deviceB).get('/api/v1/auth/me')).status, 200, 'This device stays signed in')
    console.log('✓ Sessions are listed and other devices can be signed out.')
  } finally {
    if (browser) await browser.close().catch(() => {})
    server.kill()
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
}

main().then(
  () => {
    console.log('\nAll P4 collaboration and instance-admin checks passed.')
    process.exit(0)
  },
  err => {
    console.error(err)
    process.exit(1)
  }
)
