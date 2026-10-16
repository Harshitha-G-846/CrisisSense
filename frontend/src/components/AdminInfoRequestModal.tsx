import React, { useState } from 'react'
import { Mail, X, Send, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react'
import { api, type IncidentDetail, type Incident, type AdminInfoRequestResponse } from '../services/api'

interface AdminInfoRequestModalProps {
  isOpen: boolean
  onClose: () => void
  incident?: IncidentDetail | Incident | null
  incidentId?: string
  citizenName?: string | null
  citizenEmail?: string | null
  onSuccess?: (response: AdminInfoRequestResponse) => void
}

export const AdminInfoRequestModal: React.FC<AdminInfoRequestModalProps> = ({
  isOpen,
  onClose,
  incident,
  incidentId: propIncidentId,
  citizenName: propCitizenName,
  citizenEmail: propCitizenEmail,
  onSuccess,
}) => {
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successResponse, setSuccessResponse] = useState<AdminInfoRequestResponse | null>(null)

  if (!isOpen) return null

  const resolvedIncidentId = propIncidentId || incident?.incident_id
  const detail = (incident && 'submitting_citizen' in incident) ? (incident as IncidentDetail) : null
  const citizenInfo = detail?.submitting_citizen
  const email = propCitizenEmail || citizenInfo?.email
  const citizenDisplayName = propCitizenName || citizenInfo?.full_name
  const isAnonymous = !email || email === 'No linked citizen account'

  // Mask recipient email for display
  const getMaskedDisplayEmail = () => {
    if (!email || email === 'No linked citizen account') return 'N/A'
    const parts = email.split('@')
    if (parts.length === 2 && parts[0].length > 2) {
      return `${parts[0].slice(0, 2)}***@${parts[1]}`
    }
    return '***@' + (parts[1] || '')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading || isAnonymous || !resolvedIncidentId) return

    const trimmed = message.trim()
    if (!trimmed) {
      setError('Please provide a message explaining what information is required.')
      return
    }

    setLoading(true)
    setError(null)
    setSuccessResponse(null)

    try {
      const res = await api.requestIncidentInfo(resolvedIncidentId, trimmed)
      setSuccessResponse(res)
      setMessage('')
      if (onSuccess) {
        onSuccess(res)
      }
    } catch (err: unknown) {
      const errorObj = err as Error
      setError(errorObj.message || 'Failed to dispatch information request email.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-info-request-title"
      onClick={() => !loading && onClose()}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '16px',
      }}
    >
      <div
        className="admin-info-modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '540px',
          background: 'var(--bg-surface-elevated)',
          border: '1px solid var(--border-medium)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '18px 24px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'rgba(133, 84, 58, 0.1)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Mail size={20} color="var(--palette-camel)" />
            <h3
              id="admin-info-request-title"
              style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}
            >
              Request Citizen Information
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            aria-label="Close modal"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '12px 16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              fontSize: '13px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Incident:</span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {incident?.incident_type || 'Crisis Incident'} ({resolvedIncidentId || 'N/A'})
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Submitting Citizen:</span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                {citizenDisplayName || (isAnonymous ? 'Anonymous' : 'Registered Citizen')}
              </span>
            </div>
            {!isAnonymous && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Verified Email:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--palette-camel)' }}>
                  {getMaskedDisplayEmail()}
                </span>
              </div>
            )}
          </div>

          {isAnonymous ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                background: 'rgba(234, 184, 131, 0.12)',
                border: '1px solid var(--palette-camel)',
                borderRadius: 'var(--radius-sm)',
                padding: '12px',
                fontSize: '13px',
                color: 'var(--text-primary)',
              }}
            >
              <AlertCircle size={18} color="var(--palette-camel)" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <strong>Anonymous Incident Report:</strong> This incident was submitted without an authenticated citizen
                account. Official email inquiries can only be sent to incidents with a verified citizen contact.
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {error && (
                <div
                  role="alert"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid var(--severity-critical)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '10px 12px',
                    fontSize: '13px',
                    color: 'var(--text-primary)',
                  }}
                >
                  <AlertCircle size={16} color="var(--severity-critical)" />
                  <span>{error}</span>
                </div>
              )}

              {successResponse && (
                <div
                  role="status"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    background: 'rgba(34, 197, 94, 0.1)',
                    border: '1px solid var(--status-verified)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '10px 12px',
                    fontSize: '13px',
                    color: 'var(--status-verified)',
                  }}
                >
                  <CheckCircle2 size={16} />
                  <span>{successResponse.message}</span>
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label
                  htmlFor="admin-info-message"
                  style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}
                >
                  Official Response Inquiry:
                </label>
                <textarea
                  id="admin-info-message"
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="e.g., Please confirm the current water level at your location and if emergency medical transport is urgently required..."
                  disabled={loading}
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-medium)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    outline: 'none',
                    resize: 'vertical',
                  }}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  This message will be dispatched directly to the citizen via secure email notification.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={loading}
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--border-medium)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-secondary)',
                    padding: '8px 16px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={loading || !message.trim()}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    background: 'var(--palette-coffee-bean)',
                    border: 'none',
                    borderRadius: 'var(--radius-sm)',
                    color: '#ffffff',
                    padding: '8px 18px',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: loading || !message.trim() ? 'not-allowed' : 'pointer',
                    opacity: loading || !message.trim() ? 0.6 : 1,
                  }}
                >
                  {loading ? (
                    <>
                      <RefreshCw size={14} className="spin" />
                      <span>Dispatching…</span>
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      <span>Send Information Request</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
