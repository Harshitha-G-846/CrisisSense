/**
 * api.ts - ResQ-Sense API Client and Data Contracts
 * Member 4 Integration & Frontend Layer
 */

const API_BASE_URL =
  (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ||
  'http://127.0.0.1:8001'

// --- Core Data Contracts ---

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'

export type VerificationStatus =
  | 'PENDING'
  | 'VERIFIED'
  | 'NEEDS_MORE_INFO'
  | 'REJECTED'
  | 'UNKNOWN'

export type IncidentStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED'

export type ResponseStatus = 'NOT_PLANNED' | 'PLANNED' | 'AUTHORIZED'

export type VerificationDecision =
  | 'APPROVE'
  | 'REJECT'
  | 'NEED_MORE_INFORMATION'

export interface LocationInfo {
  text?: string
  city?: string
  state?: string
  country?: string
  latitude?: number | null
  longitude?: number | null
}

export interface CrisisAnalysis {
  is_crisis?: boolean | null
  incident_type?: string | null
  information_type?: string | null
  severity?: string | null
  needs?: string[]
  locations?: LocationInfo[]
  crisis_probability?: number | null
  message?: string
  [key: string]: unknown
}

export interface EvidenceItem {
  source: string
  polarity: string
  weight: number
  finding: string
  details?: Record<string, unknown>
}

export interface CurrentnessData {
  currentness: 'CURRENT' | 'OLD' | 'UNCERTAIN' | string
  confidence: number
  action: 'ALLOW' | 'HUMAN_VERIFICATION_REQUIRED' | string
  has_conflict?: boolean
  conflicts_detected: string[]
  evidence: EvidenceItem[]
}

export interface LinkedReport {
  report_id: string
  original_text: string
  crisis_analysis?: CrisisAnalysis | null
  currentness?: CurrentnessData | null
  received_at?: string | null
}

export interface Incident {
  incident_id?: string
  incident_type?: string
  location_name?: string | null
  latitude?: number | null
  longitude?: number | null
  severity?: string
  needs?: string[]
  status?: IncidentStatus | string
  verification_status?: VerificationStatus | string
  response_status?: ResponseStatus | string
  report_count?: number
  has_conflict?: boolean
  conflicts_detected?: string[]
  created_at?: string | null
  updated_at?: string | null
  [key: string]: unknown
}

export interface IncidentDetail extends Incident {
  reports?: LinkedReport[]
  has_conflict?: boolean
  conflicts_detected?: string[]
}

export interface AnalyzeResult {
  report_id: string | null
  incident_id: string | null
  storage_status?: string
  crisis_analysis: CrisisAnalysis
  currentness: CurrentnessData
  has_conflict?: boolean
  conflicts_detected?: string[]
}

export interface VerificationResponse {
  incident_id: string
  decision: VerificationDecision
  verification_status: string
  reason?: string | null
  message: string
}

export interface FeedbackResponse {
  incident_id: string
  feedback: string
  situation_changed: boolean
  detected_needs: string[]
  updated_needs: string[]
  status: string
  message: string
}

export interface ResourceCandidate {
  resource_id: string
  name: string
  resource_type: string
  department: string
  availability: string
  distance_km: number
  is_synthetic?: boolean
  availability_is_simulated?: boolean
}

export interface NeedRecommendation {
  need: string
  candidates: ResourceCandidate[]
}

export interface DepartmentRecommendation {
  department: string
  required_for?: string[]
}

export interface ResourceRecommendationData {
  incident_id?: string
  mode?: string
  verification_status?: string
  human_approval_required?: boolean
  radius_km?: number
  distance_method?: string
  required_needs?: string[]
  recommended_departments?: (string | DepartmentRecommendation)[]
  unmapped_needs?: string[]
  recommendations?: NeedRecommendation[]
  unmet_needs?: string[]
  reason?: string
  is_synthetic?: boolean
  availability_is_simulated?: boolean
  dataset_version?: string
  dataset_label?: string
  simulation_notice?: string
}

export interface RevisedPlanResponse {
  incident_id: string
  incident_type?: string
  location?: string | null
  severity?: string
  needs?: string[]
  resource_recommendation?: ResourceRecommendationData
  human_approval_required?: boolean
  message?: string
}

export interface AuthorizeResponse {
  success: boolean
  incident_id: string
  response_status?: string
  verification_status?: string
  incident_status?: string
  message: string
}

export interface ResourceItem {
  resource_id: string
  name: string
  resource_type: string
  department: string
  capabilities: string[]
  location_name: string
  latitude: number
  longitude: number
  availability: 'AVAILABLE' | 'BUSY' | 'OFFLINE'
}

export interface ResourceListResponse {
  total: number
  limit: number
  offset: number
  items: ResourceItem[]
}

// --- Request Wrapper ---

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers as Record<string, string>),
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let errorDetail = ''
    try {
      const errJson = await response.json()
      errorDetail =
        errJson.detail || errJson.message || JSON.stringify(errJson)
    } catch {
      errorDetail = await response.text()
    }
    throw new Error(errorDetail || `HTTP error ${response.status}`)
  }

  return response.json() as Promise<T>
}

