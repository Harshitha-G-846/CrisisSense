import React from 'react'
import {
  LayoutDashboard,
  FilePlus2,
  Search,
  Map as MapIcon,
  Inbox,
  CheckCircle2,
  XCircle,
  ArrowLeftRight,
  Layers,
} from 'lucide-react'

export type AppView =
  | 'landing'
  | 'citizen-home'
  | 'citizen-report'
  | 'citizen-status'
  | 'citizen-map'
  | 'authority-overview'
  | 'authority-incoming'
  | 'authority-verified'
  | 'authority-rejected'
  | 'authority-map'
  | 'authority-resources'

interface DockProps {
  currentView: AppView
  onNavigate: (view: AppView) => void
  incomingCount?: number
  verifiedCount?: number
  rejectedCount?: number
}

interface DockItem {
  id: AppView | 'switch-role'
  label: string
  icon: React.ReactNode
  badge?: number | string
  action?: () => void
}

export const Dock: React.FC<DockProps> = ({
  currentView,
  onNavigate,
  incomingCount = 0,
  verifiedCount = 0,
  rejectedCount = 0,
}) => {
  const isCitizen = currentView.startsWith('citizen')

  if (currentView === 'landing') {
    return null
  }

  const citizenItems: DockItem[] = [
    {
      id: 'citizen-home',
      label: 'Portal Home',
      icon: <LayoutDashboard size={20} />,
    },
    {
      id: 'citizen-report',
      label: 'Report Incident',
      icon: <FilePlus2 size={20} />,
    },
    {
      id: 'citizen-status',
      label: 'Track Reference',
      icon: <Search size={20} />,
    },
    {
      id: 'citizen-map',
      label: 'Crisis Map',
      icon: <MapIcon size={20} />,
    },
    {
      id: 'switch-role',
      label: 'Authority Ops',
      icon: <ArrowLeftRight size={20} />,
      action: () => onNavigate('authority-overview'),
    },
  ]

  const authorityItems: DockItem[] = [
    {
      id: 'authority-overview',
      label: 'Command Hub',
      icon: <Layers size={20} />,
    },
    {
      id: 'authority-incoming',
      label: 'Incoming',
      icon: <Inbox size={20} />,
      badge: incomingCount > 0 ? incomingCount : undefined,
    },
    {
      id: 'authority-verified',
      label: 'Verified',
      icon: <CheckCircle2 size={20} />,
      badge: verifiedCount > 0 ? verifiedCount : undefined,
    },
    {
      id: 'authority-rejected',
      label: 'Rejected',
      icon: <XCircle size={20} />,
      badge: rejectedCount > 0 ? rejectedCount : undefined,
    },
    {
      id: 'authority-map',
      label: 'Tactical Map',
      icon: <MapIcon size={20} />,
    },
    {
      id: 'switch-role',
      label: 'Citizen Portal',
      icon: <ArrowLeftRight size={20} />,
      action: () => onNavigate('citizen-home'),
    },
  ]

  const items = isCitizen ? citizenItems : authorityItems

  return (
    <nav className="dock-container" aria-label="Quick Navigation Dock">
      <div className="dock-bar">
        <div className="dock-role-indicator">
          <span className="dock-role-dot" />
          <span className="dock-role-text">
            {isCitizen ? 'Citizen Portal' : 'Authority Workspace'}
          </span>
        </div>

        <div className="dock-divider" />

        <div className="dock-items">
          {items.map((item) => {
            const isActive = currentView === item.id

            return (
              <button
                key={item.id}
                type="button"
                className={`dock-button ${isActive ? 'active' : ''}`}
                onClick={() => {
                  if (item.action) {
                    item.action()
                  } else {
                    onNavigate(item.id as AppView)
                  }
                }}
                aria-label={item.label}
                title={item.label}
              >
                <div className="dock-icon-wrapper">
                  {item.icon}
                  {item.badge !== undefined && (
                    <span className="dock-badge">{item.badge}</span>
                  )}
                </div>
                <span className="dock-tooltip">{item.label}</span>
                {isActive && <span className="dock-active-dot" />}
              </button>
            )
          })}
        </div>
      </div>
    </nav>
  )
}
