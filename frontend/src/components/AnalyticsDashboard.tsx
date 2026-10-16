import React, { useEffect, useState } from 'react'
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Activity,
  FileText,
  CheckCircle2,
  RefreshCw,
  Layers,
} from 'lucide-react'
import { api, type AnalyticsMetrics } from '../services/api'

export const AnalyticsDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<AnalyticsMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchMetrics = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getAnalyticsMetrics()
      setMetrics(data)
    } catch (err: unknown) {
      const errorObj = err as Error
      setError(errorObj.message || 'Unable to load crisis analytics data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMetrics()
  }, [])

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '60px 20px',
          gap: '12px',
          color: 'var(--text-muted)',
        }}
      >
        <RefreshCw size={24} className="spin" color="var(--palette-camel)" />
        <span style={{ fontSize: '14px', fontWeight: 500 }}>Loading real-time crisis intelligence metrics…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div
        role="alert"
        style={{
          padding: '30px',
          background: 'var(--bg-surface)',
          border: '1px solid var(--severity-critical)',
          borderRadius: 'var(--radius-md)',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <AlertTriangle size={32} color="var(--severity-critical)" />
        <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Failed to Load Crisis Analytics</div>
        <div style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>{error}</div>
        <button
          type="button"
          onClick={fetchMetrics}
          style={{
            marginTop: '8px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            background: 'var(--palette-coffee-bean)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '8px 16px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} /> Retry
        </button>
      </div>
    )
  }

  if (!metrics || metrics.total_incidents === 0) {
    return (
      <div
        style={{
          padding: '50px 30px',
          background: 'var(--bg-surface)',
          border: '1px dashed var(--border-medium)',
          borderRadius: 'var(--radius-md)',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <BarChart3 size={40} color="var(--palette-camel)" opacity={0.6} />
        <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
          No Incident Records In Database Yet
        </h4>
        <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)', maxWidth: '440px' }}>
          Real data visualizations dynamically render based on genuine citizen reports and emergency operations.
          As soon as reports are submitted and analysed, distribution charts and timeline trends will appear here.
        </p>
      </div>
    )
  }

  const {
    total_incidents,
    total_reports,
    severity_distribution = {},
    verification_distribution = {},
    incident_types = {},
    timeline = [],
  } = metrics

  // Severity color mapping (Incident.severity)
  const severityColors: Record<string, string> = {
    CRITICAL: 'var(--severity-critical)',
    HIGH: 'var(--severity-high)',
    MEDIUM: 'var(--severity-medium)',
    LOW: 'var(--severity-low)',
    UNKNOWN: 'var(--palette-faded-copper)',
  }

  // Verification status color mapping (Incident.verification_status)
  const verificationColors: Record<string, string> = {
    VERIFIED: 'var(--status-verified)',
    PENDING: 'var(--severity-medium)',
    NEEDS_MORE_INFO: 'var(--severity-low)',
    REJECTED: 'var(--status-rejected)',
  }

  const criticalCount = severity_distribution['CRITICAL'] || 0

  // Standard ordered status categories ensuring 100% database field coverage
  const severityCategories = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
  if (severity_distribution['UNKNOWN']) {
    severityCategories.push('UNKNOWN')
  }

  const verificationCategories = [
    { key: 'VERIFIED', label: 'Verified' },
    { key: 'PENDING', label: 'Pending Review' },
    { key: 'NEEDS_MORE_INFO', label: 'Needs More Info' },
    { key: 'REJECTED', label: 'Rejected' },
  ]

  return (
    <div className="analytics-dashboard" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* KPI Overview Cards (Cleaned: Total Incidents, Citizen Reports, Critical Incidents) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '16px',
        }}
      >
        {/* Total Incidents */}
        <div
          style={{
            background: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '20px 22px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Total Incidents
            </div>
            <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '4px', lineHeight: 1.1 }}>
              {total_incidents}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              Cluster records in database
            </div>
          </div>
          <div
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '50%',
              background: 'rgba(191, 141, 98, 0.16)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Activity size={22} color="var(--palette-camel)" />
          </div>
        </div>

        {/* Citizen Reports (Renamed with documented counting logic) */}
        <div
          style={{
            background: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '20px 22px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Citizen Reports
            </div>
            <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '4px', lineHeight: 1.1 }}>
              {total_reports}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              Submitted reports count (<code>Report.id</code>)
            </div>
          </div>
          <div
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '50%',
              background: 'rgba(133, 84, 58, 0.16)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <FileText size={22} color="var(--palette-coffee-bean)" />
          </div>
        </div>

        {/* Critical Incidents */}
        <div
          style={{
            background: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '20px 22px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div>
            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Critical Incidents
            </div>
            <div style={{ fontSize: '32px', fontWeight: 800, color: 'var(--severity-critical)', marginTop: '4px', lineHeight: 1.1 }}>
              {criticalCount}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              Life-threatening emergencies
            </div>
          </div>
          <div
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '50%',
              background: 'rgba(239, 68, 68, 0.16)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <AlertTriangle size={22} color="var(--severity-critical)" />
          </div>
        </div>
      </div>

      {/* Main Analytics Distribution Charts Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '20px',
        }}
      >
        {/* Chart 1: Case Severity Distribution (Determined by Incident.severity) */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '22px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="var(--palette-camel)" />
              <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Case Severity Distribution
              </h4>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '26px' }}>
              Field: <code>Incident.severity</code> (Emergency threat &amp; priority level)
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {severityCategories.map((sev) => {
              const count = severity_distribution[sev] || 0
              const pct = total_incidents > 0 ? Math.round((count / total_incidents) * 100) : 0
              const color = severityColors[sev] || 'var(--palette-camel)'
              return (
                <div key={sev} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span
                        style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: color,
                          display: 'inline-block',
                        }}
                      />
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{sev}</span>
                    </div>
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div
                    style={{
                      height: '9px',
                      borderRadius: '5px',
                      background: 'var(--bg-surface-subtle)',
                      border: '1px solid var(--border-subtle)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${pct}%`,
                        background: color,
                        borderRadius: '4px',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Chart 2: Case Verification Workflow Distribution (Determined by Incident.verification_status) */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '22px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={18} color="var(--status-verified)" />
              <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Verification Workflow Distribution
              </h4>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '26px' }}>
              Field: <code>Incident.verification_status</code> (Authority verification state)
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {verificationCategories.map(({ key, label }) => {
              const count = verification_distribution[key] || 0
              const pct = total_incidents > 0 ? Math.round((count / total_incidents) * 100) : 0
              const color = verificationColors[key] || 'var(--palette-camel)'
              return (
                <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span
                        style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: color,
                          display: 'inline-block',
                        }}
                      />
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{label}</span>
                    </div>
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div
                    style={{
                      height: '9px',
                      borderRadius: '5px',
                      background: 'var(--bg-surface-subtle)',
                      border: '1px solid var(--border-subtle)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${pct}%`,
                        background: color,
                        borderRadius: '4px',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Chart 3: Top Incident Categories (Incident.incident_type) */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '22px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="var(--palette-faded-copper)" />
              <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Top Incident Categories
              </h4>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '26px' }}>
              Field: <code>Incident.incident_type</code> (NLP disaster classification)
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {Object.keys(incident_types).length === 0 ? (
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center', padding: '16px 0' }}>
                No category records available.
              </div>
            ) : (
              Object.entries(incident_types).map(([typ, count]) => {
                const pct = total_incidents > 0 ? Math.round((count / total_incidents) * 100) : 0
                return (
                  <div key={typ} style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{typ}</span>
                      <span style={{ color: 'var(--text-secondary)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div
                      style={{
                        height: '9px',
                        borderRadius: '5px',
                        background: 'var(--bg-surface-subtle)',
                        border: '1px solid var(--border-subtle)',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${pct}%`,
                          background: 'var(--palette-camel)',
                          borderRadius: '4px',
                          transition: 'width 0.4s ease',
                        }}
                      />
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Chart 4: Timeline Trend (Real Reports Over Time) */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '22px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={18} color="var(--palette-sandy-clay)" />
              <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Timeline Trend
              </h4>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '26px' }}>
              Field: <code>Incident.created_at</code> (Chronological submission activity)
            </span>
          </div>

          {timeline.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0' }}>
              No chronological date records available yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {timeline.slice(-6).map((item) => (
                <div
                  key={item.date}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    background: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '12px',
                  }}
                >
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{item.date}</span>
                  <span
                    style={{
                      fontWeight: 700,
                      color: 'var(--palette-sandy-clay)',
                      padding: '2px 8px',
                      borderRadius: '10px',
                      background: 'rgba(234, 184, 131, 0.15)',
                    }}
                  >
                    {item.count} {item.count === 1 ? 'incident' : 'incidents'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
