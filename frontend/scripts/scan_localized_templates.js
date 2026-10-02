import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { NodeTypes, parse as parseTemplate } from '@vue/compiler-dom'

const DISPLAY_ATTRIBUTES = new Set(['alt', 'aria-label', 'placeholder', 'title'])

// These are exact, reviewed exceptions to the UI-copy rule. Their meanings
// are language-neutral brand/version tokens, physical key names, file types,
// or example input syntax. Keep each exception tied to its source file.
const ALLOWLIST = {
  'components/AppSidebar.vue': {
    'EasyExam': 'Product brand name.',
    'FSRS': 'Standard name of the scheduling algorithm.',
    'v1.0.7': 'Software release version, not prose.',
  },
  'components/CommandPalette.vue': {
    'ESC': 'Physical keyboard key name.',
    'esc': 'Physical keyboard key name.',
  },
  'components/LocaleToggle.vue': {
    'English': 'Autonym used to identify the English locale.',
    'zh-CN': 'BCP 47 locale identifier.',
    'EN': 'Standard abbreviation displayed on the language toggle.',
  },
  'components/ThemeToggle.vue': {
    'light': 'Theme state enum used to select the translated label.',
  },
  'features/exam/ExamView.vue': {
    'ESSAY': 'Question-type enum used to select translated input guidance.',
    'SUBJECTIVE': 'Question-type enum used to select translated input guidance.',
  },
  'components/AiConfigModal.vue': {
    'https://api.openai.com/v1': 'Example endpoint URL entered by the operator.',
    'sk-...': 'API key format example, not translatable prose.',
    'http://localhost:8000/v1/search': 'Example endpoint URL entered by the operator.',
  },
  'views/MistakesView.vue': {
    'mistakes': 'Tab state enum, not user-facing prose.',
  },
  'views/ImportView.vue': {
    'HIGH': 'PDF parser confidence enum.',
    '.xlsx': 'File extension.',
    '.csv': 'File extension.',
    '.json': 'File extension.',
    '.md / .txt': 'File extensions.',
    '.pdf': 'File extension.',
    'KB': 'Kilobyte file size unit.',
  },
  'views/PracticeViewV1.vue': {
    'ELIMINATION': 'Practice-mode enum.',
    'FSRS': 'Standard name of the scheduling algorithm.',
    'PRACTICE': 'Practice-mode enum.',
    'user': 'Message author enum, not visible prose.',
    'Enter ↵': 'Physical keyboard key name.',
    'Space ␣': 'Physical keyboard key name.',
    'Enter': 'Physical keyboard key name.',
    'Space': 'Physical keyboard key name.',
    '(+10m)': 'FSRS interval notation.',
    '(+1d)': 'FSRS interval notation.',
    '(+3d)': 'FSRS interval notation.',
    '(+7d)': 'FSRS interval notation.',
  },
  'views/HomeView.vue': {
    'ADMIN': 'Account-role enum.',
    'EDITOR': 'Account-role enum.',
    'MNEMONIC': 'Question-type enum.',
    'SUMMARY': 'Question-type enum.',
    'running': 'AI batch status enum.',
    'stopped': 'AI batch status enum.',
    'https://api.openai.com/v1': 'Example endpoint URL entered by the operator.',
    'sk-...': 'API key format example, not translatable prose.',
    'http://localhost:8000/v1/search': 'Example endpoint URL entered by the operator.',
  },
}

function isTranslationKey(value) {
  return /^[A-Za-z][\w-]*(?:\.[A-Za-z][\w-]*)+$/.test(value)
}

