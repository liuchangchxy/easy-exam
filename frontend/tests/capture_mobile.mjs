import { spawn } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import net from 'node:net'
import crypto from 'node:crypto'
import { chromium } from 'playwright'

const repoRoot = path.resolve(process.cwd())
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const ARTIFACT_DIR = 'C:\\Users\\chang\\.gemini\\antigravity\\brain\\767e6073-da89-477b-a7e0-6c0676dd27d6'
const SCREENSHOT_DIR = path.join(repoRoot, 'screenshots', 'mobile')

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true })
}
if (!fs.existsSync(ARTIFACT_DIR)) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true })
}

async function getFreePort() {
  return new Promise((resolve) => {
    const srv = net.createServer()
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port
      srv.close(() => resolve(port))
    })
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
          throw new Error('Token mismatch')
        }
        return true
      }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 300))
  }
  throw new Error(`Server at ${url} failed to start`)
}

async function run() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fnexam-mobile-'))
  const tempDbPath = path.join(tempDir, 'mobile_test.db')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const BASE_URL = `http://127.0.0.1:${port}`

  console.log(`Starting FastAPI on port ${port}...`)
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
        EASYEXAM_SECRET_KEY: 'mobile-secret-key-32bytes-ci!!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  server.stderr.on('data', d => {
    const text = d.toString()
    if (!text.includes('GET /') && !text.includes('POST /')) {
      console.error('[Server Error]', text)
    }
  })

  let browser = null
  try {
    await waitForServer(BASE_URL, instanceToken)
    console.log('Server ready. Launching mobile viewport in Chrome...')

    browser = await chromium.launch({
      executablePath: CHROME_PATH,
      headless: true,
    })

    // Standard iPhone 14/15 viewport: 390 x 844
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    })
    const page = await context.newPage()

    // 1. Login Page
    await page.goto(BASE_URL)
    await page.waitForSelector('.auth-page')
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_login_mobile.png') })

    // Register user
    await page.click('button:has-text("首次使用？创建账号")')
    await page.fill('input[placeholder="用户名"]', 'mobile_tester')
    await page.fill('input[placeholder="密码（至少 8 位）"]', 'password-123456')
    await page.click('button:has-text("注册并登录")')
    await page.waitForSelector('.home-page')

    // Create Bank and Seed Questions
    const token = await page.evaluate(() => localStorage.getItem('easyexam_token'))
    const createBankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: '系统集成项目管理真题',
        category: '软考',
        description: '系统集成历年真题精选'
      })
    })
    const bank = await createBankRes.json()

    // Import questions
    const mdContent = fs.readFileSync(path.join(repoRoot, 'data', 'ruankao_system_integration_142.md'), 'utf-8')
    await fetch(`${BASE_URL}/api/v1/imports/banks/${bank.id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        format: 'markdown',
        content: mdContent.slice(0, 8000), // First few questions
        duplicate_strategy: 'merge'
      })
    })

    // Reload HomeView so it shows the bank
    await page.reload()
    await page.waitForSelector('.bank-card')
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_home_mobile.png') })

    // 2. Start Practice Session
    await page.click('button:has-text("开始刷题")')
    await page.waitForSelector('.practice-page')
    await page.waitForSelector('.question-card')
    await page.waitForTimeout(500)

    // Capture Practice View (Unanswered)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_practice_unanswered_viewport.png') })
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_practice_unanswered_fullpage.png'), fullPage: true })

    // Inspect layout bounding boxes on Practice View
    const metrics = await page.evaluate(() => {
      const vh = window.innerHeight
      const vw = window.innerWidth
      const header = document.querySelector('.compact-header')?.getBoundingClientRect()
      const questionCard = document.querySelector('.question-card')?.getBoundingClientRect()
      const stem = document.querySelector('.question-stem')?.getBoundingClientRect()
      const optionsContainer = document.querySelector('.options-list')?.getBoundingClientRect()
      const options = Array.from(document.querySelectorAll('.option')).map(o => o.getBoundingClientRect())
      const actionBar = document.querySelector('.ergonomic-action-bar')?.getBoundingClientRect()
      const practicePage = document.querySelector('.practice-page')?.getBoundingClientRect()

      return {
        viewport: { width: vw, height: vh },
        practicePage: practicePage ? { top: practicePage.top, bottom: practicePage.bottom, width: practicePage.width, height: practicePage.height, margin: window.getComputedStyle(document.querySelector('.practice-page')).margin } : null,
        header: header ? { height: header.height, top: header.top, bottom: header.bottom } : null,
        questionCard: questionCard ? { height: questionCard.height, padding: window.getComputedStyle(document.querySelector('.question-card')).padding } : null,
        stem: stem ? { height: stem.height } : null,
        optionsCount: options.length,
        optionsTotalHeight: options.reduce((sum, o) => sum + o.height, 0),
        optionsContainerHeight: optionsContainer?.height,
        actionBar: actionBar ? { height: actionBar.height, padding: window.getComputedStyle(document.querySelector('.ergonomic-action-bar')).padding } : null,
      }
    })

    console.log('Practice Metrics:', JSON.stringify(metrics, null, 2))

    // 3. Select an Option and Submit
    await page.click('.option:first-child')
    await page.waitForTimeout(300)
    await page.click('button:has-text("提交答案")')
    await page.waitForTimeout(800)
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_practice_submitted_viewport.png') })
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_practice_submitted_fullpage.png'), fullPage: true })

    // Copy screenshots to Artifact Directory
    const files = fs.readdirSync(SCREENSHOT_DIR)
    for (const f of files) {
      fs.copyFileSync(path.join(SCREENSHOT_DIR, f), path.join(ARTIFACT_DIR, f))
    }

    console.log('Screenshots taken and copied successfully.')
    fs.writeFileSync(path.join(SCREENSHOT_DIR, 'metrics.json'), JSON.stringify(metrics, null, 2))
    fs.writeFileSync(path.join(ARTIFACT_DIR, 'metrics.json'), JSON.stringify(metrics, null, 2))


  } finally {
    if (browser) await browser.close()
    server.kill()
  }
}

run().catch(err => {
  console.error(err)
  process.exit(1)
})
