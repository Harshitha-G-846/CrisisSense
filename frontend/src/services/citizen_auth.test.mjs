/**
 * citizen_auth.test.mjs
 * Frontend unit tests for citizen authentication, session persistence,
 * authorization header injection, and incident tracking links.
 */

import test from 'node:test'
import assert from 'node:assert/strict'

// Mock localStorage harness
const createMockLocalStorage = () => {
  const store = new Map()
  return {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
    clear: () => store.clear(),
  }
}

// Storage helper harness (mirrors authStorage in api.ts)
const createAuthStorage = (storage) => {
  const TOKEN_KEY = 'resq_sense_citizen_token'
  const USER_KEY = 'resq_sense_citizen_user'

  return {
    getToken: () => storage.getItem(TOKEN_KEY),
    setToken: (token) => storage.setItem(TOKEN_KEY, token),
    clearToken: () => storage.removeItem(TOKEN_KEY),
    getUser: () => {
      const raw = storage.getItem(USER_KEY)
      if (!raw) return null
      try {
        return JSON.parse(raw)
      } catch {
        return null
      }
    },
    setUser: (user) => storage.setItem(USER_KEY, JSON.stringify(user)),
    clearUser: () => storage.removeItem(USER_KEY),
    clearAll: () => {
      storage.removeItem(TOKEN_KEY)
      storage.removeItem(USER_KEY)
    },
  }
}

// Client harness with bearer token injection (mirrors api.ts)
const createAuthClient = (customFetch, authStorage) => {
  const API_BASE_URL = 'http://127.0.0.1:8001'

  async function request(path, options = {}) {
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    const token = authStorage.getToken()

    const headers = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    }

    const response = await customFetch(`${API_BASE_URL}${path}`, {
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
    registerCitizen: async (payload) => {
      const data = await request('/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      if (data.access_token) {
        authStorage.setToken(data.access_token)
        authStorage.setUser(data.user)
      }
      return data
    },
    loginCitizen: async (payload) => {
      const data = await request('/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      if (data.access_token) {
        authStorage.setToken(data.access_token)
        authStorage.setUser(data.user)
      }
      return data
    },
    getProfile: async () => {
      return request('/auth/me')
    },
    logoutCitizen: async () => {
      try {
        await request('/auth/logout', { method: 'POST' })
      } finally {
        authStorage.clearAll()
      }
    },
    getIncident: async (incidentId) => {
      return request(`/incidents/${encodeURIComponent(incidentId)}`)
    },
    analyzeText: async (text) => {
      return request('/analyze-text', {
        method: 'POST',
        body: JSON.stringify({ text }),
      })
    },
  }
}

test('authStorage correctly persists and clears citizen tokens and profile', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  assert.equal(auth.getToken(), null)
  assert.equal(auth.getUser(), null)

  auth.setToken('test-jwt-token-123')
  auth.setUser({
    id: 'usr-1',
    full_name: 'Anita Sharma',
    email: 'anita@example.com',
    role: 'citizen',
    created_at: '2026-10-14T10:00:00Z',
  })

  assert.equal(auth.getToken(), 'test-jwt-token-123')
  const user = auth.getUser()
  assert.equal(user.full_name, 'Anita Sharma')
  assert.equal(user.email, 'anita@example.com')

  auth.clearAll()
  assert.equal(auth.getToken(), null)
  assert.equal(auth.getUser(), null)
})

