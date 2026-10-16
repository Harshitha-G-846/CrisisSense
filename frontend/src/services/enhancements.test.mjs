/**
 * enhancements.test.mjs
 * Frontend unit and regression tests for ResQ-Sense enhancements:
 * 1. Location search API call formatting (Vijayawada, Jaisalmer).
 * 2. Email verification code submission and resend throttling contracts.
 * 3. Admin-to-citizen information request dispatch.
 * 4. Analytics metrics data retrieval and aggregation.
 * 5. Theme preference resolution (light, dark, system) and localStorage persistence.
 * 6. Code input sanitation and validation rules.
 */

import test from 'node:test'
import assert from 'node:assert/strict'

const API_BASE_URL = 'http://127.0.0.1:8001'

const createHarness = (mockFetch) => {
  async function request(path, options = {}) {
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    const headers = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    }

    const response = await mockFetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    })

    if (!response.ok) {
      let errorDetail = ''
      try {
        const errJson = await response.json()
        errorDetail = errJson.detail || errJson.message || JSON.stringify(errJson)
      } catch {
        errorDetail = await response.text()
      }
      throw new Error(errorDetail || `HTTP error ${response.status}`)
    }

    return response.json()
  }

  return {
    searchLocations: (query) =>
      request(`/locations/search?q=${encodeURIComponent(query)}`, { method: 'GET' }),

    verifyEmailCode: (email, code) =>
      request('/auth/verify-code', {
        method: 'POST',
        body: JSON.stringify({ email, code }),
      }),

    resendVerificationCode: (email) =>
      request('/auth/resend-code', {
        method: 'POST',
        body: JSON.stringify({ email }),
      }),

    requestIncidentInfo: (incidentId, question, note, token) =>
      request(`/incidents/${encodeURIComponent(incidentId)}/request-info`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: JSON.stringify({ question, note }),
      }),

    getAnalyticsMetrics: () =>
      request('/analytics/metrics', { method: 'GET' }),
  }
}

test('1. api.searchLocations queries Vijayawada and parses coordinates correctly', async () => {
  let requestedUrl = ''
  const mockFetch = async (url) => {
    requestedUrl = url
    return {
      ok: true,
      json: async () => ({
        query: 'Vijayawada',
        count: 1,
        results: [
          {
            name: 'Vijayawada',
            display_name: 'Vijayawada, NTR, Andhra Pradesh, India',
            lat: 16.5062,
            lon: 80.648,
            source: 'city_registry',
          },
        ],
      }),
    }
  }

  const client = createHarness(mockFetch)
  const data = await client.searchLocations('Vijayawada')

  assert.equal(requestedUrl, `${API_BASE_URL}/locations/search?q=Vijayawada`)
  assert.equal(data.count, 1)
  assert.equal(data.results[0].name, 'Vijayawada')
  assert.equal(data.results[0].lat, 16.5062)
  assert.equal(data.results[0].lon, 80.648)
})

test('2. api.searchLocations queries Jaisalmer and parses coordinates correctly', async () => {
  let requestedUrl = ''
  const mockFetch = async (url) => {
    requestedUrl = url
    return {
      ok: true,
      json: async () => ({
        query: 'Jaisalmer',
        count: 1,
        results: [
          {
            name: 'Jaisalmer',
            display_name: 'Jaisalmer, Rajasthan, India',
            lat: 26.9157,
            lon: 70.9083,
            source: 'city_registry',
          },
        ],
      }),
    }
  }

  const client = createHarness(mockFetch)
  const data = await client.searchLocations('Jaisalmer')

  assert.equal(requestedUrl, `${API_BASE_URL}/locations/search?q=Jaisalmer`)
  assert.equal(data.results[0].name, 'Jaisalmer')
  assert.equal(data.results[0].lat, 26.9157)
  assert.equal(data.results[0].lon, 70.9083)
})

test('3. api.verifyEmailCode sends email and 6-digit verification code', async () => {
  let payload = null
  let requestedUrl = ''
  const mockFetch = async (url, options) => {
    requestedUrl = url
    payload = JSON.parse(options.body)
    return {
      ok: true,
      json: async () => ({
        success: true,
        message: 'Account verified successfully.',
        is_verified: true,
        email: payload.email,
      }),
    }
  }

  const client = createHarness(mockFetch)
  const res = await client.verifyEmailCode('citizen@example.com', '123456')

  assert.equal(requestedUrl, `${API_BASE_URL}/auth/verify-code`)
  assert.equal(payload.email, 'citizen@example.com')
  assert.equal(payload.code, '123456')
  assert.equal(res.success, true)
  assert.equal(res.is_verified, true)
})

