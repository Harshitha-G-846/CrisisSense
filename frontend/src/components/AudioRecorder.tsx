import React, { useState, useRef, useEffect } from 'react'
import { Mic, Square, RotateCcw, Volume2, AlertCircle, CheckCircle2 } from 'lucide-react'

interface AudioRecorderProps {
  onAudioReady: (file: File | null) => void
  disabled?: boolean
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({ onAudioReady, disabled = false }) => {
  const [status, setStatus] = useState<'idle' | 'recording' | 'recorded'>('idle')
  const [duration, setDuration] = useState<number>(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    return () => {
      // Clean up timer and streams on unmount
      if (timerRef.current) clearInterval(timerRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }
    }
  }, [audioUrl])

  const formatTime = (secs: number) => {
    const mins = Math.floor(secs / 60)
    const remaining = secs % 60
    return `${mins.toString().padStart(2, '0')}:${remaining.toString().padStart(2, '0')}`
  }

  const startRecording = async () => {
    setErrorMessage(null)

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErrorMessage('Audio recording is not supported on this browser or platform.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      // Choose supported MIME type
      const mimeTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
      let selectedMime = ''
      for (const m of mimeTypes) {
        if (MediaRecorder.isTypeSupported(m)) {
          selectedMime = m
          break
        }
      }

      const recorder = selectedMime
        ? new MediaRecorder(stream, { mimeType: selectedMime })
        : new MediaRecorder(stream)

      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (evt) => {
        if (evt.data && evt.data.size > 0) {
          chunksRef.current.push(evt.data)
        }
      }

      recorder.onstop = () => {
        const recordedBlob = new Blob(chunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        })

        if (recordedBlob.size === 0) {
          setErrorMessage('Recorded audio is empty (0 bytes). Please try recording again.')
          setStatus('idle')
          onAudioReady(null)
          return
        }

        const ext = recorder.mimeType.includes('ogg') ? '.ogg' : '.webm'
        const audioFile = new File([recordedBlob], `voice_report_${Date.now()}${ext}`, {
          type: recordedBlob.type,
        })

        const url = URL.createObjectURL(recordedBlob)
        setAudioUrl(url)
        setStatus('recorded')
        onAudioReady(audioFile)
      }

      recorder.start(250) // collect chunks every 250ms
      setStatus('recording')
      setDuration(0)

      timerRef.current = window.setInterval(() => {
        setDuration((prev) => prev + 1)
      }, 1000)
    } catch (err: unknown) {
      const error = err as Error
      if (
        error.name === 'NotAllowedError' ||
        error.name === 'PermissionDeniedError' ||
        error.message?.includes('Permission denied')
      ) {
        setErrorMessage(
          'Microphone permission denied. Please allow microphone access in your browser settings to record voice reports.',
        )
      } else {
        setErrorMessage(`Microphone error: ${error.message || 'Unable to access audio device.'}`)
      }
      setStatus('idle')
    }
  }

  const stopRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
  }

  const handleReRecord = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
      setAudioUrl(null)
    }
    setDuration(0)
    setStatus('idle')
    setErrorMessage(null)
    onAudioReady(null)
  }

  return (
    <div
      className="audio-recorder-widget"
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-medium)',
        borderRadius: 'var(--radius-md)',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Volume2 size={18} color="var(--accent-secondary)" aria-hidden="true" />
          <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
            Voice Incident Recorder
          </span>
        </div>
        {status === 'recording' && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              fontWeight: 700,
              color: 'var(--color-vermilion)',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: 'var(--color-vermilion)',
                animation: 'pulse 1s infinite alternate',
              }}
            />
            Recording: {formatTime(duration)}
          </span>
        )}
        {status === 'recorded' && (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--status-verified)',
            }}
          >
            <CheckCircle2 size={14} /> Ready ({formatTime(duration)})
          </span>
        )}
      </div>

      {errorMessage && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid var(--severity-critical)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontSize: '12px',
            color: 'var(--text-primary)',
          }}
        >
          <AlertCircle size={16} color="var(--severity-critical)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>{errorMessage}</span>
        </div>
      )}

      {status === 'idle' && (
        <button
          type="button"
          onClick={startRecording}
          disabled={disabled}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            background: 'var(--palette-coffee-bean)',
            color: '#fcf9f5',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 16px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.6 : 1,
            transition: 'opacity 0.2s',
          }}
        >
          <Mic size={16} aria-hidden="true" />
          <span>Start Audio Recording</span>
        </button>
      )}

      {status === 'recording' && (
        <button
          type="button"
          onClick={stopRecording}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            background: 'var(--severity-critical)',
            color: '#ffffff',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 16px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <Square size={16} fill="currentColor" aria-hidden="true" />
          <span>Stop Recording</span>
        </button>
      )}

      {status === 'recorded' && audioUrl && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <audio
            controls
            src={audioUrl}
            style={{ width: '100%', height: '36px', borderRadius: 'var(--radius-sm)' }}
          />
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={handleReRecord}
              disabled={disabled}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'transparent',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-sm)',
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <RotateCcw size={14} aria-hidden="true" />
              <span>Re-record</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
