import { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  ArrowLeftRight,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { api, authStorage, type Incident, type CitizenUser } from './services/api'
import {
  handleCitizenNavigation,
  handleAuthSuccess,
  handleAuthModalClose,
  handleCitizenLogout as executeCitizenLogout,
  isCitizenSessionActive,
} from './services/authGate'
import { AuthModal } from './components/AuthModal'
import { AdminAuthModal } from './components/AdminAuthModal'
import { Dock, type AppView } from './components/Dock'
import { LandingPage } from './components/LandingPage'
import { CitizenPortal } from './components/CitizenPortal'
import { AuthorityWorkspace } from './components/AuthorityWorkspace'
import { InteractiveMap } from './components/Map'
import './index.css'
import './App.css'

export function App() {
  const [currentView, setCurrentView] = useState<AppView>('landing')
  const [pendingCitizenView, setPendingCitizenView] = useState<AppView | null>(null)
  const [showCitizenAuthModal, setShowCitizenAuthModal] = useState(false)
  const [showAdminAuthModal, setShowAdminAuthModal] = useState(false)
  const [publicMonitoredCount, setPublicMonitoredCount] = useState<number>(0)
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedMapIncident, setSelectedMapIncident] =
    useState<Incident | null>(null)
  const [loading, setLoading] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [initialTrackingId, setInitialTrackingId] = useState<string | undefined>(
    undefined,
  )

  // Parse URL query params for direct incident tracking links (e.g. from confirmation emails)
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search)
      const incidentIdParam = params.get('incident_id')
      const viewParam = params.get('view')

      if (incidentIdParam) {
        setInitialTrackingId(incidentIdParam)
        setCurrentView('citizen-status')
      } else if (viewParam === 'citizen-status') {
        if (isCitizenSessionActive()) {
          setCurrentView('citizen-status')
        } else {
          setPendingCitizenView('citizen-status')
          setShowCitizenAuthModal(true)
        }
      } else if (viewParam === 'citizen-report') {
        if (isCitizenSessionActive()) {
          setCurrentView('citizen-report')
        } else {
          setPendingCitizenView('citizen-report')
          setShowCitizenAuthModal(true)
        }
      } else if (viewParam === 'citizen-home') {
        if (isCitizenSessionActive()) {
          setCurrentView('citizen-home')
        } else {
          setPendingCitizenView('citizen-home')
          setShowCitizenAuthModal(true)
        }
      } else if (viewParam === 'authority') {
        if (authStorage.isAuthority()) {
          setCurrentView('authority-overview')
        } else {
          setShowAdminAuthModal(true)
        }
      }
    } catch {
      // ignore URL parsing errors
    }
  }, [])

  // Public stats for landing page and grid count (does not expose private incidents)
  useEffect(() => {
    api
      .getPublicStats()
      .then((stats) => {
        setPublicMonitoredCount(stats.monitored_incidents)
        setBackendOnline(true)
      })
      .catch(() => {
        setBackendOnline(false)
      })
  }, [])

  // Load Authority Incidents for Workspace and Live Badges (Authority Protected)
  const refreshIncidents = useCallback(async () => {
    if (!authStorage.isAuthority()) {
      setIncidents([])
      return
    }
    setLoading(true)
    try {
      const data = await api.listIncidents()
      setIncidents(data)
      setBackendOnline(true)
    } catch (err) {
      console.warn('Backend connection warning:', err)
      setBackendOnline(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshIncidents()
  }, [refreshIncidents])

  // Count calculations for dock badges
  const incomingCount = incidents.filter(
    (i) =>
      i.verification_status === 'PENDING' ||
      i.verification_status === 'NEEDS_MORE_INFO',
  ).length

  const verifiedCount = incidents.filter(
    (i) => i.verification_status === 'VERIFIED',
  ).length

  const rejectedCount = incidents.filter(
    (i) => i.verification_status === 'REJECTED',
  ).length

  const navigateToCitizenView = useCallback(
    (targetView: AppView = 'citizen-home') => {
      const next = handleCitizenNavigation(
        targetView,
        {
          currentView,
          pendingCitizenView,
          showCitizenAuthModal,
          showAdminAuthModal,
        },
        isCitizenSessionActive(),
      )
      setCurrentView(next.currentView)
      setPendingCitizenView(next.pendingCitizenView)
      setShowCitizenAuthModal(next.showCitizenAuthModal)
    },
    [currentView, pendingCitizenView, showCitizenAuthModal, showAdminAuthModal],
  )

  const handleSelectRole = (role: 'citizen' | 'authority') => {
    if (role === 'citizen') {
      navigateToCitizenView('citizen-home')
    } else {
      if (authStorage.isAuthority()) {
        setCurrentView('authority-overview')
        void refreshIncidents()
      } else {
        setShowAdminAuthModal(true)
      }
    }
  }

  const handleCitizenAuthSuccess = (user: CitizenUser) => {
    const next = handleAuthSuccess(user, {
      currentView,
      pendingCitizenView,
      showCitizenAuthModal,
      showAdminAuthModal,
    })
    setCurrentView(next.currentView)
    setPendingCitizenView(next.pendingCitizenView)
    setShowCitizenAuthModal(next.showCitizenAuthModal)
  }

  const handleCitizenAuthClose = () => {
    const next = handleAuthModalClose({
      currentView,
      pendingCitizenView,
      showCitizenAuthModal,
      showAdminAuthModal,
    })
    setPendingCitizenView(next.pendingCitizenView)
    setShowCitizenAuthModal(next.showCitizenAuthModal)
  }

  const handleCitizenLogout = async () => {
    try {
      await api.logoutCitizen()
    } catch {
      // ignore network errors
    }
    const next = executeCitizenLogout({
      currentView,
      pendingCitizenView,
      showCitizenAuthModal,
      showAdminAuthModal,
    })
    setCurrentView(next.currentView)
    setPendingCitizenView(next.pendingCitizenView)
    setShowCitizenAuthModal(next.showCitizenAuthModal)
  }

  const handleDockNavigate = (view: AppView) => {
    if (view.startsWith('citizen')) {
      navigateToCitizenView(view)
    } else {
      if (authStorage.isAuthority()) {
        setCurrentView(view)
        void refreshIncidents()
      } else {
        setShowAdminAuthModal(true)
      }
    }
  }

  const isCitizen = currentView.startsWith('citizen')

  return (
    <div className="resq-app-container">
      {/* Top Header Bar for signed-in views */}
      {currentView !== 'landing' && (
        <header className="app-global-header">
          <div className="header-left">
            <button
              type="button"
              className="brand-logo-btn"
              onClick={() => setCurrentView('landing')}
              title="Return to Home Portal"
            >
              <div className="brand-icon-wrapper">
                <Activity size={18} />
              </div>
              <div className="brand-titles">
                <span className="brand-title-main">ResQ-Sense</span>
                <span className="brand-title-sub">Crisis Intelligence</span>
              </div>
            </button>

            <div className="role-current-tag">
              {isCitizen ? (
                <>
                  <Users size={14} />
                  <span>Citizen Portal</span>
                </>
              ) : (
                <>
                  <ShieldCheck size={14} />
                  <span>Authority Operations</span>
                </>
              )}
            </div>
          </div>

          <div className="header-right">
            <div
              className={`backend-status-pill ${
                backendOnline === true
                  ? 'online'
                  : backendOnline === false
                  ? 'offline'
                  : 'checking'
              }`}
            >
              <span className="status-indicator-dot" />
              <span>
                {isCitizen
                  ? 'Citizen Dispatch Network'
                  : backendOnline === true
                  ? `Command Feed: ${incidents.length} Incidents`
                  : backendOnline === false
                  ? 'API Offline'
                  : 'Connecting API…'}
              </span>
            </div>

            {/* Authority can navigate to Citizen Portal, but Citizen Portal never has switch to Authority */}
            {!isCitizen && (
              <button
                type="button"
                className="role-switcher-btn"
                onClick={() => navigateToCitizenView('citizen-home')}
              >
                <ArrowLeftRight size={14} />
                <span>Switch to Citizen Portal</span>
              </button>
            )}

            {/* Citizen Logout button */}
            {isCitizen && isCitizenSessionActive() && (
              <button
                type="button"
                className="role-switcher-btn"
                style={{
                  borderColor: 'rgba(239, 68, 68, 0.4)',
                  background: 'rgba(239, 68, 68, 0.12)',
                  color: '#fca5a5',
                }}
                onClick={() => void handleCitizenLogout()}
                title="Sign out of Citizen Portal"
              >
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            )}

            {/* Administrator Logout button */}
            {!isCitizen && authStorage.isAuthority() && (
              <button
                type="button"
                className="role-switcher-btn"
                style={{
                  borderColor: 'rgba(239, 68, 68, 0.4)',
                  background: 'rgba(239, 68, 68, 0.12)',
                  color: '#fca5a5',
                }}
                onClick={() => {
                  api.logoutAdmin()
                  setCurrentView('landing')
                  setIncidents([])
                }}
                title="Sign out of Authority Workspace"
              >
                <LogOut size={14} />
                <span>Admin Logout</span>
              </button>
            )}

            {!isCitizen && (
              <button
                type="button"
                className="header-sync-btn"
                onClick={() => void refreshIncidents()}
                disabled={loading}
                title="Sync live records from backend"
              >
                <RefreshCw size={14} className={loading ? 'spinner' : ''} />
              </button>
            )}
          </div>
        </header>
      )}

      {/* Main View Area */}
      <main className="app-main-viewport">
        {currentView === 'landing' && (
          <LandingPage
            onSelectRole={handleSelectRole}
            incidentCount={publicMonitoredCount}
          />
        )}

        {/* Citizen Views */}
        {currentView === 'citizen-home' && (
          <CitizenPortal
            initialView="home"
            onViewMap={() => setCurrentView('citizen-map')}
            onLogout={handleCitizenLogout}
          />
        )}

        {currentView === 'citizen-report' && (
          <CitizenPortal
            initialView="report"
            onViewMap={() => setCurrentView('citizen-map')}
            onLogout={handleCitizenLogout}
          />
        )}

        {currentView === 'citizen-status' && (
          <CitizenPortal
            initialView="status"
            initialIncidentId={initialTrackingId}
            onViewMap={() => setCurrentView('citizen-map')}
            onLogout={handleCitizenLogout}
          />
        )}

        {currentView === 'citizen-map' && (
          <div className="standalone-map-wrapper">
            <div className="standalone-map-header">
              <div>
                <h2>Live Incident Map — India</h2>
                <p>
                  Explore active emergency signals reported by citizens and
                  confirmed by response authorities.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="btn-glass"
                  onClick={() => navigateToCitizenView('citizen-report')}
                >
                  <span>Report New Emergency</span>
                </button>
                {isCitizenSessionActive() && (
                  <button
                    type="button"
                    className="btn-glass"
                    onClick={() => void handleCitizenLogout()}
                    title="Sign out of Citizen Portal"
                  >
                    <LogOut size={14} />
                    <span>Sign Out</span>
                  </button>
                )}
              </div>
            </div>
            <InteractiveMap
              incidents={incidents}
              selectedIncident={selectedMapIncident}
              onSelectIncident={(inc) => setSelectedMapIncident(inc)}
            />
          </div>
        )}

        {/* Authority Views - Protected by Administrator Authentication */}
        {currentView === 'authority-overview' && (
          authStorage.isAuthority() ? (
            <AuthorityWorkspace initialTab="all" />
          ) : (
            <div className="authority-forbidden-card" style={{ padding: '80px 20px', textAlign: 'center' }}>
              <ShieldCheck size={48} style={{ color: '#ef4444', marginBottom: '16px' }} />
              <h2 style={{ color: '#f8fafc', marginBottom: '8px' }}>Administrator Authentication Required</h2>
              <p style={{ color: '#94a3b8', maxWidth: '480px', margin: '0 auto 24px auto' }}>
                Access to the Authority Command Hub is restricted to verified emergency response administrators.
              </p>
              <button
                type="button"
                className="btn-primary-glow"
                onClick={() => setShowAdminAuthModal(true)}
              >
                Sign In as Administrator
              </button>
            </div>
          )
        )}

        {currentView === 'authority-incoming' && (
          authStorage.isAuthority() ? (
            <AuthorityWorkspace initialTab="incoming" />
          ) : (
            <div className="authority-forbidden-card" style={{ padding: '80px 20px', textAlign: 'center' }}>
              <h2>Administrator Authentication Required</h2>
              <button type="button" className="btn-primary-glow" onClick={() => setShowAdminAuthModal(true)}>
                Sign In as Administrator
              </button>
            </div>
          )
        )}

        {currentView === 'authority-verified' && (
          authStorage.isAuthority() ? (
            <AuthorityWorkspace initialTab="verified" />
          ) : (
            <div className="authority-forbidden-card" style={{ padding: '80px 20px', textAlign: 'center' }}>
              <h2>Administrator Authentication Required</h2>
              <button type="button" className="btn-primary-glow" onClick={() => setShowAdminAuthModal(true)}>
                Sign In as Administrator
              </button>
            </div>
          )
        )}

        {currentView === 'authority-rejected' && (
          authStorage.isAuthority() ? (
            <AuthorityWorkspace initialTab="rejected" />
          ) : (
            <div className="authority-forbidden-card" style={{ padding: '80px 20px', textAlign: 'center' }}>
              <h2>Administrator Authentication Required</h2>
              <button type="button" className="btn-primary-glow" onClick={() => setShowAdminAuthModal(true)}>
                Sign In as Administrator
              </button>
            </div>
          )
        )}

        {currentView === 'authority-map' && (
          authStorage.isAuthority() ? (
            <AuthorityWorkspace initialTab="map" />
          ) : (
            <div className="authority-forbidden-card" style={{ padding: '80px 20px', textAlign: 'center' }}>
              <h2>Administrator Authentication Required</h2>
              <button type="button" className="btn-primary-glow" onClick={() => setShowAdminAuthModal(true)}>
                Sign In as Administrator
              </button>
            </div>
          )
        )}
      </main>

      {/* Mac-Style Floating Navigation Dock */}
      <Dock
        currentView={currentView}
        onNavigate={handleDockNavigate}
        incomingCount={incomingCount}
        verifiedCount={verifiedCount}
        rejectedCount={rejectedCount}
      />

      {/* Citizen Gate Authentication Modal */}
      <AuthModal
        isOpen={showCitizenAuthModal}
        onClose={handleCitizenAuthClose}
        onSuccess={handleCitizenAuthSuccess}
        message="Sign in or register as a citizen to access the Citizen Emergency Portal."
      />

      {/* Dedicated Administrator Authentication Modal */}
      <AdminAuthModal
        isOpen={showAdminAuthModal}
        onClose={() => setShowAdminAuthModal(false)}
        onSuccess={() => {
          setShowAdminAuthModal(false)
          setCurrentView('authority-overview')
          void refreshIncidents()
        }}
      />
    </div>
  )
}

export default App