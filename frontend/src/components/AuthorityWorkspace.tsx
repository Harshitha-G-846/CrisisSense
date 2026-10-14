import React, { useState, useEffect, useMemo } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bot,
  Building2,
  CheckCircle2,
  Clock,
  Compass,
  Eye,
  HelpCircle,
  Inbox,
  Layers,
  MapPin,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Truck,
  User,
  X,
  XCircle,
} from 'lucide-react'
import { ErrorBoundary } from './ErrorBoundary'
import {
  api,
  type Incident,
  type IncidentDetail,
  type VerificationDecision,
  type RevisedPlanResponse,
  type AuthorizeResponse,
} from '../services/api'
import { InteractiveMap } from './Map'

interface AuthorityWorkspaceProps {
  initialTab?: 'incoming' | 'verified' | 'rejected' | 'all' | 'map'
  onSelectMapIncident?: (incident: Incident) => void
}

const SEVERITY_WEIGHTS: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
  UNKNOWN: 0,
}

export const AuthorityWorkspace: React.FC<AuthorityWorkspaceProps> = ({
  initialTab = 'incoming',
}) => {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null)
  const [incidentDetail, setIncidentDetail] = useState<IncidentDetail | null>(null)
  const [loadingList, setLoadingList] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [listError, setListError] = useState<string | null>(null)

  // Section Tab
  const [activeQueue, setActiveQueue] = useState<
    'incoming' | 'verified' | 'rejected' | 'all' | 'map'
  >(initialTab)

  // Sorting: 'severity' | 'recent'
  const [sortBy, setSortBy] = useState<'severity' | 'recent'>('severity')

  // Search filter
  const [searchQuery, setSearchQuery] = useState('')

  // Verification Form State
  const [verificationReason, setVerificationReason] = useState('')
  const [verificationSubmitting, setVerificationSubmitting] = useState(false)
  const [verificationBanner, setVerificationBanner] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)

  // Replan & Authorization State
  const [replanSubmitting, setReplanSubmitting] = useState(false)
  const [responsePlan, setResponsePlan] = useState<RevisedPlanResponse | null>(null)
  const [authSubmitting, setAuthSubmitting] = useState(false)
  const [authResult, setAuthResult] = useState<AuthorizeResponse | null>(null)
  const [planError, setPlanError] = useState<string | null>(null)
  const [showRawJson, setShowRawJson] = useState(false)

  // Situational Feedback State
  const [feedbackInput, setFeedbackInput] = useState('')
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false)
  const [feedbackResult, setFeedbackResult] = useState<string | null>(null)

  // Incident Deletion State
  const [incidentToDelete, setIncidentToDelete] = useState<Incident | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [actionNotice, setActionNotice] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)

  // Handle Permanent Incident Deletion
  const handleConfirmDelete = async () => {
    if (!incidentToDelete?.incident_id || isDeleting) return
    const targetId = incidentToDelete.incident_id
    setIsDeleting(true)
    setActionNotice(null)

    try {
      await api.deleteIncident(targetId)

      // Immediately remove from state so list, queue counts, and map markers update instantly
      setIncidents((prev) => prev.filter((inc) => inc.incident_id !== targetId))

      // If the deleted incident was currently selected in the inspector, clear selection
      if (selectedIncident?.incident_id === targetId) {
        setSelectedIncident(null)
        setIncidentDetail(null)
        setResponsePlan(null)
        setAuthResult(null)
      }

      setActionNotice({
        type: 'success',
        text: `Incident ${targetId} was permanently deleted.`,
      })
      setIncidentToDelete(null)

      // Background reload from API to ensure full synchronization with backend
      void loadIncidents()
    } catch (err) {
      setActionNotice({
        type: 'error',
        text:
          err instanceof Error
            ? `Failed to delete incident: ${err.message}`
            : 'Failed to delete incident.',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  useEffect(() => {
    setActiveQueue(initialTab)
  }, [initialTab])

  // Load Incidents List
  const loadIncidents = async () => {
    setLoadingList(true)
    setListError(null)
    try {
      const data = await api.listIncidents()
      setIncidents(data)

      // Maintain selection if still present
      if (selectedIncident?.incident_id) {
        const found = data.find(
          (item) => item.incident_id === selectedIncident.incident_id,
        )
        if (found) {
          setSelectedIncident(found)
        }
      }
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : 'Unable to load incidents.',
      )
    } finally {
      setLoadingList(false)
    }
  }

  useEffect(() => {
    void loadIncidents()
  }, [])

  // Load Full Incident Details
  useEffect(() => {
    if (!selectedIncident?.incident_id) {
      setIncidentDetail(null)
      setResponsePlan(null)
      setAuthResult(null)
      setPlanError(null)
      setVerificationBanner(null)
      setFeedbackResult(null)
      return
    }

    let isMounted = true
    setLoadingDetail(true)
    setPlanError(null)
    setVerificationBanner(null)
    setFeedbackResult(null)

    api
      .getIncident(selectedIncident.incident_id)
      .then((detail) => {
        if (isMounted) {
          setIncidentDetail(detail)
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.warn('Failed to load full incident detail:', err)
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoadingDetail(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [selectedIncident?.incident_id])

  // Filter & Queue Segregation
  const filteredIncidents = useMemo(() => {
    return incidents.filter((item) => {
      const status = (item.verification_status || 'PENDING').toUpperCase()

      // Section filtering
      if (activeQueue === 'incoming') {
        if (status !== 'PENDING' && status !== 'NEEDS_MORE_INFO') return false
      } else if (activeQueue === 'verified') {
        if (status !== 'VERIFIED') return false
      } else if (activeQueue === 'rejected') {
        if (status !== 'REJECTED') return false
      }

      // Search Query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase()
        const idMatch = (item.incident_id || '').toLowerCase().includes(query)
        const typeMatch = (item.incident_type || '').toLowerCase().includes(query)
        const locMatch = (item.location_name || '').toLowerCase().includes(query)
        if (!idMatch && !typeMatch && !locMatch) return false
      }

      return true
    })
  }, [incidents, activeQueue, searchQuery])

  // Strict Severity Sorting
  const sortedIncidents = useMemo(() => {
    const list = [...filteredIncidents]

    if (sortBy === 'severity') {
      list.sort((a, b) => {
        const weightA =
          SEVERITY_WEIGHTS[(a.severity || 'UNKNOWN').toUpperCase()] ?? 0
        const weightB =
          SEVERITY_WEIGHTS[(b.severity || 'UNKNOWN').toUpperCase()] ?? 0

        if (weightB !== weightA) {
          return weightB - weightA // Critical -> High -> Medium -> Low -> Unknown
        }

        // Tie-breaker: creation timestamp descending
        const dateA = a.created_at ? new Date(a.created_at).getTime() : 0
        const dateB = b.created_at ? new Date(b.created_at).getTime() : 0
        return dateB - dateA
      })
    } else {
      list.sort((a, b) => {
        const dateA = a.created_at ? new Date(a.created_at).getTime() : 0
        const dateB = b.created_at ? new Date(b.created_at).getTime() : 0
        return dateB - dateA
      })
    }

    return list
  }, [filteredIncidents, sortBy])

  // Counts for tabs
  const queueCounts = useMemo(() => {
    return {
      incoming: incidents.filter(
        (i) =>
          i.verification_status === 'PENDING' ||
          i.verification_status === 'NEEDS_MORE_INFO',
      ).length,
      verified: incidents.filter((i) => i.verification_status === 'VERIFIED')
        .length,
      rejected: incidents.filter((i) => i.verification_status === 'REJECTED')
        .length,
      all: incidents.length,
    }
  }, [incidents])

  // Handle Human Verification
  const handleVerify = async (decision: VerificationDecision) => {
    if (!selectedIncident?.incident_id) return

    const actionText =
      decision === 'APPROVE'
        ? 'VERIFY and APPROVE'
        : decision === 'REJECT'
        ? 'REJECT'
        : 'REQUEST MORE INFORMATION for'

    const confirm = window.confirm(
      `Confirm decision: Are you sure you want to ${actionText} Incident #${selectedIncident.incident_id}?`,
    )
    if (!confirm) return

    setVerificationSubmitting(true)
    setVerificationBanner(null)

    try {
      const res = await api.verifyIncident(
        selectedIncident.incident_id,
        decision,
        verificationReason.trim() || undefined,
      )

      setVerificationBanner({
        type: 'success',
        text: res.message || 'Verification decision recorded.',
      })
      setVerificationReason('')

      // Reload list and details
      await loadIncidents()
      if (selectedIncident.incident_id) {
        const updated = await api.getIncident(selectedIncident.incident_id)
        setIncidentDetail(updated)
      }
    } catch (err) {
      setVerificationBanner({
        type: 'error',
        text:
          err instanceof Error
            ? `Verification failed: ${err.message}`
            : 'Verification action failed.',
      })
    } finally {
      setVerificationSubmitting(false)
    }
  }

  // Handle Response Replan
  const handleReplan = async () => {
    if (!selectedIncident?.incident_id) return

    // Guard: Rejected incidents cannot be planned
    if (selectedIncident.verification_status === 'REJECTED') {
      setPlanError('Incident is rejected. It is not eligible for response planning.')
      return
    }

    setReplanSubmitting(true)
    setPlanError(null)
    setResponsePlan(null)
    setAuthResult(null)

    try {
      const plan = await api.replanIncident(selectedIncident.incident_id)
      setResponsePlan(plan)
    } catch (err) {
      setPlanError(
        err instanceof Error ? `Replanning failed: ${err.message}` : 'Failed to generate response plan.',
      )
    } finally {
      setReplanSubmitting(false)
    }
  }

  // Handle Authorization
  const handleAuthorize = async () => {
    if (!selectedIncident?.incident_id) return

    // Guard: verification prerequisite
    if (selectedIncident.verification_status !== 'VERIFIED') {
      alert('Incident must be VERIFIED before a response plan can be authorized.')
      return
    }

    const confirm = window.confirm(
      'Explicit Authority Authorization Required:\n\n' +
        'Authorize this response plan?\n\n' +
        'NOTE: This authorizes the operational response plan. Physical resource dispatch will NOT occur automatically without separate dispatch instruction.',
    )
    if (!confirm) return

    setAuthSubmitting(true)
    setPlanError(null)

    try {
      const res = await api.authorizeResponse(selectedIncident.incident_id)
      setAuthResult(res)
      await loadIncidents()
      if (selectedIncident.incident_id) {
        const updated = await api.getIncident(selectedIncident.incident_id)
        setIncidentDetail(updated)
      }
    } catch (err) {
      setPlanError(
        err instanceof Error
          ? `Authorization failed: ${err.message}`
          : 'Failed to authorize plan.',
      )
    } finally {
      setAuthSubmitting(false)
    }
  }

  // Handle Situation Feedback
  const handleFeedback = async () => {
    if (!selectedIncident?.incident_id || !feedbackInput.trim()) return

    setFeedbackSubmitting(true)
    setFeedbackResult(null)

    try {
      const res = await api.submitFeedback(
        selectedIncident.incident_id,
        feedbackInput.trim(),
      )
      setFeedbackResult(
        res.situation_changed
          ? `Situation Escalation Detected! Additional needs identified: [${res.detected_needs.join(', ')}]. Replanning is required.`
          : 'Feedback logged. No critical situation change detected.',
      )
      setFeedbackInput('')
      await loadIncidents()
      if (selectedIncident.incident_id) {
        const updated = await api.getIncident(selectedIncident.incident_id)
        setIncidentDetail(updated)
      }
    } catch (err) {
      setFeedbackResult(
        err instanceof Error ? `Feedback error: ${err.message}` : 'Failed to process feedback.',
      )
    } finally {
      setFeedbackSubmitting(false)
    }
  }

  const isSelectedRejected =
    selectedIncident?.verification_status === 'REJECTED'
  const isSelectedVerified =
    selectedIncident?.verification_status === 'VERIFIED'

  return (
    <div className="authority-workspace-layout">
      {/* Workspace Top Control Bar */}
      <header className="authority-topbar">
        <div className="workspace-branding">
          <ShieldCheck size={22} className="brand-shield" />
          <div>
            <h1>Authority Operations Hub</h1>
            <p>Multimodal Intelligence • Human Verification • Response Orchestration</p>
          </div>
        </div>

        <div className="topbar-actions">
          <button
            type="button"
            className="action-btn-glass"
            onClick={() => void loadIncidents()}
            disabled={loadingList}
            title="Refresh Incidents from Backend"
          >
            <RefreshCw size={15} className={loadingList ? 'spinner' : ''} />
            <span>{loadingList ? 'Refreshing…' : 'Sync Feed'}</span>
          </button>
        </div>
      </header>

      {/* Action Notification Banner */}
      {actionNotice && (
        <div className={`workspace-action-banner ${actionNotice.type}`} role="status">
          <div className="action-banner-content">
            {actionNotice.type === 'success' ? (
              <CheckCircle2 size={16} />
            ) : (
              <AlertCircle size={16} />
            )}
            <span>{actionNotice.text}</span>
          </div>
          <button
            type="button"
            className="action-banner-close"
            onClick={() => setActionNotice(null)}
            aria-label="Dismiss message"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Queue Tabs & Sort Toolbar */}
      <div className="authority-queue-nav">
        <div className="queue-tabs-group">
          <button
            type="button"
            className={`queue-tab ${activeQueue === 'incoming' ? 'active' : ''}`}
            onClick={() => setActiveQueue('incoming')}
          >
            <Inbox size={16} />
            <span>Incoming Queue</span>
            <span className="queue-badge alert">{queueCounts.incoming}</span>
          </button>

          <button
            type="button"
            className={`queue-tab ${activeQueue === 'verified' ? 'active' : ''}`}
            onClick={() => setActiveQueue('verified')}
          >
            <CheckCircle2 size={16} />
            <span>Verified Incidents</span>
            <span className="queue-badge verified">{queueCounts.verified}</span>
          </button>

          <button
            type="button"
            className={`queue-tab ${activeQueue === 'rejected' ? 'active' : ''}`}
            onClick={() => setActiveQueue('rejected')}
          >
            <XCircle size={16} />
            <span>Rejected Records</span>
            <span className="queue-badge rejected">{queueCounts.rejected}</span>
          </button>

          <button
            type="button"
            className={`queue-tab ${activeQueue === 'all' ? 'active' : ''}`}
            onClick={() => setActiveQueue('all')}
          >
            <Layers size={16} />
            <span>All Records</span>
            <span className="queue-badge neutral">{queueCounts.all}</span>
          </button>

          <button
            type="button"
            className={`queue-tab ${activeQueue === 'map' ? 'active' : ''}`}
            onClick={() => setActiveQueue('map')}
          >
            <Compass size={16} />
            <span>Tactical Map</span>
          </button>
        </div>

        {activeQueue !== 'map' && (
          <div className="queue-filters-bar">
            {/* Search filter */}
            <div className="queue-search-box">
              <Search size={14} />
              <input
                type="text"
                placeholder="Filter by ID, category, or location..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="clear-search"
                >
                  &times;
                </button>
              )}
            </div>

            {/* Severity Sort Toggle */}
            <div className="sort-toggle-group">
              <span className="sort-label">Sort:</span>
              <button
                type="button"
                className={`sort-btn ${sortBy === 'severity' ? 'active' : ''}`}
                onClick={() => setSortBy('severity')}
              >
                Severity First
              </button>
              <button
                type="button"
                className={`sort-btn ${sortBy === 'recent' ? 'active' : ''}`}
                onClick={() => setSortBy('recent')}
              >
                Most Recent
              </button>
            </div>
          </div>
        )}
      </div>

      {/* FULL MAP VIEW TAB */}
      {activeQueue === 'map' ? (
        <div className="authority-map-view-container">
          <InteractiveMap
            incidents={incidents}
            selectedIncident={selectedIncident}
            onSelectIncident={(inc) => {
              setSelectedIncident(inc)
              // switch to incoming or all to inspect
              if (inc.verification_status === 'VERIFIED') {
                setActiveQueue('verified')
              } else if (inc.verification_status === 'REJECTED') {
                setActiveQueue('rejected')
              } else {
                setActiveQueue('incoming')
              }
            }}
          />
        </div>
      ) : (
        /* MAIN SPLIT WORKSPACE: INCIDENT LIST + INSPECTOR */
        <div className="authority-split-workspace">
          {/* LEFT: INCIDENTS QUEUE LIST */}
          <aside className="incidents-sidebar-panel">
            <div className="sidebar-header-row">
              <div className="sidebar-heading">
                <h2>
                  {activeQueue === 'incoming' && 'Incoming Incidents'}
                  {activeQueue === 'verified' && 'Verified Queue'}
                  {activeQueue === 'rejected' && 'Rejected Incidents'}
                  {activeQueue === 'all' && 'Consolidated Incidents'}
                </h2>
                <span className="sidebar-count">
                  {sortedIncidents.length} records
                </span>
              </div>
            </div>

            {listError && (
              <div className="sidebar-alert error">
                <AlertCircle size={15} />
                <span>{listError}</span>
              </div>
            )}

            {loadingList && sortedIncidents.length === 0 && (
              <div className="sidebar-loading">
                <RefreshCw size={18} className="spinner" />
                <span>Loading incident feed…</span>
              </div>
            )}

            {!loadingList && sortedIncidents.length === 0 && (
              <div className="sidebar-empty">
                <Inbox size={28} />
                <h3>No Incidents in this Queue</h3>
                <p>
                  {activeQueue === 'incoming'
                    ? 'All pending incidents have been processed.'
                    : 'No records match the current filter criteria.'}
                </p>
              </div>
            )}

            <div className="incident-cards-scroll">
              {sortedIncidents.map((incident) => {
                const isSelected =
                  selectedIncident?.incident_id === incident.incident_id
                const sev = (incident.severity || 'LOW').toUpperCase()
                const ver = (incident.verification_status || 'PENDING').toUpperCase()

                return (
                  <div
                    key={incident.incident_id}
                    className={`incident-card-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedIncident(incident)}
                  >
                    <div className="card-topline">
                      <span className="incident-card-id">
                        {incident.incident_id}
                      </span>
                      <div className="card-topline-right">
                        <span className={`badge badge-${sev.toLowerCase()}`}>
                          {sev}
                        </span>
                        <button
                          type="button"
                          className="btn-delete-incident"
                          title={`Delete incident ${incident.incident_id}`}
                          aria-label={`Delete incident ${incident.incident_id}`}
                          disabled={isDeleting}
                          onClick={(e) => {
                            e.stopPropagation()
                            setIncidentToDelete(incident)
                          }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>

                    <h3 className="incident-card-title">
                      {incident.incident_type || 'Unclassified Crisis'}
                    </h3>

                    <div className="incident-card-location">
                      <MapPin size={13} />
                      <span>{incident.location_name || 'Location unavailable'}</span>
                      {incident.latitude != null && incident.longitude != null && (
                        <span className="coords-dot" title="Coordinates Available">• GPS</span>
                      )}
                    </div>

                    <div className="card-footer-meta">
                      <span className={`ver-badge status-${ver.toLowerCase()}`}>
                        {ver.replaceAll('_', ' ')}
                      </span>
                      {incident.has_conflict && (
                        <span className="conflict-badge-pill" title="Conflicting evidence detected across modalities">
                          <AlertTriangle size={11} />
                          <span>Conflicting Evidence</span>
                        </span>
                      )}
                      <span className="report-badge">
                        {incident.report_count ?? 1} report{incident.report_count === 1 ? '' : 's'}
                      </span>
                      {incident.created_at && (
                        <span className="time-badge">
                          {new Date(incident.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </aside>

          {/* RIGHT: INCIDENT DETAIL INSPECTOR */}
          <main className="incident-inspector-panel">
            <ErrorBoundary fallbackTitle="Incident Inspector Interrupted">
              {!selectedIncident ? (
              <div className="inspector-placeholder">
                <Compass size={40} />
                <h2>Select an Incident from Queue</h2>
                <p>
                  Choose any incident card to inspect its multimodal evidence,
                  NLP classification, human verification decisions, and response
                  recommendations.
                </p>
              </div>
            ) : (
              <div className="inspector-content">
                {/* Header Banner */}
                <header className="inspector-header">
                  <div className="header-titles">
                    <div className="id-copy-row">
                      <span className="inspector-id">
                        {selectedIncident.incident_id}
                      </span>
                      <span
                        className={`badge badge-${(
                          selectedIncident.severity || 'LOW'
                        ).toLowerCase()}`}
                      >
                        {selectedIncident.severity || 'UNKNOWN'} SEVERITY
                      </span>
                      <span
                        className={`badge badge-${(
                          selectedIncident.verification_status || 'PENDING'
                        ).toLowerCase()}`}
                      >
                        {selectedIncident.verification_status?.replaceAll('_', ' ')}
                      </span>
                    </div>
                    <h2>
                      {selectedIncident.incident_type || 'Crisis Incident'}
                    </h2>
                  </div>

                  <div className="header-actions">
                    <button
                      type="button"
                      className="icon-close-btn"
                      onClick={() => setSelectedIncident(null)}
                      title="Deselect Incident"
                    >
                      <X size={18} />
                    </button>
                  </div>
                </header>

                {/* Conflicting Evidence Alert Banner */}
                {(selectedIncident.has_conflict ||
                  incidentDetail?.has_conflict ||
                  (incidentDetail?.conflicts_detected &&
                    incidentDetail.conflicts_detected.length > 0)) && (
                  <div className="inspector-alert-banner conflict-alert-banner">
                    <AlertTriangle size={20} className="conflict-icon" />
                    <div className="conflict-banner-body">
                      <div className="conflict-banner-title">
                        CONFLICTING EVIDENCE DETECTED — HUMAN REVIEW REQUIRED
                      </div>
                      <p className="conflict-banner-desc">
                        The submitted description and uploaded multimodal evidence do not agree.
                        ResQ-Sense does not prioritize text over media when conflicting signals exist;
                        this report requires manual human verification before response planning or dispatch can proceed.
                      </p>
                      {incidentDetail?.conflicts_detected &&
                        incidentDetail.conflicts_detected.length > 0 && (
                          <div className="conflict-details-list">
                            <span className="conflict-details-heading">Conflicting evidence signals:</span>
                            <ul>
                              {incidentDetail.conflicts_detected.map((conf, cIdx) => (
                                <li key={cIdx}>{conf}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      <button
                        type="button"
                        className="btn-review-evidence"
                        onClick={() => {
                          const el = document.getElementById('citizen-evidence-section')
                          if (el) el.scrollIntoView({ behavior: 'smooth' })
                        }}
                      >
                        <Eye size={14} />
                        <span>Review Evidence</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Status Notice / Warnings */}
                {isSelectedRejected && (
                  <div className="inspector-alert-banner danger">
                    <XCircle size={18} />
                    <div>
                      <strong>Incident Rejected by Authority</strong>
                      <p>
                        This incident has been rejected and is not eligible for
                        response planning or resource recommendations under safety
                        protocols.
                      </p>
                    </div>
                  </div>
                )}

                {verificationBanner && (
                  <div
                    className={`inspector-alert-banner ${
                      verificationBanner.type === 'success' ? 'success' : 'danger'
                    }`}
                  >
                    {verificationBanner.type === 'success' ? (
                      <CheckCircle2 size={18} />
                    ) : (
                      <AlertCircle size={18} />
                    )}
                    <span>{verificationBanner.text}</span>
                  </div>
                )}

                {/* Section 1: Overview & Location Coordinates */}
                <section className="inspector-section">
                  <h3 className="section-title">
                    <MapPin size={16} />
                    <span>Location &amp; Spatial Intelligence</span>
                  </h3>

                  <div className="meta-card-grid">
                    <div className="meta-card">
                      <span className="card-lbl">Reported Locality</span>
                      <strong>
                        {selectedIncident.location_name || 'Not provided'}
                      </strong>
                    </div>

                    <div className="meta-card">
                      <span className="card-lbl">GPS Coordinates</span>
                      <strong>
                        {selectedIncident.latitude != null &&
                        selectedIncident.longitude != null
                          ? `${selectedIncident.latitude.toFixed(4)}, ${selectedIncident.longitude.toFixed(4)}`
                          : 'Coordinates unavailable'}
                      </strong>
                    </div>

                    <div className="meta-card">
                      <span className="card-lbl">Operational Lifecycle</span>
                      <strong>{selectedIncident.status || 'OPEN'}</strong>
                    </div>

                    <div className="meta-card">
                      <span className="card-lbl">Response Plan Status</span>
                      <strong>
                        {selectedIncident.response_status || 'NOT_PLANNED'}
                      </strong>
                    </div>
                  </div>
                </section>

                {/* Submitting Citizen Identity Section */}
                <section className="inspector-section submitting-citizen-section">
                  <h3 className="section-title">
                    <User size={16} />
                    <span>Submitting Citizen Identity</span>
                  </h3>

                  <div className="meta-card-grid">
                    <div className="meta-card">
                      <span className="card-lbl">Citizen Name</span>
                      <strong>
                        {incidentDetail?.submitting_citizen?.full_name || 'Anonymous submission'}
                      </strong>
                    </div>

                    <div className="meta-card">
                      <span className="card-lbl">Registered Email</span>
                      <strong>
                        {incidentDetail?.submitting_citizen?.email || 'No linked citizen account'}
                      </strong>
                    </div>

                    <div className="meta-card">
                      <span className="card-lbl">Account Status</span>
                      <div>
                        {incidentDetail?.submitting_citizen?.email && incidentDetail.submitting_citizen.email !== 'No linked citizen account' ? (
                          <span
                            className="badge badge-verified"
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                          >
                            <ShieldCheck size={12} />
                            <span>Authenticated Citizen</span>
                          </span>
                        ) : (
                          <span
                            className="badge badge-pending"
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                          >
                            <HelpCircle size={12} />
                            <span>No linked citizen account</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {incidentDetail?.submitting_citizen?.id && (
                      <div className="meta-card">
                        <span className="card-lbl">Citizen Account ID</span>
                        <code style={{ fontSize: '11px', color: '#818cf8', wordBreak: 'break-all' }}>
                          {incidentDetail.submitting_citizen.id}
                        </code>
                      </div>
                    )}
                  </div>
                </section>

                {/* Section 2: Multimodal Evidence & Reports (from GET /incidents/{id}) */}
                <section id="citizen-evidence-section" className="inspector-section">
                  <h3 className="section-title">
                    <Bot size={16} />
                    <span>Citizen Evidence &amp; Multimodal AI Analysis</span>
                  </h3>

                  {loadingDetail ? (
                    <div className="detail-loading-box">
                      <RefreshCw size={16} className="spinner" />
                      <span>Fetching linked evidence and AI outputs…</span>
                    </div>
                  ) : incidentDetail?.reports && incidentDetail.reports.length > 0 ? (
                    <div className="evidence-reports-list">
                      {incidentDetail.reports.map((rep, idx) => (
                        <div key={rep.report_id || idx} className="evidence-item-card">
                          <div className="evidence-card-top">
                            <span className="report-id-code">
                              Report #{rep.report_id}
                            </span>
                            {rep.received_at && (
                              <span className="report-timestamp">
                                Received:{' '}
                                {new Date(rep.received_at).toLocaleString()}
                              </span>
                            )}
                          </div>

                          <div className="original-text-box">
                            <span className="box-sub">Original Citizen Signal:</span>
                            <p>"{rep.original_text}"</p>
                          </div>

                          {/* NLP Classification Output */}
                          {rep.crisis_analysis && (
                            <div className="ai-sub-analysis">
                              <span className="ai-sub-title">
                                <Sparkles size={14} />
                                NLP Incident Classification
                              </span>
                              <div className="ai-tags-row">
                                <span className="ai-pill">
                                  Crisis:{' '}
                                  {rep.crisis_analysis.is_crisis ? 'YES' : 'NO'} (
                                  {typeof rep.crisis_analysis.crisis_probability ===
                                  'number'
                                    ? `${(
                                        rep.crisis_analysis.crisis_probability *
                                        100
                                      ).toFixed(1)}%`
                                    : 'N/A'}
                                  )
                                </span>
                                <span className="ai-pill">
                                  Info Type:{' '}
                                  {rep.crisis_analysis.information_type || 'General'}
                                </span>
                                <span className="ai-pill">
                                  Assessed Severity:{' '}
                                  {rep.crisis_analysis.severity || 'Unknown'}
                                </span>
                              </div>
                            </div>
                          )}

                          {/* Multimodal Currentness Verification */}
                          {rep.currentness && (
                            <div className="currentness-sub-analysis">
                              <span className="ai-sub-title">
                                <Clock size={14} />
                                Multimodal Currentness Verification
                              </span>
                              <div className="currentness-meta-row">
                                <span
                                  className={`currentness-badge verdict-${(
                                    rep.currentness.currentness || 'CURRENT'
                                  ).toLowerCase()}`}
                                >
                                  Temporal Verdict: {rep.currentness.currentness}
                                </span>
                                <span className="currentness-badge action">
                                  Policy Action: {rep.currentness.action}
                                </span>
                                <span className="currentness-badge confidence">
                                  Confidence:{' '}
                                  {(rep.currentness.confidence * 100).toFixed(0)}%
                                </span>
                              </div>

                              {rep.currentness.conflicts_detected &&
                                rep.currentness.conflicts_detected.length > 0 && (
                                  <div className="conflict-warning-box">
                                    <AlertTriangle size={14} />
                                    <span>
                                      Conflicts Detected:{' '}
                                      {rep.currentness.conflicts_detected.join(', ')}
                                    </span>
                                  </div>
                                )}

                              {rep.currentness.evidence &&
                                rep.currentness.evidence.length > 0 && (
                                  <div className="evidence-provenance-table">
                                    <span className="table-caption">
                                      Evidence Provenance:
                                    </span>
                                    {rep.currentness.evidence.map((ev, evIdx) => (
                                      <div
                                        key={evIdx}
                                        className="provenance-row"
                                      >
                                        <span className="prov-source">
                                          {ev.source}
                                        </span>
                                        <span className="prov-finding">
                                          {ev.finding}
                                        </span>
                                        <span
                                          className={`prov-polarity ${ev.polarity.toLowerCase()}`}
                                        >
                                          {ev.polarity}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="evidence-single-view">
                      <p>
                        Needs:{' '}
                        {(selectedIncident.needs || []).length > 0
                          ? (selectedIncident.needs || []).join(', ')
                          : 'None specified'}
                      </p>
                    </div>
                  )}
                </section>

                {/* Section 3: Human Verification Decision Controls */}
                <section className="inspector-section verification-box">
                  <h3 className="section-title">
                    <ShieldCheck size={16} />
                    <span>Human Verification Decision</span>
                  </h3>
                  <p className="section-desc">
                    AI recommends classification and assesses evidence. An
                    authorized human commander makes the final verification
                    decision.
                  </p>

                  <div className="verification-notes-group">
                    <label htmlFor="auth-reason">
                      Operational Rationale / Commander Notes (Optional)
                    </label>
                    <textarea
                      id="auth-reason"
                      rows={2}
                      className="form-textarea"
                      placeholder="Add justification for approval, specific items required for info request, or grounds for rejection..."
                      value={verificationReason}
                      onChange={(e) => setVerificationReason(e.target.value)}
                    />
                  </div>

                  <div className="verification-btn-group">
                    <button
                      type="button"
                      className="btn-verify approve"
                      disabled={verificationSubmitting}
                      onClick={() => void handleVerify('APPROVE')}
                    >
                      <CheckCircle2 size={16} />
                      <span>Verify Incident (Approve)</span>
                    </button>

                    <button
                      type="button"
                      className="btn-verify info"
                      disabled={verificationSubmitting}
                      onClick={() => void handleVerify('NEED_MORE_INFORMATION')}
                    >
                      <HelpCircle size={16} />
                      <span>Request More Information</span>
                    </button>

                    <button
                      type="button"
                      className="btn-verify reject"
                      disabled={verificationSubmitting}
                      onClick={() => void handleVerify('REJECT')}
                    >
                      <XCircle size={16} />
                      <span>Reject Incident</span>
                    </button>
                  </div>
                </section>

                {/* Section 4: Situational Escalation & Feedback */}
                <section className="inspector-section">
                  <h3 className="section-title">
                    <AlertTriangle size={16} />
                    <span>Situational Update &amp; Escalation Feedback</span>
                  </h3>
                  <p className="section-desc">
                    Record field updates or citizen feedback. Escalation keywords
                    (e.g., "spreading", "trapped", "water") dynamically update
                    incident needs and flag replanning requirements.
                  </p>

                  <div className="feedback-form-inline">
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g. 'Fire spreading to adjacent warehouse, 3 more people trapped, medical and water tankers required'"
                      value={feedbackInput}
                      onChange={(e) => setFeedbackInput(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn-primary-glow"
                      onClick={() => void handleFeedback()}
                      disabled={feedbackSubmitting || !feedbackInput.trim()}
                    >
                      {feedbackSubmitting ? (
                        <RefreshCw size={15} className="spinner" />
                      ) : (
                        <ArrowRight size={15} />
                      )}
                      <span>Analyze Update</span>
                    </button>
                  </div>

                  {feedbackResult && (
                    <div className="feedback-result-note">
                      <Sparkles size={14} />
                      <span>{feedbackResult}</span>
                    </div>
                  )}
                </section>

                {/* Section 5: Response Planning & Authorization */}
                <section className="inspector-section response-plan-box">
                  <h3 className="section-title">
                    <Truck size={16} />
                    <span>Response Planning &amp; Explicit Authorization</span>
                  </h3>
                  <p className="section-desc">
                    Generate resource candidate recommendations using spatial
                    proximity and department routing rules. Response plans
                    require explicit human commander authorization before deployment.
                  </p>

                  {isSelectedRejected ? (
                    <div className="rejected-guard-box">
                      <XCircle size={16} />
                      <span>
                        Response planning disabled: Incident is marked REJECTED.
                        (Backend policy: "Incident is not eligible for recommendations")
                      </span>
                    </div>
                  ) : (
                    <div className="response-actions-row">
                      <button
                        type="button"
                        className="btn-primary-glow"
                        onClick={() => void handleReplan()}
                        disabled={replanSubmitting}
                      >
                        {replanSubmitting ? (
                          <>
                            <RefreshCw size={16} className="spinner" />
                            <span>Routing Resources &amp; Computing Plan…</span>
                          </>
                        ) : (
                          <>
                            <Compass size={16} />
                            <span>
                              {responsePlan ? 'Replan Response' : 'Generate Response Plan'}
                            </span>
                          </>
                        )}
                      </button>

                      <button
                        type="button"
                        className={`btn-authorize ${
                          !isSelectedVerified ? 'disabled' : ''
                        }`}
                        onClick={() => void handleAuthorize()}
                        disabled={
                          authSubmitting ||
                          !isSelectedVerified ||
                          !responsePlan ||
                          selectedIncident.response_status === 'AUTHORIZED'
                        }
                        title={
                          !isSelectedVerified
                            ? 'Incident must be VERIFIED before authorization'
                            : 'Authorize Response Plan'
                        }
                      >
                        {authSubmitting ? (
                          <>
                            <RefreshCw size={16} className="spinner" />
                            <span>Authorizing Plan…</span>
                          </>
                        ) : selectedIncident.response_status === 'AUTHORIZED' ? (
                          <>
                            <CheckCircle2 size={16} />
                            <span>Response Plan Authorized</span>
                          </>
                        ) : (
                          <>
                            <ShieldCheck size={16} />
                            <span>Authorize Response Plan</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}

                  {planError && (
                    <div className="plan-error-alert">
                      <AlertCircle size={15} />
                      <span>{planError}</span>
                    </div>
                  )}

                  {authResult && (
                    <div className="auth-success-card">
                      <div className="auth-card-top">
                        <CheckCircle2 size={18} />
                        <strong>Authorization Recorded Successfully</strong>
                      </div>
                      <p>{authResult.message}</p>
                      <small className="auth-note">
                        Human authority approved response plan. No automatic resource
                        dispatch was triggered.
                      </small>
                    </div>
                  )}

                  {/* Planning Loading Indicator */}
                  {replanSubmitting && (
                    <div className="detail-loading-box">
                      <RefreshCw size={16} className="spinner" />
                      <span>Computing resource candidates and emergency department routing…</span>
                    </div>
                  )}

                  {/* READABLE RESPONSE PLAN PRESENTATION */}
                  {responsePlan && (
                    <div className="readable-plan-container">
                      <div className="plan-summary-banner">
                        <div className="banner-item">
                          <span>Plan Status:</span>
                          <strong>PLANNED (Awaiting Human Approval)</strong>
                        </div>
                        <div className="banner-item">
                          <span>Search Radius:</span>
                          <strong>
                            {responsePlan.resource_recommendation?.radius_km ??
                              25}{' '}
                            km
                          </strong>
                        </div>
                      </div>

                      {/* SIMULATED RESOURCES DEMO DISCLAIMER BANNER */}
                      <div className="simulated-resources-banner">
                        <div className="sim-badge-row">
                          <span className="sim-badge">
                            <Sparkles size={13} />
                            SIMULATED RESOURCES — DEMO DATA
                          </span>
                          <span className="sim-version-badge">
                            Dataset: {responsePlan.resource_recommendation?.dataset_version || 'crisissense-synth-v1.0'}
                          </span>
                        </div>
                        <p className="sim-disclaimer-text">
                          {responsePlan.resource_recommendation?.simulation_notice ||
                            'Resource units, geographical locations, and availability statuses shown below are synthetically generated demonstration records. They are intended for decision-support algorithm testing only and must not be treated as live operational assets.'}
                        </p>
                      </div>

                      {/* Recommended Departments */}
                      <div className="plan-section-card">
                        <div className="card-sub-header">
                          <Building2 size={16} />
                          <h4>Recommended Emergency Departments</h4>
                        </div>
                        <div className="departments-recommendations-grid">
                          {(
                            responsePlan.resource_recommendation
                              ?.recommended_departments || []
                          ).length > 0 ? (
                            (
                              responsePlan.resource_recommendation
                                ?.recommended_departments || []
                            ).map((deptItem, idx) => {
                              const deptName =
                                typeof deptItem === 'string'
                                  ? deptItem
                                  : deptItem?.department || 'Emergency Services'
                              const requiredFor =
                                typeof deptItem === 'object' &&
                                Array.isArray(deptItem?.required_for)
                                  ? deptItem.required_for
                                  : []
                              const deptKey = `dept-${deptName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${idx}`

                              return (
                                <div key={deptKey} className="dept-recommendation-card">
                                  <div className="dept-card-title-row">
                                    <Building2 size={15} />
                                    <strong>{deptName}</strong>
                                  </div>
                                  {requiredFor.length > 0 ? (
                                    <div className="dept-card-needs-row">
                                      <span className="dept-needs-label">Assigned Needs:</span>
                                      <div className="dept-needs-tags">
                                        {requiredFor.map((need, nIdx) => (
                                          <span
                                            key={`${deptKey}-need-${need}-${nIdx}`}
                                            className="dept-need-pill"
                                          >
                                            {need.replaceAll('_', ' ')}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  ) : (
                                    <span className="text-muted text-sm">
                                      Primary response dispatch
                                    </span>
                                  )}
                                </div>
                              )
                            })
                          ) : (
                            <span className="text-muted">
                              No specific department routing identified.
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Required Needs & Candidates */}
                      <div className="plan-section-card">
                        <div className="card-sub-header">
                          <Truck size={16} />
                          <h4>Resource Candidates by Need</h4>
                        </div>

                        {responsePlan.resource_recommendation?.recommendations &&
                        responsePlan.resource_recommendation.recommendations
                          .length > 0 ? (
                          <div className="needs-recommendations-list">
                            {responsePlan.resource_recommendation.recommendations.map(
                              (rec, recIdx) => {
                                const needName = rec.need || `Need #${recIdx + 1}`
                                const recKey = `rec-${needName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${recIdx}`
                                return (
                                  <div key={recKey} className="need-rec-block">
                                    <div className="need-rec-header">
                                      <span className="need-label">
                                        Need: <strong>{needName.replaceAll('_', ' ')}</strong>
                                      </span>
                                      <span className="candidates-count">
                                        {(rec.candidates || []).length} candidates found
                                      </span>
                                    </div>

                                    {(rec.candidates || []).length > 0 ? (
                                      <div className="candidates-table-wrapper">
                                        <table className="candidates-table">
                                          <thead>
                                            <tr>
                                              <th>Unit Name (Demo)</th>
                                              <th>Type</th>
                                              <th>Department</th>
                                              <th>Distance</th>
                                              <th>Simulated Availability</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {rec.candidates.map((cand, candIdx) => {
                                              const candKey = `cand-${cand.resource_id || cand.name || candIdx}`
                                              const simAvail = (cand.availability || 'AVAILABLE').toLowerCase()
                                              return (
                                                <tr key={candKey}>
                                                  <td>
                                                    <strong>{cand.name}</strong>
                                                    <span className="unit-demo-tag">SIMULATED</span>
                                                  </td>
                                                  <td>{cand.resource_type}</td>
                                                  <td>{cand.department}</td>
                                                  <td>{cand.distance_km} km</td>
                                                  <td>
                                                    <span className={`avail-badge sim-${simAvail}`}>
                                                      Simulated: {cand.availability}
                                                    </span>
                                                  </td>
                                                </tr>
                                              )
                                            })}
                                          </tbody>
                                        </table>
                                      </div>
                                    ) : (
                                      <div className="no-candidates-notice">
                                        <AlertCircle size={14} />
                                        <span>
                                          No nearby resource candidates found in
                                          database for this need.
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                )
                              },
                            )}
                          </div>
                        ) : (
                          <p className="text-muted">
                            No candidate recommendations generated.
                          </p>
                        )}
                      </div>

                      {/* Unmet Needs */}
                      {(
                        responsePlan.resource_recommendation?.unmet_needs || []
                      ).length > 0 && (
                        <div className="unmet-needs-warning-card">
                          <div className="unmet-title">
                            <AlertTriangle size={16} />
                            <strong>Unmet Incident Needs (Resource Shortage)</strong>
                          </div>
                          <p>
                            The response network currently has zero available
                            resources matching the following critical needs:
                          </p>
                          <div className="unmet-tags-row">
                            {(
                              responsePlan.resource_recommendation
                                ?.unmet_needs || []
                            ).map((unmet, unmetIdx) => {
                              const unmetStr =
                                typeof unmet === 'string'
                                  ? unmet
                                  : String(unmet)
                              const unmetKey = `unmet-${unmetStr.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${unmetIdx}`
                              return (
                                <span key={unmetKey} className="unmet-tag">
                                  {unmetStr.replaceAll('_', ' ')}
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      )}

                      {/* Collapsible raw JSON for debugging */}
                      <div className="collapsible-raw-json">
                        <button
                          type="button"
                          className="raw-json-toggle"
                          onClick={() => setShowRawJson(!showRawJson)}
                        >
                          <span>{showRawJson ? 'Hide' : 'Inspect'} Raw Backend API Response</span>
                        </button>
                        {showRawJson && (
                          <pre className="raw-json-pre">
                            {JSON.stringify(responsePlan, null, 2)}
                          </pre>
                        )}
                      </div>
                    </div>
                  )}
                </section>
              </div>
            )}
            </ErrorBoundary>
          </main>
        </div>
      )}

      {/* Permanent Deletion Confirmation Modal Dialog */}
      {incidentToDelete && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
          onClick={() => !isDeleting && setIncidentToDelete(null)}
        >
          <div
            className="delete-confirm-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="delete-modal-header">
              <div className="delete-modal-icon">
                <Trash2 size={20} />
              </div>
              <div className="delete-modal-titles">
                <h3 id="delete-dialog-title">Delete Incident</h3>
                <span className="delete-modal-id">
                  {incidentToDelete.incident_id}
                </span>
              </div>
            </div>

            <div className="delete-modal-body">
              <p className="delete-modal-message">
                Are you sure you want to permanently delete this incident?
              </p>
              <p className="delete-modal-subtext">
                This will permanently delete this incident along with its linked citizen reports and evidence from the database. This action cannot be undone.
              </p>
            </div>

            <div className="delete-modal-actions">
              <button
                type="button"
                className="btn-modal-cancel"
                disabled={isDeleting}
                onClick={() => setIncidentToDelete(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-modal-delete"
                disabled={isDeleting}
                onClick={() => void handleConfirmDelete()}
              >
                {isDeleting ? (
                  <>
                    <RefreshCw size={14} className="spinner" />
                    <span>Deleting…</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    <span>Delete</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
