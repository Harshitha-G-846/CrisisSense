import React, { useState } from 'react'
import { AlertCircle, CheckCircle2, Eye, EyeOff, Lock, Mail, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { api, type CitizenUser } from '../services/api'

interface AdminAuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (user: CitizenUser) => void
}

export const AdminAuthModal: React.FC<AdminAuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const resetForm = () => {
    setEmail('')
    setPassword('')
    setShowPassword(false)
    setError(null)
    setSuccessMsg(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return

    setError(null)
    setSuccessMsg(null)

    const cleanEmail = email.trim()
    if (!cleanEmail) {
      setError('Please enter your administrator email address.')
      return
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(cleanEmail)) {
      setError('Please enter a valid email address format.')
      return
    }

    if (!password) {
      setError('Please enter your administrator password.')
      return
    }

    setLoading(true)
    try {
      const res = await api.loginAdmin({
        email: cleanEmail,
        password,
      })

      if (res.user.role !== 'authority' && res.user.role !== 'admin') {
        throw new Error('Access denied: Account does not possess administrator privileges.')
      }

      setSuccessMsg('Administrator credentials verified! Opening Command Workspace…')
      setTimeout(() => {
        onSuccess(res.user)
        resetForm()
        onClose()
      }, 500)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Administrator authentication failed. Please check credentials and retry.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-auth-modal-title"
      onClick={() => !loading && onClose()}
    >
      <div
        className="auth-modal-card admin-variant"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="auth-modal-header admin-header">
          <div className="admin-badge-tag">
            <ShieldCheck size={16} />
            <span>Authorized Personnel Only</span>
          </div>
          <button
            type="button"
            className="auth-close-btn"
            onClick={onClose}
            disabled={loading}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="auth-modal-body">
          <div className="auth-heading admin-heading">
            <div className="admin-icon-halo">
              <ShieldCheck size={28} />
            </div>
            <h2 id="admin-auth-modal-title">Authority Command Hub</h2>
            <p className="auth-subtitle">
              Sign in with authorized administrator credentials to review emergency
              records, verify incoming signals, and dispatch response plans.
            </p>
          </div>

          {error && (
            <div className="auth-alert error" role="alert">
              <div className="auth-alert-content">
                <AlertCircle size={16} className="auth-alert-icon" />
                <span className="auth-alert-text">{error}</span>
              </div>
            </div>
          )}

          {successMsg && (
            <div className="auth-alert success" role="status">
              <div className="auth-alert-content">
                <CheckCircle2 size={16} className="auth-alert-icon" />
                <span className="auth-alert-text">{successMsg}</span>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="auth-field-group">
              <label htmlFor="admin-email">Administrator Email</label>
              <div className="auth-input-wrapper">
                <Mail size={16} className="input-icon" />
                <input
                  id="admin-email"
                  type="email"
                  placeholder="commander@resqsense.org"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  autoComplete="username"
                  required
                />
              </div>
            </div>

            <div className="auth-field-group">
              <label htmlFor="admin-password">Secure Password</label>
              <div className="auth-input-wrapper">
                <Lock size={16} className="input-icon" />
                <input
                  id="admin-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword((prev) => !prev)}
                  disabled={loading}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="auth-submit-btn admin-submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw size={15} className="spinner" />
                  <span>Verifying Authorization…</span>
                </>
              ) : (
                <>
                  <ShieldCheck size={16} />
                  <span>Access Operations Hub</span>
                </>
              )}
            </button>
          </form>

          <div className="admin-footer-notice">
            <p>
              This portal is restricted to designated disaster response coordinators,
              NDRF liaisons, and authorized emergency dispatchers.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
