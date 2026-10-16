import { useState, useEffect, useCallback } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Copy,
  Flame,
  Image as ImageIcon,
  Info,
  MapPin,
  Mic,
  PhoneCall,
  Radio,
  Send,
  ShieldAlert,
  Sparkles,
  Video,
  X,
  RefreshCw,
  Search,
  AlertTriangle,
  Check,
  Eye,
  LogIn,
  Mail,
} from 'lucide-react'
import {
  api,
  authStorage,
  type AnalyzeResult,
  type CitizenUser,
  type Incident,
  type IncidentDetail,
  type LocationInfo,
} from '../services/api'
import { AuthModal } from './AuthModal'
import { AudioRecorder } from './AudioRecorder'
import { LocationSearchPicker } from './LocationSearchPicker'

interface SavedReport {
  incident_id: string
  report_id?: string
  text: string
  location?: string
  timestamp: string
}

const LOCAL_STORAGE_KEY = 'resq_sense_citizen_reports'

export const CitizenPortal: React.FC<{
  initialView?: 'home' | 'report' | 'status'
  initialIncidentId?: string
  onViewMap?: () => void
  onLogout?: () => void
}> = ({ initialView = 'home', initialIncidentId, onViewMap }) => {
  const [activeTab, setActiveTab] = useState<'home' | 'report' | 'status'>(
    initialIncidentId ? 'status' : initialView,
  )

  // Citizen Authentication State
  const [currentUser, setCurrentUser] = useState<CitizenUser | null>(() =>
    authStorage.getUser(),
  )
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authModalMessage, setAuthModalMessage] = useState<string | undefined>()

  // Citizen-specific server-side incidents isolation
  const [myIncidents, setMyIncidents] = useState<Incident[]>([])
  const [loadingIncidents, setLoadingIncidents] = useState(false)

  // Report Form State
  const [description, setDescription] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')
  const [locationName, setLocationName] = useState('')
  const [deviceCoords, setDeviceCoords] = useState<{
    lat: number
    lon: number
  } | null>(null)
  const [selectedLocation, setSelectedLocation] = useState<LocationInfo | null>(null)
  const [mediaFile, setMediaFile] = useState<File | null>(null)
  const [mediaType, setMediaType] = useState<'image' | 'video' | 'audio' | null>(
    null,
  )
  const [mediaMode, setMediaMode] = useState<'upload' | 'record'>('upload')
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submissionResult, setSubmissionResult] =
    useState<AnalyzeResult | null>(null)
  const [copiedId, setCopiedId] = useState(false)

  // Status Lookup State
  const [searchId, setSearchId] = useState(initialIncidentId || '')
  const [trackedIncident, setTrackedIncident] = useState<IncidentDetail | null>(
    null,
  )
  const [trackingLoading, setTrackingLoading] = useState(false)
  const [trackingError, setTrackingError] = useState<string | null>(null)

  // Feedback on Tracked Incident State
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false)
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null)

  // Saved Reports in LocalStorage
  const [savedReports, setSavedReports] = useState<SavedReport[]>([])

  // Fetch only the authenticated citizen's personal incidents
  const refreshMyIncidents = useCallback(async () => {
    if (!authStorage.getToken() || !authStorage.isCitizen()) {
      setMyIncidents([])
      return
    }
    setLoadingIncidents(true)
    try {
      const data = await api.listCitizenIncidents()
      setMyIncidents(data)
    } catch (err) {
      console.warn('Could not load citizen incidents:', err)
      setMyIncidents([])
    } finally {
      setLoadingIncidents(false)
    }
  }, [])

  // Hydrate citizen user profile and verify active session token
  useEffect(() => {
    const token = authStorage.getToken()
    if (token) {
      api
        .getProfile()
        .then((profile) => {
          setCurrentUser(profile)
          authStorage.setUser(profile)
        })
        .catch(() => {
          authStorage.clearAll()
          setCurrentUser(null)
          setMyIncidents([])
        })
    }
  }, [])

  useEffect(() => {
    if (currentUser && currentUser.role === 'citizen') {
      void refreshMyIncidents()
    } else {
      setMyIncidents([])
    }
  }, [currentUser, refreshMyIncidents])

  // Auto-track initial incident ID if provided
  useEffect(() => {
    if (initialIncidentId) {
      setSearchId(initialIncidentId)
      setActiveTab('status')
      void handleTrackIncident(initialIncidentId)
    } else {
      setActiveTab(initialView)
    }
  }, [initialView, initialIncidentId])

  useEffect(() => {
    try {
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY)
      if (stored) {
        setSavedReports(JSON.parse(stored))
      }
    } catch {
      // ignore storage errors
    }
  }, [])

  const saveReportToHistory = (item: SavedReport) => {
    try {
      const updated = [item, ...savedReports.filter((r) => r.incident_id !== item.incident_id)].slice(
        0,
        10,
      )
      setSavedReports(updated)
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(updated))
    } catch {
      // ignore storage errors
    }
  }


  // Media Handler
  const handleMediaUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const type = file.type
    if (type.startsWith('image/')) {
      setMediaType('image')
    } else if (type.startsWith('video/')) {
      setMediaType('video')
    } else if (type.startsWith('audio/')) {
      setMediaType('audio')
    } else {
      alert('Supported media formats: Images (JPG/PNG), Videos (MP4/MOV), and Audio (MP3/WAV).')
      return
    }

    setMediaFile(file)
  }

  // Submit Report
  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!description.trim() && !mediaFile) {
      setSubmitError('Please provide an incident description or upload media evidence.')
      return
    }

    // Require citizen authentication for incident submission
    if (!currentUser) {
      setAuthModalMessage(
        'Please sign in or create a citizen account to submit your emergency report. This links your incident, ensures secure tracking ownership, and sends official email confirmation.',
      )
      setShowAuthModal(true)
      return
    }

    setSubmitting(true)
    setSubmitError(null)

    try {
      let combinedText = description.trim()
      if (locationName.trim()) {
        combinedText += ` (Reported Location: ${locationName.trim()})`
      }
      if (selectedCategory && selectedCategory !== 'Other') {
        combinedText = `[Incident: ${selectedCategory}] ${combinedText}`
      }

      let result: AnalyzeResult

      if (mediaFile) {
        const formData = new FormData()
        if (combinedText) {
          formData.append('text', combinedText)
        }
        if (locationName.trim()) {
          formData.append('location_name', locationName.trim())
        }
        if (deviceCoords) {
          formData.append('latitude', String(deviceCoords.lat))
          formData.append('longitude', String(deviceCoords.lon))
        }
        if (mediaType === 'image') formData.append('image', mediaFile)
        else if (mediaType === 'video') formData.append('video', mediaFile)
        else if (mediaType === 'audio') formData.append('audio', mediaFile)

        result = await api.analyzeEvidence(formData)
      } else {
        result = await api.analyzeText(
          combinedText,
          locationName.trim() || undefined,
          deviceCoords?.lat,
          deviceCoords?.lon,
        )
      }

      setSubmissionResult(result)

      if (result.incident_id) {
        saveReportToHistory({
          incident_id: result.incident_id,
          report_id: result.report_id || undefined,
          text: description.trim(),
          location: locationName.trim(),
          timestamp: new Date().toISOString(),
        })
        void refreshMyIncidents()
      }

      // Reset form
      setDescription('')
      setLocationName('')
      setDeviceCoords(null)
      setMediaFile(null)
      setMediaType(null)
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : 'Submission failed. Please check network and retry.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  // Lookup Incident Status
  const handleTrackIncident = async (idToSearch?: string) => {
    const id = (idToSearch || searchId).trim()
    if (!id) return

    setTrackingLoading(true)
    setTrackingError(null)
    setFeedbackMessage(null)

    try {
      const data = await api.getIncident(id)
      setTrackedIncident(data)
    } catch (err) {
      setTrackedIncident(null)
      setTrackingError(
        err instanceof Error
          ? err.message
          : 'Could not find incident with that Reference ID. Please verify and try again.',
      )
    } finally {
      setTrackingLoading(false)
    }
  }

  // Submit Feedback
  const handleSubmitFeedback = async () => {
    if (!trackedIncident?.incident_id || !feedbackText.trim()) return

    setFeedbackSubmitting(true)
    setFeedbackMessage(null)

    try {
      const res = await api.submitFeedback(
        trackedIncident.incident_id,
        feedbackText.trim(),
      )
      setFeedbackMessage(
        res.situation_changed
          ? `Alert: Situation change recognized! Additional needs updated: [${res.detected_needs.join(', ')}]`
          : 'Feedback recorded by response team. No major escalation detected.',
      )
      setFeedbackText('')
      // Refresh incident
      void handleTrackIncident(trackedIncident.incident_id)
    } catch (err) {
      setFeedbackMessage(
        err instanceof Error ? `Feedback submission failed: ${err.message}` : 'Failed to submit feedback.',
      )
    } finally {
      setFeedbackSubmitting(false)
    }
  }

  const copyReferenceId = (id: string) => {
    navigator.clipboard.writeText(id)
    setCopiedId(true)
    setTimeout(() => setCopiedId(false), 2000)
  }

  return (
    <div className="citizen-portal-container">
      {/* Citizen Sub-Navigation Header */}
      <header className="citizen-portal-nav">
        <div className="citizen-portal-tabs">
          <button
            type="button"
            className={`citizen-tab-btn ${activeTab === 'home' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('home')
              setSubmissionResult(null)
            }}
          >
            <Radio size={16} />
            <span>Emergency Home</span>
          </button>

          <button
            type="button"
            className={`citizen-tab-btn ${activeTab === 'report' ? 'active' : ''}`}
            onClick={() => setActiveTab('report')}
          >
            <FilePlus2Icon size={16} />
            <span>Report Incident</span>
          </button>

          <button
            type="button"
            className={`citizen-tab-btn ${activeTab === 'status' ? 'active' : ''}`}
            onClick={() => setActiveTab('status')}
          >
            <Search size={16} />
            <span>Track Status</span>
            {((currentUser ? myIncidents.length : savedReports.length) > 0) && (
              <span className="tab-pill">
                {currentUser ? myIncidents.length : savedReports.length}
              </span>
            )}
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {onViewMap && (
            <button
              type="button"
              className="citizen-map-link-btn"
              onClick={onViewMap}
            >
              <MapPin size={15} />
              <span>View Active Map</span>
            </button>
          )}

          <div className="citizen-auth-controls">
            {currentUser ? (
              <div className="citizen-user-pill">
                <div className="citizen-user-avatar">
                  {currentUser.full_name ? currentUser.full_name.charAt(0).toUpperCase() : 'U'}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span className="citizen-user-name">{currentUser.full_name}</span>
                  <span className="citizen-user-email">{currentUser.email}</span>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="citizen-auth-btn"
                onClick={() => {
                  setAuthModalMessage(undefined)
                  setShowAuthModal(true)
                }}
              >
                <LogIn size={14} />
                <span>Sign In / Register</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* VIEW: HOME GREETING */}
      {activeTab === 'home' && (
        <div className="citizen-home-view">
          <section className="citizen-greeting-hero">
            <div className="greeting-badge">
              <Sparkles size={14} />
              <span>ResQ-Sense Citizen Emergency Dispatch</span>
            </div>

            <h1>
              Have you witnessed an <span>emergency?</span>
            </h1>

            <p className="greeting-subtext">
              Submit real-time crisis reports with photos, videos, or voice notes.
              Your signals are analyzed by AI and forwarded to authorized emergency
              responders for human verification and resource deployment.
            </p>

            <div className="greeting-cta-group">
              <button
                type="button"
                className="btn-primary-glow"
                onClick={() => setActiveTab('report')}
              >
                <AlertCircle size={18} />
                <span>Report an Incident Now</span>
              </button>

              <button
                type="button"
                className="btn-glass"
                onClick={() => setActiveTab('status')}
              >
                <Search size={18} />
                <span>Track Existing Report</span>
              </button>
            </div>
          </section>

          {/* Emergency Helplines Card */}
          <section className="emergency-numbers-grid">
            <div className="emergency-card medical">
              <div className="emergency-card-icon">
                <PhoneCall size={20} />
              </div>
              <div className="emergency-card-body">
                <span className="emergency-number">108</span>
                <strong>Ambulance &amp; Emergency Medical</strong>
                <p>24/7 National Emergency Medical Services</p>
              </div>
            </div>

            <div className="emergency-card fire">
              <div className="emergency-card-icon">
                <Flame size={20} />
              </div>
              <div className="emergency-card-body">
                <span className="emergency-number">101</span>
                <strong>Fire &amp; Rescue Services</strong>
                <p>Building fires, gas leaks, industrial hazards</p>
              </div>
            </div>

            <div className="emergency-card disaster">
              <div className="emergency-card-icon">
                <ShieldAlert size={20} />
              </div>
              <div className="emergency-card-body">
                <span className="emergency-number">1077 / 1070</span>
                <strong>Disaster Management (NDRF / SDMA)</strong>
                <p>Floods, cyclones, earthquakes, landslides</p>
              </div>
            </div>
          </section>

          {/* Authenticated Citizen Personal Incidents Dashboard */}
          {currentUser ? (
            <section className="citizen-isolated-dashboard">
              <div className="citizen-dashboard-header">
                <div className="citizen-dashboard-title">
                  <ShieldAlert size={18} style={{ color: '#818cf8' }} />
                  <h3>Your Emergency Incident Reports</h3>
                  <span className="citizen-count-badge">
                    {myIncidents.length} {myIncidents.length === 1 ? 'Incident' : 'Incidents'} • {myIncidents.length} {myIncidents.length === 1 ? 'Personal Report' : 'Personal Reports'}
                  </span>
                </div>
                {loadingIncidents && (
                  <span className="text-muted text-sm" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <RefreshCw size={13} className="spinner" /> Syncing...
                  </span>
                )}
              </div>

              {myIncidents.length === 0 ? (
                <div className="citizen-empty-state-card">
                  <div className="citizen-empty-icon">
                    <ShieldAlert size={26} />
                  </div>
                  <h4>No Incident Reports Submitted Yet</h4>
                  <p>
                    Your personal citizen dashboard displays 0 incidents and 0 reports. When you submit an emergency report, its real-time verification status, department routing, and official reference code will appear here securely.
                  </p>
                  <button
                    type="button"
                    className="citizen-empty-cta"
                    onClick={() => setActiveTab('report')}
                  >
                    <span>Submit Your First Emergency Report</span>
                  </button>
                </div>
              ) : (
                <div className="citizen-incidents-list">
                  {myIncidents.map((inc) => {
                    const incId = inc.incident_id || 'UNKNOWN'
                    return (
                      <div
                        key={incId}
                        className="citizen-incident-card"
                        onClick={() => {
                          if (inc.incident_id) {
                            setSearchId(inc.incident_id)
                            setActiveTab('status')
                            void handleTrackIncident(inc.incident_id)
                          }
                        }}
                        title="Click to track live dispatch status"
                      >
                        <div className="citizen-incident-card-top">
                          <span className="citizen-incident-id" title={incId}>
                            {incId}
                          </span>
                          <span
                            className={`citizen-status-badge ${(
                              inc.verification_status || 'pending'
                            )
                              .toLowerCase()
                              .replace(/\s+/g, '_')}`}
                          >
                            {inc.verification_status || 'PENDING'}
                          </span>
                        </div>
                        <div className="citizen-incident-type">
                          {inc.incident_type || 'Crisis Incident'}
                        </div>
                        <div className="citizen-incident-meta">
                          <span className="citizen-incident-location">
                            <MapPin size={12} />
                            {inc.location_name || 'Location Not Specified'}
                          </span>
                          <span>
                            {inc.created_at
                              ? new Date(inc.created_at).toLocaleDateString()
                              : 'Recently'}
                          </span>
                        </div>
                        {inc.verification_status === 'NEEDS_MORE_INFO' && inc.admin_feedback && (
                          <div className="citizen-card-feedback-hint">
                            <AlertCircle size={12} />
                            <span>Requested Info: {inc.admin_feedback}</span>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
          ) : (
            savedReports.length > 0 && (
              <section className="recent-submissions-card">
                <div className="card-header-row">
                  <div className="card-title-group">
                    <Clock size={16} />
                    <h3>Your Recent Incident Reports</h3>
                  </div>
                  <span className="text-muted text-sm">Stored locally on this device</span>
                </div>

                <div className="saved-reports-grid">
                  {savedReports.map((report) => (
                    <div
                      key={report.incident_id}
                      className="saved-report-pill"
                      onClick={() => {
                        setSearchId(report.incident_id)
                        setActiveTab('status')
                        void handleTrackIncident(report.incident_id)
                      }}
                    >
                      <div className="pill-header">
                        <span className="pill-id">{report.incident_id}</span>
                        <span className="pill-time">
                          {new Date(report.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="pill-text">{report.text || 'Incident reported'}</p>
                      {report.location && (
                        <span className="pill-loc">
                          <MapPin size={12} />
                          {report.location}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )
          )}
        </div>
      )}

      {/* VIEW: REPORT INCIDENT FORM */}
      {activeTab === 'report' && (
        <div className="citizen-report-view">
          {submissionResult ? (
            /* SUCCESS CONFIRMATION SCREEN */
            <div className="submission-success-card">
              <div className="success-badge-icon">
                <CheckCircle2 size={36} />
              </div>

              <h2>Emergency Report Submitted Successfully</h2>

              <p className="success-instruction">
                Your report has been securely registered in the ResQ-Sense emergency
                response network. The authorities have been alerted for verification.
              </p>

              <div className="reference-id-container">
                <span className="reference-label">Official Incident Reference ID</span>
                <div className="reference-code-box">
                  <code>{submissionResult.incident_id || 'PENDING-ID'}</code>
                  {submissionResult.incident_id && (
                    <button
                      type="button"
                      className="copy-btn"
                      onClick={() =>
                        copyReferenceId(submissionResult.incident_id as string)
                      }
                      title="Copy Reference ID"
                    >
                      {copiedId ? <Check size={16} /> : <Copy size={16} />}
                      <span>{copiedId ? 'Copied' : 'Copy'}</span>
                    </button>
                  )}
                </div>
                {submissionResult.report_id && (
                  <span className="report-sub-id">
                    Linked Report ID: {submissionResult.report_id}
                  </span>
                )}
              </div>

              {/* Submission Email Confirmation Notice */}
              {submissionResult.email_notification && (
                <div
                  className={`email-confirmation-card ${submissionResult.email_notification.status.toLowerCase()}`}
                >
                  <Mail size={20} className="email-icon" />
                  <div className="email-body-text">
                    <span className="email-title">
                      {submissionResult.email_notification.status === 'SENT' &&
                        'Confirmation Email Dispatched'}
                      {submissionResult.email_notification.status === 'MOCKED' &&
                        'Confirmation Email Generated (Mock Delivery Active)'}
                      {submissionResult.email_notification.status === 'FAILED' &&
                        'Confirmation Email Notice'}
                      {submissionResult.email_notification.status === 'SKIPPED' &&
                        'Email Notice'}
                    </span>
                    <span className="email-subtext">
                      {submissionResult.email_notification.status === 'SENT' &&
                        `An official confirmation email with Reference ID ${submissionResult.incident_id} and a direct tracking link has been sent to ${submissionResult.email_notification.recipient}.`}
                      {submissionResult.email_notification.status === 'MOCKED' &&
                        `A confirmation email with tracking link was generated for ${submissionResult.email_notification.recipient}. (Live Gmail SMTP credentials pending from team; email saved in server mock outbox).`}
                      {submissionResult.email_notification.status === 'FAILED' &&
                        `Incident submitted successfully, but automated email delivery failed (${submissionResult.email_notification.error || 'SMTP delivery issue'}). Please keep your Reference ID handy.`}
                      {submissionResult.email_notification.status === 'SKIPPED' &&
                        (submissionResult.email_notification.message ||
                          'No registered citizen email account was linked.')}
                    </span>
                  </div>
                </div>
              )}

              {/* Conflicting Evidence Alert */}
              {(submissionResult.has_conflict ||
                (submissionResult.currentness?.conflicts_detected &&
                  submissionResult.currentness.conflicts_detected.length > 0)) && (
                <div className="citizen-conflict-card" id="citizen-conflict-alert">
                  <div className="citizen-conflict-top">
                    <AlertTriangle size={22} className="conflict-icon-warning" />
                    <div>
                      <h3 className="conflict-title">
                        CONFLICTING EVIDENCE DETECTED — HUMAN REVIEW REQUIRED
                      </h3>
                      <p className="conflict-subtitle">
                        The submitted description and uploaded media evidence do not agree.
                        ResQ-Sense does not prioritize text over media when conflicting signals exist;
                        this report requires manual human authority review before verification.
                      </p>
                    </div>
                  </div>

                  {submissionResult.currentness?.conflicts_detected &&
                    submissionResult.currentness.conflicts_detected.length > 0 && (
                      <div className="conflict-sources-box">
                        <span className="conflict-sources-label">
                          Detected Contradictions Across Modalities:
                        </span>
                        <ul>
                          {submissionResult.currentness.conflicts_detected.map((conf, cIdx) => (
                            <li key={cIdx}>{conf}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                  <div className="conflict-actions-bar">
                    <button
                      type="button"
                      className="btn-review-evidence"
                      onClick={() => {
                        const target = document.getElementById('citizen-evidence-breakdown')
                        if (target) target.scrollIntoView({ behavior: 'smooth' })
                      }}
                    >
                      <Eye size={15} />
                      <span>Review Evidence</span>
                    </button>
                    <span className="conflict-status-notice">
                      Status: Forwarded to Authority Human Review (Report retained, not auto-rejected)
                    </span>
                  </div>
                </div>
              )}

              {/* Temporal Uncertainty / Verification Notice (when no explicit modality contradiction exists) */}
              {!submissionResult.has_conflict &&
                !(submissionResult.currentness?.conflicts_detected &&
                  submissionResult.currentness.conflicts_detected.length > 0) &&
                (submissionResult.currentness?.action === 'HUMAN_VERIFICATION_REQUIRED' ||
                  submissionResult.currentness?.currentness === 'UNCERTAIN') && (
                <div className="citizen-conflict-card uncertainty-notice" id="citizen-uncertainty-alert" style={{ borderColor: 'rgba(234, 179, 8, 0.4)', background: 'rgba(234, 179, 8, 0.08)' }}>
                  <div className="citizen-conflict-top">
                    <AlertTriangle size={22} style={{ color: '#eab308' }} />
                    <div>
                      <h3 className="conflict-title" style={{ color: 'var(--severity-medium-color)' }}>
                        TEMPORAL UNCERTAINTY — HUMAN VERIFICATION REQUIRED
                      </h3>
                      <p className="conflict-subtitle">
                        Temporal currentness could not be verified conclusively from available metadata and text claims.
                        This report has been forwarded for manual human authority review.
                      </p>
                    </div>
                  </div>
                  <div className="conflict-actions-bar">
                    <button
                      type="button"
                      className="btn-review-evidence"
                      onClick={() => {
                        const target = document.getElementById('citizen-evidence-breakdown')
                        if (target) target.scrollIntoView({ behavior: 'smooth' })
                      }}
                    >
                      <Eye size={15} />
                      <span>Review Evidence</span>
                    </button>
                    <span className="conflict-status-notice">
                      Status: Forwarded to Authority Human Review (Report retained)
                    </span>
                  </div>
                </div>
              )}

              {(() => {
  const visualEvidence = submissionResult.currentness?.evidence?.find(
    (item) =>
      item.source === 'IMAGE_CLASSIFICATION' ||
      item.source === 'IMAGE_NORMAL_CLASSIFICATION',
  )

  const details = visualEvidence?.details
  const predictedClass =
    typeof details?.predicted_class === 'string'
      ? details.predicted_class
      : null
  const confidence =
    typeof details?.confidence === 'number' &&
    Number.isFinite(details.confidence)
      ? details.confidence
      : null
  const hasError = details?.error === true

  return visualEvidence && predictedClass && !hasError ? (
    <div className="ai-stat-item">
      <span className="stat-label">AI Visual Prediction</span>
      <strong>
        {predictedClass.charAt(0).toUpperCase() + predictedClass.slice(1)}
      </strong>
      {confidence !== null && (
        <span>
          Model confidence: {(confidence * 100).toFixed(2)}%
        </span>
      )}
      <small>
        Visual evidence only; this does not independently verify an incident.
      </small>
    </div>
  ) : null
})()}

              <div id="citizen-evidence-breakdown" className="ai-preliminary-grid">
                <div className="ai-stat-item">
                  <span className="stat-label">Detected Category</span>
                  <strong>
                    {submissionResult.crisis_analysis?.incident_type
                      ? submissionResult.crisis_analysis.incident_type
                      : submissionResult.crisis_analysis?.is_crisis === false
                      ? 'Analysis unavailable (Non-crisis text)'
                      : 'Analysis unavailable'}
                  </strong>
                </div>

                <div className="ai-stat-item">
                  <span className="stat-label">Assessed Severity</span>
                  {submissionResult.crisis_analysis?.severity ? (
                    <span
                      className={`badge badge-${submissionResult.crisis_analysis.severity.toLowerCase()}`}
                    >
                      {submissionResult.crisis_analysis.severity}
                    </span>
                  ) : (
                    <span className="badge badge-pending">
                      Analysis unavailable
                    </span>
                  )}
                </div>

                <div className="ai-stat-item">
                  <span className="stat-label">Currentness Verification</span>
                  {submissionResult.currentness?.currentness ? (
                    <span
                      className={`badge badge-${submissionResult.currentness.currentness.toLowerCase()}`}
                    >
                      {submissionResult.currentness.currentness}
                    </span>
                  ) : (
                    <span className="badge badge-pending">
                      Pending review
                    </span>
                  )}
                </div>
              </div>

              <div className="success-actions">
                <button
                  type="button"
                  className="btn-primary-glow"
                  onClick={() => {
                    if (submissionResult.incident_id) {
                      setSearchId(submissionResult.incident_id)
                      setActiveTab('status')
                      void handleTrackIncident(submissionResult.incident_id)
                    }
                  }}
                >
                  <Search size={16} />
                  <span>Track Review &amp; Dispatch Status</span>
                </button>

                <button
                  type="button"
                  className="btn-glass"
                  onClick={() => {
                    setSubmissionResult(null)
                  }}
                >
                  <FilePlus2Icon size={16} />
                  <span>Submit Another Report</span>
                </button>
              </div>
            </div>
          ) : (
            /* REPORT SUBMISSION FORM */
            <form className="report-form-card" onSubmit={handleSubmitReport}>
              <div className="form-card-header">
                <div>
                  <h2>Report an Emergency Incident</h2>
                  <p>
                    Provide as much specific information as possible. AI will
                    assist in extracting location, required assistance, and
                    severity.
                  </p>
                </div>
                <div className="form-badge-live">
                  <Radio size={14} />
                  <span>Live Dispatch Feed</span>
                </div>
              </div>

              {submitError && (
                <div className="form-error-alert" role="alert">
                  <AlertCircle size={18} />
                  <div>
                    <strong>Submission Failed</strong>
                    <p>{submitError}</p>
                  </div>
                </div>
              )}

              {/* Description Field */}
              <div className="form-group">
                <label htmlFor="incident-desc">
                  Incident Description <span className="required-star">*</span>
                </label>
                <textarea
                  id="incident-desc"
                  rows={4}
                  className="form-textarea"
                  placeholder="Describe what happened: e.g. 'Flash flood in Assam near NH-37, water level rising fast, several families trapped on roof needing rescue boats and food.'"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required={!mediaFile}
                />
                <span className="form-hint">
                  Include visible hazards, number of people injured or stranded, and urgent requirements.
                </span>
              </div>

              {/* Category Selector */}
              <div className="form-group">
                <label htmlFor="incident-cat">Incident Category (Optional)</label>
                <select
                  id="incident-cat"
                  className="form-select"
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                >
                  <option value="">Auto-Detect via AI</option>
                  <option value="Fire">Fire / Wildfire</option>
                  <option value="Flood">Flood / Flash Flood</option>
                  <option value="Building Collapse">Building Collapse</option>
                  <option value="Road Accident">Road Accident / Highway Collision</option>
                  <option value="Earthquake">Earthquake</option>
                  <option value="Cyclone">Cyclone / Severe Storm</option>
                  <option value="Landslide">Landslide</option>
                  <option value="Explosion">Explosion / Blast</option>
                  <option value="Other">Other Environmental Crisis</option>
                </select>
              </div>

              {/* Location Input with Search, Indian Cities support & Device GPS */}
              <div className="form-group">
                <LocationSearchPicker
                  selectedLocation={selectedLocation}
                  onLocationSelect={(loc: LocationInfo | null) => {
                    setSelectedLocation(loc)
                    if (loc) {
                      setLocationName(loc.text || '')
                      if (loc.latitude != null && loc.longitude != null) {
                        setDeviceCoords({ lat: loc.latitude, lon: loc.longitude })
                      }
                    } else {
                      setLocationName('')
                      setDeviceCoords(null)
                    }
                  }}
                />
              </div>

              {/* Multimodal Upload & Audio Recording */}
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label style={{ margin: 0 }}>Media Evidence (Photo, Video, or Voice Audio)</label>
                  {!mediaFile && (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        className={`btn-mode-toggle ${mediaMode === 'upload' ? 'active' : ''}`}
                        onClick={() => setMediaMode('upload')}
                        style={{
                          background: mediaMode === 'upload' ? 'var(--palette-camel)' : 'rgba(191, 141, 98, 0.15)',
                          color: mediaMode === 'upload' ? '#ffffff' : 'var(--palette-sandy-clay)',
                          border: '1px solid var(--border-medium)',
                          borderRadius: '6px',
                          padding: '4px 10px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Upload File
                      </button>
                      <button
                        type="button"
                        className={`btn-mode-toggle ${mediaMode === 'record' ? 'active' : ''}`}
                        onClick={() => setMediaMode('record')}
                        style={{
                          background: mediaMode === 'record' ? 'var(--palette-camel)' : 'rgba(191, 141, 98, 0.15)',
                          color: mediaMode === 'record' ? '#ffffff' : 'var(--palette-sandy-clay)',
                          border: '1px solid var(--border-medium)',
                          borderRadius: '6px',
                          padding: '4px 10px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Record Voice Live
                      </button>
                    </div>
                  )}
                </div>

                {!mediaFile ? (
                  mediaMode === 'record' ? (
                    <AudioRecorder
                      onAudioReady={(file: File | null) => {
                        setMediaFile(file)
                        setMediaType(file ? 'audio' : null)
                      }}
                    />
                  ) : (
                    <div className="media-dropzone">
                      <input
                        type="file"
                        id="media-file-input"
                        className="hidden-file-input"
                        accept="image/*,video/*,audio/*"
                        onChange={handleMediaUpload}
                      />
                      <label htmlFor="media-file-input" className="dropzone-label">
                        <div className="dropzone-icons">
                          <ImageIcon size={22} />
                          <Video size={22} />
                          <Mic size={22} />
                        </div>
                        <strong>Upload Media Evidence</strong>
                        <span>
                          Supports Images (OCR scan), Videos (Frame analysis), or Voice notes (Whisper transcription)
                        </span>
                      </label>
                    </div>
                  )
                ) : (
                  <div className="media-attached-card">
                    <div className="media-file-meta">
                      {mediaType === 'image' && <ImageIcon size={20} />}
                      {mediaType === 'video' && <Video size={20} />}
                      {mediaType === 'audio' && <Mic size={20} />}
                      <div>
                        <strong>{mediaFile.name}</strong>
                        <span>
                          {(mediaFile.size / (1024 * 1024)).toFixed(2)} MB •{' '}
                          {mediaType?.toUpperCase()} Attachment
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="remove-media-btn"
                      onClick={() => {
                        setMediaFile(null)
                        setMediaType(null)
                      }}
                      title="Remove attachment"
                    >
                      <X size={16} />
                    </button>
                  </div>
                )}
              </div>

              {/* Submit Buttons */}
              <div className="form-actions-row">
                <button
                  type="submit"
                  className="btn-primary-glow full-width"
                  disabled={submitting}
                >
                  {submitting ? (
                    <>
                      <RefreshCw size={18} className="spinner" />
                      <span>Transmitting &amp; AI Processing…</span>
                    </>
                  ) : (
                    <>
                      <Send size={18} />
                      <span>Submit Emergency Report</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* VIEW: TRACK INCIDENT STATUS */}
      {activeTab === 'status' && (
        <div className="citizen-status-view">
          <div className="status-lookup-header">
            <div>
              <h2>Track Report Reference</h2>
              <p>
                Enter your Incident Reference ID to follow real-time verification
                and response status.
              </p>
            </div>

            {/* Reference Search Bar */}
            <form
              className="status-search-form"
              onSubmit={(e) => {
                e.preventDefault()
                void handleTrackIncident()
              }}
            >
              <input
                type="text"
                className="search-input"
                placeholder="Enter Reference (e.g. INC-4919...)"
                value={searchId}
                onChange={(e) => setSearchId(e.target.value)}
                required
              />
              <button
                type="submit"
                className="search-submit-btn"
                disabled={trackingLoading}
              >
                {trackingLoading ? (
                  <RefreshCw size={16} className="spinner" />
                ) : (
                  <Search size={16} />
                )}
                <span>Search</span>
              </button>
            </form>
          </div>

          {/* Stored Reports Quick Chips */}
          {((currentUser && myIncidents.length > 0) || (!currentUser && savedReports.length > 0)) && (
            <div className="saved-chips-bar">
              <span className="chips-label">Your Submissions:</span>
              {(currentUser && myIncidents.length > 0
                ? myIncidents
                    .filter((inc): inc is Incident & { incident_id: string } => Boolean(inc.incident_id))
                    .map((inc) => ({
                      incident_id: inc.incident_id,
                      status: inc.verification_status,
                    }))
                : savedReports.map((r) => ({
                    incident_id: r.incident_id,
                    status: undefined,
                  }))
              ).map((item) => (
                <button
                  key={item.incident_id}
                  type="button"
                  className={`chip-button ${searchId === item.incident_id ? 'active' : ''}`}
                  onClick={() => {
                    setSearchId(item.incident_id)
                    void handleTrackIncident(item.incident_id)
                  }}
                >
                  <span>{item.incident_id.slice(0, 12)}…</span>
                  {item.status && (
                    <span style={{ fontSize: '10px', opacity: 0.8, marginLeft: '4px' }}>
                      ({item.status})
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}

          {trackingError && (
            <div className="form-error-alert" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={18} />
                <strong>Lookup Notice</strong>
              </div>
              <p style={{ margin: '4px 0 0 0' }}>{trackingError}</p>
              {!currentUser && (
                <div style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px solid rgba(255, 255, 255, 0.1)', width: '100%' }}>
                  <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Submitted this incident? Citizen incident records are private. Sign in with your registered account to view your submission details.
                  </p>
                  <button
                    type="button"
                    className="citizen-auth-btn"
                    style={{ padding: '6px 12px', fontSize: '12px' }}
                    onClick={() => {
                      setAuthModalMessage('Sign in to view your submitted incident.')
                      setShowAuthModal(true)
                    }}
                  >
                    <LogIn size={13} />
                    <span>Sign In to View Private Incident</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {trackedIncident && (
            <div className="tracked-incident-detail-card">
              <div className="tracked-header">
                <div>
                  <span className="tracked-id-badge">
                    {trackedIncident.incident_id}
                  </span>
                  <h2>{trackedIncident.incident_type || 'Crisis Incident'}</h2>
                </div>

                <div className="tracked-status-badges">
                  <span
                    className={`badge badge-${(
                      trackedIncident.severity || 'LOW'
                    ).toLowerCase()}`}
                  >
                    Severity: {trackedIncident.severity || 'UNKNOWN'}
                  </span>

                  <span
                    className={`badge badge-${(
                      trackedIncident.verification_status || 'PENDING'
                    ).toLowerCase()}`}
                  >
                    Verification:{' '}
                    {trackedIncident.verification_status?.replaceAll('_', ' ') ||
                      'PENDING'}
                  </span>
                </div>
              </div>

              {/* Contradictory Evidence Notice if present */}
              {(trackedIncident.has_conflict ||
                (trackedIncident.conflicts_detected &&
                  trackedIncident.conflicts_detected.length > 0)) && (
                <div className="citizen-conflict-card" style={{ marginBottom: '16px' }}>
                  <div className="citizen-conflict-top">
                    <AlertTriangle size={20} className="conflict-icon-warning" />
                    <div>
                      <strong className="conflict-title">
                        CONFLICTING EVIDENCE DETECTED — HUMAN REVIEW REQUIRED
                      </strong>
                      <p className="conflict-subtitle">
                        The description and media uploaded for this incident contain conflicting signals.
                        The system requires human reviewer verification before confirmation.
                      </p>
                    </div>
                  </div>
                  {trackedIncident.conflicts_detected &&
                    trackedIncident.conflicts_detected.length > 0 && (
                      <div className="conflict-sources-box">
                        <ul>
                          {trackedIncident.conflicts_detected.map((conf, cIdx) => (
                            <li key={cIdx}>{conf}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                </div>
              )}

              {/* Status explanation notice */}
              <div className="verification-meaning-banner">
                {trackedIncident.verification_status === 'VERIFIED' && (
                  <div className="status-banner-content verified">
                    <CheckCircle2 size={18} />
                    <span>
                      Verified by emergency authority. Response planning is active.
                    </span>
                  </div>
                )}
                {trackedIncident.verification_status === 'PENDING' && (
                  <div className="status-banner-content pending">
                    <Clock size={18} />
                    <span>
                      Under review by response coordinators. Multimodal evidence is being validated.
                    </span>
                  </div>
                )}
                {trackedIncident.verification_status === 'NEEDS_MORE_INFO' && (
                  <div className="status-banner-content warning">
                    <AlertCircle size={18} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontWeight: 600 }}>
                        Authorities requested additional information:
                      </span>
                      {trackedIncident.admin_feedback ? (
                        <p style={{ margin: 0, fontStyle: 'italic', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
                          "{trackedIncident.admin_feedback}"
                        </p>
                      ) : (
                        <span>Please provide an update or additional details below.</span>
                      )}
                    </div>
                  </div>
                )}
                {trackedIncident.verification_status === 'REJECTED' && (
                  <div className="status-banner-content rejected">
                    <X size={18} />
                    <span>
                      Incident rejected or marked duplicate by authorities.
                    </span>
                  </div>
                )}
              </div>

              {/* Core Details Grid */}
              <div className="detail-meta-grid">
                <div className="meta-block">
                  <span className="meta-label">Incident Location</span>
                  <strong>
                    {trackedIncident.location_name || 'Location text unavailable'}
                  </strong>
                  {trackedIncident.latitude != null &&
                    trackedIncident.longitude != null && (
                      <span className="meta-sub">
                        Coordinates: {trackedIncident.latitude.toFixed(4)},{' '}
                        {trackedIncident.longitude.toFixed(4)}
                      </span>
                    )}
                </div>

                <div className="meta-block">
                  <span className="meta-label">Operational Status</span>
                  <strong>{trackedIncident.status || 'OPEN'}</strong>
                </div>

                <div className="meta-block">
                  <span className="meta-label">Identified Assistance Needs</span>
                  <div className="needs-tag-row">
                    {(trackedIncident.needs || []).length > 0 ? (
                      (trackedIncident.needs || []).map((n) => (
                        <span key={n} className="need-tag">
                          {n.replaceAll('_', ' ')}
                        </span>
                      ))
                    ) : (
                      <span className="text-muted">None specified</span>
                    )}
                  </div>
                </div>

                <div className="meta-block">
                  <span className="meta-label">Reports Consolidated</span>
                  <strong>{trackedIncident.report_count ?? 1} citizen reports</strong>
                </div>
              </div>

              {/* Citizen Feedback / Update Input */}
              <div className="incident-feedback-section">
                <h3>Provide Situation Update or Additional Needs</h3>
                <p>
                  Has the situation changed, spread, or are more people trapped?
                  Submitting updates automatically triggers AI escalation analysis.
                </p>

                <textarea
                  className="form-textarea"
                  rows={3}
                  placeholder="e.g. 'Water is entering the ground floor, 5 more people stranded, urgent ambulance and food needed.'"
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                />

                <div className="feedback-submit-row">
                  <button
                    type="button"
                    className="btn-primary-glow"
                    onClick={() => void handleSubmitFeedback()}
                    disabled={feedbackSubmitting || !feedbackText.trim()}
                  >
                    {feedbackSubmitting ? (
                      <>
                        <RefreshCw size={15} className="spinner" />
                        <span>Sending Update…</span>
                      </>
                    ) : (
                      <>
                        <Send size={15} />
                        <span>Submit Live Feedback</span>
                      </>
                    )}
                  </button>
                </div>

                {feedbackMessage && (
                  <div className="feedback-result-banner">
                    <Info size={16} />
                    <span>{feedbackMessage}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Citizen Authentication Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={(user) => {
          setCurrentUser(user)
          setShowAuthModal(false)
          if (searchId.trim()) {
            void handleTrackIncident(searchId.trim())
          }
        }}
        message={authModalMessage}
      />
    </div>
  )
}

function FilePlus2Icon(props: { size?: number }) {
  return (
    <svg
      width={props.size || 20}
      height={props.size || 20}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M9 15h6" />
      <path d="M12 12v6" />
    </svg>
  )
}