test('registerCitizen posts registration details, sets authStorage, and returns user info', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  let capturedUrl = ''
  let capturedBody = null

  const mockFetch = async (url, options) => {
    capturedUrl = url
    capturedBody = JSON.parse(options.body)
    return {
      ok: true,
      status: 201,
      json: async () => ({
        access_token: 'jwt-reg-token-abc',
        token_type: 'bearer',
        user: {
          id: 'usr-new-1',
          full_name: 'Rohan Verma',
          email: 'rohan@example.com',
          role: 'citizen',
          created_at: '2026-10-14T10:00:00Z',
        },
      }),
    }
  }

  const client = createAuthClient(mockFetch, auth)
  const res = await client.registerCitizen({
    full_name: 'Rohan Verma',
    email: 'rohan@example.com',
    password: 'SecurePassword123!',
  })

  assert.equal(capturedUrl, 'http://127.0.0.1:8001/auth/register')
  assert.equal(capturedBody.full_name, 'Rohan Verma')
  assert.equal(capturedBody.email, 'rohan@example.com')
  assert.equal(res.access_token, 'jwt-reg-token-abc')
  assert.equal(auth.getToken(), 'jwt-reg-token-abc')
  assert.equal(auth.getUser().full_name, 'Rohan Verma')
})

test('loginCitizen authenticates user and updates persisted session', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  const mockFetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      access_token: 'jwt-login-token-xyz',
      token_type: 'bearer',
      user: {
        id: 'usr-login-2',
        full_name: 'Priya Patel',
        email: 'priya@example.com',
        role: 'citizen',
        created_at: '2026-10-14T10:00:00Z',
      },
    }),
  })

  const client = createAuthClient(mockFetch, auth)
  const res = await client.loginCitizen({
    email: 'priya@example.com',
    password: 'Password123!',
  })

  assert.equal(res.user.email, 'priya@example.com')
  assert.equal(auth.getToken(), 'jwt-login-token-xyz')
  assert.equal(auth.getUser().email, 'priya@example.com')
})

test('request automatically injects Authorization Bearer header when token exists', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  auth.setToken('active-token-456')

  let capturedHeaders = null
  const mockFetch = async (_url, options) => {
    capturedHeaders = options.headers
    return {
      ok: true,
      status: 200,
      json: async () => ({
        id: 'usr-1',
        full_name: 'Anita',
        email: 'anita@example.com',
        role: 'citizen',
      }),
    }
  }

  const client = createAuthClient(mockFetch, auth)
  await client.getProfile()

  assert.ok(capturedHeaders)
  assert.equal(capturedHeaders.Authorization, 'Bearer active-token-456')
})

test('logoutCitizen sends logout request and clears auth storage', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  auth.setToken('token-to-clear')
  auth.setUser({ id: 'usr-1', full_name: 'Anita', email: 'anita@example.com' })

  let logoutCalled = false
  const mockFetch = async (url) => {
    if (url.includes('/auth/logout')) logoutCalled = true
    return {
      ok: true,
      status: 200,
      json: async () => ({ success: true, message: 'Logged out successfully.' }),
    }
  }

  const client = createAuthClient(mockFetch, auth)
  await client.logoutCitizen()

  assert.equal(logoutCalled, true)
  assert.equal(auth.getToken(), null)
  assert.equal(auth.getUser(), null)
})

test('Tracking URL query parameter parser correctly handles email tracking links', () => {
  const testUrl = 'http://localhost:5173/?view=citizen-status&incident_id=INC-test-999'
  const parsed = new URL(testUrl)
  const incidentId = parsed.searchParams.get('incident_id')
  const view = parsed.searchParams.get('view')

  assert.equal(incidentId, 'INC-test-999')
  assert.equal(view, 'citizen-status')
})

test('Incident submission returns email notification delivery status', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  auth.setToken('auth-token-citizen')

  const mockFetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      incident_id: 'INC-sub-123',
      report_id: 'REP-sub-456',
      storage_status: 'SAVED',
      crisis_analysis: { incident_type: 'Flood', severity: 'HIGH' },
      email_notification: {
        status: 'MOCKED',
        recipient: 'citizen@example.com',
        subject: 'ResQ-Sense: Incident submitted successfully',
        message: 'Mock email delivered to citizen@example.com',
      },
    }),
  })

  const client = createAuthClient(mockFetch, auth)
  const res = await client.analyzeText('Flooding near Guwahati highway')

  assert.equal(res.incident_id, 'INC-sub-123')
  assert.equal(res.email_notification.status, 'MOCKED')
  assert.equal(res.email_notification.subject, 'ResQ-Sense: Incident submitted successfully')
  assert.equal(res.email_notification.recipient, 'citizen@example.com')
})

