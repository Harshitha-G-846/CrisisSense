import React, { useState, useEffect, useRef } from 'react'
import { Search, MapPin, Navigation, X, Loader2, AlertCircle } from 'lucide-react'
import { api, type LocationInfo, type LocationSearchResult } from '../services/api'

interface LocationSearchPickerProps {
  selectedLocation: LocationInfo | null
  onLocationSelect: (location: LocationInfo | null) => void
  disabled?: boolean
}

export const LocationSearchPicker: React.FC<LocationSearchPickerProps> = ({
  selectedLocation,
  onLocationSelect,
  disabled = false,
}) => {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<LocationSearchResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [deviceLocLoading, setDeviceLocLoading] = useState(false)

  const dropdownRef = useRef<HTMLDivElement>(null)
  const debounceTimerRef = useRef<number | null>(null)

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (evt: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(evt.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleQueryChange = (text: string) => {
    setQuery(text)
    setErrorMessage(null)

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    if (text.trim().length < 2) {
      setResults([])
      setIsOpen(false)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    debounceTimerRef.current = window.setTimeout(async () => {
      try {
        const response = await api.searchLocations(text)
        setResults(response.results || [])
        setIsOpen(true)
        if (response.results.length === 0) {
          setErrorMessage(`No geographic locations found for "${text}". Please verify the city name.`)
        }
      } catch (err: unknown) {
        const error = err as Error
        setErrorMessage(error.message || 'Location search service is currently unavailable.')
        setResults([])
      } finally {
        setIsLoading(false)
      }
    }, 300)
  }

  const handleSelectResult = (res: LocationSearchResult) => {
    onLocationSelect({
      text: res.display_name,
      city: res.city,
      state: res.state,
      country: res.country,
      latitude: res.latitude,
      longitude: res.longitude,
    })
    setQuery('')
    setIsOpen(false)
    setResults([])
    setErrorMessage(null)
  }

  const handleUseDeviceLocation = () => {
    if (!navigator.geolocation) {
      setErrorMessage('Device geolocation is not supported by your browser.')
      return
    }

    setDeviceLocLoading(true)
    setErrorMessage(null)

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setDeviceLocLoading(false)
        onLocationSelect({
          text: `Device GPS (${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)})`,
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        })
        setIsOpen(false)
      },
      (err) => {
        setDeviceLocLoading(false)
        if (err.code === err.PERMISSION_DENIED) {
          setErrorMessage('Device location access was denied. You can search for your city by name without permissions.')
        } else {
          setErrorMessage('Unable to retrieve device coordinates. Please search for your city by name.')
        }
      },
      { timeout: 10000, enableHighAccuracy: true },
    )
  }

  const handleClearSelection = () => {
    onLocationSelect(null)
    setQuery('')
    setResults([])
    setErrorMessage(null)
  }

  return (
    <div className="location-search-picker" ref={dropdownRef} style={{ position: 'relative' }}>
      {selectedLocation ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-surface-elevated)',
            border: '1px solid var(--palette-camel)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 14px',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
            <MapPin size={18} color="var(--palette-camel)" style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {selectedLocation.text || selectedLocation.city || 'Selected Location'}
              </div>
              {selectedLocation.latitude != null && selectedLocation.longitude != null && (
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {selectedLocation.latitude.toFixed(4)}°, {selectedLocation.longitude.toFixed(4)}°
                </div>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={handleClearSelection}
            disabled={disabled}
            aria-label="Remove selected location"
            title="Remove location"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: disabled ? 'not-allowed' : 'pointer',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={16} />
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search
              size={16}
              color="var(--text-muted)"
              style={{ position: 'absolute', left: '12px', pointerEvents: 'none' }}
              aria-hidden="true"
            />
            <input
              type="text"
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              onFocus={() => results.length > 0 && setIsOpen(true)}
              placeholder="Search city or location (e.g., Vijayawada, Jaisalmer, Delhi)..."
              disabled={disabled}
              style={{
                width: '100%',
                padding: '10px 38px 10px 36px',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                fontSize: '13px',
                outline: 'none',
              }}
            />
            {isLoading ? (
              <Loader2
                size={16}
                color="var(--palette-camel)"
                className="spin"
                style={{ position: 'absolute', right: '12px' }}
              />
            ) : query ? (
              <button
                type="button"
                onClick={() => handleQueryChange('')}
                style={{
                  position: 'absolute',
                  right: '10px',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '2px',
                }}
              >
                <X size={14} />
              </button>
            ) : null}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <button
              type="button"
              onClick={handleUseDeviceLocation}
              disabled={disabled || deviceLocLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'transparent',
                border: 'none',
                color: 'var(--palette-camel)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: disabled || deviceLocLoading ? 'not-allowed' : 'pointer',
                padding: '2px 4px',
              }}
            >
              {deviceLocLoading ? (
                <Loader2 size={13} className="spin" />
              ) : (
                <Navigation size={13} aria-hidden="true" />
              )}
              <span>Use Current Device Location (GPS)</span>
            </button>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              City searches do not require GPS permission
            </span>
          </div>

          {errorMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '12px',
                color: 'var(--palette-faded-copper)',
                padding: '4px 0',
              }}
            >
              <AlertCircle size={14} style={{ flexShrink: 0 }} />
              <span>{errorMessage}</span>
            </div>
          )}

          {isOpen && results.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: '46px',
                left: 0,
                right: 0,
                background: 'var(--bg-surface-elevated)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-sm)',
                boxShadow: 'var(--shadow-md)',
                maxHeight: '240px',
                overflowY: 'auto',
                zIndex: 50,
              }}
            >
              {results.map((res, idx) => (
                <button
                  key={`${res.latitude}-${res.longitude}-${idx}`}
                  type="button"
                  onClick={() => handleSelectResult(res)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '10px',
                    background: 'transparent',
                    border: 'none',
                    borderBottom:
                      idx < results.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                    color: 'var(--text-primary)',
                    textAlign: 'left',
                    cursor: 'pointer',
                    fontSize: '13px',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = 'var(--bg-surface-hover)')
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = 'transparent')
                  }
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                    <MapPin size={15} color="var(--palette-camel)" style={{ flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontWeight: 600,
                          color: 'var(--text-primary)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {res.display_name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {res.city}{res.state ? `, ${res.state}` : ''} ({res.latitude.toFixed(4)}°, {res.longitude.toFixed(4)}°)
                      </div>
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '10px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: 'rgba(191, 141, 98, 0.15)',
                      color: 'var(--palette-camel)',
                      fontWeight: 600,
                      flexShrink: 0,
                    }}
                  >
                    {res.source === 'local_registry' ? 'Verified City' : 'Geocoded'}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
