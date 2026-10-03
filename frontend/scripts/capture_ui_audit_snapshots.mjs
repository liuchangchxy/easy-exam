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
const snapshotDir = process.env.SNAPSHOT_DIR || path.join(os.homedir(), '.gemini', 'antigravity', 'brain', '82b64ccb-5ad8-4477-8bdc-770bbf2aa712', 'snapshots')

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

async function main() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'easyexam-ui-audit-'))
  const tempDbPath = path.join(tempDir, 'audit.db')
  const port = await getFreePort()
  const instanceToken = crypto.randomUUID()
  const BASE_URL = `http://127.0.0.1:${port}`

  const pythonBin = fs.existsSync(path.join(repoRoot, '.venv/bin/python'))
    ? path.join(repoRoot, '.venv/bin/python')
    : 'python'

  console.log(`Starting FastAPI on port ${port}...`)
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
        EASYEXAM_SECRET_KEY: 'audit-secret-key-32bytes-secure!',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  )

  let serverErrorOutput = ''
  serverProcess.stderr.on('data', chunk => {
    serverErrorOutput += chunk.toString()
  })

  let browser = null
  try {
    await waitForServer(BASE_URL)
    console.log('FastAPI server is up. Launching Chromium...')

    browser = await chromium.launch({ headless: true })

    // 1. 桌面端走查 (1280x800)
    console.log('Taking Desktop snapshots (1280x800)...')
    const desktopContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      locale: 'zh-CN',
    })
    const dPage = await desktopContext.newPage()

    // 登录页
    await dPage.goto(BASE_URL)
    await dPage.waitForSelector('.auth-page', { timeout: 10000 })
    await dPage.screenshot({ path: path.join(snapshotDir, '01-login-desktop.png') })

    // 注册并自动登录
    await dPage.click('button:has-text("首次使用？创建账号")')
    await dPage.fill('input[placeholder="用户名"]', 'auditor_user')
    await dPage.fill('input[placeholder*="密码"]', 'Password123!')
    await dPage.click('button:has-text("注册并登录")')
    await dPage.waitForSelector('.home-page', { timeout: 10000 })

    const token = await dPage.evaluate(() => localStorage.getItem('easyexam_token'))

    // 通过 API 播种题库和丰富题目
    console.log('Seeding bank and sample questions via API...')
    const bankRes = await fetch(`${BASE_URL}/api/v1/banks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        name: '计算机网络与架构设计精选题库',
        category: '软件水平考试',
        description: '涵盖TCP/IP协议栈、微服务高并发削峰、分布式缓存调优与故障恢复策略的核心单选与多选题。',
      }),
    })
    const bank = await bankRes.json()
    const bankId = bank.id

    // Question 1: Single choice
    await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        stem: '在TCP三次握手中，当客户端主动发送SYN报文并收到服务端的SYN+ACK报文后，客户端当前处于哪种连接状态？',
        type: 'SINGLE',
        options: [
          { key: 'A', content: 'ESTABLISHED（已建立连接）' },
          { key: 'B', content: 'SYN_SENT（已发送同步请求）' },
          { key: 'C', content: 'SYN_RCVD（收到同步请求并等待最终确认）' },
          { key: 'D', content: 'TIME_WAIT（等待足够时间确保对端收到ACK）' },
        ],
        answer: 'A',
        explanation: '客户端发送SYN后进入SYN_SENT状态；收到服务端的SYN+ACK并回复最后的ACK报文后，客户端便立即进入ESTABLISHED状态。服务端在收到该ACK报文后才进入ESTABLISHED。',
        tags: ['计算机网络', 'TCP协议'],
      }),
    })

    // Question 2: Multi choice
    await fetch(`${BASE_URL}/api/v1/banks/${bankId}/questions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        stem: '某分布式电商系统在高并发秒杀活动中遭遇严重数据库写瓶颈，下列哪些治理与改造方案可以有效提升吞吐量并防止雪崩？（多选）',
        type: 'MULTI',
        options: [
          { key: 'A', content: '引入分布式消息队列（如 RocketMQ/Kafka）进行异步削峰与落盘' },
          { key: 'B', content: '采用水平分库分表（Sharding）策略，按用户或订单维度分散IO压力' },
          { key: 'C', content: '在主库中开启强同步复制并增加实时多表联查触发器' },
          { key: 'D', content: '基于 Redis 预扣减库存，并配合定期批量原子刷盘' },
        ],
        answer: 'ABD',
        explanation: '选项A、B、D均能显著降低实时数据库写入压力；选项C会极大加剧事务阻塞延时与死锁概率，属于典型反模式。',
        tags: ['高并发', '架构设计'],
      }),
    })

    // 刷新页面展示题库卡片
    await dPage.reload()
    await dPage.waitForSelector('.bank-card', { timeout: 10000 })
    await dPage.screenshot({ path: path.join(snapshotDir, '02-home-desktop.png') })

    // 进入做题：未作答态
    await dPage.click('button:has-text("顺序通刷")')
    await dPage.waitForSelector('.practice-page', { timeout: 10000 })
    await dPage.screenshot({ path: path.join(snapshotDir, '03-practice-unanswered-desktop.png') })

    // 选中选项并提交判分
    await dPage.click('.option:has-text("ESTABLISHED")')
    await dPage.waitForTimeout(200)
    await dPage.click('button:has-text("提交答案")')
    await dPage.waitForSelector('.quick-verdict-bar', { timeout: 5000 })
    await dPage.waitForTimeout(300)
    await dPage.screenshot({ path: path.join(snapshotDir, '04-practice-answered-desktop.png') })

    // 展开解析后做题界面
    await dPage.screenshot({ path: path.join(snapshotDir, '05-practice-explanation-desktop.png') })

    // 导航到错题攻克
    await dPage.click('.btn-back')
    await dPage.waitForSelector('.home-page', { timeout: 5000 })
    await dPage.click('.sidebar-nav-item:has-text("错题")')
    await dPage.waitForSelector('.mistakes-page', { timeout: 5000 })
    await dPage.screenshot({ path: path.join(snapshotDir, '06-mistakes-desktop.png') })

    await desktopContext.close()

    // 2. 移动端走查 (375x812, iPhone 12)
    console.log('Taking Mobile snapshots (375x812)...')
    const mobileContext = await browser.newContext({
      viewport: { width: 375, height: 812 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
      locale: 'zh-CN',
    })
    const mPage = await mobileContext.newPage()

    // 移动端登录页
    await mPage.goto(BASE_URL)
    await mPage.waitForSelector('.auth-page', { timeout: 10000 })
    await mPage.screenshot({ path: path.join(snapshotDir, '01-login-mobile.png') })

    // 登录同一账号
    await mPage.fill('input[placeholder="用户名"]', 'auditor_user')
    await mPage.fill('input[placeholder*="密码"]', 'Password123!')
    await mPage.click('button[type="submit"]')
    await mPage.waitForSelector('.home-page', { timeout: 10000 })
    await mPage.screenshot({ path: path.join(snapshotDir, '02-home-mobile.png') })

    // 移动端进入做题
    await mPage.click('.bank-primary-actions button.primary')
    await mPage.waitForSelector('.practice-page', { timeout: 10000 })
    await mPage.screenshot({ path: path.join(snapshotDir, '03-practice-mobile.png') })

    // 点击顶栏答题卡抽屉
    const sheetPill = await mPage.$('.btn-sheet-trigger-pill')
    if (sheetPill) {
      await sheetPill.click()
      await mPage.waitForSelector('.sheet-modal-drawer', { timeout: 3000 })
      await mPage.screenshot({ path: path.join(snapshotDir, '04-practice-sheet-drawer-mobile.png') })
      await mPage.click('.btn-close-sheet')
    }

    // 移动端错题中心
    const mistakesNavItem = await mPage.$('.mobile-nav-item:has-text("错题")')
    if (mistakesNavItem) {
      await mistakesNavItem.click()
      await mPage.waitForSelector('.mistakes-page', { timeout: 5000 })
      await mPage.screenshot({ path: path.join(snapshotDir, '05-mistakes-mobile.png') })
    }

    await mobileContext.close()
    console.log('SUCCESS: All snapshots captured in:', snapshotDir)
  } catch (err) {
    console.error('Error during snapshot capture:', err)
    if (serverErrorOutput) {
      console.error('Server stderr:', serverErrorOutput)
    }
    throw err
  } finally {
    if (browser) await browser.close()
    if (serverProcess) {
      serverProcess.kill('SIGTERM')
    }
  }
}

main().catch(err => {
  console.error(err)
  process.exit(1)
})