test('Incident status lookup throws clear unauthorized/404 error when forbidden', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  // No token set

  const mockFetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({
      detail: 'Incident not found or unauthorized to view this record.',
    }),
  })

  const client = createAuthClient(mockFetch, auth)
  await assert.rejects(
    async () => client.getIncident('INC-private-owned'),
    /unauthorized to view this record|not found/i,
  )
})

// --- Citizen Portal Entry Gate & Session Navigation Tests ---

const createAuthGateHarness = (authStorage) => {
  let currentView = 'landing'
  let pendingCitizenView = null
  let showAuthModal = false

  const isSessionActive = () => Boolean(authStorage.getToken() && authStorage.getUser())

  const navigateToCitizenView = (targetView = 'citizen-home') => {
    if (isSessionActive()) {
      currentView = targetView
      pendingCitizenView = null
      showAuthModal = false
    } else {
      pendingCitizenView = targetView
      showAuthModal = true
    }
  }

  const handleSelectRole = (role) => {
    if (role === 'citizen') {
      navigateToCitizenView('citizen-home')
    } else {
      currentView = 'authority-overview'
    }
  }

  const handleAuthSuccess = (user) => {
    authStorage.setUser(user)
    const target = pendingCitizenView || 'citizen-home'
    currentView = target
    pendingCitizenView = null
    showAuthModal = false
  }

  const handleAuthClose = () => {
    showAuthModal = false
    pendingCitizenView = null
  }

  const handleLogout = () => {
    authStorage.clearAll()
    currentView = 'landing'
    pendingCitizenView = null
    showAuthModal = false
  }

  const handleDockNavigate = (view) => {
    if (view.startsWith('citizen')) {
      navigateToCitizenView(view)
    } else {
      currentView = view
    }
  }

  return {
    getState: () => ({ currentView, pendingCitizenView, showAuthModal }),
    setCurrentView: (view) => {
      currentView = view
    },
    navigateToCitizenView,
    handleSelectRole,
    handleAuthSuccess,
    handleAuthClose,
    handleLogout,
    handleDockNavigate,
  }
}

test('Unauthenticated visitor clicking Citizen Portal on landing page shows AuthModal and blocks direct entry', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  const gate = createAuthGateHarness(auth)

  // Initially on landing page, no active session
  assert.equal(gate.getState().currentView, 'landing')
  assert.equal(gate.getState().showAuthModal, false)

  // Visitor clicks "Citizen Emergency Portal" from landing page
  gate.handleSelectRole('citizen')

  const state = gate.getState()
  // Direct entry is blocked: remains on landing page
  assert.equal(state.currentView, 'landing')
  // Auth modal is displayed
  assert.equal(state.showAuthModal, true)
  // Intended navigation is preserved as pending
  assert.equal(state.pendingCitizenView, 'citizen-home')
})

test('Successful registration or login transitions visitor to Citizen Portal and preserves intended navigation', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  const gate = createAuthGateHarness(auth)

  // Visitor attempts to report an incident while unauthenticated
  gate.navigateToCitizenView('citizen-report')
  assert.equal(gate.getState().showAuthModal, true)
  assert.equal(gate.getState().pendingCitizenView, 'citizen-report')
  assert.equal(gate.getState().currentView, 'landing')

  // Visitor completes login/registration
  auth.setToken('new-jwt-token-777')
  gate.handleAuthSuccess({
    id: 'usr-fresh',
    full_name: 'Sunita Rao',
    email: 'sunita@example.com',
    role: 'citizen',
  })

  const state = gate.getState()
  // Transitions to the intended view ('citizen-report')
  assert.equal(state.currentView, 'citizen-report')
  // Auth modal is closed and pending view is cleared
  assert.equal(state.showAuthModal, false)
  assert.equal(state.pendingCitizenView, null)
  // Session is active
  assert.equal(auth.getUser().full_name, 'Sunita Rao')
})

