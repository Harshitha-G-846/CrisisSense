import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  Maximize2,
  AlertTriangle,
  Layers,
  X,
} from 'lucide-react'
import type { Incident } from '../services/api'

interface MapProps {
  incidents: Incident[]
  selectedIncident: Incident | null
  onSelectIncident: (incident: Incident) => void
}

function getSeverityColor(severity?: string): string {
  switch ((severity || '').toUpperCase()) {
    case 'CRITICAL':
      return '#ef4444' // red
    case 'HIGH':
      return '#f97316' // orange
    case 'MEDIUM':
      return '#eab308' // yellow
    case 'LOW':
      return '#38bdf8' // blue
    default:
      return '#94a3b8' // slate
  }
}

function createMarkerIcon(incident: Incident, isSelected: boolean): L.DivIcon {
  const color = getSeverityColor(incident.severity)
  const isCritical = (incident.severity || '').toUpperCase() === 'CRITICAL'
  const isHigh = (incident.severity || '').toUpperCase() === 'HIGH'
  const size = isSelected ? 38 : 28

  const html = `
    <div class="custom-map-marker ${isSelected ? 'selected' : ''}" style="--marker-color: ${color}; width: ${size}px; height: ${size}px;">
      <div class="marker-core" style="background-color: ${color};">
        <span class="marker-inner-dot"></span>
      </div>
      ${(isCritical || isHigh || isSelected) ? `<div class="marker-pulse" style="border-color: ${color};"></div>` : ''}
    </div>
  `

  return L.divIcon({
    className: 'leaflet-custom-div-icon',
    html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  })
}

