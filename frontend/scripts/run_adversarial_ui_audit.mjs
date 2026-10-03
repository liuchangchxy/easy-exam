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
const snapshotDir = process.env.SNAPSHOT_DIR || path.join(os.homedir(), '.gemini', 'antigravity', 'brain', '82b64ccb-5ad8-4477-8bdc-770bbf2aa712', 'snapshots', 'adversarial')

fs.mkdirSync(snapshotDir, { recursive: true })

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

async function waitForServer(url, timeoutMs = 25000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${url}/api/v1/health`)
      if (res.ok) return true
    } catch (_) {}
    await new Promise(r => setTimeout(r, 400))
  }
  throw new Error(`Server at ${url} failed to start within ${timeoutMs}ms`)
}

async function detectAnomalies(page, pageName, viewportName) {
  return await page.evaluate(({ pageName, viewportName }) => {
    const anomalies = []
    const docWidth = document.documentElement.scrollWidth
    const winWidth = window.innerWidth
    if (docWidth > winWidth + 1) {
      const overflowingElements = []
      const allEls = document.querySelectorAll('*')
      for (const el of allEls) {
        const rect = el.getBoundingClientRect()
        if (rect.right > winWidth + 2) {
          const tag = el.tagName.toLowerCase()
          const cls = (el.className && typeof el.className === 'string') ? el.className.split(' ').slice(0, 3).join('.') : ''
          overflowingElements.push(`${tag}.${cls} (right: ${Math.round(rect.right)}px > ${winWidth}px)`)
          if (overflowingElements.length >= 5) break
        }
      }
      anomalies.push({
        type: 'HORIZONTAL_OVERFLOW',
        severity: 'P1',
        detail: `[${pageName}] 在 ${viewportName} 下发生整页横向撑破滚动！文档宽度 ${docWidth}px > 视口宽度 ${winWidth}px。超界元素: ${overflowingElements.join(', ')}`
      })
    }

    if (winWidth <= 480) {
      const smallTargets = []
      const interactives = document.querySelectorAll('button:not([disabled]), a[href], input:not([type="hidden"]), select')
      for (const el of interactives) {
        const style = window.getComputedStyle(el)
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue
        const rect = el.getBoundingClientRect()
        if (rect.width === 0 || rect.height === 0) continue
        if (rect.bottom < 0 || rect.top > window.innerHeight) continue

        if (rect.width < 40 || rect.height < 40) {
          const text = (el.textContent || el.getAttribute('aria-label') || el.value || '').trim().slice(0, 20)
          const tag = el.tagName.toLowerCase()
          const cls = (el.className && typeof el.className === 'string') ? el.className.split(' ').slice(0, 2).join('.') : ''
          smallTargets.push(`${tag}.${cls} "${text}" (${Math.round(rect.width)}x${Math.round(rect.height)}px)`)
          if (smallTargets.length >= 8) break
        }
      }
      if (smallTargets.length > 0) {
        anomalies.push({
          type: 'SMALL_TOUCH_TARGETS',
          severity: 'P2',
          detail: `[${pageName}] 在 ${viewportName} 下存在 ${smallTargets.length}+ 处触控目标小于 40px: ${smallTargets.join('; ')}`
        })
      }
    }

    return anomalies
  }, { pageName, viewportName })
}

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'easyexam-adv-audit-'))
  const tempDbPath = path.join(tempDir, 'adv_audit.db')
  const storageStateFile = path.join(tempDir, 'state.json')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const BASE_URL = `http://127.0.0.1:${port}`

  const pythonBin = fs.existsSync(path.join(repoRoot, '.venv/bin/python'))
    ? path.join(repoRoot, '.venv/bin/python')
    : 'python'

  console.log(`[ADV-AUDIT] Starting backend with temporary DB at ${tempDbPath}...`)
  const serverProcess = spawn(
    pythonBin,
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: repoRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        DB_PATH: tempDbPath,
        INSTANCE_TOKEN: instanceToken,
        EASYEXAM_SECRET_KEY: 'adv-audit-secret-key-32bytes-secure!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  let browser = null
  const allAnomalies = []

  try {
    await waitForServer(BASE_URL)
    console.log('[ADV-AUDIT] Backend is ready. Launching Playwright...')

    browser = await chromium.launch({ headless: true })

    // Step 1: Initial Desktop Session to Register Auditor & Seed Chaos Fixture
    const setupContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      locale: 'zh-CN'
    })
    const setupPage = await setupContext.newPage()
    await setupPage.goto(BASE_URL)
    await setupPage.waitForSelector('.auth-page', { timeout: 10000 })

    await setupPage.click('button:has-text("首次使用？创建账号")')
    await setupPage.fill('input[placeholder="用户名"]', 'chaos_auditor')
    await setupPage.fill('input[placeholder*="密码"]', 'Password123!')
    await setupPage.click('button:has-text("注册并登录")')
    await setupPage.waitForSelector('.home-page', { timeout: 10000 })

    // Save browser storage state so all subsequent contexts inherit authentication
    await setupContext.storageState({ path: storageStateFile })

    const token = await setupPage.evaluate(() => localStorage.getItem('easyexam_token'))

    // 2. Create Chaos Bank with 76-character name and 15 tags
    console.log('[ADV-AUDIT] Seeding chaos stress bank & questions via API...')
    const chaosBankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        name: '2026年全国硕士研究生招生考试思想政治理论核心考点精讲精练与真题冲刺拔高题库（终极突破版·内部强化资料）',
        category: '考研政治',
        description: '本题库涵盖马克思主义基本原理概论、毛泽东思想和中国特色社会主义理论体系概论、中国近现代史纲要、思想道德修养与法律基础、形势与政策以及当代世界经济与政治全科目超详细深度解析，专为冲刺90分量身打造。',
        tags: ['考研政治', '马原', '毛中特', '史纲', '思修法基', '当代政经', '冲刺模考', '高频必刷', '错题收割', '名师划重点', '押题卷', '选择题技巧', '论述模板', '时政热点', '终极预测']
      })
    })
    const chaosBank = await chaosBankRes.json()

    // 3. Inject Extreme Questions into Chaos Bank
    const longStem = `【案例背景材料与综合论述】\n根据唯物辩证法关于量变与质变的辩证统一规律，事物的发展总是从微小的量变开始，量变是质变的必要准备，质变是量变的必然结果。请结合爱因斯坦质能方程 $E=mc^2$ 与高斯积分公式 $\\int_{-\\infty}^{+\\infty} e^{-x^2} dx = \\sqrt{\\pi}$ 进行跨学科哲学推导。\n\n同时在现代大型工程软件架构实践中，我们遇到如下未经代码审查的底层配置常量定义：\n` +
      `\`\`\`typescript\n` +
      `const REALLY_REALLY_EXTREMELY_LONG_UNSPACED_VARIABLE_NAME_CONFIG_IDENTIFIER_THAT_CANNOT_BE_BROKEN_NATURALLY_INTO_LINES = "SUPER_LONG_PAYLOAD_STRING_0123456789_ABCDEF_GHIJKL_MNOPQR_STUVWXYZ_9876543210_ZZZZZZZZZZZZZZZZZZZZZZZZ";\n` +
      `\`\`\`\n` +
      `材料同时指出，在数字时代与全球化格局交织的新技术范式下，生产力与生产关系的矛盾运动展现出空前的复杂性与异化特征。请分析下列哪一项关于现代自动化认知系统的表述最为严谨且符合唯物史观？`

    await fetch(`${BASE_URL}/api/v1/banks/${chaosBank.id}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        stem: longStem,
        type: 'SINGLE',
        options: [
          { key: 'A', content: '生产关系对生产力的反作用仅在封建自然经济形态下有效，数字劳动已彻底超越唯物史观解释边界。' },
          { key: 'B', content: '科学技术作为第一生产力，能够从根本上取代人类体力劳动与抽象思维劳动的主体性地位。' },
          { key: 'C', content: '【深度超长选项】数字生产工具的迭代并未从根本上消除资本增殖逻辑对活劳动的吸纳与重构，人工智能与算法推荐系统依然建立在历史沉淀的数据要素与集体认知劳动的基础上，必须坚持生产力决定生产关系、经济基础决定上层建筑的基本历史辩证法规律，任何技术崇拜论都是唯心史观在现代工业文明下的新变种。' },
          { key: 'D', content: '量变引起质变是一次性完成的突变过程，不需要连续渐进性的能量与物质积累。' },
          { key: 'E', content: '选项E：极端边界选项，测试布局是否能容纳超过5个以上的选项单列容器。' },
          { key: 'F', content: '选项F：测试键盘快捷键F是否能正常触发选中与提交响应。' },
          { key: 'G', content: '选项G：测试移动端视口高度在承载7个以上选项时，底部操作栏是否产生视口溢出或遮挡。' },
          { key: 'H', content: '选项H：终极极限选项，用于压测答题卡网格排列及A~H枚举字符的排版鲁棒性。' }
        ],
        answer: 'C',
        explanation: '唯物史观认为，生产工具是生产力发展水平的标志。数字时代的算法与数据要素仍然是生产力范畴的劳动资料与对象，没有改变人类社会发展的客观基本规律。',
        tags: ['马克思主义哲学', '长材料分析']
      })
    })

    await setupContext.close()

    // Viewport matrix
    const viewports = [
      { name: '320px-ultra-narrow', width: 320, height: 667, isMobile: true },
      { name: '375px-mobile', width: 375, height: 812, isMobile: true },
      { name: '1280px-desktop', width: 1280, height: 800, isMobile: false }
    ]

    for (const vp of viewports) {
      console.log(`\n========================================`)
      console.log(`[ADV-AUDIT] Running tests on viewport: ${vp.name} (${vp.width}x${vp.height})`)
      console.log(`========================================`)

      const ctx = await browser.newContext({
        storageState: storageStateFile,
        viewport: { width: vp.width, height: vp.height },
        isMobile: vp.isMobile,
        hasTouch: vp.isMobile,
        deviceScaleFactor: vp.isMobile ? 2 : 1,
        locale: 'zh-CN'
      })
      const page = await ctx.newPage()

      // 1. Audit HomeView with Chaos Bank
      await page.goto(`${BASE_URL}/#/`)
      await page.waitForSelector('.bank-card', { timeout: 10000 })
      await page.waitForTimeout(500)
      const homeShot = path.join(snapshotDir, `01-home-chaos-${vp.name}.png`)
      await page.screenshot({ path: homeShot, fullPage: true })
      const homeAnomalies = await detectAnomalies(page, 'HomeView-Chaos', vp.name)
      allAnomalies.push(...homeAnomalies)

      // 2. Audit PracticeViewV1 with Stress Question
      // Click "顺序通刷" or the primary action on the chaos bank card
      const practiceBtn = await page.locator('.bank-primary-actions button.primary, button:has-text("顺序通刷")').first()
      if (await practiceBtn.count() > 0) {
        await practiceBtn.click()
        await page.waitForSelector('.practice-page', { timeout: 10000 })
        await page.waitForTimeout(600)
        const practiceShot = path.join(snapshotDir, `02-practice-stress-${vp.name}.png`)
        await page.screenshot({ path: practiceShot, fullPage: true })
        const practiceAnomalies = await detectAnomalies(page, 'PracticeView-Stress', vp.name)
        allAnomalies.push(...practiceAnomalies)

        // Open Answer Sheet Drawer on mobile
        if (vp.isMobile) {
          const sheetTrigger = await page.$('.btn-sheet-trigger-pill, .btn-open-drawer')
          if (sheetTrigger) {
            await sheetTrigger.click()
            await page.waitForTimeout(400)
            const sheetShot = path.join(snapshotDir, `02b-practice-drawer-${vp.name}.png`)
            await page.screenshot({ path: sheetShot })
            const drawerAnomalies = await detectAnomalies(page, 'PracticeView-Drawer', vp.name)
            allAnomalies.push(...drawerAnomalies)
            const closeBtn = await page.$('.drawer-header button, .btn-drawer-close, .btn-close-sheet')
            if (closeBtn) await closeBtn.click()
          }
        }
      }

      // 3. Audit ImportView (Unexamined view)
      await page.goto(`${BASE_URL}/#/import`)
      await page.waitForSelector('.import-page', { timeout: 10000 })
      await page.waitForTimeout(400)
      const importShot = path.join(snapshotDir, `03-import-${vp.name}.png`)
      await page.screenshot({ path: importShot, fullPage: true })
      const importAnomalies = await detectAnomalies(page, 'ImportView', vp.name)
      allAnomalies.push(...importAnomalies)

      // 4. Audit LearningView (Unexamined view)
      await page.goto(`${BASE_URL}/#/learning`)
      await page.waitForSelector('.learning-dashboard, .learning-container, main', { timeout: 10000 })
      await page.waitForTimeout(400)
      const learningShot = path.join(snapshotDir, `04-learning-${vp.name}.png`)
      await page.screenshot({ path: learningShot, fullPage: true })
      const learningAnomalies = await detectAnomalies(page, 'LearningView', vp.name)
      allAnomalies.push(...learningAnomalies)

      // 5. Audit NotesView (Unexamined view)
      await page.goto(`${BASE_URL}/#/notes`)
      await page.waitForSelector('.notes-view, main', { timeout: 10000 })
      await page.waitForTimeout(400)
      const notesShot = path.join(snapshotDir, `05-notes-${vp.name}.png`)
      await page.screenshot({ path: notesShot, fullPage: true })
      const notesAnomalies = await detectAnomalies(page, 'NotesView', vp.name)
      allAnomalies.push(...notesAnomalies)

      // 6. Audit MistakesView (Unexamined view on mobile/narrow)
      await page.goto(`${BASE_URL}/#/mistakes`)
      await page.waitForSelector('.mistakes-page, main', { timeout: 10000 })
      await page.waitForTimeout(400)
      const mistakesShot = path.join(snapshotDir, `06-mistakes-${vp.name}.png`)
      await page.screenshot({ path: mistakesShot, fullPage: true })
      const mistakesAnomalies = await detectAnomalies(page, 'MistakesView', vp.name)
      allAnomalies.push(...mistakesAnomalies)

      await ctx.close()
    }

    console.log('\n========================================')
    console.log(`[ADV-AUDIT] Audit finished! Total anomalies detected: ${allAnomalies.length}`)
    console.log('========================================')
    for (const an of allAnomalies) {
      console.log(`[${an.severity}] ${an.type}: ${an.detail}`)
    }

    // Write findings to JSON
    const reportPath = path.join(snapshotDir, 'adversarial_findings.json')
    fs.writeFileSync(reportPath, JSON.stringify(allAnomalies, null, 2))
    console.log(`[ADV-AUDIT] Report saved to ${reportPath}`)

  } finally {
    if (browser) await browser.close()
    serverProcess.kill()
  }
}

main().catch(err => {
  console.error('[ADV-AUDIT] Error during audit:', err)
  process.exit(1)
})
