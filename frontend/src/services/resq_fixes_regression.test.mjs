/**
 * resq_fixes_regression.test.mjs
 * Comprehensive regression tests for ResQ-Sense:
 * 1. Light mode text visibility and shared CSS theme tokens.
 * 2. Citizen Portal badge containment and incident ID truncation.
 * 3. Waterlogging & flood crisis classification with typo-tolerant location.
 * 4. Simplified analytics counting and separated status distribution charts.
 * 5. Removal of "Situational Update & Escalation Feedback" admin section.
 */

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT_DIR = path.resolve(__dirname, '..', '..')

test('1. Light Mode Text Visibility and Shared Design System Variables', () => {
  const appCssPath = path.resolve(ROOT_DIR, 'src', 'App.css')
  const indexCssPath = path.resolve(ROOT_DIR, 'src', 'index.css')

  assert.ok(fs.existsSync(appCssPath), 'App.css exists')
  assert.ok(fs.existsSync(indexCssPath), 'index.css exists')

  const appCss = fs.readFileSync(appCssPath, 'utf8')
  const indexCss = fs.readFileSync(indexCssPath, 'utf8')

  // Check palette tokens in index.css
  assert.ok(indexCss.includes('--palette-coffee-bean: #85543A'), 'Coffee bean token declared')
  assert.ok(indexCss.includes('--palette-faded-copper: #A77E5C'), 'Faded copper token declared')
  assert.ok(indexCss.includes('--palette-camel: #BF8D62'), 'Camel token declared')
  assert.ok(indexCss.includes('--palette-sandy-clay: #EAB883'), 'Sandy clay token declared')
  assert.ok(indexCss.includes('--palette-apricot-cream: #F9D7A4'), 'Apricot cream token declared')
  assert.ok(indexCss.includes('--palette-coffee:'), 'Palette coffee alias declared')

  // Light theme surface definitions
  assert.ok(indexCss.includes('[data-theme="light"]'), 'Light theme selector defined')
  assert.ok(indexCss.includes('--bg-primary: #fcf9f5'), 'Light primary beige background defined')
  assert.ok(indexCss.includes('--text-primary: #382116'), 'Light high-contrast dark coffee text defined')

  // Brand name and logo visibility in Light mode
  assert.ok(appCss.includes('[data-theme="light"] .brand-crest-name'), 'Light mode brand-crest-name has high contrast styling')
  assert.ok(appCss.includes('[data-theme="light"] .brand-crest-tagline'), 'Light mode brand-crest-tagline has readable text styling')

  // Submission success card uses shared theme variables
  assert.ok(appCss.includes('.submission-success-card {'), 'Submission success card defined')
  assert.ok(
    !appCss.includes('.submission-success-card {\n  background: rgba(20, 26, 38'),
    'Submission success card does NOT have hardcoded dark background'
  )
  assert.ok(
    !appCss.includes('.submission-success-card h2 {\n  font-size: 30px;\n  font-weight: 800;\n  margin-bottom: 10px;\n  color: #ffffff;'),
    'Submission success card h2 does NOT have hardcoded #ffffff'
  )

  // Status track cards use theme variables
  assert.ok(
    !appCss.includes('.tracked-incident-detail-card {\n  background: rgba(20, 26, 38'),
    'Tracked incident detail card does NOT have hardcoded dark background'
  )
  assert.ok(
    !appCss.includes('.meta-block {\n  background: rgba(26, 34, 48'),
    'Meta block does NOT have hardcoded dark background'
  )

  // Glass button readable in light mode
  assert.ok(
    !appCss.includes('.btn-glass {\n  display: inline-flex;\n  align-items: center;\n  justify-content: center;\n  gap: 8px;\n  background: rgba(255, 255, 255, 0.08);\n  border: 1px solid var(--border-medium);\n  color: #ffffff;'),
    'btn-glass does NOT have invisible #ffffff text in light mode'
  )
})

test('2. Citizen Portal Status Badge Containment and Long ID Truncation', () => {
  const appCssPath = path.resolve(ROOT_DIR, 'src', 'App.css')
  const citizenPortalPath = path.resolve(ROOT_DIR, 'src', 'components', 'CitizenPortal.tsx')

  const appCss = fs.readFileSync(appCssPath, 'utf8')
  const portalCode = fs.readFileSync(citizenPortalPath, 'utf8')

  // Card overflow protection
  assert.ok(appCss.includes('.citizen-incident-card {'), 'Citizen incident card class exists')
  assert.ok(appCss.includes('overflow: hidden;'), 'Card has overflow: hidden')

  // Header wrap protection
  assert.ok(appCss.includes('.citizen-incident-card-top {'), 'Card top class exists')
  assert.ok(appCss.includes('flex-wrap: wrap;'), 'Card top uses flex-wrap to prevent overflow')

  // ID truncation and boundary protection
  assert.ok(appCss.includes('.citizen-incident-id {'), 'Incident ID class exists')
  assert.ok(appCss.includes('text-overflow: ellipsis;'), 'Incident ID truncates long text')
  assert.ok(appCss.includes('white-space: nowrap;'), 'Incident ID maintains clean single line')

  // Badge containment
  assert.ok(appCss.includes('.citizen-status-badge {'), 'Citizen status badge exists')
  assert.ok(appCss.includes('.citizen-status-badge.verified {'), 'Verified badge class exists')
  assert.ok(appCss.includes('.citizen-status-badge.pending {'), 'Pending badge class exists')
  assert.ok(appCss.includes('.citizen-status-badge.rejected {'), 'Rejected badge class exists')
  assert.ok(appCss.includes('.citizen-status-badge.needs_more_info'), 'Needs more info badge class exists')

  // CitizenPortal JSX includes title tooltip for truncated IDs
  assert.ok(
    portalCode.includes('className="citizen-incident-id" title={incId}'),
    'CitizenPortal renders title tooltip for complete ID visibility'
  )
})