// --- API Service Methods ---

export const api = {
  getBaseUrl: () => API_BASE_URL,

  checkHealth: () =>
    request<{ message: string; version: string }>('/'),

  listIncidents: () =>
    request<Incident[]>('/incidents'),

  getIncident: (incidentId: string) =>
    request<IncidentDetail>(`/incidents/${encodeURIComponent(incidentId)}`),

  listResources: (params?: {
    limit?: number
    offset?: number
    resource_type?: string
    availability?: 'AVAILABLE' | 'BUSY' | 'OFFLINE'
  }) => {
    const query = new URLSearchParams()
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.offset) query.set('offset', String(params.offset))
    if (params?.resource_type) query.set('resource_type', params.resource_type)
    if (params?.availability) query.set('availability', params.availability)
    const qs = query.toString() ? `?${query.toString()}` : ''
    return request<ResourceListResponse>(`/resources${qs}`)
  },

  getIncidentResources: (
    incidentId: string,
    params?: { radius_km?: number; per_need?: number },
  ) => {
    const query = new URLSearchParams()
    if (params?.radius_km) query.set('radius_km', String(params.radius_km))
    if (params?.per_need) query.set('per_need', String(params.per_need))
    const qs = query.toString() ? `?${query.toString()}` : ''
    return request<ResourceRecommendationData>(
      `/incidents/${encodeURIComponent(incidentId)}/resources${qs}`,
    )
  },

  analyzeText: (text: string) =>
    request<AnalyzeResult>('/analyze-text', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  analyzeEvidence: (formData: FormData) =>
    request<AnalyzeResult>('/analyze', {
      method: 'POST',
      body: formData,
    }),

  verifyIncident: (
    incidentId: string,
    decision: VerificationDecision,
    reason?: string,
  ) =>
    request<VerificationResponse>(
      `/incidents/${encodeURIComponent(incidentId)}/verify`,
      {
        method: 'POST',
        body: JSON.stringify({ decision, reason: reason || null }),
      },
    ),

  submitFeedback: (incidentId: string, feedback: string) =>
    request<FeedbackResponse>(
      `/incidents/${encodeURIComponent(incidentId)}/feedback`,
      {
        method: 'POST',
        body: JSON.stringify({ feedback }),
      },
    ),

  replanIncident: (incidentId: string) =>
    request<RevisedPlanResponse>(
      `/incidents/${encodeURIComponent(incidentId)}/replan`,
      { method: 'POST' },
    ),

  authorizeResponse: (incidentId: string) =>
    request<AuthorizeResponse>(
      `/incidents/${encodeURIComponent(incidentId)}/authorize`,
      { method: 'POST' },
    ),

  updateIncidentStatus: (incidentId: string, status: IncidentStatus) =>
    request<{
      incident_id: string
      status: string
      verification_status: string
      updated_at: string
    }>(`/incidents/${encodeURIComponent(incidentId)}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
}
