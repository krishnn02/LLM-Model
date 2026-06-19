/**
 * OmniFood - Session Management Hook
 * Manages authentication state for food delivery platform accounts.
 * Handles login flow, session status, and disconnection via REST API.
 */

import { useState, useCallback, useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || ''

export interface PlatformSession {
  platform: string
  connected: boolean
  user_info: string | null
  phone: string | null
  membership: string | null
  connected_at: string | null
  login_in_progress: boolean
}

export type LoginStatus = 'idle' | 'opening' | 'waiting' | 'confirming' | 'error'

export interface UseSessionReturn {
  sessions: Record<string, PlatformSession>
  loginStatus: Record<string, LoginStatus>
  fetchSessions: () => Promise<void>
  startLogin: (platform: string) => Promise<void>
  confirmLogin: (platform: string) => Promise<void>
  cancelLogin: (platform: string) => Promise<void>
  disconnect: (platform: string) => Promise<void>
  errors: Record<string, string | null>
  loading: boolean
}

export function useSession(): UseSessionReturn {
  const [sessions, setSessions] = useState<Record<string, PlatformSession>>({})
  const [loginStatus, setLoginStatus] = useState<Record<string, LoginStatus>>({})
  const [errors, setErrors] = useState<Record<string, string | null>>({})
  const [loading, setLoading] = useState(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/api/sessions`)
      if (!res.ok) throw new Error('Failed to fetch sessions')
      const data = await res.json()
      if (mountedRef.current) {
        setSessions(data.sessions || {})
      }
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [])

  // Load sessions on mount
  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const startLogin = useCallback(async (platform: string) => {
    const key = platform.toLowerCase()
    setLoginStatus(prev => ({ ...prev, [key]: 'opening' }))
    setErrors(prev => ({ ...prev, [key]: null }))

    try {
      const res = await fetch(`${API_BASE}/api/sessions/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: key }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to start login')
      }

      if (mountedRef.current) {
        setLoginStatus(prev => ({ ...prev, [key]: 'waiting' }))
      }
    } catch (err: any) {
      if (mountedRef.current) {
        setLoginStatus(prev => ({ ...prev, [key]: 'error' }))
        setErrors(prev => ({ ...prev, [key]: err.message }))
      }
    }
  }, [])

  const confirmLogin = useCallback(async (platform: string) => {
    const key = platform.toLowerCase()
    setLoginStatus(prev => ({ ...prev, [key]: 'confirming' }))
    setErrors(prev => ({ ...prev, [key]: null }))

    try {
      const res = await fetch(`${API_BASE}/api/sessions/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: key }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to confirm login')
      }

      // Refresh sessions
      await fetchSessions()

      if (mountedRef.current) {
        setLoginStatus(prev => ({ ...prev, [key]: 'idle' }))
      }
    } catch (err: any) {
      if (mountedRef.current) {
        setLoginStatus(prev => ({ ...prev, [key]: 'error' }))
        setErrors(prev => ({ ...prev, [key]: err.message }))
      }
    }
  }, [fetchSessions])

  const cancelLogin = useCallback(async (platform: string) => {
    const key = platform.toLowerCase()

    try {
      await fetch(`${API_BASE}/api/sessions/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: key }),
      })
    } catch {
      // Silently handle
    }

    if (mountedRef.current) {
      setLoginStatus(prev => ({ ...prev, [key]: 'idle' }))
      setErrors(prev => ({ ...prev, [key]: null }))
    }
  }, [])

  const disconnect = useCallback(async (platform: string) => {
    const key = platform.toLowerCase()
    setErrors(prev => ({ ...prev, [key]: null }))

    try {
      const res = await fetch(`${API_BASE}/api/sessions/disconnect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: key }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to disconnect')
      }

      // Refresh sessions
      await fetchSessions()
    } catch (err: any) {
      if (mountedRef.current) {
        setErrors(prev => ({ ...prev, [key]: err.message }))
      }
    }
  }, [fetchSessions])

  return {
    sessions,
    loginStatus,
    fetchSessions,
    startLogin,
    confirmLogin,
    cancelLogin,
    disconnect,
    errors,
    loading,
  }
}