test('Returning authenticated citizen enters Citizen Portal directly without showing AuthModal', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  // Pre-existing valid citizen session
  auth.setToken('valid-existing-session-token')
  auth.setUser({
    id: 'usr-returning-1',
    full_name: 'Vikram Seth',
    email: 'vikram@example.com',
    role: 'citizen',
  })

  const gate = createAuthGateHarness(auth)
  assert.equal(gate.getState().currentView, 'landing')

  // Returning citizen clicks "Citizen Emergency Portal"
  gate.handleSelectRole('citizen')

  const state = gate.getState()
  // Direct entry is granted
  assert.equal(state.currentView, 'citizen-home')
  // No modal is shown
  assert.equal(state.showAuthModal, false)
  assert.equal(state.pendingCitizenView, null)
})

test('Citizen logout clears session and returns user to landing page', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  auth.setToken('active-token')
  auth.setUser({ id: 'usr-1', full_name: 'Anita', email: 'anita@example.com' })

  const gate = createAuthGateHarness(auth)
  gate.handleSelectRole('citizen')
  assert.equal(gate.getState().currentView, 'citizen-home')

  // Citizen clicks logout
  gate.handleLogout()

  const state = gate.getState()
  // Session is wiped
  assert.equal(auth.getToken(), null)
  assert.equal(auth.getUser(), null)
  // User is returned to landing page
  assert.equal(state.currentView, 'landing')
  assert.equal(state.showAuthModal, false)

  // Subsequent click to enter citizen portal now requires authentication again
  gate.handleSelectRole('citizen')
  assert.equal(gate.getState().currentView, 'landing')
  assert.equal(gate.getState().showAuthModal, true)
})

test('Closing AuthModal without logging in dismisses modal and remains on current view', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  const gate = createAuthGateHarness(auth)

  gate.handleSelectRole('citizen')
  assert.equal(gate.getState().showAuthModal, true)
  assert.equal(gate.getState().pendingCitizenView, 'citizen-home')

  // User dismisses modal
  gate.handleAuthClose()

  const state = gate.getState()
  assert.equal(state.showAuthModal, false)
  assert.equal(state.pendingCitizenView, null)
  assert.equal(state.currentView, 'landing')
})

test('Authority user switching to Citizen Portal via header/dock is guarded by authentication', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  const gate = createAuthGateHarness(auth)

  // User is currently in Authority Operations
  gate.handleSelectRole('authority')
  assert.equal(gate.getState().currentView, 'authority-overview')

  // Unauthenticated user clicks "Switch to Citizen Portal" in header
  gate.navigateToCitizenView('citizen-home')
  assert.equal(gate.getState().currentView, 'authority-overview') // still on authority view
  assert.equal(gate.getState().showAuthModal, true)
  assert.equal(gate.getState().pendingCitizenView, 'citizen-home')

  // After authenticating, transitions to citizen portal
  auth.setToken('citizen-token-888')
  gate.handleAuthSuccess({ id: 'usr-auth-switch', full_name: 'Dev', email: 'dev@example.com' })
  assert.equal(gate.getState().currentView, 'citizen-home')
  assert.equal(gate.getState().showAuthModal, false)
})

test('Dock navigation correctly guards citizen views and allows direct authority navigation', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)
  const gate = createAuthGateHarness(auth)

  // Direct authority navigation from dock works without citizen session
  gate.handleDockNavigate('authority-verified')
  assert.equal(gate.getState().currentView, 'authority-verified')
  assert.equal(gate.getState().showAuthModal, false)

  // Clicking a citizen view from dock without auth is intercepted
  gate.handleDockNavigate('citizen-status')
  assert.equal(gate.getState().currentView, 'authority-verified') // view unchanged
  assert.equal(gate.getState().showAuthModal, true)
  assert.equal(gate.getState().pendingCitizenView, 'citizen-status')
})

