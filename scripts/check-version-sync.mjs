#!/usr/bin/env node
/**
 * Fail if npm / PyPI / runtime version strings drift.
 * Used by CI, publish workflows, and `npm run check:version`.
 */
import { readFileSync } from 'node:fs'

const pkg = JSON.parse(readFileSync('package.json', 'utf8'))
const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'))
const pyproject = readFileSync('pyproject.toml', 'utf8')
const initPy = readFileSync('src/mcp_secure_remote/__init__.py', 'utf8')
const versionTs = readFileSync('src/lib/version.ts', 'utf8')

const version = pkg.version
const errors = []

if (!/^\d+\.\d+\.\d+$/.test(version)) {
  errors.push(`package.json version "${version}" is not a plain x.y.z semver`)
}

if (lock.version !== version) {
  errors.push(`package-lock.json top-level version is "${lock.version}", expected "${version}"`)
}

const lockPkgVersion = lock.packages?.['']?.version
if (lockPkgVersion !== version) {
  errors.push(`package-lock.json packages[""].version is "${lockPkgVersion}", expected "${version}"`)
}

const pyMatch = pyproject.match(/^version\s*=\s*"([^"]+)"/m)
if (!pyMatch) {
  errors.push('pyproject.toml is missing a project version = "..." field')
} else if (pyMatch[1] !== version) {
  errors.push(`pyproject.toml version is "${pyMatch[1]}", expected "${version}"`)
}

if (!initPy.includes(`__version__ = "${version}"`)) {
  errors.push(`src/mcp_secure_remote/__init__.py does not set __version__ = "${version}"`)
}

if (!versionTs.includes(`export const VERSION = '${version}'`)) {
  errors.push(`src/lib/version.ts does not export VERSION = '${version}'`)
}

if (errors.length > 0) {
  console.error('Version sync check failed:')
  for (const err of errors) console.error(`  - ${err}`)
  process.exit(1)
}

console.log(`Version sync OK: ${version}`)
