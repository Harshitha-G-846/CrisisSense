/**
 * crisis_backdrop.test.mjs
 * Comprehensive unit tests verifying the replacement of the 6-scene SVG slideshow
 * with the dedicated floating incident-photo field surrounding the ResQ-Sense brand.
 */

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const LANDING_PAGE_PATH = path.resolve('src/components/LandingPage.tsx')
const APP_CSS_PATH = path.resolve('src/App.css')
const PUBLIC_INCIDENTS_PATH = path.resolve('public/incidents')

test('1. Six-scene SVG slideshow is completely removed and replaced', () => {
  const code = fs.readFileSync(LANDING_PAGE_PATH, 'utf-8').replace(/\r\n/g, '\n')
  const css = fs.readFileSync(APP_CSS_PATH, 'utf-8').replace(/\r\n/g, '\n')

  // Old backdrop container and classes must not exist
  assert.ok(
    !code.includes('className="atmospheric-crisis-backdrop"'),
    'Old .atmospheric-crisis-backdrop must not be rendered in LandingPage.tsx'
  )
  assert.ok(
    !css.includes('.atmospheric-crisis-backdrop {'),
    'Old .atmospheric-crisis-backdrop rules must be removed from App.css'
  )
  assert.ok(
    !code.includes('crisis-scene-layer'),
    'Old .crisis-scene-layer must not exist in LandingPage.tsx'
  )
  assert.ok(
    !css.includes('.crisis-scene-layer {'),
    'Old .crisis-scene-layer rules must be removed from App.css'
  )

  // Old scene rotation hook must be gone
  assert.ok(
    !code.includes('activeSceneIndex'),
    'Old activeSceneIndex state and interval hook must be removed'
  )

  // Old SVG disaster scenes must not be present
  const oldSvgLandmarks = [
    'Scene 0: Flooding',
    'Scene 1: Cyclone',
    'Scene 2: Earthquake',
    'Scene 3: Tsunami',
    'Scene 4: Urban Fire Breakout',
    'Scene 5: Forest Wildfire',
    'flood-sky',
    'cyclone-space',
    'quake-magma-glow',
    'tsunami-water',
    'urban-furnace-core',
    'wildfire-crown-front',
  ]
  for (const landmark of oldSvgLandmarks) {
    assert.ok(
      !code.includes(landmark),
      `Old SVG artwork landmark "${landmark}" must not exist in LandingPage.tsx`
    )
  }
})

test('2. Dedicated floating incident-photo field is rendered with authentic incident photos', () => {
  const code = fs.readFileSync(LANDING_PAGE_PATH, 'utf-8').replace(/\r\n/g, '\n')

  // Container mounted behind foreground content
  assert.ok(
    code.includes('className="floating-incident-field"'),
    'LandingPage.tsx must render .floating-incident-field'
  )
  assert.ok(
    code.includes('aria-hidden="true"'),
    'Floating field must have aria-hidden="true" for screen reader accessibility'
  )

  // Verify all 16 photo tiles exist in code
  for (let i = 1; i <= 16; i++) {
    const numStr = String(i).padStart(2, '0')
    assert.ok(
      code.includes(`tile_${numStr}.jpg`),
      `Photo tile /incidents/tile_${numStr}.jpg must be registered in INCIDENT_PHOTO_TILES`
    )
  }

  // Verify all 16 image files physically exist in public/incidents/ and are non-empty
  for (let i = 1; i <= 16; i++) {
    const numStr = String(i).padStart(2, '0')
    const filePath = path.join(PUBLIC_INCIDENTS_PATH, `tile_${numStr}.jpg`)
    assert.ok(
      fs.existsSync(filePath),
      `Image file ${filePath} must exist on disk`
    )
    const stats = fs.statSync(filePath)
    assert.ok(stats.size > 10000, `Image file tile_${numStr}.jpg must be a valid image > 10KB`)
  }

  // Verify full category representation
  const requiredCategories = [
    'Flood Rescue',
    'Cyclone / Storm',
    'Earthquake Collapse',
    'Tsunami Surge',
    'Urban Inferno',
    'Forest Wildfire',
    'Search & Rescue',
    'Medical Triage',
    'Disaster Relief',
    'Helicopter Evac',
    'Fire Brigade',
    'Infrastructure',
    'Field Medic',
  ]
  for (const cat of requiredCategories) {
    assert.ok(
      code.includes(`'${cat}'`) || code.includes(`"${cat}"`),
      `Incident photo field must include category: "${cat}"`
    )
  }
})