function literalText(expression) {
  const values = []
  const pattern = /(['"])((?:\\.|(?!\1)[^\\])*)\1/g
  for (const match of expression.matchAll(pattern)) {
    const value = match[2]
    if (!isTranslationKey(value) && /[\p{L}]{2}/u.test(value)) values.push(value)
  }
  return values
}

function walk(node, visit) {
  visit(node)
  for (const child of node.children || []) walk(child, visit)
}

function scanSource(source, relativePath) {
  const violations = []
  const uses = new Map()
  const { descriptor, errors } = parseSfc(source, { filename: relativePath })
  if (errors.length) {
    return { violations: [`${relativePath}: invalid Vue template`], uses }
  }
  if (descriptor.template) {
    const ast = parseTemplate(descriptor.template.content, { comments: false })
    walk(ast, node => {
    const checkCopy = (raw, context) => {
      const text = raw.trim()
      if (/[\p{L}]{2}/u.test(text)) {
        uses.set(text, (uses.get(text) || 0) + 1)
        if (!ALLOWLIST[relativePath]?.[text]) {
          violations.push(`${relativePath}: ${context} must use t(): "${text}"`)
        }
      }
    }
    if (node.type === NodeTypes.TEXT) checkCopy(node.content, 'visible text')
    if (node.type === NodeTypes.INTERPOLATION) {
      for (const value of literalText(node.content.content)) checkCopy(value, 'interpolated text')
    }
    if (node.type !== NodeTypes.ELEMENT) return
    for (const prop of node.props) {
      if (prop.type === NodeTypes.ATTRIBUTE && DISPLAY_ATTRIBUTES.has(prop.name) && prop.value) {
        const value = prop.value.content.trim()
        if (/[\p{L}]{2}/u.test(value) && !isTranslationKey(value)) {
          uses.set(value, (uses.get(value) || 0) + 1)
          if (!ALLOWLIST[relativePath]?.[value]) {
            violations.push(`${relativePath}: ${prop.name} must use t(): "${value}"`)
          }
        }
      } else if (prop.type === NodeTypes.DIRECTIVE
          && prop.arg?.type === NodeTypes.SIMPLE_EXPRESSION
          && DISPLAY_ATTRIBUTES.has(prop.arg.content)
          && prop.exp?.type === NodeTypes.SIMPLE_EXPRESSION) {
        for (const value of literalText(prop.exp.content)) {
          const key = `${relativePath}|${value}`
          uses.set(value, (uses.get(value) || 0) + 1)
          if (!ALLOWLIST[relativePath]?.[value]) {
            violations.push(`${relativePath}: ${prop.arg.content} must localize literal "${value}"`)
          }
        }
      }
    }
    })
  }

  for (const script of [descriptor.script, descriptor.scriptSetup].filter(Boolean)) {
    const dialogPattern = /\b(?:window\.)?(?:alert|confirm|prompt)\s*\(([^;]*?)\)/gs
    for (const match of script.content.matchAll(dialogPattern)) {
      const untranslatedPart = match[1].replace(/\bt\s*\(\s*(['"])(?:\\.|(?!\1)[^\\])*\1(?:\s*,\s*[^)]*)?\)/g, '')
      for (const value of literalText(untranslatedPart)) {
        if (!ALLOWLIST[relativePath]?.[value]) {
          violations.push(`${relativePath}: browser dialog must use t(): "${value}"`)
        }
      }
    }
  }
  return { violations, uses }
}

function walkVueFiles(root) {
  const results = []
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const fullPath = path.join(directory, entry.name)
      if (entry.isDirectory()) visit(fullPath)
      else if (entry.name.endsWith('.vue')) {
        const relative = path.relative(root, fullPath).split(path.sep).join('/')
        results.push({ relative, source: fs.readFileSync(fullPath, 'utf8') })
      }
    }
  }
  visit(root)
  return results
}

export function inspectVueTemplates(root) {
  const violations = []
  const observed = new Map()
  for (const file of walkVueFiles(root)) {
    const result = scanSource(file.source, file.relative)
    violations.push(...result.violations)
    for (const [text, count] of result.uses) {
      const key = `${file.relative}|${text}`
      observed.set(key, (observed.get(key) || 0) + count)
    }
  }
  return violations
}

export function inspectVueSource(source) {
  return scanSource(source, 'fixture.vue').violations
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src')
  const violations = inspectVueTemplates(root)
  if (violations.length) {
    console.error('Localization source gate failed:')
    for (const item of violations) console.error(`  - ${item}`)
    process.exitCode = 1
  } else {
    console.log('Localization source gate passed: Vue template copy uses translated messages or reviewed language-neutral tokens.')
  }
}
