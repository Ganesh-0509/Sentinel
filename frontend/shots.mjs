// Capture each route for visual review. Not part of the app bundle.
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = process.env.SHOT_BASE ?? 'http://localhost:5174'
const OUT = '../reports/screens'
const ROUTES = [
  ['overview', '/'],
  ['map', '/map'],
  ['zones', '/zones'],
  ['zone-detail', '/zones/COB-B'],
  ['alerts', '/alerts'],
  ['analytics', '/analytics'],
  ['incidents', '/incidents'],
  ['permits', '/permits'],
  ['compliance', '/compliance'],
  ['evidence', '/evidence'],
]

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })

// put the plant into an interesting state
try {
  await page.request.post(`${BASE}/api/v1/clock/set?minute=58`)
} catch (e) {
  console.error('clock set failed:', e.message)
}

for (const [name, route] of ROUTES) {
  await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2600) // let async data land and charts settle
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
  console.log('captured', name)
}

await browser.close()