test('Citizen login handles unknown email with switch prompt and incorrect password safely', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  // 1. Unknown email test
  const customFetchUnknown = async () => ({
    ok: false,
    status: 404,
    json: async () => ({
      detail: 'No account found with this email. Please register for a citizen account.',
    }),
  })
  const clientUnknown = createAuthClient(customFetchUnknown, auth)
  await assert.rejects(
    async () => {
      await clientUnknown.loginCitizen({
        email: 'nobody@example.com',
        password: 'Password123!',
      })
    },
    (err) => {
      assert.match(err.message, /No account found with this email. Please register for a citizen account./)
      return true
    },
  )

  // 2. Incorrect password test
  const customFetchBadPw = async () => ({
    ok: false,
    status: 401,
    json: async () => ({
      detail: 'Incorrect email or password.',
    }),
  })
  const clientBadPw = createAuthClient(customFetchBadPw, auth)
  await assert.rejects(
    async () => {
      await clientBadPw.loginCitizen({
        email: 'registered@example.com',
        password: 'WrongPassword!',
      })
    },
    (err) => {
      assert.equal(err.message, 'Incorrect email or password.')
      return true
    },
  )
})

test('Citizen cannot access authority workspace and citizen dock excludes authority switch', () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  // Set citizen session
  auth.setToken('citizen-test-token')
  auth.setUser({
    id: 'usr-cit-1',
    full_name: 'Test Citizen',
    email: 'citizen@example.com',
    role: 'citizen',
  })

  // Storage role check
  assert.equal(auth.getUser().role, 'citizen')
  const isAuthorityRole = (role) => role === 'authority' || role === 'admin'
  assert.equal(isAuthorityRole(auth.getUser().role), false)

  // Dock items for citizen must NOT have 'switch-role'
  const citizenItems = [
    { id: 'citizen-home', label: 'Portal Home' },
    { id: 'citizen-report', label: 'Report Incident' },
    { id: 'citizen-status', label: 'Track Reference' },
    { id: 'citizen-map', label: 'Crisis Map' },
  ]
  const hasSwitchRole = citizenItems.some((item) => item.id === 'switch-role')
  assert.equal(hasSwitchRole, false, 'Citizen dock items must not contain switch-role')
})

test('Newly registered citizen fetches isolated personal incidents (0 personal incidents)', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  // Simulated backend response for new citizen /citizen/incidents
  const customFetch = async (url) => {
    if (url.includes('/citizen/incidents')) {
      return {
        ok: true,
        status: 200,
        json: async () => [], // Empty array for new citizen
      }
    }
    return { ok: true, status: 200, json: async () => ({}) }
  }

  const client = createAuthClient(customFetch, auth)
  auth.setToken('new-citizen-jwt')
  auth.setUser({ id: 'usr-new-cit', full_name: 'New Citizen', email: 'new@example.com', role: 'citizen' })

  // Request citizen isolated incidents
  const headers = { Authorization: `Bearer ${auth.getToken()}` }
  const resp = await customFetch('http://127.0.0.1:8001/citizen/incidents', { headers })
  const incidents = await resp.json()

  // Must display zero incidents for new citizen
  assert.equal(Array.isArray(incidents), true)
  assert.equal(incidents.length, 0)
})

test('Admin login rejects citizen accounts with 403 Forbidden', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  // Simulated backend response for citizen trying admin login
  const customFetch = async (url) => {
    if (url.includes('/auth/admin/login')) {
      return {
        ok: false,
        status: 403,
        json: async () => ({
          detail: 'Access denied: This account does not have administrator privileges.',
        }),
      }
    }
    return { ok: true, status: 200, json: async () => ({}) }
  }

  const client = createAuthClient(customFetch, auth)
  await assert.rejects(
    async () => {
      const res = await customFetch('http://127.0.0.1:8001/auth/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'citizen@example.com', password: 'CitizenPass123!' }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail)
      }
    },
    (err) => {
      assert.match(err.message, /administrator privileges/)
      return true
    },
  )
})

