import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(scriptDir, '..')
const localesDir = path.join(repoRoot, 'apps', 'web', 'src', 'locales')
const baseLocaleFile = 'en-US.json'
const localeFilePattern = /^[A-Za-z]{2}(?:-[A-Za-z]{2})?\.json$/
const placeholderPattern = /\{([^{}]+)\}/g

function flattenMessages(value, prefix = '') {
  if (typeof value === 'string') {
    return [[prefix, value]]
  }

  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Unsupported locale value at key "${prefix || '<root>'}"`)
  }

  return Object.entries(value).flatMap(([key, nestedValue]) => {
    const nextPrefix = prefix ? `${prefix}.${key}` : key
    return flattenMessages(nestedValue, nextPrefix)
  })
}

function extractPlaceholders(message) {
  if (typeof message !== 'string') {
    return []
  }

  return [...message.matchAll(placeholderPattern)]
    .map((match) => match[1].trim())
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right))
}

function difference(left, right) {
  return left.filter((entry) => !right.includes(entry))
}

function formatSection(title, entries, formatter = (entry) => `- ${entry}`) {
  if (entries.length === 0) {
    return ''
  }

  return `${title}\n${entries.map(formatter).join('\n')}\n`
}

async function readLocale(localeFile) {
  const localePath = path.join(localesDir, localeFile)
  const localeContent = await readFile(localePath, 'utf8')

  try {
    return JSON.parse(localeContent)
  } catch (error) {
    throw new Error(`Failed to parse ${localeFile}: ${error.message}`)
  }
}

async function main() {
  const localeFiles = (await readdir(localesDir))
    .filter((entry) => localeFilePattern.test(entry) && entry !== baseLocaleFile)
    .sort((left, right) => left.localeCompare(right))

  if (localeFiles.length === 0) {
    throw new Error('No translated locale files were found to compare against en-US.json.')
  }

  const baseLocale = await readLocale(baseLocaleFile)
  const baseEntries = new Map(flattenMessages(baseLocale))
  const baseKeys = [...baseEntries.keys()].sort((left, right) => left.localeCompare(right))
  const failures = []

  for (const localeFile of localeFiles) {
    const locale = await readLocale(localeFile)
    const localeEntries = new Map(flattenMessages(locale))
    const localeKeys = [...localeEntries.keys()].sort((left, right) => left.localeCompare(right))

    const missingKeys = difference(baseKeys, localeKeys)
    const extraKeys = difference(localeKeys, baseKeys)
    const placeholderMismatches = baseKeys
      .filter((key) => localeEntries.has(key))
      .flatMap((key) => {
        const basePlaceholders = extractPlaceholders(baseEntries.get(key))
        const localePlaceholders = extractPlaceholders(localeEntries.get(key))

        if (JSON.stringify(basePlaceholders) === JSON.stringify(localePlaceholders)) {
          return []
        }

        return [
          {
            key,
            expected: basePlaceholders,
            actual: localePlaceholders,
          },
        ]
      })

    if (missingKeys.length === 0 && extraKeys.length === 0 && placeholderMismatches.length === 0) {
      continue
    }

    const sections = [
      formatSection('Missing keys:', missingKeys),
      formatSection('Extra keys:', extraKeys),
      formatSection('Placeholder mismatches:', placeholderMismatches, (entry) => {
        const expected = entry.expected.length > 0 ? entry.expected.join(', ') : '<none>'
        const actual = entry.actual.length > 0 ? entry.actual.join(', ') : '<none>'
        return `- ${entry.key}: expected [${expected}] but found [${actual}]`
      }),
    ]
      .filter(Boolean)
      .join('\n')

    failures.push(`Locale ${localeFile} has regressions:\n${sections}`)
  }

  if (failures.length > 0) {
    console.error(failures.join('\n'))
    process.exitCode = 1
    return
  }

  console.log(
    `Locale regression check passed for ${localeFiles.length} locale file(s): ${localeFiles.join(', ')}`
  )
}

await main()
