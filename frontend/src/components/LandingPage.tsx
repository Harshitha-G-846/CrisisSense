import React from 'react'
import {
  Activity,
  ArrowUpRight,
  Bot,
  Compass,
  Radio,
  ShieldCheck,
  Users,
} from 'lucide-react'

interface LandingPageProps {
  onSelectRole: (role: 'citizen' | 'authority') => void
  incidentCount?: number
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onSelectRole,
  incidentCount = 0,
}) => {
  return (
    <div className="resq-landing-wrapper">
      {/* Background ambient radar glow */}
      <div className="ambient-radar-glow" />

      {/* Landing Navigation Header */}
      <header className="landing-nav-bar">
        <div className="brand-badge-group">
          <div className="brand-icon-box">
            <Activity size={22} />
          </div>
          <div className="brand-text-box">
            <span className="brand-name">ResQ-Sense</span>
            <span className="brand-sub">Crisis Intelligence</span>
          </div>
        </div>

        <div className="network-status-chip">
          <span className="pulse-dot" />
          <span>Active Response Grid</span>
          <span className="count-pill">{incidentCount} Monitored</span>
        </div>
      </header>

      {/* Hero Section */}
      <main className="landing-hero-content">
        <div className="hero-eyebrow-pill">
          <Radio size={14} />
          <span>Multimodal Crisis Intelligence &amp; Human Response System</span>
        </div>

        <h1 className="hero-main-title">
          When Every Second Matters,
          <br />
          <span>Every Signal Counts.</span>
        </h1>

        <p className="hero-tagline">
          ResQ-Sense fuses multimodal citizen signals—text, imagery, and audio—into
          verified situational intelligence with human-in-the-loop response authorization.
        </p>

        {/* Dual Access Doors */}
        <div className="role-access-cards-grid">
          {/* User / Citizen Portal */}
          <div
            className="access-card citizen"
            onClick={() => onSelectRole('citizen')}
          >
            <div className="access-card-glow" />
            <div className="access-card-header">
              <div className="access-card-icon citizen">
                <Users size={24} />
              </div>
              <span className="access-role-label">Citizen &amp; Witness</span>
            </div>

            <h3>Citizen Emergency Portal</h3>

            <p>
              Witnessed an incident? Submit reports with photos, videos, or
              voice notes, track live status, and provide real-time updates.
            </p>

            <button type="button" className="access-entry-btn citizen">
              <span>Enter Citizen Portal</span>
              <ArrowUpRight size={16} />
            </button>
          </div>

          {/* Authority Operations Workspace */}
          <div
            className="access-card authority"
            onClick={() => onSelectRole('authority')}
          >
            <div className="access-card-glow authority" />
            <div className="access-card-header">
              <div className="access-card-icon authority">
                <ShieldCheck size={24} />
              </div>
              <span className="access-role-label">Authorized Personnel</span>
            </div>

            <h3>Authority Operations Hub</h3>

            <p>
              Inspect incoming crisis signals, verify multimodal evidence, review
              resource recommendations, and explicitly authorize response plans.
            </p>

            <button type="button" className="access-entry-btn authority">
              <span>Open Command Workspace</span>
              <ArrowUpRight size={16} />
            </button>
          </div>
        </div>

        {/* Core Principles */}
        <div className="core-pillars-row">
          <div className="pillar-item">
            <Bot size={16} />
            <span>AI Multimodal Fusion</span>
          </div>
          <div className="pillar-separator">•</div>
          <div className="pillar-item">
            <ShieldCheck size={16} />
            <span>Human-Authorized Decision</span>
          </div>
          <div className="pillar-separator">•</div>
          <div className="pillar-item">
            <Compass size={16} />
            <span>National Spatial Intelligence</span>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="landing-footer-bar">
        <span>ResQ-Sense Emergency Intelligence Network</span>
        <span>Human oversight required before all emergency deployments.</span>
      </footer>
    </div>
  )
}