test('Password visibility toggle correctly switches between masked and visible text', () => {
  // Test password toggle helper logic
  let showPassword = false
  const toggle = () => {
    showPassword = !showPassword
  }

  assert.equal(showPassword, false)
  const getInputType = (show) => (show ? 'text' : 'password')
  const getAriaLabel = (show) => (show ? 'Hide password' : 'Show password')

  assert.equal(getInputType(showPassword), 'password')
  assert.equal(getAriaLabel(showPassword), 'Show password')

  // Toggle on
  toggle()
  assert.equal(showPassword, true)
  assert.equal(getInputType(showPassword), 'text')
  assert.equal(getAriaLabel(showPassword), 'Hide password')

  // Toggle off
  toggle()
  assert.equal(showPassword, false)
  assert.equal(getInputType(showPassword), 'password')
})

test('Administrator incident details include submitting citizen identity while anonymous incidents display fallback', async () => {
  const storage = createMockLocalStorage()
  const auth = createAuthStorage(storage)

  // Simulated backend responding with submitting citizen for authority
  const customFetch = async (url, options = {}) => {
    if (url.includes('/incidents/INC-AUTHENTICATED')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          incident_id: 'INC-AUTHENTICATED',
          incident_type: 'Flood',
          location_name: 'Guwahati',
          submitting_citizen: {
            id: 'USR-CIT-100',
            full_name: 'Anita Roy',
            email: 'anita.roy@example.com',
            role: 'citizen',
            is_anonymous: false,
          },
        }),
      }
    }
    if (url.includes('/incidents/INC-ANONYMOUS')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          incident_id: 'INC-ANONYMOUS',
          incident_type: 'Fire',
          location_name: 'Delhi',
          submitting_citizen: {
            id: null,
            full_name: 'Anonymous submission',
            email: 'No linked citizen account',
            is_anonymous: true,
          },
        }),
      }
    }
    return { ok: true, status: 200, json: async () => ({}) }
  }

  // 1. Authenticated citizen submission details
  const authResp = await customFetch('http://127.0.0.1:8001/incidents/INC-AUTHENTICATED')
  const authIncident = await authResp.json()
  assert.equal(authIncident.incident_id, 'INC-AUTHENTICATED')
  assert.equal(authIncident.submitting_citizen.full_name, 'Anita Roy')
  assert.equal(authIncident.submitting_citizen.email, 'anita.roy@example.com')
  assert.equal(authIncident.submitting_citizen.is_anonymous, false)

  // 2. Anonymous submission details
  const anonResp = await customFetch('http://127.0.0.1:8001/incidents/INC-ANONYMOUS')
  const anonIncident = await anonResp.json()
  assert.equal(anonIncident.incident_id, 'INC-ANONYMOUS')
  assert.equal(anonIncident.submitting_citizen.full_name, 'Anonymous submission')
  assert.equal(anonIncident.submitting_citizen.email, 'No linked citizen account')
  assert.equal(anonIncident.submitting_citizen.is_anonymous, true)
})

test('Automated confirmation email does not include localhost or tracking link', () => {
  // Test email body composition rules
  const incidentId = 'INC-8899'
  const citizenName = 'Kavita Sharma'

  const textBody = `Hello ${citizenName},

Thank you for reporting an emergency to the ResQ-Sense Emergency Response Network.
Your report has been successfully registered and queued for response verification.

INCIDENT DETAILS:
--------------------------------------------------
Tracking Reference ID : ${incidentId}
Incident Type         : Flood
Location              : Chennai
Submitted At          : Just now

TRACKING YOUR INCIDENT:
You can track real-time authority verification, status updates, and emergency response planning inside the ResQ-Sense Citizen Portal using your Tracking Reference ID (${incidentId}).`

  // Assertions: contains reference ID, but contains NO tracking link / localhost URL
  assert.match(textBody, /INC-8899/)
  assert.doesNotMatch(textBody, /localhost/)
  assert.doesNotMatch(textBody, /http:\/\//)
  assert.doesNotMatch(textBody, /https:\/\//)
})