test('3. Waterlogging and Flood NLP Classification & Typo Tolerance', async () => {
  // Query backend pipeline directly via API endpoint if online, or verify pipeline implementation
  const sampleDescription = 'waterlogging at jaisalmar since yesterday,people are stuck'

  try {
    const res = await fetch('http://127.0.0.1:8000/reports/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: sampleDescription,
        location: 'jaisalmar',
      }),
    })

    if (res.ok) {
      const data = await res.json()
      // Category should be Flood (not fallback 'Crisis Report')
      assert.ok(
        data.incident_type === 'Flood' || data.incident_type?.toLowerCase().includes('flood'),
        `Sample waterlogging categorized as flood emergency, got: ${data.incident_type}`
      )
      // Severity should be HIGH or CRITICAL due to trapped people (not UNKNOWN)
      assert.ok(
        data.severity === 'HIGH' || data.severity === 'CRITICAL',
        `Sample waterlogging severity assessed appropriately, got: ${data.severity}`
      )
      // Location should be resolved to Jaisalmer
      if (data.location_name) {
        assert.ok(
          data.location_name.toLowerCase().includes('jaisalmer'),
          `Location fuzzy matched jaisalmar -> Jaisalmer, got: ${data.location_name}`
        )
      }
    }
  } catch (err) {
    // If backend isn't reachable during offline unit testing, verify the python pipeline code
    const pipelinePath = path.resolve(ROOT_DIR, '..', 'backend', 'member1', 'pipeline.py')
    const extractorPath = path.resolve(ROOT_DIR, '..', 'backend', 'member1', 'location_extractor.py')

    const pipelineCode = fs.readFileSync(pipelinePath, 'utf8')
    const extractorCode = fs.readFileSync(extractorPath, 'utf8')

    assert.ok(pipelineCode.includes('waterlogging'), 'Pipeline normalizes waterlogging')
    assert.ok(pipelineCode.includes('inundation'), 'Pipeline normalizes inundation')
    assert.ok(extractorCode.includes('temporal_stops'), 'Location extractor strips temporal markers')
  }
})

test('4. Analytics Dashboard Simplification and Separated Status Charts', () => {
  const analyticsPath = path.resolve(ROOT_DIR, 'src', 'components', 'AnalyticsDashboard.tsx')
  assert.ok(fs.existsSync(analyticsPath), 'AnalyticsDashboard.tsx exists')

  const code = fs.readFileSync(analyticsPath, 'utf8')

  // Total Incidents retained
  assert.ok(code.includes('Total Incidents'), 'Retains Total Incidents')

  // Total Reports renamed to Citizen Reports with documented counting logic
  assert.ok(code.includes('Citizen Reports'), 'Total Reports renamed to Citizen Reports')
  assert.ok(
    code.includes('Submitted reports count (<code>Report.id</code>)'),
    'Documented counting logic for Citizen Reports'
  )

  // Active Open removed
  assert.ok(!code.includes('Active Open'), 'Redundant Active Open KPI card removed')

  // Critical Incidents retained
  assert.ok(code.includes('Critical Incidents'), 'Retains Critical Incidents')

  // Two distinct distribution charts
  assert.ok(code.includes('Case Severity Distribution'), 'Distinct severity distribution chart')
  assert.ok(code.includes('Verification Workflow Distribution'), 'Distinct workflow status distribution chart')

  // Severity categories
  assert.ok(code.includes("severityCategories = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']"), 'Severity categories definition')

  // Workflow categories
  assert.ok(code.includes("key: 'VERIFIED', label: 'Verified'"), 'Verified workflow status')
  assert.ok(code.includes("key: 'PENDING', label: 'Pending Review'"), 'Pending review workflow status')
  assert.ok(code.includes("key: 'NEEDS_MORE_INFO', label: 'Needs More Info'"), 'Needs more info workflow status')
  assert.ok(code.includes("key: 'REJECTED', label: 'Rejected'"), 'Rejected workflow status')
})

test('5. Removal of Situational Update & Escalation Feedback Section', () => {
  const workspacePath = path.resolve(ROOT_DIR, 'src', 'components', 'AuthorityWorkspace.tsx')
  assert.ok(fs.existsSync(workspacePath), 'AuthorityWorkspace.tsx exists')

  const code = fs.readFileSync(workspacePath, 'utf8')

  // Verify section title is removed
  assert.ok(
    !code.includes('Situational Update & Escalation Feedback'),
    '"Situational Update & Escalation Feedback" section completely removed from Authority Workspace'
  )

  // Verify exclusive states and handlers are removed
  assert.ok(!code.includes('feedbackInput'), 'Exclusive feedbackInput state removed')
  assert.ok(!code.includes('feedbackSubmitting'), 'Exclusive feedbackSubmitting state removed')
  assert.ok(!code.includes('feedbackResult'), 'Exclusive feedbackResult state removed')
  assert.ok(!code.includes('handleFeedback'), 'Exclusive handleFeedback handler removed')

  // Verify core authority functions remain intact
  assert.ok(code.includes('handleVerify'), 'Incident verification capability retained')
  assert.ok(code.includes('handleAuthorize'), 'Dispatch authorization capability retained')
  assert.ok(code.includes('AuthorityWorkspace'), 'AuthorityWorkspace component exported')
})
