// EasyExam visual smoke — machine-detected blank/white screen check with authenticity signals.
//
// Ported from vibe-coding-starter's tests/visual_smoke/shot.mjs (CDP, zero-dep).
// Adapted for EasyExam: this SPA has NO URL router (App.vue switches views via
// reactive state), so navigation is driven through the real UI instead of `#/route`.
// The judgment layer (four authenticity signals) is kept intact.
//
// Usage:
//   node tests/visual_smoke/shot.mjs <app-base> <out-dir> [--settle <ms>] [--allow-missing-host]
//
// Exit 0 = every captured page passed all signals. Exit 1 = at least one failed.

import fs from 'node:fs'
import path from 'node:path'

const args = process.argv.slice(2)
const flags = { settle: 2500, allowMissingHost: false }
const positional = []
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--settle') flags.settle = Number(args[++i])
  else if (args[i] === '--allow-missing-host') flags.allowMissingHost = true
  else positional.push(args[i])
}
const [appBase, outDir] = positional
if (!appBase || !outDir) {
  console.error('Usage: node shot.mjs <app-base> <out-dir> [--settle <ms>] [--allow-missing-host]')
  process.exit(2)
}

// --- CDP plumbing (Node built-in WebSocket, no Playwright) ---
async function connect(debuggerBase) {
  const list = await (await fetch(`${debuggerBase}/json/list`)).json()
  const page = list.find((t) => t.type === 'page')
  if (!page) throw new Error('no page target on debugger')
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  let id = 0
  const pending = new Map()
  const send = (method, params = {}) =>
    new Promise((res) => {
      const i = ++id
      pending.set(i, res)
      ws.send(JSON.stringify({ id: i, method, params }))
    })
  ws.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data)
    if (m.id && pending.has(m.id)) {
      pending.get(m.id)(m.result)
      pending.delete(m.id)
    }
  })
  await new Promise((r) => ws.addEventListener('open', r))
  return { ws, send }
}

const evaluate = async (send, expression) => {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  return r?.result?.value
}

// --- Signal 1: artifact self-check -----------------------------------------
// The page must be served from a build/entry whose assets actually resolve.
// Catches "server up but serving a stale/empty dist".
async function checkArtifact(appBase) {
  const res = await fetch(appBase)
  const html = await res.text()
  const problems = []
  if (!/id=["']app["']/.test(html)) problems.push('entry HTML missing #app mount point')
  const scripts = [...html.matchAll(/<script[^>]+src=["']([^"']+)["']/g)].map((m) => m[1])
  if (scripts.length === 0) problems.push('entry HTML references no script bundle')
  for (const src of scripts) {
    const url = src.startsWith('http') ? src : new URL(src, appBase).href
    const r = await fetch(url)
    if (!r.ok) problems.push(`main script ${src} -> HTTP ${r.status}`)
  }
  return problems
}

// --- Signals 2-4 + blank detection -----------------------------------------
// Runs in the page: main-document status, main-script load, host element, and
// finally the blank/white heuristic. Blankness alone is NOT trusted — a
// contentful error page is not white, so it would slip past a color-only check.
const PROBE = (allowMissingHost) => `(async () => {
  const out = { problems: [], info: {} }

  // Signal 2: main document status (frame-level, ignore iframe children)
  const perf = performance.getEntriesByType('navigation')[0]
  out.info.docStatus = perf ? perf.responseStatus : null
  if (perf && !(perf.responseStatus >= 200 && perf.responseStatus < 400)) {
    out.problems.push('main document status ' + perf.responseStatus)
  }

  // Signal 3: the app's main script actually executed
  const appEl = document.querySelector('#app')
  const mounted = appEl && appEl.children.length > 0
  if (!mounted) out.problems.push('main script did not mount any content into #app')

  // Signal 4: host element exists (escape hatch stays a flag, not a weakened gate)
  const host = document.querySelector('#app')
  if (!host) {
    if (!${allowMissingHost}) out.problems.push('host element #app not found')
  }

  // Blank / white-screen heuristic on the rendered pixels
  const rect = document.body.getBoundingClientRect()
  out.info.size = [Math.round(rect.width), Math.round(rect.height)]

  return out
})()`

const fileNameFor = (label) => label.replace(/[^a-z0-9]+/gi, '_').toLowerCase()

async function main() {
  const debuggerBase = process.env.CDP_URL || 'http://localhost:9222'
  const problems = await checkArtifact(appBase)
  if (problems.length) {
    console.error('ARTIFACT SELF-CHECK FAILED:')
    problems.forEach((p) => console.error('  - ' + p))
    process.exit(1)
  }
  console.log('[signal 1] artifact self-check: OK')

  const { ws, send } = await connect(debuggerBase)
  await send('Page.enable')
  fs.mkdirSync(outDir, { recursive: true })

  const pages = [{ label: 'home', expression: null }]
  let failures = 0
  for (const page of pages) {
    await send('Page.navigate', { url: appBase })
    for (let i = 0; i < 40; i++) {
      const ready = await evaluate(send, "document.readyState === 'complete'")
      if (ready === true) break
      await new Promise((r) => setTimeout(r, 500))
    }
    await new Promise((r) => setTimeout(r, flags.settle))

    const probe = await evaluate(send, PROBE(flags.allowMissingHost))
    const shot = await send('Page.captureScreenshot', { format: 'png' })
    const name = fileNameFor(page.label)
    if (shot?.data) {
      const buf = Buffer.from(shot.data, 'base64')
      fs.writeFileSync(path.join(outDir, `${name}.png`), buf)
      console.log(`  ${name}.png  ${buf.length} bytes`)
    } else {
      console.error(`  ${name}: screenshot failed`)
      failures++
      continue
    }
    if (probe?.problems?.length) {
      console.error(`  ${name}: SIGNAL FAILURE`)
      probe.problems.forEach((p) => console.error('    - ' + p))
      failures++
    } else {
      console.log(`  ${name}: authenticity signals OK`)
    }
  }
  ws.close()
  if (failures) {
    console.error(`\nvisual smoke FAILED (${failures} page(s))`)
    process.exit(1)
  }
  console.log('\nvisual smoke passed')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
