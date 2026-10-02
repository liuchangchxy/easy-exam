import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = path.resolve(frontendRoot, '..')
const configPath = path.join(repoRoot, 'localization.config.json')
const requiredChecks = ['catalog', 'source', 'contract', 'browser']
const requiredLocales = ['zh-CN', 'en-US']
const requiredScripts = {
  catalog: 'check:localization:catalog',
  source: 'check:localization',
  contract: 'test:unit',
  browser: 'test:localization:e2e',
}

export function validateLocalizationConfig(config, packageJson) {
  const problems = []
  if (config.schema_version !== 1) problems.push('schema_version must be 1')
  if (config.applicable !== true) problems.push('applicable must remain true for EasyExam')
  if (!Array.isArray(config.locales) || config.locales.length < 2 || new Set(config.locales).size !== config.locales.length) {
    problems.push('locales must contain at least two distinct locale identifiers')
  }
  for (const locale of requiredLocales) {
    if (!config.locales?.includes(locale)) problems.push(`locales must include ${locale}`)
  }
  if (!config.locales?.includes(config.default_locale)) problems.push('default_locale must be included in locales')

  for (const name of requiredChecks) {
    const command = config.checks?.[name]
    if (!Array.isArray(command) || command.some(part => typeof part !== 'string' || !part.trim())) {
      problems.push(`checks.${name} must be a non-empty argument array`)
      continue
    }
    if (command[0] !== 'npm' || command[1] !== '--prefix' || command[2] !== 'frontend' || command[3] !== 'run') {
      problems.push(`checks.${name} must dispatch through npm --prefix frontend run ${requiredScripts[name]}`)
      continue
    }
    const script = command[4]
    if (!script || !packageJson.scripts?.[script]) problems.push(`checks.${name} references a missing frontend npm script`)
    if (script !== requiredScripts[name]) problems.push(`checks.${name} must use the enforced script ${requiredScripts[name]}`)
  }
  return problems
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  const packageJson = JSON.parse(fs.readFileSync(path.join(frontendRoot, 'package.json'), 'utf8'))
  const problems = validateLocalizationConfig(config, packageJson)
  if (problems.length) {
    console.error(`Localization config gate failed (${configPath}):`)
    for (const problem of problems) console.error(`  - ${problem}`)
    process.exitCode = 1
  } else {
    console.log(`Localization config gate passed: ${config.locales.join(', ')}; all ${requiredChecks.length} delivery stages are configured.`)
  }
}