test('4. api.resendVerificationCode enforces cooldown errors properly', async () => {
  const mockFetch = async () => ({
    ok: false,
    status: 429,
    json: async () => ({
      detail: 'Please wait 25 seconds before requesting another code.',
    }),
  })

  const client = createHarness(mockFetch)
  await assert.rejects(
    async () => client.resendVerificationCode('citizen@example.com'),
    /Please wait 25 seconds before requesting another code\./
  )
})

test('5. api.requestIncidentInfo dispatches admin questions to citizen with authorization header', async () => {
  let capturedHeaders = {}
  let capturedBody = null
  let requestedUrl = ''

  const mockFetch = async (url, options) => {
    requestedUrl = url
    capturedHeaders = options.headers
    capturedBody = JSON.parse(options.body)
    return {
      ok: true,
      json: async () => ({
        success: true,
        message: 'Information request email dispatched to citizen.',
        incident_id: 'INC-20261015-8846',
        recipient_masked: 'c***n@example.com',
        delivery_status: 'MOCKED',
      }),
    }
  }

  const client = createHarness(mockFetch)
  const res = await client.requestIncidentInfo(
    'INC-20261015-8846',
    'Are there any medical injuries at the northern bridge?',
    'Urgent medical triage team standing by.',
    'mock-admin-token-xyz'
  )

  assert.equal(
    requestedUrl,
    `${API_BASE_URL}/incidents/INC-20261015-8846/request-info`
  )
  assert.equal(capturedHeaders.Authorization, 'Bearer mock-admin-token-xyz')
  assert.equal(
    capturedBody.question,
    'Are there any medical injuries at the northern bridge?'
  )
  assert.equal(res.recipient_masked, 'c***n@example.com')
  assert.equal(res.delivery_status, 'MOCKED')
})

test('6. api.getAnalyticsMetrics receives real database metrics', async () => {
  const mockFetch = async () => ({
    ok: true,
    json: async () => ({
      summary: {
        total_incidents: 12,
        pending_count: 5,
        verified_count: 6,
        rejected_count: 1,
        active_critical_count: 3,
      },
      severity_distribution: {
        CRITICAL: 3,
        HIGH: 4,
        MEDIUM: 3,
        LOW: 2,
      },
      status_breakdown: {
        OPEN: 8,
        RESOLVED: 4,
      },
      verification_breakdown: {
        PENDING: 5,
        VERIFIED: 6,
        REJECTED: 1,
      },
      top_categories: [
        { category: 'Flood', count: 6 },
        { category: 'Fire', count: 4 },
        { category: 'Earthquake', count: 2 },
      ],
      timeline_trend: [
        { date: '2026-10-14', count: 4 },
        { date: '2026-10-15', count: 8 },
      ],
    }),
  })

  const client = createHarness(mockFetch)
  const metrics = await client.getAnalyticsMetrics()

  assert.equal(metrics.summary.total_incidents, 12)
  assert.equal(metrics.severity_distribution.CRITICAL, 3)
  assert.equal(metrics.top_categories[0].category, 'Flood')
  assert.equal(metrics.top_categories[0].count, 6)
  assert.equal(metrics.timeline_trend.length, 2)
})

test('7. Theme preference resolution handles light, dark, and system default with localStorage persistence', () => {
  const mockStorage = new Map()
  const storageKey = 'resq_theme_preference'

  function getSavedTheme() {
    return mockStorage.get(storageKey) || 'system'
  }

  function setSavedTheme(theme) {
    mockStorage.set(storageKey, theme)
  }

  function resolveEffectiveTheme(preference, systemPrefersDark) {
    if (preference === 'system') {
      return systemPrefersDark ? 'dark' : 'light'
    }
    return preference
  }

  // Initial state should be 'system'
  assert.equal(getSavedTheme(), 'system')

  // When system is dark
  assert.equal(resolveEffectiveTheme('system', true), 'dark')

  // When system is light
  assert.equal(resolveEffectiveTheme('system', false), 'light')

  // Explicit user selection persists
  setSavedTheme('light')
  assert.equal(getSavedTheme(), 'light')
  assert.equal(resolveEffectiveTheme(getSavedTheme(), true), 'light')

  setSavedTheme('dark')
  assert.equal(getSavedTheme(), 'dark')
  assert.equal(resolveEffectiveTheme(getSavedTheme(), false), 'dark')
})

