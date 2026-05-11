import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface FeatureCardProps {
  icon: ReactNode
  title: string
  description: string
  delay?: number
}

export default function FeatureCard({ icon, title, description, delay = 0 }: FeatureCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 25 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay, duration: 0.5 }}
      className="glass-card glass-card-hover p-7 flex flex-col gap-4 cursor-default"
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, rgba(108,99,255,0.15), rgba(0,212,170,0.15))',
          color: '#6c63ff',
        }}
      >
        {icon}
      </div>
      <h3 className="text-lg font-semibold" style={{ color: '#e8e8ed' }}>
        {title}
      </h3>
      <p className="text-sm leading-relaxed" style={{ color: '#8888a0' }}>
        {description}
      </p>
    </motion.div>
  )
}
