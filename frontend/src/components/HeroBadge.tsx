import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

export default function HeroBadge() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium"
      style={{
        background: 'linear-gradient(135deg, rgba(108,99,255,0.12), rgba(0,212,170,0.12))',
        border: '1px solid rgba(108,99,255,0.2)',
        color: '#a09cff',
      }}
    >
      <Sparkles size={14} style={{ color: '#6c63ff' }} />
      AI-Powered Food Price Aggregator
      <span className="w-1.5 h-1.5 rounded-full animate-blink" style={{ background: '#00d4aa' }} />
    </motion.div>
  )
}