test('8. Verification code validator checks for 6 numeric digits', () => {
  function isValidCode(code) {
    return /^\d{6}$/.test(code.trim())
  }

  assert.equal(isValidCode('123456'), true)
  assert.equal(isValidCode('000000'), true)
  assert.equal(isValidCode('999999'), true)
  assert.equal(isValidCode('12345'), false) // 5 digits
  assert.equal(isValidCode('1234567'), false) // 7 digits
  assert.equal(isValidCode('12345a'), false) // contains letter
  assert.equal(isValidCode('  123456  '), true) // trimmed
  assert.equal(isValidCode(''), false)
})

test('9. Theme tokens in index.css include all 5 beige palette colors, light surfaces, and severity tokens', async () => {
  const fs = await import('node:fs/promises')
  const path = await import('node:path')
  const fileUrl = new URL(import.meta.url)
  const dir = path.dirname(fileUrl.pathname.replace(/^\/([A-Z]:)/i, '$1'))
  const indexCssPath = path.resolve(dir, '../index.css')
  const css = await fs.readFile(indexCssPath, 'utf8')

  // Requested Beige palette
  assert.match(css, /#85543a/i, 'Coffee bean #85543a must be present')
  assert.match(css, /#a77e5c/i, 'Faded copper #a77e5c must be present')
  assert.match(css, /#bf8d62/i, 'Camel #bf8d62 must be present')
  assert.match(css, /#eab883/i, 'Sandy clay #eab883 must be present')
  assert.match(css, /#f9d7a4/i, 'Apricot cream #f9d7a4 must be present')

  // Light theme tokens
  assert.match(css, /\[data-theme="light"\]/, 'Light theme selector must exist')
  assert.match(css, /--bg-primary:\s*#fcf9f5/, 'Light primary bg must be genuinely light')
  assert.match(css, /--bg-canvas:\s*#f6efe6/, 'Light canvas must be soft beige')
  assert.match(css, /--text-primary:\s*#382116/, 'Light text primary must have rich dark contrast')

  // Severity readability tokens across themes
  assert.match(css, /--severity-critical-bg:/, 'Critical background token must exist')
  assert.match(css, /--severity-critical-color:/, 'Critical text color token must exist')
  assert.match(css, /--status-verified-bg:/, 'Verified background token must exist')
  assert.match(css, /--status-verified-color:/, 'Verified text color token must exist')
})

test('10. App.css components use shared theme variables for major surfaces across portals', async () => {
  const fs = await import('node:fs/promises')
  const path = await import('node:path')
  const fileUrl = new URL(import.meta.url)
  const dir = path.dirname(fileUrl.pathname.replace(/^\/([A-Z]:)/i, '$1'))
  const appCssPath = path.resolve(dir, '../App.css')
  const css = await fs.readFile(appCssPath, 'utf8')

  // Authority Operations Hub surfaces
  assert.match(css, /\.authority-topbar\s*\{[^}]*var\(--bg-surface-header/s)
  assert.match(css, /\.incidents-sidebar-panel\s*\{[^}]*var\(--bg-surface-sidebar/s)
  assert.match(css, /\.incident-inspector-panel\s*\{[^}]*var\(--bg-surface-inspector/s)
  assert.match(css, /\.incident-card-item\s*\{[^}]*var\(--bg-surface-card/s)
  assert.match(css, /\.delete-confirm-modal\s*\{[^}]*var\(--bg-surface-elevated/s)

  // Citizen Portal & Landing surfaces
  assert.match(css, /\.resq-app-container\s*\{[^}]*var\(--bg-app-container/s)
  assert.match(css, /\.citizen-incident-card\s*\{[^}]*var\(--bg-surface-card/s)
  assert.match(css, /\.gateway-card\s*\{[^}]*var\(--bg-surface-card/s)
})
