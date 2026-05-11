/**
 * OmniFood Agent - WebSocket Hook
 * Manages real-time connection to the FastAPI backend for streaming agent logs.
 */

import { useState, useRef, useCallback } from 'react'
import type { LogMessage, AgentResult, ConnectionStatus } from '../types'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/agent'

interface UseAgentReturn {
  logs: LogMessage[]
  result: AgentResult | null
  status: ConnectionStatus
  error: string | null
  search: (query: string) => void
  reset: () => void
}

export function useAgent(): UseAgentReturn {
  const [logs, setLogs] = useState<LogMessage[]>([])
  const [result, setResult] = useState<AgentResult | null>(null)
  const [status, setStatus] = useState<ConnectionStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const reset = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setLogs([])
    setResult(null)
    setStatus('idle')
    setError(null)
  }, [])

  const search = useCallback((query: string) => {
    // Cleanup previous connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    setLogs([])
    setResult(null)
    setError(null)
    setStatus('connecting')

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('connected')
      // Send query to the backend
      ws.send(JSON.stringify({ query }))
      setStatus('streaming')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'log':
            setLogs((prev) => [...prev, { type: 'log', message: data.message }])
            break

          case 'error':
            setError(data.message)
            setLogs((prev) => [
              ...prev,
              { type: 'error', message: `❌ Error: ${data.message}` },
            ])
            setStatus('error')
            break

          case 'result':
            setResult(data.data as AgentResult)
            break

          case 'done':
            setStatus('done')
            break

          default:
            console.warn('Unknown message type:', data.type)
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onerror = (event) => {
      console.error('WebSocket error:', event)
      setError('Connection error — is the backend running on port 8000?')
      setStatus('error')
      setLogs((prev) => [
        ...prev,
        {
          type: 'error',
          message: '❌ WebSocket connection failed. Make sure the backend is running (python main.py)',
        },
      ])
    }

    ws.onclose = (event) => {
      if (status !== 'done' && status !== 'error') {
        // Unexpected close
        if (event.code !== 1000) {
          setStatus('error')
          setError('Connection closed unexpectedly')
        }
      }
    }
  }, [])

  return { logs, result, status, error, search, reset }
}
