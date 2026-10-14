import { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  ArrowLeftRight,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { api, type Incident } from './services/api'
import { Dock, type AppView } from './components/Dock'
import { LandingPage } from './components/LandingPage'
import { CitizenPortal } from './components/CitizenPortal'
import { AuthorityWorkspace } from './components/AuthorityWorkspace'
import { InteractiveMap } from './components/Map'
import './index.css'
import './App.css'

export function App() {
  const [currentView, setCurrentView] = useState<AppView>('landing')
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedMapIncident, setSelectedMapIncident] =
    useState<Incident | null>(null)
  const [loading, setLoading] = useState(false)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)

  // Load Incidents for Live Dock Badges and Counts
  const refreshIncidents = useCallback(async () => {
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

  const handleSelectRole = (role: 'citizen' | 'authority') => {
    if (role === 'citizen') {
      setCurrentView('citizen-home')
    } else {
      setCurrentView('authority-overview')
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
                {backendOnline === true
                  ? `Live Feed: ${incidents.length} Incidents`
                  : backendOnline === false
                  ? 'API Offline'
                  : 'Connecting API…'}
              </span>
            </div>

            <button
              type="button"
              className="role-switcher-btn"
              onClick={() => {
                if (isCitizen) {
                  setCurrentView('authority-overview')
                } else {
                  setCurrentView('citizen-home')
                }
              }}
            >
              <ArrowLeftRight size={14} />
              <span>
                Switch to {isCitizen ? 'Authority Operations' : 'Citizen Portal'}
              </span>
            </button>

            <button
              type="button"
              className="header-sync-btn"
              onClick={() => void refreshIncidents()}
              disabled={loading}
              title="Sync live records from backend"
            >
              <RefreshCw size={14} className={loading ? 'spinner' : ''} />
            </button>
          </div>
        </header>
      )}

      {/* Main View Area */}
      <main className="app-main-viewport">
        {currentView === 'landing' && (
          <LandingPage
            onSelectRole={handleSelectRole}
            incidentCount={incidents.length}
          />
        )}

        {/* Citizen Views */}
        {currentView === 'citizen-home' && (
          <CitizenPortal
            initialView="home"
            onViewMap={() => setCurrentView('citizen-map')}
          />
        )}

        {currentView === 'citizen-report' && (
          <CitizenPortal
            initialView="report"
            onViewMap={() => setCurrentView('citizen-map')}
          />
        )}

        {currentView === 'citizen-status' && (
          <CitizenPortal
            initialView="status"
            onViewMap={() => setCurrentView('citizen-map')}
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
              <button
                type="button"
                className="btn-glass"
                onClick={() => setCurrentView('citizen-report')}
              >
                <span>Report New Emergency</span>
              </button>
            </div>
            <InteractiveMap
              incidents={incidents}
              selectedIncident={selectedMapIncident}
              onSelectIncident={(inc) => setSelectedMapIncident(inc)}
            />
          </div>
        )}

        {/* Authority Views */}
        {currentView === 'authority-overview' && (
          <AuthorityWorkspace initialTab="all" />
        )}

        {currentView === 'authority-incoming' && (
          <AuthorityWorkspace initialTab="incoming" />
        )}

        {currentView === 'authority-verified' && (
          <AuthorityWorkspace initialTab="verified" />
        )}

        {currentView === 'authority-rejected' && (
          <AuthorityWorkspace initialTab="rejected" />
        )}

        {currentView === 'authority-map' && (
          <AuthorityWorkspace initialTab="map" />
        )}
      </main>

      {/* Mac-Style Floating Navigation Dock */}
      <Dock
        currentView={currentView}
        onNavigate={setCurrentView}
        incomingCount={incomingCount}
        verifiedCount={verifiedCount}
        rejectedCount={rejectedCount}
      />
    </div>
  )
}

export default App