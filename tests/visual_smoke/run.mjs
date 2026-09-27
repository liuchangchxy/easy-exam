// Visual smoke runner: builds nothing, serves frontend/dist on a free port,
// launches headless Chrome on a free debugging port, then invokes shot.mjs.
//
// Dynamic ports are mandatory here (matching frontend/tests/capture_ui_screenshots.mjs
// and browser_e2e.test.js): fixed ports collide with stray processes and are
// blocked in sandboxed environments.
//
// Usage: node tests/visual_smoke/run.mjs [--settle <ms>] [--allow-missing-host]

import { spawn } from 'node:child_process'
import net from 'node:net'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')
const distDir = path.join(repoRoot, 'frontend', 'dist')
const outDir = path.join(repoRoot, 'screenshots', 'visual_smoke')
const CHROME = process.env.CHROME_PATH
  || 'C:/Program Files/Google/Chrome/Application/chrome.exe'

if (!fs.existsSync(path.join(distDir, 'index.html'))) {
  console.error(`No build found at ${distDir}. Run: npm --prefix frontend run build`)
  process.exit(2)
}

const freePort = () => new Promise((res, rej) => {
  const s = net.createServer()
  s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)) })
  s.on('error', rej)
})

const appPort = await freePort()
const cdpPort = await freePort()
console.log(`serving ${distDir} on :${appPort}, CDP on :${cdpPort}`)

const serverPy = [
  'import http.server, socketserver, os',
  'os.chdir(os.environ["SMOKE_DIST"])',
  'class H(http.server.SimpleHTTPRequestHandler):',
  '    def log_message(self, *a): pass',
  'socketserver.TCPServer.allow_reuse_address = True',
  'socketserver.TCPServer(("127.0.0.1", int(os.environ["SMOKE_PORT"])), H).serve_forever()',
].join('\n')

const server = spawn('python', ['-c', serverPy], {
  stdio: ['ignore', 'pipe', 'pipe'],
  env: { ...process.env, SMOKE_DIST: distDir, SMOKE_PORT: String(appPort) },
})
// Profile lives in the OS temp dir, never in the repo.
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'easyexam-vsprof-'))
const chrome = spawn(CHROME, [
  '--headless=new', '--no-sandbox', '--window-size=1280,900',
  `--remote-debugging-port=${cdpPort}`, `--user-data-dir=${profile}`, 'about:blank',
], { stdio: ['ignore', 'pipe', 'pipe'] })

const cleanup = () => {
  try { server.kill() } catch {}
  try { chrome.kill() } catch {}
  try { fs.rmSync(profile, { recursive: true, force: true }) } catch {}
}

await new Promise((r) => setTimeout(r, 4000))

const passthrough = process.argv.slice(2)
const child = spawn(process.execPath, [
  path.join(__dirname, 'shot.mjs'),
  `http://127.0.0.1:${appPort}`,
  outDir,
  ...passthrough,
], {
  cwd: repoRoot,
  env: { ...process.env, CDP_URL: `http://localhost:${cdpPort}` },
  stdio: 'inherit',
})

child.on('exit', (code) => { cleanup(); process.exit(code ?? 1) })
process.on('SIGINT', () => { cleanup(); process.exit(130) })
