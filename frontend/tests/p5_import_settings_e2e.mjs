// P5 acceptance: the import wizard keeps its work, imports run in the
// background, and settings stop overwriting each other.
//
// The P5 audit findings were all "the surface promises something the data model
// cannot honour": a reload in the middle of an import lost the mapping, a big
// file froze the page with no way out, and the settings page wrote every field
// on every save, so editing the AI model wiped the web-search base URL. This
// drives the real server and a real Chromium to prove the three are gone.
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

const TERMINAL = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'PRECHECK_FAILED'])

async function waitJob(client, jobId, timeoutMs = 40000) {
  const start = Date.now()
  let last = null
  while (Date.now() - start < timeoutMs) {
    const res = await client.get(`/api/v1/imports/jobs/${jobId}`)
    assert.equal(res.status, 200, res.text)
    last = res.body
    if (TERMINAL.has(last.status)) return last
    await new Promise(r => setTimeout(r, 200))
  }
  throw new Error(`Job ${jobId} never reached a terminal status: ${JSON.stringify(last)}`)
}

function csvOf(count, prefix) {
  const rows = ['stem,answer,options']
  for (let i = 0; i < count; i += 1) {
    rows.push(`${prefix} 第 ${i + 1} 题, A, 选项甲|选项乙`)
  }
  return rows.join('\n')
}

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'p5-import-'))
  const tempDbPath = path.join(tempDir, 'p5.db')
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
        EASYEXAM_SECRET_KEY: 'p5-import-secret-key-32-bytes-long',
      },
      stdio: ['ignore', 'ignore', 'ignore'],
    }
  )

  let browser = null
  try {
    await waitForServer(baseUrl, instanceToken)

    const stamp = Date.now()
    const ownerName = `p5_owner_${stamp}`.slice(0, 40)
    const otherName = `p5_other_${stamp}`.slice(0, 40)
    const password = 'Password123!'
    const anon = api(baseUrl)
    assert.equal((await anon.post('/api/v1/auth/register', { username: ownerName, password })).status, 201)
    const otherReg = await anon.post('/api/v1/auth/register', { username: otherName, password })
    assert.equal(otherReg.status, 201, otherReg.text)
    assert.equal(otherReg.body.is_admin, false)

    const ownerToken = (await anon.post('/api/v1/auth/login', { username: ownerName, password })).body.token
    const otherToken = (await anon.post('/api/v1/auth/login', { username: otherName, password })).body.token
    const asOwner = api(baseUrl, ownerToken)
    const asOther = api(baseUrl, otherToken)

    const bank = await asOwner.post('/api/v1/banks', { name: `P5 导入题库 ${stamp}` })
    assert.equal(bank.status, 201, bank.text)
    const bankId = bank.body.id

    // ------------------------------------------------- 1. draft survives work
    // A wizard step that cannot be resumed is the headline P5 defect: closing
    // the tab mid-mapping threw away everything the user had chosen.
    const draft = await asOwner.post(`/api/v1/imports/banks/${bankId}/drafts`, {
      source_kind: 'file',
      filename: 'questions.csv',
      step: 1,
      state: { mapping: { stem: 0, answer: 1, options: 2 }, header_row: 1 },
    })
    assert.equal(draft.status, 201, draft.text)
    const draftId = draft.body.id
    assert.equal(draft.body.step, 1)
    assert.deepEqual(draft.body.state.mapping, { stem: 0, answer: 1, options: 2 })

    const listed = await asOwner.get(`/api/v1/imports/banks/${bankId}/drafts`)
    assert.equal(listed.status, 200, listed.text)
    assert.ok(listed.body.some(row => row.id === draftId), '分步草稿必须出现在未完成列表里')
    assert.equal(listed.body[0].state, undefined, '列表不背解析状态，只给摘要')

    const advanced = await asOwner.put(`/api/v1/imports/drafts/${draftId}`, {
      step: 2,
      state: { mapping: { stem: 0, answer: 1, options: 2 }, header_row: 1, strategy: 'skip' },
    })
    assert.equal(advanced.status, 200, advanced.text)
    assert.equal(advanced.body.step, 2)

    // Reopening it — the "resume" path — returns the state it was left in.
    const reopened = await asOwner.get(`/api/v1/imports/drafts/${draftId}`)
    assert.equal(reopened.status, 200, reopened.text)
    assert.equal(reopened.body.step, 2)
    assert.equal(reopened.body.state.strategy, 'skip')
    assert.equal((await asOther.get(`/api/v1/imports/drafts/${draftId}`)).status, 404, '别人的草稿不确认存在')

    assert.equal((await asOwner.del(`/api/v1/imports/drafts/${draftId}`)).status, 204)
    const afterDelete = await asOwner.get(`/api/v1/imports/banks/${bankId}/drafts`)
    assert.equal(afterDelete.body.some(row => row.id === draftId), false)
    console.log('✓ A wizard draft keeps its mapping across steps, resumes, and discards cleanly.')

    // ------------------------------------------------- 2. background import
    const csv = csvOf(2, 'P5 后台导入')
    const form = new FormData()
    form.append('file', new Blob([csv], { type: 'text/csv' }), 'p5.csv')
    form.append('duplicate_strategy', 'skip')
    const started = await fetch(`${baseUrl}/api/v1/imports/banks/${bankId}/jobs`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${ownerToken}` },
      body: form,
    })
    const startedText = await started.text()
    assert.equal(started.status, 202, startedText)
    const jobId = JSON.parse(startedText).job_id
    const done = await waitJob(asOwner, jobId)
    assert.equal(done.status, 'COMPLETED', JSON.stringify(done))
    assert.equal(done.format, 'csv')
    assert.equal(done.imported_count, 2)
    assert.equal(done.total, 2)
    assert.equal(done.progress, 2)
    assert.ok(done.completed_at, '完成的任务带完成时间')
    const questions = await asOwner.get(`/api/v1/banks/${bankId}/questions`)
    assert.equal(questions.status, 200)
    assert.ok(
      questions.body.some(q => String(q.stem).includes('P5 后台导入')),
      '后台导入的题目真的落到了题库里'
    )

    // A file that cannot be parsed must end with a reason, not spin forever.
    const broken = await asOwner.post(`/api/v1/imports/banks/${bankId}/jobs`, { format: 'json', content: '{not valid json' })
    assert.equal(broken.status, 202, broken.text)
    const brokenFinal = await waitJob(asOwner, broken.body.job_id)
    assert.equal(brokenFinal.status, 'FAILED')
    assert.ok(brokenFinal.reason, '失败的任务必须说明原因')
    console.log('✓ Background import reports progress and imports; an unreadable file fails with a reason.')

    // ------------------------------------------- 3. cancel a long-running job
    const bigCsv = csvOf(1200, 'P5 大文件')
    const bigForm = new FormData()
    bigForm.append('file', new Blob([bigCsv], { type: 'text/csv' }), 'big.csv')
    bigForm.append('duplicate_strategy', 'skip')
    const bigStarted = await fetch(`${baseUrl}/api/v1/imports/banks/${bankId}/jobs`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${ownerToken}` },
      body: bigForm,
    })
    assert.equal(bigStarted.status, 202)
    const bigId = (await bigStarted.json()).job_id
    const cancelled = await asOwner.post(`/api/v1/imports/jobs/${bigId}/cancel`)
    assert.equal(cancelled.status, 200, cancelled.text)
    assert.ok(['CANCELLED', 'COMPLETED', 'RUNNING'].includes(cancelled.body.status), cancelled.body.status)
    const bigFinal = await waitJob(asOwner, bigId)
    assert.ok(['CANCELLED', 'COMPLETED'].includes(bigFinal.status), JSON.stringify(bigFinal))
    if (bigFinal.status === 'CANCELLED') {
      assert.ok(bigFinal.imported_count < bigFinal.total, '取消后不能凭空导入完整个文件')
    }
    console.log(`✓ A running import can be cancelled (${bigFinal.status}, ${bigFinal.imported_count}/${bigFinal.total}).`)

    // ------------------------------------------------- 4. settings layering
    // The old PUT wrote the whole config from the page's state, so touching one
    // field clobbered the others. PATCH writes only the keys the user changed.
    const aiOnly = await asOwner.patch('/api/v1/ai/config', { ai_model: 'p5-layered-model' })
    assert.equal(aiOnly.status, 200, aiOnly.text)
    const searchOnly = await asOwner.patch('/api/v1/ai/config', {
      search_api_base: 'http://127.0.0.1:9/P5-search',
    })
    assert.equal(searchOnly.status, 200, searchOnly.text)
    const layered = await asOwner.get('/api/v1/ai/config')
    assert.equal(layered.status, 200, layered.text)
    assert.equal(layered.body.ai_model, 'p5-layered-model', '改联网设置不能冲掉 AI 模型')
    assert.equal(layered.body.search_api_base, 'http://127.0.0.1:9/P5-search', '改 AI 模型不能冲掉联网地址')
    console.log('✓ Per-field saves layer: editing AI leaves web search alone, and vice versa.')

    // The connection probe must answer, and must not leak what it probed.
    const probe = await asOwner.post('/api/v1/ai/config/test', { kind: 'ai' })
    assert.equal(probe.status, 200, probe.text)
    assert.equal(probe.body.ok, false, 'A dead endpoint must report failure, not success')
    assert.ok(probe.body.message, '失败也要给人看得懂的消息')
    assert.ok(!probe.body.message.includes('p5-layered-model'), '探针消息不能回显配置内容')
    assert.equal((await asOwner.post('/api/v1/ai/config/test', { kind: 'nonsense' })).status, 422)
    console.log('✓ The connection probe answers with a message and leaks nothing.')

    // ------------------------------------------------------ 5. browser: wizard
    browser = await chromium.launch({ headless: true })
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
    const page = await context.newPage()

    await login(page, baseUrl, ownerName, password)
    const wizardCsv = Buffer.from(csvOf(3, 'Wizard 导入'), 'utf8')
    const pickWizardFile = async () => {
      await page.setInputFiles('.file-input-hidden', {
        name: 'wizard.csv',
        mimeType: 'text/csv',
        buffer: wizardCsv,
      })
    }

    await page.goto(`${baseUrl}/#/import?bankId=${bankId}`)
    await page.waitForSelector('[data-step="source"]', { timeout: 10000 })
    await pickWizardFile()
    await page.locator('[data-step="source"] .btn-primary').click()
    await page.waitForSelector('[data-step="check"]', { timeout: 15000 })
    assert.ok(
      (await page.locator('[data-step="check"]').innerText()).length > 0,
      'The mapping step must render the file it just read'
    )

    // The wizard's work is only "kept" if it survives a reload: the step is
    // synced to the server as a draft, and coming back shows it as resumable.
    await page.waitForTimeout(1000)
    const wizardDrafts = await asOwner.get(`/api/v1/imports/banks/${bankId}/drafts`)
    assert.equal(wizardDrafts.status, 200, wizardDrafts.text)
    assert.ok(wizardDrafts.body.length >= 1, 'The wizard must persist its step as a resumable draft')
    await page.reload()
    await page.waitForSelector('.import-page', { timeout: 10000 })
    // The same tab reopened must come back at the step it left, not at step 1.
    await page.waitForSelector('[data-step="check"], [data-testid="resume-needs-file"]', { timeout: 10000 })
    assert.match(
      await page.evaluate(() => location.hash),
      /step=2|draft=/,
      '刷新后必须回到原来的步骤，而不是从第一步重来'
    )

    // A fresh visit offers the unfinished work back instead of forgetting it.
    // A hash-to-hash goto keeps the component alive, so reload to get the
    // pristine "open the page again" state a returning user actually sees.
    await page.goto(`${baseUrl}/#/import?bankId=${bankId}`)
    await page.reload()
    await page.waitForSelector('.import-page', { timeout: 10000 })
    await page.waitForSelector('[data-testid="import-resume"]', { timeout: 10000 })
    const resumeText = await page.locator('[data-testid="import-resume"]').innerText()
    assert.match(resumeText, /继续|草稿|未完成/, `未完成的导入必须能被看见，实际：${resumeText}`)
    await page.locator('[data-testid="draft-resume"]').first().click()
    await page.waitForSelector('[data-step="check"]', { timeout: 10000 })
    console.log('✓ A reload returns to the saved step, and a fresh visit offers the draft back.')

    // Re-run it from the top and finish; the receipt has to name what happened.
    await page.goto(`${baseUrl}/#/import?bankId=${bankId}`)
    await page.reload()
    await page.waitForSelector('.import-page', { timeout: 10000 })
    await page.waitForSelector('[data-step="source"]', { timeout: 10000 })
    await pickWizardFile()
    await page.locator('[data-step="source"] .btn-primary').click()
    await page.waitForSelector('[data-step="check"]', { timeout: 15000 })
    await page.locator('[data-step="check"] .btn-primary').click()
    await page.waitForSelector('[data-step="duplicates"]', { timeout: 10000 })
    await page.locator('[data-step="duplicates"] .btn-primary').click()
    await page.waitForSelector('[data-testid="import-result"]', { timeout: 15000 })

    const wizardStart = Date.now()
    let wizardImported = false
    while (Date.now() - wizardStart < 30000) {
      const rows = await asOwner.get(`/api/v1/banks/${bankId}/questions`)
      if (rows.body.some(q => String(q.stem).includes('Wizard 导入'))) {
        wizardImported = true
        break
      }
      await new Promise(r => setTimeout(r, 250))
    }
    assert.ok(wizardImported, 'Finishing the wizard must actually import the questions')
    const resultText = await page.locator('[data-testid="import-result"]').innerText()
    assert.ok(/Wizard|题库|完成|导入|\d/.test(resultText), `The result step must report the outcome, saw: ${resultText.slice(0, 120)}`)
    console.log('✓ The wizard survives a reload, resumes from its draft, and imports through a background job.')

    // ------------------------------------------------------ 6. browser: settings
    await page.goto(`${baseUrl}/#/settings?section=ai`)
    await page.goto(`${baseUrl}/#/settings?section=ai`)
    await page.waitForSelector('[data-testid="ai-test"]', { timeout: 10000 })
    await page.locator('[data-testid="ai-test"]').click()
    await page.waitForFunction(
      () => {
        const el = document.querySelector('.settings-section [role="status"], .settings-section [role="alert"]')
        return !!el && /测试|连接|失败|成功|超时|[Ee]rror/.test(el.textContent || '')
      },
      null,
      { timeout: 15000 }
    )
    const testText = await page
      .locator('.settings-section [role="status"], .settings-section [role="alert"]')
      .first()
      .innerText()
    assert.ok(testText.trim().length > 0, '测试连接必须给出可见结论')

    // Editing the model in the page must persist exactly that key.
    const modelInput = page.locator('.settings-section input[placeholder="gpt-4o-mini"]')
    await modelInput.fill('p5-browser-model')
    await modelInput.blur()
    const start = Date.now()
    let browserLayered = null
    while (Date.now() - start < 10000) {
      browserLayered = (await asOwner.get('/api/v1/ai/config')).body
      if (browserLayered?.ai_model === 'p5-browser-model') break
      await new Promise(r => setTimeout(r, 150))
    }
    assert.equal(browserLayered.ai_model, 'p5-browser-model', '页面上的改动必须真的保存')
    assert.equal(
      browserLayered.search_api_base,
      'http://127.0.0.1:9/P5-search',
      '页面保存 AI 模型时不能覆盖联网地址'
    )
    console.log('✓ The settings page tests a connection in place and saves one field at a time.')
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
  () => {
    console.log('\nAll P5 import, job and settings checks passed.')
    process.exit(0)
  },
  err => {
    console.error(err)
    process.exit(1)
  }
)
