/**
 * OmniFood Agent - Search History Hook
 * Persists recent searches in localStorage for quick re-use.
 */

import { useState, useCallback, useEffect } from 'react'
import type { HistoryEntry } from '../types'

const STORAGE_KEY = 'omnifood_history'
const MAX_HISTORY = 10

export function useHistory() {
  const [history, setHistory] = useState<HistoryEntry[]>([])

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        setHistory(JSON.parse(stored))
      }
    } catch {
      // Silently fail if localStorage is unavailable
    }
  }, [])

  const addEntry = useCallback((query: string, winner?: string) => {
    setHistory((prev) => {
      // Remove duplicate if exists
      const filtered = prev.filter((e) => e.query.toLowerCase() !== query.toLowerCase())
      const updated = [
        { query, timestamp: Date.now(), winner },
        ...filtered,
      ].slice(0, MAX_HISTORY)

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
      } catch {
        // Silently fail
      }

      return updated
    })
  }, [])

  const removeEntry = useCallback((index: number) => {
    setHistory((prev) => {
      const updated = prev.filter((_, i) => i !== index)
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
      } catch {
        // Silently fail
      }
      return updated
    })
  }, [])

  const clearHistory = useCallback(() => {
    setHistory([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Silently fail
    }
  }, [])

  return { history, addEntry, removeEntry, clearHistory }
}
