import React, { useState, useEffect, useRef } from 'react'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  Lock,
  Mail,
  RefreshCw,
  User,
  X,
  KeyRound,
} from 'lucide-react'
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
  const [mode, setMode] = useState<'login' | 'register' | 'verify'>(initialMode)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    if (resendCooldown > 0) {
      timerRef.current = window.setTimeout(() => {
        setResendCooldown((prev) => prev - 1)
      }, 1000)
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [resendCooldown])

  if (!isOpen) return null

  const resetForm = () => {
    setFullName('')
    setEmail('')
    setPassword('')
    setVerificationCode('')
    setShowPassword(false)
    setError(null)
    setSuccessMsg(null)
    setResendCooldown(0)
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

  const handleVerifySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return

    setError(null)
    setSuccessMsg(null)

    const cleanCode = verificationCode.trim()
    if (!cleanCode) {
      setError('Please enter the 6-digit verification code.')
      return
    }

    if (!/^\d{6}$/.test(cleanCode)) {
      setError('Verification code must be exactly 6 digits.')
      return
    }

    setLoading(true)
    try {
      const res = await api.verifyEmailCode(email, cleanCode)
      setSuccessMsg('Account verified successfully! Establishing citizen session…')
      setTimeout(() => {
        onSuccess(res.user)
        resetForm()
        onClose()
      }, 500)
    } catch (err: unknown) {
      const errorObj = err as Error
      setError(errorObj.message || 'Invalid or expired verification code.')
    } finally {
      setLoading(false)
    }
  }

  const handleResendCode = async () => {
    if (resendLoading || resendCooldown > 0 || !email) return
    setError(null)
    setResendLoading(true)
    try {
      const res = await api.resendVerificationCode(email)
      setSuccessMsg(res.message || 'A fresh verification code has been dispatched to your email.')
      setResendCooldown(30)
    } catch (err: unknown) {
      const errorObj = err as Error
      setError(errorObj.message || 'Unable to resend verification code.')
    } finally {
      setResendLoading(false)
    }
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
        if (res.user && res.user.is_verified === false) {
          setMode('verify')
          setSuccessMsg(
            'Account registered! A 6-digit verification code has been dispatched to your email address.',
          )
          setResendCooldown(30)
        } else {
          setSuccessMsg('Account created successfully! Establishing citizen session…')
          setTimeout(() => {
            onSuccess(res.user)
            resetForm()
            onClose()
          }, 500)
        }
      } else {
        const res = await api.loginCitizen({
          email: cleanEmail,
          password,
        })
        if (res.user && res.user.is_verified === false) {
          setMode('verify')
          setSuccessMsg('Please enter your verification code to access your citizen account.')
          setResendCooldown(15)
        } else {
          setSuccessMsg('Signed in successfully! Entering Citizen Portal…')
          setTimeout(() => {
            onSuccess(res.user)
            resetForm()
            onClose()
          }, 400)
        }
      }
    } catch (err) {
      const rawError =
        err instanceof Error ? err.message : 'Authentication failed. Please try again.'
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
      <div className="auth-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="auth-modal-header">
          {mode === 'verify' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <KeyRound size={18} color="var(--palette-camel)" />
              <span style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-primary)' }}>
                Email Verification
              </span>
            </div>
          ) : (
            <div className="auth-modal-tabs">
              <button
                type="button"
                className={`auth-tab-btn ${mode === 'login' ? 'active' : ''}`}
                onClick={() => {
                  setMode('login')
                  setError(null)
                  setSuccessMsg(null)
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
                  setSuccessMsg(null)
                }}
                disabled={loading}
              >
                Register
              </button>
            </div>
          )}
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
              {mode === 'verify'
                ? 'Verify Your Email Address'
                : mode === 'login'
                ? 'Citizen Sign In'
                : 'Citizen Registration'}
            </h2>
            <p className="auth-subtitle">
              {mode === 'verify'
                ? `Enter the single-use 6-digit code sent to ${email}.`
                : message
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

          {mode === 'verify' ? (
            <form onSubmit={handleVerifySubmit} className="auth-form" noValidate>
              <div className="auth-field-group">
                <label htmlFor="auth-verification-code">6-Digit Verification Code</label>
                <div className="auth-input-wrapper">
                  <KeyRound size={16} className="input-icon" />
                  <input
                    id="auth-verification-code"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    placeholder="123456"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                    disabled={loading}
                    autoComplete="one-time-code"
                    required
                    style={{ letterSpacing: '4px', fontSize: '18px', fontWeight: 700 }}
                  />
                </div>
                <span className="auth-help-text">
                  Code expires in 15 minutes. Check your inbox and spam folder.
                </span>
              </div>

              <button type="submit" className="auth-submit-btn" disabled={loading || verificationCode.length !== 6}>
                {loading ? (
                  <>
                    <RefreshCw size={15} className="spinner" />
                    <span>Verifying Code…</span>
                  </>
                ) : (
                  <span>Verify &amp; Activate Account</span>
                )}
              </button>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginTop: '12px',
                  fontSize: '12px',
                }}
              >
                <button
                  type="button"
                  onClick={handleResendCode}
                  disabled={resendLoading || resendCooldown > 0}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: resendCooldown > 0 ? 'var(--text-muted)' : 'var(--palette-camel)',
                    fontWeight: 600,
                    cursor: resendCooldown > 0 ? 'not-allowed' : 'pointer',
                  }}
                >
                  {resendLoading
                    ? 'Resending…'
                    : resendCooldown > 0
                    ? `Resend Code in ${resendCooldown}s`
                    : 'Resend Verification Code'}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setMode('login')
                    setError(null)
                    setSuccessMsg(null)
                  }}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                  }}
                >
                  Back to Sign In
                </button>
              </div>
            </form>
          ) : (
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

              <button type="submit" className="auth-submit-btn" disabled={loading}>
                {loading ? (
                  <>
                    <RefreshCw size={15} className="spinner" />
                    <span>{mode === 'login' ? 'Signing in…' : 'Creating account…'}</span>
                  </>
                ) : (
                  <span>
                    {mode === 'login' ? 'Sign In to ResQ-Sense' : 'Register Citizen Account'}
                  </span>
                )}
              </button>
            </form>
          )}

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
                    setSuccessMsg(null)
                  }}
                  disabled={loading}
                >
                  Create citizen account
                </button>
              </p>
            ) : mode === 'register' ? (
              <p>
                Already have an account?{' '}
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    setMode('login')
                    setError(null)
                    setSuccessMsg(null)
                  }}
                  disabled={loading}
                >
                  Sign in
                </button>
              </p>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