export const InteractiveMap: React.FC<MapProps> = ({
  incidents,
  selectedIncident,
  onSelectIncident,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<L.Map | null>(null)
  const markersLayerRef = useRef<L.LayerGroup | null>(null)
  const markersMapRef = useRef<Map<string, L.Marker>>(new Map())

  const [severityFilter, setSeverityFilter] = useState<string>('ALL')
  const [showUnmappedList, setShowUnmappedList] = useState(false)

  // Filter valid incidents with real coordinates
  const mappedIncidents = incidents.filter(
    (inc) =>
      typeof inc.latitude === 'number' &&
      typeof inc.longitude === 'number' &&
      !isNaN(inc.latitude) &&
      !isNaN(inc.longitude),
  )

  const unmappedIncidents = incidents.filter(
    (inc) =>
      inc.latitude == null ||
      inc.longitude == null ||
      isNaN(inc.latitude as number) ||
      isNaN(inc.longitude as number),
  )

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return
    if (mapInstanceRef.current) return

    // India center coordinate [22.5, 82.0], zoom 5
    const map = L.map(mapContainerRef.current, {
      center: [22.5, 82.0],
      zoom: 5,
      minZoom: 4,
      maxZoom: 18,
      zoomControl: false,
    })


    // OpenStreetMap tiles (no API key required)
    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      },
    ).addTo(map)


    L.control.zoom({ position: 'bottomright' }).addTo(map)

    const markersGroup = L.layerGroup().addTo(map)
    markersLayerRef.current = markersGroup
    mapInstanceRef.current = map

    return () => {
      map.remove()
      mapInstanceRef.current = null
    }
  }, [])

  // Render Markers
  useEffect(() => {
    const map = mapInstanceRef.current
    const markersGroup = markersLayerRef.current
    if (!map || !markersGroup) return

    markersGroup.clearLayers()
    markersMapRef.current.clear()

    const filtered = mappedIncidents.filter((inc) => {
      if (severityFilter === 'ALL') return true
      return (inc.severity || 'UNKNOWN').toUpperCase() === severityFilter
    })

    filtered.forEach((incident) => {
      if (incident.latitude == null || incident.longitude == null) return

      const isSelected =
        selectedIncident?.incident_id === incident.incident_id

      const marker = L.marker([incident.latitude, incident.longitude], {
        icon: createMarkerIcon(incident, isSelected),
        title: incident.incident_type || 'Incident',
      })

      const locationLabel =
        incident.location_name ||
        `${incident.latitude.toFixed(3)}, ${incident.longitude.toFixed(3)}`

      const popupHtml = `
        <div class="map-popup-card">
          <div class="map-popup-header">
            <span class="map-popup-type">${incident.incident_type || 'Crisis Alert'}</span>
            <span class="map-popup-severity badge-${(incident.severity || 'LOW').toLowerCase()}">
              ${incident.severity || 'UNKNOWN'}
            </span>
          </div>
          <div class="map-popup-location">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
              <circle cx="12" cy="10" r="3"></circle>
            </svg>
            <span>${locationLabel}</span>
          </div>
          <div class="map-popup-status">
            <span>Status: <strong>${incident.status || 'OPEN'}</strong></span>
            <span>Verify: <strong>${incident.verification_status || 'PENDING'}</strong></span>
          </div>
          <button id="inspect-btn-${incident.incident_id}" class="map-popup-btn">
            Inspect Incident Details
          </button>
        </div>
      `

      marker.bindPopup(popupHtml, {
        className: 'custom-leaflet-popup',
        maxWidth: 280,
      })

      marker.on('popupopen', () => {
        const btn = document.getElementById(`inspect-btn-${incident.incident_id}`)
        if (btn) {
          btn.onclick = () => {
            onSelectIncident(incident)
          }
        }
      })

      marker.on('click', () => {
        onSelectIncident(incident)
      })

      if (incident.incident_id) {
        markersMapRef.current.set(incident.incident_id, marker)
      }

      markersGroup.addLayer(marker)
    })
  }, [mappedIncidents, selectedIncident, severityFilter, onSelectIncident])

  // Center on Selected Incident
  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map || !selectedIncident) return

    if (
      typeof selectedIncident.latitude === 'number' &&
      typeof selectedIncident.longitude === 'number'
    ) {
      map.flyTo([selectedIncident.latitude, selectedIncident.longitude], 11, {
        animate: true,
        duration: 1.2,
      })

      if (selectedIncident.incident_id) {
        const marker = markersMapRef.current.get(selectedIncident.incident_id)
        if (marker) {
          marker.openPopup()
        }
      }
    }
  }, [selectedIncident])

  const resetIndiaView = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([22.5, 82.0], 5, {
        animate: true,
        duration: 1,
      })
    }
  }

  return (
    <div className="map-wrapper-card">
      <div className="map-toolbar">
        <div className="map-title-group">
          <div className="map-status-icon">
            <Layers size={18} />
          </div>
          <div>
            <h3>Tactical Crisis Map — India</h3>
            <p>
              Showing {mappedIncidents.length} geocoded incidents across Indian
              regions
            </p>
          </div>
        </div>

        <div className="map-filters">
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((lvl) => (
            <button
              key={lvl}
              type="button"
              className={`map-chip ${severityFilter === lvl ? 'active' : ''} ${lvl !== 'ALL' ? `chip-${lvl.toLowerCase()}` : ''
                }`}
              onClick={() => setSeverityFilter(lvl)}
            >
              {lvl === 'ALL' ? 'All Severities' : lvl}
            </button>
          ))}

          <button
            type="button"
            className="map-action-btn"
            onClick={resetIndiaView}
            title="Reset Pan to National India View"
          >
            <Maximize2 size={15} />
            <span>Center India</span>
          </button>
        </div>
      </div>

      <div className="map-viewport-container" ref={mapContainerRef} />

      <div className="map-footer-bar">
        <div className="map-legend">
          <span className="legend-label">Severity Index:</span>
          <span className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#ef4444' }} />
            Critical
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#f97316' }} />
            High
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#eab308' }} />
            Medium
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: '#38bdf8' }} />
            Low
          </span>
        </div>

        {unmappedIncidents.length > 0 && (
          <div className="unmapped-indicator">
            <button
              type="button"
              className="unmapped-toggle-btn"
              onClick={() => setShowUnmappedList(!showUnmappedList)}
            >
              <AlertTriangle size={14} />
              <span>
                {unmappedIncidents.length} incidents lack precise coordinates
              </span>
            </button>

            {showUnmappedList && (
              <div className="unmapped-dropdown">
                <div className="unmapped-dropdown-header">
                  <strong>Unmapped Crisis Signals</strong>
                  <button
                    type="button"
                    onClick={() => setShowUnmappedList(false)}
                    aria-label="Close unmapped list"
                  >
                    <X size={14} />
                  </button>
                </div>
                <p className="unmapped-desc">
                  These records contain incident reports but have no GPS coordinates
                  in the database. They are available in the incident queue.
                </p>
                <div className="unmapped-list">
                  {unmappedIncidents.map((inc) => (
                    <div
                      key={inc.incident_id}
                      className="unmapped-item"
                      onClick={() => {
                        onSelectIncident(inc)
                        setShowUnmappedList(false)
                      }}
                    >
                      <div className="unmapped-item-header">
                        <strong>{inc.incident_type || 'Incident'}</strong>
                        <span
                          className={`badge badge-${(
                            inc.severity || 'LOW'
                          ).toLowerCase()}`}
                        >
                          {inc.severity || 'UNKNOWN'}
                        </span>
                      </div>
                      <span className="unmapped-loc">
                        {inc.location_name || 'Location text unspecified'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
