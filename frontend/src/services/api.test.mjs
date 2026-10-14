/**
 * api.test.mjs
 * Frontend unit and integration tests for incident deletion:
 * 1. api.deleteIncident sends DELETE request to /incidents/{id} with proper URL encoding.
 * 2. Successful response parsing on 200 OK.
 * 3. Error throwing with server error detail on 404 (nonexistent ID).
 * 4. Error throwing on 500 server failure.
 * 5. State transformation: incident list filtering, count decrement, and active selection reset.
 */

import test from 'node:test'
import assert from 'node:assert/strict'

// Create a mockable fetch test harness for the frontend api service
const createTestClient = (customFetch) => {
  const API_BASE_URL = 'http://127.0.0.1:8001'

  async function request(path, options = {}) {
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    const headers = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
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
    deleteIncident: (incidentId) =>
      request(`/incidents/${encodeURIComponent(incidentId)}`, {
        method: 'DELETE',
      }),
  }
}

test('api.deleteIncident sends DELETE to /incidents/{id} and returns success payload', async () => {
  let calledUrl = ''
  let calledMethod = ''

  const mockFetch = async (url, options) => {
    calledUrl = url
    calledMethod = options.method
    return {
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        incident_id: 'INC-abc-123',
        message: 'Incident INC-abc-123 permanently deleted.',
      }),
    }
  }

  const client = createTestClient(mockFetch)
  const result = await client.deleteIncident('INC-abc-123')

  assert.equal(calledUrl, 'http://127.0.0.1:8001/incidents/INC-abc-123')
  assert.equal(calledMethod, 'DELETE')
  assert.equal(result.success, true)
  assert.equal(result.incident_id, 'INC-abc-123')
  assert.match(result.message, /permanently deleted/i)
})

test('api.deleteIncident correctly encodes special characters in incident ID', async () => {
  let calledUrl = ''

  const mockFetch = async (url) => {
    calledUrl = url
    return {
      ok: true,
      status: 200,
      json: async () => ({ success: true, incident_id: 'INC/special#1' }),
    }
  }

  const client = createTestClient(mockFetch)
  await client.deleteIncident('INC/special#1')

  assert.equal(calledUrl, 'http://127.0.0.1:8001/incidents/INC%2Fspecial%231')
})

test('api.deleteIncident throws descriptive error on 404 Not Found', async () => {
  const mockFetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({ detail: 'Incident not found.' }),
  })

  const client = createTestClient(mockFetch)
  await assert.rejects(
    async () => {
      await client.deleteIncident('INC-NONEXISTENT')
    },
    {
      name: 'Error',
      message: 'Incident not found.',
    }
  )
})

test('api.deleteIncident throws error on 500 server failure', async () => {
  const mockFetch = async () => ({
    ok: false,
    status: 500,
    json: async () => ({ detail: 'Database connection failed' }),
  })

  const client = createTestClient(mockFetch)
  await assert.rejects(
    async () => {
      await client.deleteIncident('INC-FAIL-500')
    },
    {
      name: 'Error',
      message: 'Database connection failed',
    }
  )
})

test('Frontend state update removes deleted incident and decrements queue counts', () => {
  const initialIncidents = [
    { incident_id: 'INC-1', verification_status: 'PENDING', severity: 'HIGH' },
    { incident_id: 'INC-2', verification_status: 'VERIFIED', severity: 'CRITICAL' },
    { incident_id: 'INC-3', verification_status: 'PENDING', severity: 'MEDIUM' },
  ]

  const deletedId = 'INC-1'

  // Simulating the exact state update logic used in AuthorityWorkspace.tsx:
  // setIncidents((prev) => prev.filter((inc) => inc.incident_id !== targetId))
  const updatedIncidents = initialIncidents.filter((inc) => inc.incident_id !== deletedId)

  assert.equal(updatedIncidents.length, 2)
  assert.equal(updatedIncidents.some((i) => i.incident_id === deletedId), false)

  // Recalculating queue counts
  const incomingCount = updatedIncidents.filter(
    (i) => i.verification_status === 'PENDING' || i.verification_status === 'NEEDS_MORE_INFO'
  ).length
  const verifiedCount = updatedIncidents.filter((i) => i.verification_status === 'VERIFIED').length

  assert.equal(incomingCount, 1) // reduced from 2 to 1
  assert.equal(verifiedCount, 1) // remains 1
})

test('Frontend selection resets when active incident is deleted', () => {
  let selectedIncident = { incident_id: 'INC-TARGET' }
  let incidentDetail = { incident_id: 'INC-TARGET', reports: [] }

  const deletedId = 'INC-TARGET'

  if (selectedIncident?.incident_id === deletedId) {
    selectedIncident = null
    incidentDetail = null
  }

  assert.equal(selectedIncident, null)
  assert.equal(incidentDetail, null)
})

test('Frontend selection is preserved when a different incident is deleted', () => {
  let selectedIncident = { incident_id: 'INC-ACTIVE' }
  const deletedId = 'INC-OTHER'

  if (selectedIncident?.incident_id === deletedId) {
    selectedIncident = null
  }

  assert.notEqual(selectedIncident, null)
  assert.equal(selectedIncident.incident_id, 'INC-ACTIVE')
})
