import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Compass,
  Eye,
  FileText,
  Layers,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Truck,
  Users,
  Video,
  Volume2,
} from 'lucide-react'
import { ThemeSelector } from './ThemeSelector'

interface LandingPageProps {
  onSelectRole: (role: 'citizen' | 'authority') => void
  incidentCount?: number
}

interface StoryStage {
  id: string
  number: string
  title: string
  subtitle: string
  icon: React.ReactNode
  accentColor: string
  tag: string
  description: string
  deliverables: string[]
  verificationNote: string
}

interface IncidentPhotoTile {
  id: string
  src: string
  alt: string
  category: string
  shape: 'shape-circle' | 'shape-square' | 'shape-rect-h' | 'shape-rect-v'
  side: 'left' | 'right'
  col: 'outer' | 'inner'
  style: React.CSSProperties
}

const INCIDENT_PHOTO_TILES: IncidentPhotoTile[] = [
  // Left Flank (8 tiles)
  {
    id: 'tile-01',
    src: '/incidents/tile_01.jpg',
    alt: 'Flood evacuation boat rescue operation',
    category: 'Flood Rescue',
    shape: 'shape-circle',
    side: 'left',
    col: 'outer',
    style: {
      left: '3%',
      top: '9%',
      width: '110px',
      height: '110px',
      animationDuration: '8.4s',
      animationDelay: '0.0s',
    },
  },
  {
    id: 'tile-02',
    src: '/incidents/tile_02.jpg',
    alt: 'Cyclone landfall storm conditions',
    category: 'Cyclone / Storm',
    shape: 'shape-rect-h',
    side: 'left',
    col: 'inner',
    style: {
      left: '14%',
      top: '18%',
      width: '130px',
      height: '90px',
      animationDuration: '9.1s',
      animationDelay: '1.2s',
    },
  },
  {
    id: 'tile-03',
    src: '/incidents/tile_03.jpg',
    alt: 'Earthquake rubble structural search',
    category: 'Earthquake Collapse',
    shape: 'shape-square',
    side: 'left',
    col: 'outer',
    style: {
      left: '4%',
      top: '30%',
      width: '88px',
      height: '88px',
      animationDuration: '7.8s',
      animationDelay: '2.5s',
    },
  },
  {
    id: 'tile-04',
    src: '/incidents/tile_04.jpg',
    alt: 'Giant tsunami surge wave',
    category: 'Tsunami Surge',
    shape: 'shape-rect-v',
    side: 'left',
    col: 'inner',
    style: {
      left: '17%',
      top: '40%',
      width: '82px',
      height: '112px',
      animationDuration: '8.8s',
      animationDelay: '3.8s',
    },
  },
  {
    id: 'tile-05',
    src: '/incidents/tile_05.jpg',
    alt: 'Urban commercial building fire',
    category: 'Urban Inferno',
    shape: 'shape-square',
    side: 'left',
    col: 'outer',
    style: {
      left: '3%',
      top: '52%',
      width: '124px',
      height: '124px',
      animationDuration: '9.4s',
      animationDelay: '5.1s',
    },
  },
  {
    id: 'tile-06',
    src: '/incidents/tile_06.jpg',
    alt: 'Forest wildfire aerial tanker drop',
    category: 'Forest Wildfire',
    shape: 'shape-circle',
    side: 'left',
    col: 'inner',
    style: {
      left: '16%',
      top: '64%',
      width: '72px',
      height: '72px',
      animationDuration: '8.0s',
      animationDelay: '0.6s',
    },
  },
  {
    id: 'tile-07',
    src: '/incidents/tile_07.jpg',
    alt: 'Urban search and rescue canine specialist',
    category: 'Search & Rescue',
    shape: 'shape-rect-h',
    side: 'left',
    col: 'outer',
    style: {
      left: '5%',
      top: '74%',
      width: '135px',
      height: '92px',
      animationDuration: '8.6s',
      animationDelay: '2.0s',
    },
  },
  {
    id: 'tile-08',
    src: '/incidents/tile_08.jpg',
    alt: 'Emergency ambulance triage medical unit',
    category: 'Medical Triage',
    shape: 'shape-circle',
    side: 'left',
    col: 'inner',
    style: {
      left: '15%',
      top: '85%',
      width: '96px',
      height: '96px',
      animationDuration: '9.0s',
      animationDelay: '4.3s',
    },
  },

  // Right Flank (8 tiles)
  {
    id: 'tile-09',
    src: '/incidents/tile_09.jpg',
    alt: 'Disaster relief rations and aid distribution',
    category: 'Disaster Relief',
    shape: 'shape-rect-h',
    side: 'right',
    col: 'outer',
    style: {
      right: '3%',
      top: '10%',
      width: '128px',
      height: '88px',
      animationDuration: '8.5s',
      animationDelay: '0.8s',
    },
  },
  {
    id: 'tile-10',
    src: '/incidents/tile_10.jpg',
    alt: 'Submerged town aerial river flood drone',
    category: 'Aerial Flood Scan',
    shape: 'shape-circle',
    side: 'right',
    col: 'inner',
    style: {
      right: '15%',
      top: '19%',
      width: '106px',
      height: '106px',
      animationDuration: '9.2s',
      animationDelay: '2.8s',
    },
  },
  {
    id: 'tile-11',
    src: '/incidents/tile_11.jpg',
    alt: 'Coastguard search and rescue helicopter hoist',
    category: 'Helicopter Evac',
    shape: 'shape-rect-v',
    side: 'right',
    col: 'outer',
    style: {
      right: '4%',
      top: '31%',
      width: '80px',
      height: '115px',
      animationDuration: '7.9s',
      animationDelay: '4.6s',
    },
  },
  {
    id: 'tile-12',
    src: '/incidents/tile_12.jpg',
    alt: 'Firefighter squad advancing through smoke',
    category: 'Fire Brigade',
    shape: 'shape-square',
    side: 'right',
    col: 'inner',
    style: {
      right: '16%',
      top: '42%',
      width: '128px',
      height: '128px',
      animationDuration: '9.6s',
      animationDelay: '1.6s',
    },
  },
  {
    id: 'tile-13',
    src: '/incidents/tile_13.jpg',
    alt: 'Earthquake highway overpass structural damage',
    category: 'Infrastructure',
    shape: 'shape-circle',
    side: 'right',
    col: 'outer',
    style: {
      right: '5%',
      top: '54%',
      width: '74px',
      height: '74px',
      animationDuration: '8.2s',
      animationDelay: '3.4s',
    },
  },
  {
    id: 'tile-14',
    src: '/incidents/tile_14.jpg',
    alt: 'Active flood surge emergency response',
    category: 'Flash Flood',
    shape: 'shape-rect-h',
    side: 'right',
    col: 'inner',
    style: {
      right: '16%',
      top: '65%',
      width: '122px',
      height: '84px',
      animationDuration: '8.9s',
      animationDelay: '5.4s',
    },
  },
  {
    id: 'tile-15',
    src: '/incidents/tile_15.jpg',
    alt: 'Aerial winch hoist specialist extraction',
    category: 'Aviation Rescue',
    shape: 'shape-circle',
    side: 'right',
    col: 'outer',
    style: {
      right: '4%',
      top: '75%',
      width: '92px',
      height: '92px',
      animationDuration: '8.1s',
      animationDelay: '0.3s',
    },
  },
  {
    id: 'tile-16',
    src: '/incidents/tile_16.jpg',
    alt: 'Paramedic emergency dispatch responders',
    category: 'Field Medic',
    shape: 'shape-square',
    side: 'right',
    col: 'inner',
    style: {
      right: '15%',
      top: '86%',
      width: '102px',
      height: '102px',
      animationDuration: '9.3s',
      animationDelay: '3.0s',
    },
  },
]

