import React, { useState } from 'react'
import { AlertCircle, ArrowRight, CheckCircle2, Eye, EyeOff, Lock, Mail, RefreshCw, User, X } from 'lucide-react'
import { api, type CitizenUser } from '../services/api'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (user: CitizenUser) => void
  initialMode?: 'login' | 'register'
  message?: string
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialMode = 'login',
  message,
}) => {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const resetForm = () => {
    setFullName('')
    setEmail('')
    setPassword('')
    setShowPassword(false)
    setError(null)
    setSuccessMsg(null)
  }

  const isUnknownEmailError =
    error !== null &&
    (error.toLowerCase().includes('no account found') ||
      error.toLowerCase().includes('not registered'))

  const handleSwitchToRegister = () => {
    setMode('register')
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
      setError('Please enter your email address.')
      return
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(cleanEmail)) {
      setError('Please enter a valid email address (e.g. name@example.com).')
      return
    }

    if (!password) {
      setError('Please enter your password.')
      return
    }

    if (mode === 'register') {
      const cleanName = fullName.trim()
      if (!cleanName) {
        setError('Please enter your full name.')
        return
      }

      if (password.length < 8) {
        setError('Password must be at least 8 characters long.')
        return
      }

      if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) {
        setError('Password must contain both letters and numbers.')
        return
      }
    }

    setLoading(true)
    try {
      if (mode === 'register') {
        const res = await api.registerCitizen({
          full_name: fullName.trim(),
          email: cleanEmail,
          password,
        })
        setSuccessMsg('Account created successfully! Establishing citizen session…')
        setTimeout(() => {
          onSuccess(res.user)
          resetForm()
          onClose()
        }, 500)
      } else {
        const res = await api.loginCitizen({
          email: cleanEmail,
          password,
        })
        setSuccessMsg('Signed in successfully! Entering Citizen Portal…')
        setTimeout(() => {
          onSuccess(res.user)
          resetForm()
          onClose()
        }, 400)
      }
    } catch (err) {
      const rawError = err instanceof Error ? err.message : 'Authentication failed. Please try again.'
      setError(rawError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      onClick={() => !loading && onClose()}
    >
      <div
        className="auth-modal-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="auth-modal-header">
          <div className="auth-modal-tabs">
            <button
              type="button"
              className={`auth-tab-btn ${mode === 'login' ? 'active' : ''}`}
              onClick={() => {
                setMode('login')
                setError(null)
              }}
              disabled={loading}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`auth-tab-btn ${mode === 'register' ? 'active' : ''}`}
              onClick={() => {
                setMode('register')
                setError(null)
              }}
              disabled={loading}
            >
              Register
            </button>
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
          <div className="auth-heading">
            <h2 id="auth-modal-title">
              {mode === 'login' ? 'Citizen Sign In' : 'Citizen Registration'}
            </h2>
            <p className="auth-subtitle">
              {message
                ? message
                : mode === 'login'
                ? 'Sign in to submit emergency reports and follow real-time verification.'
                : 'Create an account to track your submitted reports and receive confirmation emails.'}
            </p>
          </div>

          {error && (
            <div className="auth-alert error" role="alert">
              <div className="auth-alert-content">
                <AlertCircle size={16} className="auth-alert-icon" />
                <span className="auth-alert-text">{error}</span>
              </div>
              {isUnknownEmailError && (
                <button
                  type="button"
                  className="auth-switch-link-btn"
                  onClick={handleSwitchToRegister}
                  disabled={loading}
                >
                  <span>Register for a citizen account</span>
                  <ArrowRight size={13} />
                </button>
              )}
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

          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            {mode === 'register' && (
              <div className="auth-field-group">
                <label htmlFor="auth-full-name">Full Name</label>
                <div className="auth-input-wrapper">
                  <User size={16} className="input-icon" />
                  <input
                    id="auth-full-name"
                    type="text"
                    placeholder="Jane Doe"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    disabled={loading}
                    autoComplete="name"
                    required
                  />
                </div>
              </div>
            )}

            <div className="auth-field-group">
              <label htmlFor="auth-email">Email Address</label>
              <div className="auth-input-wrapper">
                <Mail size={16} className="input-icon" />
                <input
                  id="auth-email"
                  type="email"
                  placeholder="jane.citizen@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            <div className="auth-field-group">
              <label htmlFor="auth-password">Password</label>
              <div className="auth-input-wrapper">
                <Lock size={16} className="input-icon" />
                <input
                  id="auth-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
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
              {mode === 'register' && (
                <span className="auth-help-text">
                  Minimum 8 characters with at least one letter and one number.
                </span>
              )}
            </div>

            <button
              type="submit"
              className="auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw size={15} className="spinner" />
                  <span>{mode === 'login' ? 'Signing in…' : 'Creating account…'}</span>
                </>
              ) : (
                <span>{mode === 'login' ? 'Sign In to ResQ-Sense' : 'Register Citizen Account'}</span>
              )}
            </button>
          </form>

          <div className="auth-footer-toggle">
            {mode === 'login' ? (
              <p>
                Don't have an account yet?{' '}
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    setMode('register')
                    setError(null)
                  }}
                  disabled={loading}
                >
                  Create citizen account
                </button>
              </p>
            ) : (
              <p>
                Already have an account?{' '}
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    setMode('login')
                    setError(null)
                  }}
                  disabled={loading}
                >
                  Sign in
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
