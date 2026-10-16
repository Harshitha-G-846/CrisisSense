import React from 'react'
import { Sun, Moon, Monitor } from 'lucide-react'
import { useTheme, type ThemeMode } from '../context/ThemeContext'

interface ThemeSelectorProps {
  className?: string
  compact?: boolean
}

export const ThemeSelector: React.FC<ThemeSelectorProps> = ({ className = '', compact = false }) => {
  const { theme, setTheme } = useTheme()

  const options: Array<{ mode: ThemeMode; label: string; icon: React.ReactNode }> = [
    { mode: 'light', label: 'Light', icon: <Sun size={15} aria-hidden="true" /> },
    { mode: 'dark', label: 'Dark', icon: <Moon size={15} aria-hidden="true" /> },
    { mode: 'system', label: 'System', icon: <Monitor size={15} aria-hidden="true" /> },
  ]

  return (
    <div
      role="group"
      aria-label="Theme mode selector"
      className={`theme-selector-container ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        background: 'var(--bg-surface-elevated)',
        border: '1px solid var(--border-medium)',
        borderRadius: 'var(--radius-full)',
        padding: '3px',
        gap: '2px',
      }}
    >
      {options.map((opt) => {
        const isSelected = theme === opt.mode
        return (
          <button
            key={opt.mode}
            type="button"
            role="radio"
            aria-checked={isSelected}
            aria-label={`${opt.label} mode`}
            title={`${opt.label} mode`}
            onClick={() => setTheme(opt.mode)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: compact ? '4px 8px' : '5px 10px',
              fontSize: '12px',
              fontWeight: isSelected ? 600 : 500,
              color: isSelected ? 'var(--text-inverse)' : 'var(--text-secondary)',
              background: isSelected ? 'var(--accent-primary)' : 'transparent',
              border: 'none',
              borderRadius: 'var(--radius-full)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            {opt.icon}
            {!compact && <span>{opt.label}</span>}
          </button>
        )
      })}
    </div>
  )
}