export const LandingPage: React.FC<LandingPageProps> = ({
  onSelectRole,
  incidentCount = 0,
}) => {
  const [activeStage, setActiveStage] = useState(0)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const [scrollProgress, setScrollProgress] = useState(0)
  const heroRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mouseTargetRef = useRef({ x: 0, y: 0 })
  const mouseCurrRef = useRef({ x: 0, y: 0 })
  const animFrameRef = useRef<number | null>(null)

  // Smooth lerp mouse tracking to eliminate layout shift and create eased cinematic depth
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const { clientX, clientY } = e
    const { innerWidth, innerHeight } = window
    mouseTargetRef.current = {
      x: (clientX / innerWidth - 0.5) * 40,
      y: (clientY / innerHeight - 0.5) * 40,
    }
  }, [])

  // Scroll listener for seamless lifecycle conduit
  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY
      const maxScroll = 600
      setScrollProgress(Math.min(scrollY / maxScroll, 1))
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  // Real-time 3D Geospatial Sphere Canvas Engine
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let rot = 0.4
    let pulseTime = 0

    // Coordinates representing disaster response hubs (Lat, Long in degrees)
    const activeHubs = [
      { name: 'Guwahati (Brahm.)', lat: 26.14, lon: 91.73, status: 'active', color: '#ff4d36' },
      { name: 'Delhi Command', lat: 28.61, lon: 77.2, status: 'verified', color: '#bbf451' },
      { name: 'Mumbai Western', lat: 19.07, lon: 72.87, status: 'active', color: '#ff7056' },
      { name: 'Chennai Coastal', lat: 13.08, lon: 80.27, status: 'verified', color: '#bbf451' },
      { name: 'Kolkata Delta', lat: 22.57, lon: 88.36, status: 'active', color: '#ff4d36' },
    ]

    const render = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const rect = canvas.getBoundingClientRect()
      const width = rect.width
      const height = rect.height

      if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
        canvas.width = Math.floor(width * dpr)
        canvas.height = Math.floor(height * dpr)
      }

      ctx.save()
      ctx.scale(dpr, dpr)
      ctx.clearRect(0, 0, width, height)

      // Eased mouse interpolation
      mouseCurrRef.current.x += (mouseTargetRef.current.x - mouseCurrRef.current.x) * 0.06
      mouseCurrRef.current.y += (mouseTargetRef.current.y - mouseCurrRef.current.y) * 0.06
      setMousePos({ x: mouseCurrRef.current.x, y: mouseCurrRef.current.y })

      const cx = width / 2
      const cy = height / 2
      const baseRadius = Math.min(width, height) * 0.3
      const R = baseRadius

      // Update rotation
      if (!isReducedMotion) {
        rot += 0.007
        pulseTime += 0.03
      }

      const tilt = 23.5 * (Math.PI / 180)
      const mouseTiltX = (mouseCurrRef.current.y * 0.006)
      const mouseTiltY = (mouseCurrRef.current.x * 0.006)

      // 3D coordinate projection helper
      const project = (latDeg: number, lonDeg: number, r: number) => {
        const phi = (latDeg * Math.PI) / 180
        const theta = (lonDeg * Math.PI) / 180 + rot + mouseTiltY

        // Sphere equation
        const x0 = r * Math.cos(phi) * Math.sin(theta)
        const y0 = r * Math.sin(phi)
        const z0 = r * Math.cos(phi) * Math.cos(theta)

        // Axial tilt + mouse tilt
        const effectiveTilt = tilt + mouseTiltX
        const y1 = y0 * Math.cos(effectiveTilt) - z0 * Math.sin(effectiveTilt)
        const z1 = y0 * Math.sin(effectiveTilt) + z0 * Math.cos(effectiveTilt)
        const x1 = x0

        return { x: cx + x1, y: cy - y1, z: z1 }
      }

      // Outer atmospheric aura & Fresnel glow
      const auraGrad = ctx.createRadialGradient(cx, cy, R * 0.6, cx, cy, R * 1.35)
      auraGrad.addColorStop(0, 'rgba(168, 85, 247, 0.16)')
      auraGrad.addColorStop(0.5, 'rgba(217, 70, 239, 0.06)')
      auraGrad.addColorStop(0.85, 'rgba(255, 77, 54, 0.03)')
      auraGrad.addColorStop(1, 'transparent')
      ctx.fillStyle = auraGrad
      ctx.beginPath()
      ctx.arc(cx, cy, R * 1.35, 0, Math.PI * 2)
      ctx.fill()

      // Back-side Latitude parallels (draw before globe core)
      for (let lat = -60; lat <= 60; lat += 20) {
        ctx.beginPath()
        let first = true
        for (let lon = 0; lon <= 360; lon += 6) {
          const pt = project(lat, lon, R)
          if (pt.z < 0) {
            if (first) {
              ctx.moveTo(pt.x, pt.y)
              first = false
            } else {
              ctx.lineTo(pt.x, pt.y)
            }
          } else {
            first = true
          }
        }
        ctx.strokeStyle = 'rgba(210, 195, 235, 0.07)'
        ctx.lineWidth = 0.8
        ctx.stroke()
      }

      // Back-side Longitude meridians
      for (let lon = 0; lon < 360; lon += 30) {
        ctx.beginPath()
        let first = true
        for (let lat = -80; lat <= 80; lat += 5) {
          const pt = project(lat, lon, R)
          if (pt.z < 0) {
            if (first) {
              ctx.moveTo(pt.x, pt.y)
              first = false
            } else {
              ctx.lineTo(pt.x, pt.y)
            }
          } else {
            first = true
          }
        }
        ctx.strokeStyle = 'rgba(210, 195, 235, 0.06)'
        ctx.lineWidth = 0.8
        ctx.stroke()
      }

      // Solid sphere core with deep obsidian glass shading
      const sphereGrad = ctx.createRadialGradient(
        cx - R * 0.35,
        cy - R * 0.35,
        R * 0.1,
        cx,
        cy,
        R
      )
      sphereGrad.addColorStop(0, 'rgba(42, 22, 68, 0.95)')
      sphereGrad.addColorStop(0.55, 'rgba(22, 11, 36, 0.96)')
      sphereGrad.addColorStop(0.85, 'rgba(12, 6, 20, 0.98)')
      sphereGrad.addColorStop(1, 'rgba(8, 4, 14, 1)')
      ctx.fillStyle = sphereGrad
      ctx.beginPath()
      ctx.arc(cx, cy, R, 0, Math.PI * 2)
      ctx.fill()

      // Spherical perimeter rim light
      ctx.strokeStyle = 'rgba(168, 85, 247, 0.45)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.arc(cx, cy, R, 0, Math.PI * 2)
      ctx.stroke()

      // Front-side Latitude parallels
      for (let lat = -60; lat <= 60; lat += 20) {
        ctx.beginPath()
        let first = true
        for (let lon = 0; lon <= 360; lon += 4) {
          const pt = project(lat, lon, R)
          if (pt.z >= 0) {
            if (first) {
              ctx.moveTo(pt.x, pt.y)
              first = false
            } else {
              ctx.lineTo(pt.x, pt.y)
            }
          } else {
            first = true
          }
        }
        const depthAlpha = Math.max(0.12, 0.45 * (1 - Math.abs(lat) / 90))
        ctx.strokeStyle = `rgba(192, 132, 252, ${depthAlpha})`
        ctx.lineWidth = 1.1
        ctx.stroke()
      }

      // Front-side Longitude meridians
      for (let lon = 0; lon < 360; lon += 30) {
        ctx.beginPath()
        let first = true
        for (let lat = -85; lat <= 85; lat += 4) {
          const pt = project(lat, lon, R)
          if (pt.z >= 0) {
            if (first) {
              ctx.moveTo(pt.x, pt.y)
              first = false
            } else {
              ctx.lineTo(pt.x, pt.y)
            }
          } else {
            first = true
          }
        }
        ctx.strokeStyle = 'rgba(225, 215, 245, 0.22)'
        ctx.lineWidth = 1
        ctx.stroke()
      }

      // Orbital Trajectory Planes & Pulse Packets
      // Orbit 1: Text / Eyewitness Signal Stream (Orchid/Violet)
      const orbit1R = R * 1.32
      const angle1 = pulseTime * 1.4
      const pOrbit1 = {
        x: cx + orbit1R * Math.cos(angle1),
        y: cy + orbit1R * Math.sin(angle1) * 0.42 - mouseCurrRef.current.y * 0.1,
      }

      ctx.beginPath()
      ctx.ellipse(cx, cy, orbit1R, orbit1R * 0.42, -15 * (Math.PI / 180), 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(168, 85, 247, 0.28)'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 6])
      ctx.stroke()
      ctx.setLineDash([])

      // Orbit 2: Drone Video Telemetry (Vermilion)
      const orbit2R = R * 1.54
      const angle2 = -pulseTime * 1.1 + 1.2
      const pOrbit2 = {
        x: cx + orbit2R * Math.cos(angle2) * 0.88,
        y: cy + orbit2R * Math.sin(angle2) * 0.5 + mouseCurrRef.current.y * 0.08,
      }

      ctx.beginPath()
      ctx.ellipse(cx, cy, orbit2R * 0.88, orbit2R * 0.5, 35 * (Math.PI / 180), 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(255, 77, 54, 0.25)'
      ctx.lineWidth = 1.1
      ctx.setLineDash([6, 8])
      ctx.stroke()
      ctx.setLineDash([])

      // Orbit 3: Emergency Audio Waveform Stream (Acid Lime)
      const orbit3R = R * 1.76
      const angle3 = pulseTime * 0.85 + 2.5
      const pOrbit3 = {
        x: cx + orbit3R * Math.cos(angle3) * 0.95,
        y: cy + orbit3R * Math.sin(angle3) * 0.32,
      }

      ctx.beginPath()
      ctx.ellipse(cx, cy, orbit3R * 0.95, orbit3R * 0.32, -45 * (Math.PI / 180), 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(187, 244, 81, 0.22)'
      ctx.lineWidth = 1
      ctx.setLineDash([3, 7])
      ctx.stroke()
      ctx.setLineDash([])

      // Render Active Incident Hotspots on the Globe Surface
      let primaryTarget: { x: number; y: number } | null = null

      activeHubs.forEach((hub, idx) => {
        const pt = project(hub.lat, hub.lon, R)
        if (pt.z >= 0) {
          if (!primaryTarget && pt.z > 0.2) primaryTarget = { x: pt.x, y: pt.y }

          // Concentric pulse waves
          const pulseR = 4 + (Math.sin(pulseTime * 3 + idx) + 1) * 5
          ctx.beginPath()
          ctx.arc(pt.x, pt.y, pulseR, 0, Math.PI * 2)
          ctx.strokeStyle = hub.color === '#ff4d36' ? 'rgba(255, 77, 54, 0.45)' : 'rgba(187, 244, 81, 0.45)'
          ctx.lineWidth = 1.2
          ctx.stroke()

          // Core beacon point
          ctx.beginPath()
          ctx.arc(pt.x, pt.y, 3.2, 0, Math.PI * 2)
          ctx.fillStyle = hub.color
          ctx.shadowColor = hub.color
          ctx.shadowBlur = 10
          ctx.fill()
          ctx.shadowBlur = 0

          // Telemetry coordinate label for front-most hub
          if (idx === 0) {
            ctx.fillStyle = 'rgba(240, 235, 250, 0.85)'
            ctx.font = '9px "JetBrains Mono", monospace'
            ctx.fillText(`${hub.name}`, pt.x + 8, pt.y - 4)
            ctx.fillStyle = '#ff7056'
            ctx.fillText('SIGNAL_LOCK // 26.14°N', pt.x + 8, pt.y + 7)
          }
        }
      })

      // Default target fallback if backside
      if (!primaryTarget) {
        primaryTarget = { x: cx, y: cy }
      }

      // Draw Converging Signal Spline Arcs from Orbits down to Incident Core
      // Signal 1 (Text / Orchid)
      ctx.beginPath()
      ctx.moveTo(pOrbit1.x, pOrbit1.y)
      ctx.quadraticCurveTo(cx, cy - R * 0.4, primaryTarget.x, primaryTarget.y)
      ctx.strokeStyle = 'rgba(192, 132, 252, 0.65)'
      ctx.lineWidth = 1.4
      ctx.setLineDash([5, 5])
      ctx.lineDashOffset = -pulseTime * 15
      ctx.stroke()
      ctx.setLineDash([])

      // Signal 2 (Drone / Vermilion)
      ctx.beginPath()
      ctx.moveTo(pOrbit2.x, pOrbit2.y)
      ctx.quadraticCurveTo(cx + R * 0.3, cy + R * 0.2, primaryTarget.x, primaryTarget.y)
      ctx.strokeStyle = 'rgba(255, 77, 54, 0.7)'
      ctx.lineWidth = 1.6
      ctx.setLineDash([6, 6])
      ctx.lineDashOffset = pulseTime * 18
      ctx.stroke()
      ctx.setLineDash([])

      // Signal 3 (Audio / Acid Lime)
      ctx.beginPath()
      ctx.moveTo(pOrbit3.x, pOrbit3.y)
      ctx.quadraticCurveTo(cx - R * 0.3, cy + R * 0.1, primaryTarget.x, primaryTarget.y)
      ctx.strokeStyle = 'rgba(187, 244, 81, 0.6)'
      ctx.lineWidth = 1.3
      ctx.setLineDash([4, 4])
      ctx.lineDashOffset = -pulseTime * 12
      ctx.stroke()
      ctx.setLineDash([])

      // Orbital Satellites (Pulse Packets)
      // Node 1
      ctx.beginPath()
      ctx.arc(pOrbit1.x, pOrbit1.y, 4.5, 0, Math.PI * 2)
      ctx.fillStyle = '#c084fc'
      ctx.shadowColor = '#c084fc'
      ctx.shadowBlur = 12
      ctx.fill()
      ctx.shadowBlur = 0

      // Node 2
      ctx.beginPath()
      ctx.arc(pOrbit2.x, pOrbit2.y, 5, 0, Math.PI * 2)
      ctx.fillStyle = '#ff4d36'
      ctx.shadowColor = '#ff4d36'
      ctx.shadowBlur = 14
      ctx.fill()
      ctx.shadowBlur = 0

      // Node 3
      ctx.beginPath()
      ctx.arc(pOrbit3.x, pOrbit3.y, 4, 0, Math.PI * 2)
      ctx.fillStyle = '#bbf451'
      ctx.shadowColor = '#bbf451'
      ctx.shadowBlur = 10
      ctx.fill()
      ctx.shadowBlur = 0

      ctx.restore()
      animFrameRef.current = requestAnimationFrame(render)
    }

    animFrameRef.current = requestAnimationFrame(render)

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [])

  const stages: StoryStage[] = [
    {
      id: 'ingest',
      number: '01',
      title: 'Multimodal Field Ingest',
      subtitle: 'Capturing Raw Signals Across Text, Imagery, and Audio',
      icon: <Radio size={24} />,
      accentColor: '#ff5733',
      tag: 'FIELD INGESTION LAYER',
      description:
        'Citizens on the ground submit crisis signals through raw text messages, smartphone photography, drone video feeds, and emergency voice recordings without restrictive form hurdles.',
      deliverables: [
        'TF-IDF & Logistic Regression emergency classifier',
        'Automatic speech recognition & transcript extraction',
        'Frame sampling with visual hazard classification',
      ],
      verificationNote:
        'Multi-channel intake ensures critical evidence is captured even under erratic network connectivity.',
    },
    {
      id: 'convergence',
      number: '02',
      title: 'Report Convergence & Deduplication',
      subtitle: 'Synthesizing Multiple Citizen Signals into Unified Incidents',
      icon: <Layers size={24} />,
      accentColor: '#c084fc',
      tag: 'SPATIAL CONVERGENCE',
      description:
        'As dozens of witnesses report the same unfolding event, semantic similarity and geospatial clustering merge duplicate reports into a singular canonical incident record.',
      deliverables: [
        '24-hour sliding temporal cluster window',
        'Locality, city, and state geocoding alignment',
        'Accumulative need extraction and severity escalation',
      ],
      verificationNote:
        'Prevents operator alert fatigue and consolidates fragmented eyewitness vantage points.',
    },
    {
      id: 'verification',
      number: '03',
      title: 'Cross-Modal Evidence Audit',
      subtitle: 'Validating Currentness & Detecting Category Conflicts',
      icon: <Eye size={24} />,
      accentColor: '#9d4edd',
      tag: 'NEURAL CONFLICT AUDIT',
      description:
        'Before an incident escalates, optical character recognition and temporal reasoning cross-reference claims against video timestamps, flagging cross-modal discrepancies before human review.',
      deliverables: [
        'Video frame OCR temporal claim extraction',
        'Category compatibility matrix (e.g. Cyclone text vs. Earthquake video)',
        'Automatic policy flag: HUMAN_VERIFICATION_REQUIRED',
      ],
      verificationNote:
        'ResQ-Sense never prioritizes text over video or vice versa when signals contradict; human review is mandatory.',
    },
    {
      id: 'oversight',
      number: '04',
      title: 'Human Authority Verification',
      subtitle: 'Certified Command Boundary for Verification & Disposition',
      icon: <ShieldCheck size={24} />,
      accentColor: '#bbf451',
      tag: 'HUMAN-IN-THE-LOOP MANDATE',
      description:
        'AI algorithms propose findings; only authorized emergency commanders possess the legal and operational authority to approve, reject, or request further information on incidents.',
      deliverables: [
        'Role-gated Administrator Command Workspace',
        'Cryptographic audit trail with reason logging',
        'Explicit decision states: VERIFIED, REJECTED, NEEDS_MORE_INFO',
      ],
      verificationNote:
        'Zero automated emergency dispatches are permitted without human officer sign-off.',
    },
    {
      id: 'dispatch',
      number: '05',
      title: 'Authorized Tactical Dispatch',
      subtitle: 'Orchestrating Regional Emergency Response Logistics',
      icon: <Truck size={24} />,
      accentColor: '#ff7056',
      tag: 'LOGISTIC RESPONSE GRID',
      description:
        'Once verified, the engine calculates geodesic distances to catalogued regional resources—fire brigades, ambulances, specialized rescue teams—and compiles an actionable response plan.',
      deliverables: [
        'Catalogued regional disaster response units across India',
        'Dynamic search radius scaling up to 100 km',
        'Departmental need mapping (Medical, Fire, Search & Rescue)',
      ],
      verificationNote:
        'Commanders inspect resource proximity and execute live authorization with one click.',
    },
  ]

  return (
    <div
      className="resq-landing-wrapper"
      onMouseMove={handleMouseMove}
      ref={heroRef}
    >
      {/* Layer 0: Far Atmospheric Nebula & Deep Cosmos Parallax */}
      <div
        className="ambient-nebula-plum parallax-layer-far"
        style={{
          transform: `translate(${mousePos.x * 0.15}px, ${mousePos.y * 0.15}px)`,
        }}
      />
      <div
        className="ambient-nebula-violet parallax-layer-far"
        style={{
          transform: `translate(${-mousePos.x * 0.18}px, ${-mousePos.y * 0.18}px)`,
        }}
      />

      {/* Floating Incident-Photo Field Surrounding Brand Nameplate */}
      <div
        className="floating-incident-field"
        style={{
          transform: `translate(${mousePos.x * 0.12}px, ${mousePos.y * 0.12}px)`,
        }}
        aria-hidden="true"
      >
        {INCIDENT_PHOTO_TILES.map((tile) => (
          <div
            key={tile.id}
            className={`incident-photo-tile ${tile.shape} col-${tile.col} tile-flank-${tile.side}`}
            style={tile.style}
          >
            <div className="incident-photo-frame">
              <img
                src={tile.src}
                alt={tile.alt}
                className="incident-photo-img"
                loading="lazy"
              />
              <div className="incident-photo-tint" />
              <div className="incident-photo-caption">
                <span className="caption-dot" />
                <span className="caption-text">{tile.category}</span>
              </div>
            </div>
          </div>
        ))}
        {/* Soft Perimeter Vignette */}
        <div className="floating-field-vignette" />
      </div>

      {/* Layer 1: Mid Topographic Contours & Coordinate Grid Parallax */}
      <div
        className="topographic-grid-overlay parallax-layer-mid"
        style={{
          transform: `translate(${mousePos.x * 0.25}px, ${mousePos.y * 0.25}px)`,
        }}
      />

      {/* TOP STATUS & NAVIGATION BAR */}
      <nav className="landing-top-bar" aria-label="System Status & Quick Nav">
        <div className="telemetry-pill">
          <span className="telemetry-beacon" />
          <span className="telemetry-title">India Emergency Response Grid</span>
          <span className="telemetry-divider">/</span>
          <span className="telemetry-status">System Operational</span>
          <span className="telemetry-count">{incidentCount} Monitored</span>
        </div>

        <div className="landing-quick-nav">
          <a href="#gateways" className="quick-nav-link">
            Access Portals
          </a>
          <a href="#storytelling" className="quick-nav-link">
            Signal Lifecycle
          </a>
          <a href="#accuracy" className="quick-nav-link">
            Model Metrics
          </a>
          <a href="#oversight" className="quick-nav-link">
            Human Charter
          </a>
          <ThemeSelector />
        </div>
      </nav>

      {/* CENTERED BRAND IDENTITY FOCAL POINT */}
      <header className="centered-brand-focal">
        <div className="brand-crest-typography">
          <div className="brand-architectural-bracket">
            <span className="bracket-left">[</span>
            <span className="bracket-code">SYS_ID // 0846-GRID</span>
            <span className="bracket-right">]</span>
          </div>
          <h1 className="brand-crest-name">RESQ-SENSE</h1>
          <p className="brand-crest-tagline">
            Multimodal Crisis Intelligence &amp; Human-Authorized Response
          </p>
        </div>
      </header>

      {/* CINEMATIC HERO SECTION WITH 3D GEOSPATIAL CENTREPIECE */}
      <section className="landing-hero-cinematic" id="hero">
        {/* Layer 2: Core 3D Geospatial Centrepiece */}
        <div
          className="geospatial-centerpiece-container"
          style={{
            transform: `translate(${mousePos.x * 0.4}px, ${mousePos.y * 0.4}px) scale(${1 - scrollProgress * 0.12})`,
          }}
        >
          <canvas ref={canvasRef} className="geospatial-canvas" />

          {/* Floating Telemetry Heads-Up Badges */}
          <div
            className="hud-badge top-left"
            style={{
              transform: `translate(${-mousePos.x * 0.3}px, ${-mousePos.y * 0.3}px)`,
            }}
          >
            <span className="hud-dot orchid" />
            <span className="hud-label">TEXT_INGEST // ACTIVE</span>
          </div>

          <div
            className="hud-badge top-right"
            style={{
              transform: `translate(${mousePos.x * 0.3}px, ${-mousePos.y * 0.3}px)`,
            }}
          >
            <span className="hud-dot vermilion" />
            <span className="hud-label">DRONE_FEED // AERIAL TELEM</span>
          </div>

          <div
            className="hud-badge bottom-left"
            style={{
              transform: `translate(${-mousePos.x * 0.25}px, ${mousePos.y * 0.25}px)`,
            }}
          >
            <span className="hud-dot lime" />
            <span className="hud-label">VOICE_TRANSC // CONVERGING</span>
          </div>

          <div
            className="hud-badge bottom-right"
            style={{
              transform: `translate(${mousePos.x * 0.25}px, ${mousePos.y * 0.25}px)`,
            }}
          >
            <span className="hud-dot violet" />
            <span className="hud-label">SIGNAL_FUSION // MULTI-CHANNEL</span>
          </div>
        </div>

        {/* Layer 3: Foreground Typography & Operational Gateways */}
        <div
          className="hero-eyebrow-chip"
          style={{
            transform: `translate(${mousePos.x * 0.1}px, ${mousePos.y * 0.1}px)`,
          }}
        >
          <Radio size={14} className="eyebrow-icon" />
          <span>Next-Generation Disaster Intelligence Architecture</span>
        </div>

        <h2 className="hero-monumental-headline">
          When Every Second Matters,
          <br />
          <span className="headline-gradient-shimmer">
            Every Signal Must Converge.
          </span>
        </h2>

        <p className="hero-editorial-subtext">
          ResQ-Sense fuses citizen eyewitness reports, drone imagery, and
          emergency voice transcripts into verified situational truth—enforcing
          an inviolable human command authorization boundary before any physical
          response is deployed.
        </p>

        {/* PRIMARY ROLE ENTRY PORTALS */}
        <div className="gateways-grid-container" id="gateways">
          {/* Citizen Emergency Portal */}
          <div
            className="gateway-card citizen-gateway"
            onClick={() => onSelectRole('citizen')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onSelectRole('citizen')}
            aria-label="Enter Citizen Emergency Portal"
          >
            <div className="gateway-card-glow citizen-glow" />
            <div className="gateway-card-aura" />

            <div className="gateway-card-top">
              <div className="gateway-icon-badge citizen-badge">
                <Users size={22} />
              </div>
              <span className="gateway-role-tag">Citizen &amp; Witness</span>
            </div>

            <div className="gateway-content-body">
              <h3 className="gateway-card-title">Citizen Emergency Portal</h3>
              <p className="gateway-card-desc">
                Witnessed an unfolding crisis? Submit incident descriptions with
                photos, videos, or voice evidence, receive official tracking
                references, and monitor response progression in real time.
              </p>

              <div className="gateway-feature-badges">
                <span className="f-badge">Field Signal Ingest</span>
                <span className="f-badge">Private Reference ID</span>
                <span className="f-badge">Status Tracking</span>
              </div>
            </div>

            <button
              type="button"
              className="gateway-action-btn citizen-btn"
              onClick={(e) => {
                e.stopPropagation()
                onSelectRole('citizen')
              }}
            >
              <span>Enter Citizen Portal</span>
              <ArrowRight size={16} />
            </button>
          </div>

          {/* Authority Operations Hub */}
          <div
            className="gateway-card authority-gateway"
            onClick={() => onSelectRole('authority')}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onSelectRole('authority')}
            aria-label="Open Authority Command Workspace"
          >
            <div className="gateway-card-glow authority-glow" />
            <div className="gateway-card-aura" />

            <div className="gateway-card-top">
              <div className="gateway-icon-badge authority-badge">
                <ShieldCheck size={22} />
              </div>
              <span className="gateway-role-tag">Authorized Personnel</span>
            </div>

            <div className="gateway-content-body">
              <h3 className="gateway-card-title">Authority Operations Hub</h3>
              <p className="gateway-card-desc">
                Command center for emergency authorities. Inspect multimodal
                evidence, audit cross-modal conflicts, review nearest resource
                candidates, and explicitly authorize tactical response plans.
              </p>

              <div className="gateway-feature-badges">
                <span className="f-badge">Command Workspace</span>
                <span className="f-badge">Tactical Map</span>
                <span className="f-badge">Human-in-the-Loop Sign-off</span>
              </div>
            </div>

            <button
              type="button"
              className="gateway-action-btn authority-btn"
              onClick={(e) => {
                e.stopPropagation()
                onSelectRole('authority')
              }}
            >
              <span>Open Command Workspace</span>
              <ArrowUpRight size={16} />
            </button>
          </div>
        </div>

        {/* Scroll-Linked Signal Conduit Ray Leading Directly into Lifecycle */}
        <div className="scroll-signal-conduit" aria-hidden="true">
          <div className="conduit-line" />
          <div className="conduit-pulse-dot" />
          <span className="conduit-label">INTELLIGENCE CONVERGENCE CONDUIT</span>
        </div>
      </section>

      {/* CORE CAPABILITIES STRIP */}
      <section className="capabilities-strip telemetry-metrics-strip" aria-label="Core Capabilities">
        <div className="capability-card metric-box">
          <div className="capability-top-row">
            <div className="capability-icon-wrap metric-icon-wrap orchid">
              <Layers size={20} className="m-icon orchid" />
            </div>
            <span className="capability-index">01</span>
          </div>
          <div className="capability-text-group metric-text-group">
            <h3 className="capability-title">Multimodal Input</h3>
            <p className="capability-desc">3 Input Modalities — Text, Imagery, Audio</p>
          </div>
        </div>

        <div className="capability-card metric-box">
          <div className="capability-top-row">
            <div className="capability-icon-wrap metric-icon-wrap lime">
              <ShieldAlert size={20} className="m-icon lime" />
            </div>
            <span className="capability-index">02</span>
          </div>
          <div className="capability-text-group metric-text-group">
            <h3 className="capability-title">Evidence-Based Verification</h3>
            <p className="capability-desc">Reviewing reports and identifying conflicting information</p>
          </div>
        </div>

        <div className="capability-card metric-box">
          <div className="capability-top-row">
            <div className="capability-icon-wrap metric-icon-wrap coral">
              <Compass size={20} className="m-icon coral" />
            </div>
            <span className="capability-index">03</span>
          </div>
          <div className="capability-text-group metric-text-group">
            <h3 className="capability-title">Geospatial Intelligence</h3>
            <p className="capability-desc">Connecting incidents, locations, and response resources</p>
          </div>
        </div>

        <div className="capability-card metric-box">
          <div className="capability-top-row">
            <div className="capability-icon-wrap metric-icon-wrap violet">
              <ShieldCheck size={20} className="m-icon violet" />
            </div>
            <span className="capability-index">04</span>
          </div>
          <div className="capability-text-group metric-text-group">
            <h3 className="capability-title">Human-Authorized Response</h3>
            <p className="capability-desc">Keeping critical response decisions under human authority</p>
          </div>
        </div>
      </section>

      {/* SCROLL-DRIVEN 5-STAGE STORYTELLING SECTION */}
      <section
        className="storytelling-section-container"
        id="storytelling"
        aria-labelledby="story-section-title"
      >
        <div className="story-section-header">
          <div className="story-tag-pill">
            <Sparkles size={14} />
            <span>Crisis Intelligence Lifecycle</span>
          </div>
          <h2 id="story-section-title" className="story-main-heading">
            How Signals Become Authorized Action
          </h2>
          <p className="story-sub-heading">
            Five synchronized stages transform noisy eyewitness field
            observations into verified, human-authorized emergency operations.
          </p>
        </div>

        {/* Interactive Stage Selector Bar */}
        <div
          className="stage-tabs-selector"
          role="tablist"
          aria-label="Intelligence Lifecycle Stages"
        >
          {stages.map((stg, idx) => (
            <button
              key={stg.id}
              type="button"
              role="tab"
              aria-selected={activeStage === idx}
              aria-controls={`stage-panel-${stg.id}`}
              id={`stage-tab-${stg.id}`}
              className={`stage-tab-btn ${activeStage === idx ? 'active' : ''}`}
              onClick={() => setActiveStage(idx)}
            >
              <span className="tab-number">{stg.number}</span>
              <span className="tab-name">{stg.title}</span>
              {activeStage === idx && <span className="tab-active-indicator" />}
            </button>
          ))}
        </div>

        {/* Active Stage Detailed Display Card */}
        <div
          className="story-stage-display-card"
          id={`stage-panel-${stages[activeStage].id}`}
          role="tabpanel"
          aria-labelledby={`stage-tab-${stages[activeStage].id}`}
        >
          <div className="stage-card-columns">
            {/* Left: Stage Overview */}
            <div className="stage-overview-column">
              <div className="stage-badge-row">
                <span className="stage-index-badge">
                  Stage {stages[activeStage].number} of 05
                </span>
                <span className="stage-tag-badge">
                  {stages[activeStage].tag}
                </span>
              </div>

              <h3 className="stage-card-title">
                {stages[activeStage].title}
              </h3>
              <h4 className="stage-card-subtitle">
                {stages[activeStage].subtitle}
              </h4>

              <p className="stage-card-description">
                {stages[activeStage].description}
              </p>

              <div className="stage-deliverables-box">
                <span className="deliverables-heading">Key Architecture:</span>
                <ul>
                  {stages[activeStage].deliverables.map((item, dIdx) => (
                    <li key={dIdx}>
                      <CheckCircle2 size={15} className="d-icon" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="stage-note-box">
                <span className="note-lbl">Operational Guarantee:</span>
                <p>{stages[activeStage].verificationNote}</p>
              </div>
            </div>

            {/* Right: Architectural Visualization Mockup */}
            <div className="stage-visual-column">
              <div className="stage-preview-window">
                <div className="window-header">
                  <div className="window-dots">
                    <span className="dot red" />
                    <span className="dot yellow" />
                    <span className="dot green" />
                  </div>
                  <span className="window-title">
                    resqsense://pipeline/stage_{stages[activeStage].number}
                  </span>
                </div>

                <div className="window-body">
                  {activeStage === 0 && (
                    <div className="preview-pipeline-content">
                      <div className="preview-stream-node text-stream">
                        <FileText size={18} />
                        <div>
                          <strong>Witness Text Signal</strong>
                          <p>"Massive flooding near river bridge, families stranded."</p>
                        </div>
                      </div>
                      <div className="preview-stream-node image-stream">
                        <Video size={18} />
                        <div>
                          <strong>Drone &amp; Video Imagery</strong>
                          <p>11.2s aerial feed • 336 frames sampled</p>
                        </div>
                      </div>
                      <div className="preview-stream-node audio-stream">
                        <Volume2 size={18} />
                        <div>
                          <strong>Emergency Voice Signal</strong>
                          <p>Acoustic transcript extraction active</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeStage === 1 && (
                    <div className="preview-pipeline-content">
                      <div className="preview-convergence-node">
                        <div className="convergence-center">
                          <Compass size={24} />
                          <span>Canonical Incident</span>
                        </div>
                        <div className="converging-reports">
                          <span className="c-chip">Report #REP-8812 (Locality Match)</span>
                          <span className="c-chip">Report #REP-8814 (Semantic 94%)</span>
                          <span className="c-chip">Report #REP-8819 (GPS 0.12km)</span>
                        </div>
                      </div>
                      <div className="convergence-summary">
                        <strong>3 Eyewitness Signals Merged</strong>
                        <p>Status: Consolidated into 1 Incident Record</p>
                      </div>
                    </div>
                  )}

                  {activeStage === 2 && (
                    <div className="preview-pipeline-content">
                      <div className="conflict-audit-card">
                        <div className="audit-row ok">
                          <CheckCircle2 size={16} />
                          <span>OCR Temporal Consistency: Passed</span>
                        </div>
                        <div className="audit-row alert">
                          <ShieldAlert size={16} />
                          <span>Cross-Modal Category Check: Verified</span>
                        </div>
                        <div className="audit-verdict-box">
                          <span className="v-tag">Audit Verdict</span>
                          <strong>CURRENT (Confidence 0.94)</strong>
                          <p>Action: PROCEED_TO_HUMAN_OVERSIGHT</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeStage === 3 && (
                    <div className="preview-pipeline-content">
                      <div className="authority-review-preview">
                        <div className="preview-incident-header">
                          <span className="badge-critical">CRITICAL</span>
                          <strong>Incident #INC-9482 • Guwahati</strong>
                        </div>
                        <p className="review-prompt">
                          Certified Commander Decision Required:
                        </p>
                        <div className="decision-buttons-row">
                          <span className="decision-btn approve">APPROVE (VERIFIED)</span>
                          <span className="decision-btn info">MORE INFO</span>
                          <span className="decision-btn reject">REJECT</span>
                        </div>
                        <span className="audit-stamp">
                          Zero Autonomous Dispatch • Mandatory Cryptographic Sign-Off
                        </span>
                      </div>
                    </div>
                  )}

                  {activeStage === 4 && (
                    <div className="preview-pipeline-content">
                      <div className="dispatch-plan-preview">
                        <div className="plan-header">
                          <Truck size={16} />
                          <strong>Recommended Tactical Assets (25km Radius)</strong>
                        </div>
                        <div className="resource-rows">
                          <div className="res-row">
                            <span>SDRF Water Rescue Unit 02</span>
                            <strong className="dist">3.8 km away</strong>
                          </div>
                          <div className="res-row">
                            <span>Civil Defence Emergency Medical</span>
                            <strong className="dist">6.1 km away</strong>
                          </div>
                          <div className="res-row">
                            <span>Fire &amp; Rescue Brigade #07</span>
                            <strong className="dist">8.4 km away</strong>
                          </div>
                        </div>
                        <div className="execute-cta-box">
                          <span>Authorized for Immediate Mobilization</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* MULTIMODAL MODEL EVALUATION & ACCURACY SECTION */}
      <section
        className="multimodal-accuracy-section"
        id="accuracy"
        aria-labelledby="accuracy-section-title"
      >
        <div className="story-section-header">
          <div className="story-tag-pill">
            <Activity size={14} />
            <span>Empirical AI Benchmarks &amp; Limitations</span>
          </div>
          <h2 id="accuracy-section-title" className="story-main-heading">
            Multimodal Model Accuracy &amp; Evaluation
          </h2>
          <p className="story-sub-heading">
            Transparent reporting of verified test-set performance, validation contexts, and operational limitations across our crisis perception pipelines.
          </p>
        </div>

        {/* Operational Ground Truth Disclaimer */}
        <div className="accuracy-disclaimer-card" role="note">
          <AlertCircle size={20} className="disclaimer-icon" />
          <div className="disclaimer-text">
            <strong>Critical Distinction: Benchmark Accuracy vs. Prediction Confidence</strong>
            <p>
              Confidence scores or softmax probabilities output during live inference represent model certainty under specific inputs—they are <em>never</em> represented as model accuracy. True accuracy is strictly evaluated against standardized, held-out ground truth crisis datasets. Where rigorous benchmark data is unavailable in this environment, metrics are explicitly labeled <strong>Evaluation pending</strong>.
            </p>
          </div>
        </div>

        {/* 4 Modalities Cards Grid */}
        <div className="accuracy-cards-grid">
          {/* Card 1: Text Crisis Detection */}
          <div className="accuracy-card verified-metric">
            <div className="accuracy-card-header">
              <div className="modality-badge text">
                <FileText size={16} />
                <span>Text Modality</span>
              </div>
              <span className="eval-status-pill verified">Validated Benchmark</span>
            </div>

            <h3 className="model-name">Emergency Binary Classifier</h3>
            <p className="model-arch">TF-IDF Vectorizer + Regularized Logistic Regression (10,000 features, n-grams 1–2)</p>

            <div className="metric-highlight-box">
              <span className="metric-val">92.76%</span>
              <span className="metric-lbl">Holdout Test Set Accuracy</span>
            </div>

            <div className="metric-details-list">
              <div className="metric-detail-row">
                <span className="detail-lbl">Dataset</span>
                <span className="detail-val">CrisisLex &amp; CrisisNLP Disaster Corpora</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Evaluation Context</span>
                <span className="detail-val">Stratified 5-fold cross-validation on labeled eyewitness emergency dispatches</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Limitations</span>
                <span className="detail-val">English vocabulary baseline; shortened SMS shorthand and regional dialect transliterations (e.g. Hinglish) may exhibit reduced sensitivity.</span>
              </div>
            </div>
          </div>

          {/* Card 2: Humanitarian Info Type Categorization */}
          <div className="accuracy-card verified-metric">
            <div className="accuracy-card-header">
              <div className="modality-badge text">
                <Layers size={16} />
                <span>Text Categorization</span>
              </div>
              <span className="eval-status-pill verified">Validated Benchmark</span>
            </div>

            <h3 className="model-name">Humanitarian Information Classifier</h3>
            <p className="model-arch">TF-IDF Multi-Class Classifier (7 Humanitarian Action Categories)</p>

            <div className="metric-highlight-box">
              <span className="metric-val">71.42%</span>
              <span className="metric-lbl">Multi-Class Categorization Accuracy</span>
            </div>

            <div className="metric-details-list">
              <div className="metric-detail-row">
                <span className="detail-lbl">Dataset</span>
                <span className="detail-val">CrisisNLP Humanitarian Response Test Collection</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Evaluation Context</span>
                <span className="detail-val">Multi-class classification evaluating urgent categories: Injured/Dead, Infrastructure Damage, Caution/Advice, Donations</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Limitations</span>
                <span className="detail-val">Skewed sample distribution in disaster logs; composite messages expressing multiple concurrent needs can favor the primary syntactic clause.</span>
              </div>
            </div>
          </div>

          {/* Card 3: Visual Hazard Analysis (Image & Drone Video) */}
          <div className="accuracy-card pending-metric">
            <div className="accuracy-card-header">
              <div className="modality-badge visual">
                <Video size={16} />
                <span>Vision &amp; Video Modality</span>
              </div>
              <span className="eval-status-pill pending">Evaluation pending</span>
            </div>

            <h3 className="model-name">Visual Hazard &amp; Aerial Classifier</h3>
            <p className="model-arch">OpenAI CLIP ViT-B/32 Zero-Shot Cosine Embeddings &amp; Temporal Frame Sampling</p>

            <div className="metric-highlight-box pending">
              <span className="metric-val pending">Evaluation pending</span>
              <span className="metric-lbl">Formal Precision / Recall Benchmark</span>
            </div>

            <div className="metric-details-list">
              <div className="metric-detail-row">
                <span className="detail-lbl">Required Evaluation</span>
                <span className="detail-val">End-to-end mAP &amp; Top-1 Accuracy benchmarking on standardized disaster image/video datasets (e.g. CrisisMMD, UCF-Crime aerial subsets).</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Live Indicator</span>
                <span className="detail-val">Zero-shot prompt cosine similarities (e.g. 0.88–0.94) are advisory heuristics indicating semantic proximity, not verified dataset accuracy.</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Limitations</span>
                <span className="detail-val">Susceptible to occlusion, nighttime imagery, smoke density, and atypical aerial camera angles without domain-specific fine-tuning.</span>
              </div>
            </div>
          </div>

          {/* Card 4: Audio Speech Recognition & Acoustics */}
          <div className="accuracy-card pending-metric">
            <div className="accuracy-card-header">
              <div className="modality-badge audio">
                <Volume2 size={16} />
                <span>Audio Modality</span>
              </div>
              <span className="eval-status-pill pending">Evaluation pending</span>
            </div>

            <h3 className="model-name">Emergency Speech &amp; Voice Ingestion</h3>
            <p className="model-arch">Whisper CTC / Autoregressive ASR + Keyword Emergency Heuristics</p>

            <div className="metric-highlight-box pending">
              <span className="metric-val pending">Evaluation pending</span>
              <span className="metric-lbl">Acoustic Word Error Rate (WER)</span>
            </div>

            <div className="metric-details-list">
              <div className="metric-detail-row">
                <span className="detail-lbl">Required Evaluation</span>
                <span className="detail-val">Standardized WER and Keyword Spotting (KWS) benchmark under adverse signal-to-noise ratios (SNR &lt; 5 dB, rain, siren, distress noise).</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Live Indicator</span>
                <span className="detail-val">Whisper produces rich phonetic transcripts; however, field accuracy under high-noise Indian disaster environments remains in offline testing.</span>
              </div>
              <div className="metric-detail-row">
                <span className="detail-lbl">Limitations</span>
                <span className="detail-val">Wind noise, heavy rain on microphone, screaming, and mixed regional code-switching can degrade raw transcription fidelity.</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* HUMAN OVERSIGHT CHARTER STATEMENT */}
      <section className="oversight-charter-section" id="oversight">
        <div className="charter-crest">
          <ShieldCheck size={32} />
        </div>
        <div className="charter-body">
          <span className="charter-tag">THE RESQ-SENSE CHARTER</span>
          <h3 className="charter-headline">
            Artificial Intelligence Accelerates Perception.
            <br />
            Certified Humans Command Action.
          </h3>
          <p className="charter-paragraph">
            In life-critical emergencies, automated deployment without human
            judgment introduces unacceptable risk. ResQ-Sense enforces an
            uncompromising ethical and operational boundary: intelligent
            algorithms ingest, cluster, and verify evidence, but only authorized
            human commanders hold the authority to approve response plans and
            dispatch field responders.
          </p>
        </div>
      </section>

      {/* REFINED SYSTEM FOOTER */}
      <footer className="landing-footer-refined">
        <div className="footer-top-row">
          <div className="footer-brand-lockup">
            <div className="footer-logo-dot" />
            <span className="footer-brand-name">ResQ-Sense</span>
            <span className="footer-brand-version">v2.4 Core</span>
          </div>

          <div className="footer-system-status">
            <span className="status-indicator-live" />
            <span>National Crisis Intelligence Grid • Active</span>
          </div>
        </div>

        <div className="footer-bottom-row">
          <p className="footer-legal">
            ResQ-Sense Emergency Intelligence Network. All response plans require
            explicit human verification before deployment under national emergency protocols.
          </p>
          <div className="footer-links">
            <button
              type="button"
              className="footer-text-btn"
              onClick={() => onSelectRole('citizen')}
            >
              Citizen Portal
            </button>
            <span className="footer-sep">•</span>
            <button
              type="button"
              className="footer-text-btn"
              onClick={() => onSelectRole('authority')}
            >
              Authority Ops
            </button>
          </div>
        </div>
      </footer>
    </div>
  )
}
