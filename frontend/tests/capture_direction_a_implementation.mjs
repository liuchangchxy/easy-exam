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
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const screenshotsDir = path.resolve(__dirname, '../../screenshots/current_source_full_review_20260930_1719/direction-a-final')

if (!fs.existsSync(screenshotsDir)) {
  fs.mkdirSync(screenshotsDir, { recursive: true })
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
    await new Promise(r => setTimeout(r, 400))
  }
  throw new Error(`Server at ${url} failed to start within ${timeoutMs}ms`)
}

async function captureScreenshots() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fnexam-ui-check-'))
  const tempDbPath = path.join(tempDir, 'ui_check.db')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const BASE_URL = `http://127.0.0.1:${port}`

  console.log(`Starting FastAPI on port ${port}...`)
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
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  let browser = null
  try {
    await waitForServer(BASE_URL, instanceToken)
    console.log(`FastAPI server ready. Launching Chrome...`)
    browser = await chromium.launch({
      executablePath: CHROME_PATH,
      headless: true,
    })

    const viewports = [{ name: 'desktop', width: 1280, height: 800 }, { name: 'mobile', width: 375, height: 812, isMobile: true, hasTouch: true }, { name: 'mobile-390', width: 390, height: 844, isMobile: true, hasTouch: true }]

    for (const vp of viewports) {
      console.log(`\n--- Capturing for viewport: ${vp.name} (${vp.width}x${vp.height}) ---`)
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        isMobile: vp.isMobile || false,
        hasTouch: vp.hasTouch || false,
      })
      const page = await context.newPage()

      page.on('dialog', async d => { await d.accept() })

      // 1. Login Page
      await page.goto(BASE_URL)
      await page.waitForSelector('.auth-page')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-01-login.png`) })
      console.log(`Captured: ${vp.name}-01-login.png`)

      // Register and login
      const username = `u_${vp.name.replace(/[^a-zA-Z0-9]/g, '')}_${Date.now().toString().slice(-4)}`
      await page.click('button:has-text("创建账号")')
      await page.fill('input[placeholder="用户名"]', username)
      await page.fill('input[placeholder="密码（至少 8 位）"]', 'Password123!')
      await page.click('button[type="submit"]:has-text("注册并登录")')
      await page.waitForSelector('.home-page')

      // Get user token from localStorage
      const token = await page.evaluate(() => localStorage.getItem('easyexam_token'))

      // 2. Home Page (empty)
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-02-home-empty.png`) })
      console.log(`Captured: ${vp.name}-02-home-empty.png`)
      await page.getByRole('button', { name: '切换到深色模式' }).last().click()
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-02-home-empty-dark.png`) })
      await page.getByRole('button', { name: '切换到浅色模式' }).last().click()

      // Create a bank via UI
      await page.click('button:has-text("创建题库")')
      await page.waitForSelector('.exam-setup-dialog')
      await page.fill('input[placeholder*="软考高项"]', `UI测试题库_${vp.name}`)
      await page.fill('textarea[placeholder*="说明"]', '用于全界面视觉核验的示例题库')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-03-home-create-dialog.png`) })
      console.log(`Captured: ${vp.name}-03-home-create-dialog.png`)
      await page.click('.exam-setup-dialog button:has-text("确认创建")')
      await page.waitForSelector('.bank-card')

      // 3. Import Page
      if (vp.isMobile) await page.locator('.mobile-nav-item').nth(3).click()
      else await page.locator('.sidebar-nav-item:has-text("题库导入")').click()
      await page.waitForSelector('.import-page')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-04-import-page.png`) })
      console.log(`Captured: ${vp.name}-04-import-page.png`)

      // Return to home
      await page.click('button:has-text("返回")')
      await page.waitForSelector('.home-page')

      // Seed questions directly via backend API for the created bank
      const banksRes = await fetch(`${BASE_URL}/api/v1/banks`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const banks = await banksRes.json()
      const currentBank = banks[0]
      const bankId = currentBank.id

      // Seed 2 questions
      await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          stem: '计算机网络中，提供无连接数据报传输服务的网络层协议是？',
          type: 'SINGLE',
          options: [
            { key: 'A', content: 'TCP' },
            { key: 'B', content: 'IP' },
            { key: 'C', content: 'HTTP' },
            { key: 'D', content: 'FTP' },
          ],
          answer: 'B',
          explanation: 'IP 协议工作在网络层，提供不可靠无连接的数据报传输。',
          tags: ['网络层', '计算机网络'],
        }),
      })

      await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          stem: '以下哪些属于关系型数据库管理系统（RDBMS）？',
          type: 'MULTI',
          options: [
            { key: 'A', content: 'MySQL' },
            { key: 'B', content: 'PostgreSQL' },
            { key: 'C', content: 'Redis' },
            { key: 'D', content: 'Oracle' },
          ],
          answer: 'ABD',
          explanation: 'MySQL、PostgreSQL 和 Oracle 均为关系型数据库，Redis 为键值内存数据库。',
          tags: ['数据库'],
        }),
      })

      // Reload home to update question count
      await page.reload()
      await page.waitForSelector('.bank-card')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-04b-home-with-bank.png`) })
      console.log(`Captured: ${vp.name}-04b-home-with-bank.png`)

      // 4. Learning View
      if (vp.isMobile) await page.locator('.mobile-nav-item').nth(2).click()
      else await page.locator('.sidebar-nav-item:has-text("学习诊断")').click()
      await page.waitForSelector('.learning-page')
      await page.waitForTimeout(600)
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-05-learning-page.png`) })
      console.log(`Captured: ${vp.name}-05-learning-page.png`)

      // Return to home
      await page.click('button:has-text("返回")')
      await page.waitForSelector('.home-page')

      // 5. Mistakes View
      if (vp.isMobile) await page.locator('.mobile-nav-item').nth(1).click()
      else await page.locator('.sidebar-nav-item:has-text("错题与斩杀")').click()
      await page.waitForSelector('.mistakes-page')
      await page.waitForTimeout(600)
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-06-mistakes-page.png`) })
      console.log(`Captured: ${vp.name}-06-mistakes-page.png`)

      // Switch tab to kills
      await page.click('button:has-text("斩杀题库")')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-07-kills-page.png`) })
      console.log(`Captured: ${vp.name}-07-kills-page.png`)

      // Return to home
      await page.click('button:has-text("返回")')
      await page.waitForSelector('.home-page')

      // 6. Practice View
      await page.click('.bank-card button:has-text("开始刷题")')
      await page.waitForSelector('.practice-page')
      // Explicitly wait for question-card, stem-box, and options to finish loading
      await page.waitForSelector('.practice-page .question-card .option', { timeout: 15000 })
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-08-practice-page.png`) })
      console.log(`Captured: ${vp.name}-08-practice-page.png`)
      await page.getByRole('button', { name: '切换到深色模式' }).last().click()
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-08-practice-page-dark.png`) })
      await page.getByRole('button', { name: '切换到浅色模式' }).last().click()

      // Select first option and submit
      await page.locator('label.option').first().click()
      await page.click('button:has-text("提交答案")')
      await page.waitForSelector('.result-card')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-09-practice-result.png`) })
      console.log(`Captured: ${vp.name}-09-practice-result.png`)
      await page.getByRole('button', { name: '切换到深色模式' }).last().click()
      console.log('Practice dark computed colors:', await page.evaluate(() => ({
        theme: document.documentElement.dataset.theme,
        page: getComputedStyle(document.documentElement).getPropertyValue('--bg-page').trim(),
        card: getComputedStyle(document.documentElement).getPropertyValue('--bg-card').trim(),
        primary: getComputedStyle(document.documentElement).getPropertyValue('--primary').trim(),
        unselected: getComputedStyle(document.querySelector('.option:not(.option-correct):not(.option-wrong)')).backgroundColor,
        correct: (document.querySelector('.option.option-correct') ? getComputedStyle(document.querySelector('.option.option-correct')).backgroundColor : 'none'),
        wrong: (document.querySelector('.option.option-wrong') ? getComputedStyle(document.querySelector('.option.option-wrong')).backgroundColor : 'none'),
      })))
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-09-practice-result-dark.png`) })
      await page.getByRole('button', { name: '切换到浅色模式' }).last().click()

      // Return to home
      await page.click('.practice-page .page-header button:has-text("返回")')
      await page.waitForSelector('.home-page')

      // 7. Exam View
      await page.click('.bank-card button:has-text("开始模考")')
      await page.waitForSelector('.exam-setup-dialog')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-10-exam-setup-dialog.png`) })
      console.log(`Captured: ${vp.name}-10-exam-setup-dialog.png`)
      await page.click('.exam-setup-dialog button:has-text("开始考试")')
      await page.waitForSelector('.exam-page')
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-11-exam-page.png`) })
      console.log(`Captured: ${vp.name}-11-exam-page.png`)
      await page.getByRole('button', { name: '切换到深色模式' }).last().click()
      await page.screenshot({ path: path.join(screenshotsDir, `${vp.name}-11-exam-page-dark.png`) })
      await page.getByRole('button', { name: '切换到浅色模式' }).last().click()

      await context.close()
    }

    console.log(`\nAll visual captures finished successfully! Check docs/screenshots/`)
  } finally {
    if (browser) await browser.close()
    if (serverProcess) {
      serverProcess.kill('SIGTERM')
    }
    try {
      fs.rmSync(tempDir, { recursive: true, force: true })
    } catch (_) {}
  }
}

captureScreenshots().catch(err => {
  console.error('Screenshot script failed:', err)
  process.exit(1)
})
