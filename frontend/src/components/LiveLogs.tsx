import { useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Terminal, Loader2, AlertCircle } from 'lucide-react'
import type { LogMessage } from '../types'

interface LiveLogsProps {
  logs: LogMessage[]
  isSearching: boolean
}

export default function LiveLogs({ logs, isSearching }: LiveLogsProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  const getLogColor = (log: LogMessage): string => {
    if (log.type === 'error') return '#ff6b6b'
    if (log.message.includes('✅')) return '#00d4aa'
    if (log.message.includes('🏆')) return '#ffd700'
    if (log.message.includes('🧠')) return '#ffd700'
    if (log.message.includes('💡')) return '#ffd700'
    if (log.message.includes('⚠️')) return '#fc8019'
    if (log.message.includes('❌')) return '#ff6b6b'
    if (log.message.includes('🔴')) return '#e23744'
    if (log.message.includes('🟠')) return '#fc8019'
    if (log.message.includes('🚀')) return '#6c63ff'
    if (log.message.includes('📋')) return '#6c63ff'
    return '#8888a0'
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Terminal size={16} style={{ color: '#00d4aa' }} />
        <span className="text-sm font-semibold" style={{ color: '#e8e8ed' }}>Live Agent Logs</span>
        {isSearching && (
          <Loader2 size={14} className="animate-spin" style={{ color: '#6c63ff' }} />
        )}
        <span className="text-xs ml-auto" style={{ color: '#555570' }}>
          {logs.length} events
        </span>
      </div>

      <div
        ref={scrollRef}
        className="log-terminal p-5 h-[420px] overflow-y-auto"
      >
        {logs.length === 0 && !isSearching && (
          <div className="flex items-center justify-center h-full text-sm" style={{ color: '#555570' }}>
            Agent logs will stream here in real-time...
          </div>
        )}

        {logs.length === 0 && isSearching && (
          <div className="flex items-center justify-center h-full gap-2 text-sm" style={{ color: '#6c63ff' }}>
            <Loader2 size={16} className="animate-spin" />
            Connecting to agent...
          </div>
        )}

        <AnimatePresence>
          {logs.map((log, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25 }}
              className="log-line py-1"
              style={{ color: getLogColor(log) }}
            >
              {log.type === 'error' && <AlertCircle size={12} className="inline mr-1" />}
              {log.message}
            </motion.div>
          ))}
        </AnimatePresence>

        {isSearching && logs.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 mt-2"
          >
            <span className="w-2 h-2 rounded-full animate-blink" style={{ background: '#6c63ff' }} />
            <span className="text-xs" style={{ color: '#555570' }}>Processing...</span>
          </motion.div>
        )}
      </div>
    </div>
  )
}