test('3. Position, shapes, sizes, and bilateral distribution around ResQ-Sense brand', () => {
  const code = fs.readFileSync(LANDING_PAGE_PATH, 'utf-8').replace(/\r\n/g, '\n')
  const css = fs.readFileSync(APP_CSS_PATH, 'utf-8').replace(/\r\n/g, '\n')

  // Shapes: circular crops, rounded squares, horizontal and vertical rounded rectangles
  assert.ok(code.includes('shape-circle'), 'Must include shape-circle')
  assert.ok(code.includes('shape-square'), 'Must include shape-square')
  assert.ok(code.includes('shape-rect-h'), 'Must include shape-rect-h')
  assert.ok(code.includes('shape-rect-v'), 'Must include shape-rect-v')

  assert.ok(css.includes('.incident-photo-tile.shape-circle {\n  border-radius: 50%;'), 'Circle must have 50% border radius')
  assert.ok(css.includes('.incident-photo-tile.shape-square {\n  border-radius: 18px;'), 'Square must have rounded corners')
  assert.ok(css.includes('.incident-photo-tile.shape-rect-h {\n  border-radius: 16px;'), 'Rect-h must have rounded corners')
  assert.ok(css.includes('.incident-photo-tile.shape-rect-v {\n  border-radius: 16px;'), 'Rect-v must have rounded corners')

  // Bilateral distribution: 8 on left flank, 8 on right flank
  const tilesBlock = code.slice(code.indexOf('INCIDENT_PHOTO_TILES'), code.indexOf('export const LandingPage'))
  const leftMatches = (tilesBlock.match(/side: 'left'/g) || []).length
  const rightMatches = (tilesBlock.match(/side: 'right'/g) || []).length
  assert.equal(leftMatches, 8, 'Must have 8 photo tiles distributed along left side')
  assert.equal(rightMatches, 8, 'Must have 8 photo tiles distributed along right side')

  // Size variations between ~70px and 135px (well within 60px–140px requirement)
  assert.ok(code.includes("width: '110px'"), 'Must have 110px tile')
  assert.ok(code.includes("width: '130px'"), 'Must have 130px tile')
  assert.ok(code.includes("width: '88px'"), 'Must have 88px tile')
  assert.ok(code.includes("width: '72px'"), 'Must have 72px tile')
  assert.ok(code.includes("width: '135px'"), 'Must have 135px tile')
  assert.ok(code.includes("width: '128px'"), 'Must have 128px tile')
  assert.ok(code.includes("width: '74px'"), 'Must have 74px tile')

  // Ensure center brand clearance
  assert.ok(!code.includes("left: '30%"), 'Left tiles must not encroach on center column')
  assert.ok(!code.includes("right: '30%"), 'Right tiles must not encroach on center column')
})

test('4. Independent animation timing, overlapping visibility, and float drift keyframes', () => {
  const code = fs.readFileSync(LANDING_PAGE_PATH, 'utf-8').replace(/\r\n/g, '\n')
  const css = fs.readFileSync(APP_CSS_PATH, 'utf-8').replace(/\r\n/g, '\n')

  // Each tile has independent animation duration and delay
  const delays = [
    '0.0s', '1.2s', '2.5s', '3.8s', '5.1s', '0.6s', '2.0s', '4.3s',
    '0.8s', '2.8s', '4.6s', '1.6s', '3.4s', '5.4s', '0.3s', '3.0s'
  ]
  for (const d of delays) {
    assert.ok(
      code.includes(`animationDelay: '${d}'`),
      `Tile with animationDelay '${d}' must exist`
    )
  }

  // Keyframes definition in App.css
  assert.ok(
    css.includes('@keyframes photoTileFloat'),
    'App.css must define @keyframes photoTileFloat'
  )
  assert.ok(
    css.includes('opacity: 0.92;') || css.includes('opacity: 0.95;'),
    'photoTileFloat must have noticeable, high-visibility opacity (0.92 - 0.95)'
  )
  assert.ok(
    css.includes('transform: translateY(-8px) scale(1.02);') ||
    css.includes('transform: translateY(-8px)'),
    'photoTileFloat must include subtle floating drift'
  )

  // Floating incident field pointer-events: none and z-index: 2
  assert.ok(
    css.includes('.floating-incident-field {') && css.includes('pointer-events: none;'),
    '.floating-incident-field must have pointer-events: none'
  )
  assert.ok(
    css.includes('.floating-incident-field {') && css.includes('z-index: 2;'),
    '.floating-incident-field must sit at z-index: 2'
  )
})

test('5. Accessibility, responsive breakpoints, and legibility protection', () => {
  const css = fs.readFileSync(APP_CSS_PATH, 'utf-8').replace(/\r\n/g, '\n')

  // Reduced motion media query honors accessibility
  assert.ok(
    css.includes('@media (prefers-reduced-motion: reduce)'),
    'Reduced motion media query must exist'
  )
  assert.ok(
    css.includes('.incident-photo-tile {\n    animation: none !important;\n    transform: none !important;\n    opacity: 0.35 !important;'),
    'Reduced motion must disable animation and show calm static tiles at opacity 0.35'
  )

  // Responsive styling for mobile devices
  assert.ok(
    css.includes('@media (max-width: 768px)'),
    'Mobile media query must exist'
  )
  assert.ok(
    css.includes('.incident-photo-tile.col-inner {\n    display: none;\n  }'),
    'Inner column tiles must hide on mobile to give space to center content'
  )

  // Readability text-shadows
  assert.ok(
    css.includes('.brand-crest-name {\n  text-shadow:'),
    'Brand crest name must have text-shadow for readability over photo tiles'
  )
  assert.ok(
    css.includes('.hero-monumental-headline {\n  text-shadow:'),
    'Monumental headline must have text-shadow for readability over photo tiles'
  )
})
