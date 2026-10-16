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
const outputDir = path.join(repoRoot, 'screenshots')
fs.mkdirSync(outputDir, { recursive: true })

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
          throw new Error('Instance token mismatch')
        }
        return true
      }
    } catch (_) {}
    await new Promise(r => setTimeout(r, 400))
  }
  throw new Error(`Server at ${url} failed to start within ${timeoutMs}ms`)
}

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fnexam-ui-audit-'))
  const tempDbPath = path.join(tempDir, 'ui_audit.db')
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
        EASYEXAM_SECRET_KEY: 'easyexam-ui-audit-secret-key-32b!!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  try {
    await waitForServer(BASE_URL, instanceToken)
    console.log('Server verified. Launching browser for screenshots and visual verification...')

    const browser = await chromium.launch({ headless: true })

    // 1. Desktop Context (1280x800)
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      locale: 'zh-CN',
    })
    const page = await desktopContext.newPage()

    page.on('dialog', async d => {
      await d.accept()
    })

    // Register test user
    await page.goto(BASE_URL)
    await page.waitForSelector('.auth-page')
    await page.click('button:has-text("首次使用？创建账号")')
    await page.fill('input[placeholder="用户名"]', 'ui_designer')
    await page.fill('input[placeholder="密码（至少 8 位）"]', 'designer-password-123')
    await page.click('button:has-text("注册并登录")')
    await page.waitForSelector('.home-page')

    const userStorage = await page.evaluate(() => localStorage.getItem('easyexam_user'))
    const token = await page.evaluate(() => localStorage.getItem('easyexam_token'))
    console.log('User and token extracted from localStorage:', !!userStorage, !!token)

    // Create Bank directly via API
    const createBankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        name: '2026架构师全真模拟题库',
        category: '系统架构',
        description: '系统架构设计师专业题库'
      }),
    })
    if (!createBankRes.ok) {
      const errText = await createBankRes.text()
      throw new Error(`Failed to create bank: ${createBankRes.status} ${errText}`)
    }
    const bank = await createBankRes.json()
    console.log('Created bank via API:', bank.id, bank.name)

    // Question 1: Single choice
    await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        stem: '在软件架构评估中，评估架构能否在预期时间内完成计算任务的质量属性是？',
        type: 'SINGLE',
        options: [
          { key: 'A', content: '可用性 (Availability)' },
          { key: 'B', content: '性能 (Performance)' },
          { key: 'C', content: '安全性 (Security)' },
          { key: 'D', content: '可修改性 (Modifiability)' },
        ],
        answer: 'B',
        explanation: '性能（Performance）是指系统的响应能力，即在特定负载下完成计算任务的响应时间、吞吐率等指标。',
        tags: ['系统架构', '质量属性'],
      }),
    })

    // Question 2: Multi choice
    await fetch(`${BASE_URL}/api/v1/banks/${bank.id}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        stem: '微服务架构风格的主要特征与优势包括哪些？（多选）',
        type: 'MULTIPLE',
        options: [
          { key: 'A', content: '高度去中心化的数据管理' },
          { key: 'B', content: '服务独立部署与按需水平伸缩' },
          { key: 'C', content: '业务围绕业务能力进行垂直组织拆分' },
          { key: 'D', content: '强制所有服务使用单一编程语言统一构建' },
        ],
        answer: 'ABC',
        explanation: '微服务架构的核心是松耦合、独立部署、去中心化治理和多语言生态适配，D选项表述错误。',
        tags: ['微服务', '多选题'],
      }),
    })

    // Reload home page to see new bank and learning stats
    await page.reload()
    await page.waitForSelector('.bank-card:has-text("2026架构师全真模拟题库")')
    await page.waitForSelector('.bank-card:has-text("2026架构师全真模拟题库") button.primary')
    await page.waitForTimeout(500)

    // Capture 1: Home Page (Default Neutral Blue-Grey)
    const homeShot = path.join(outputDir, '01_desktop_home_blue_grey_light.png')
    await page.screenshot({ path: homeShot, fullPage: false })
    console.log(`Saved screenshot 1: ${homeShot}`)

    // Navigate to Practice Page
    await page.click('.bank-card:has-text("2026架构师全真模拟题库") button.primary')
    await page.waitForSelector('.practice-page')

    // Answer Q1 (select B - Performance, submit)
    await page.click('.option:has-text("性能")')
    await page.click('button:has-text("提交答案")')
    await page.waitForSelector('.result-card, .quick-verdict-bar')
    await page.waitForTimeout(500)

    // Capture 2: Practice View (Single Choice Answered + Verdict + Explanation)
    const practiceShot = path.join(outputDir, '02_desktop_practice_single_choice.png')
    await page.screenshot({ path: practiceShot, fullPage: false })
    console.log(`Saved screenshot 2: ${practiceShot}`)

    // Navigate to Settings Page
    await page.goto(`${BASE_URL}/#/settings`)
    await page.waitForSelector('.settings-page')
    await page.waitForTimeout(500)

    // Capture 3: Settings Page (8 Palettes, Custom Accent with WCAG AA badge)
    const settingsShot = path.join(outputDir, '03_desktop_settings_themes.png')
    await page.screenshot({ path: settingsShot, fullPage: false })
    console.log(`Saved screenshot 3: ${settingsShot}`)

    // Switch to Dark Mode on Settings
    await page.click('.segment-btn:has-text("深色模式")')
    await page.waitForTimeout(600)

    // Capture 4: Settings Page (Dark Mode)
    const settingsDarkShot = path.join(outputDir, '04_desktop_settings_dark_mode.png')
    await page.screenshot({ path: settingsDarkShot, fullPage: false })
    console.log(`Saved screenshot 4: ${settingsDarkShot}`)

    // Switch to another palette (e.g. ocean) in dark mode
    await page.click('.palette-preview-card[data-preview-palette="ocean"]')
    await page.waitForTimeout(400)

    // Return to light mode and navigate to Notes
    await page.click('.segment-btn:has-text("浅色模式")')
    await page.goto(`${BASE_URL}/#/notes`)
    await page.waitForSelector('.notes-page')
    await page.waitForTimeout(400)

    // Capture 5: Knowledge Notes View
    const notesShot = path.join(outputDir, '05_desktop_notes_view.png')
    await page.screenshot({ path: notesShot, fullPage: false })
    console.log(`Saved screenshot 5: ${notesShot}`)

    await desktopContext.close()

    // 2. Mobile Context (375x667 iPhone SE)
    const mobileContext = await browser.newContext({
      viewport: { width: 375, height: 667 },
      isMobile: true,
      hasTouch: true,
      locale: 'zh-CN',
    })
    const mobilePage = await mobileContext.newPage()
    await mobilePage.goto(BASE_URL)
    await mobilePage.evaluate(({ savedUser, savedToken }) => {
      localStorage.setItem('easyexam_user', savedUser)
      localStorage.setItem('easyexam_token', savedToken)
    }, { savedUser: userStorage, savedToken: token })
    await mobilePage.reload()
    await mobilePage.waitForSelector('.home-page')
    await mobilePage.waitForTimeout(400)

    // Capture 6: Mobile Home View (375px)
    const mobileHomeShot = path.join(outputDir, '06_mobile_home_375px.png')
    await mobilePage.screenshot({ path: mobileHomeShot, fullPage: false })
    console.log(`Saved screenshot 6: ${mobileHomeShot}`)

    // Mobile practice navigation
    await mobilePage.waitForSelector('.bank-card:has-text("2026架构师全真模拟题库") button.primary')
    await mobilePage.click('.bank-card:has-text("2026架构师全真模拟题库") button.primary')
    await mobilePage.waitForSelector('.practice-page')
    await mobilePage.waitForTimeout(400)

    // Capture 7: Mobile Practice View (375px)
    const mobilePracticeShot = path.join(outputDir, '07_mobile_practice_375px.png')
    await mobilePage.screenshot({ path: mobilePracticeShot, fullPage: false })
    console.log(`Saved screenshot 7: ${mobilePracticeShot}`)

    // Verify no horizontal overflow on mobile
    const scrollWidth = await mobilePage.evaluate(() => document.documentElement.scrollWidth)
    const clientWidth = await mobilePage.evaluate(() => document.documentElement.clientWidth)
    if (scrollWidth > clientWidth + 1) {
      throw new Error(`Mobile horizontal overflow detected: scrollWidth=${scrollWidth} > clientWidth=${clientWidth}`)
    }
    console.log(`Mobile zero-overflow check passed: scrollWidth=${scrollWidth} == clientWidth=${clientWidth}`)

    await mobileContext.close()
    await browser.close()
    console.log('All screenshots and visual assertions completed successfully!')
  } finally {
    server.kill()
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
}

main().catch(err => {
  console.error('Fatal error during UI audit:', err)
  process.exit(1)
})
