import { motion } from 'framer-motion'
import { Trophy, Clock, BadgePercent, CreditCard, Tag, Truck, AlertTriangle } from 'lucide-react'
import type { AgentResult, PlatformResult } from '../types'

interface DecisionCardProps {
  result: AgentResult | null
}

function PlatformRow({ data, isWinner }: { data: PlatformResult | undefined; isWinner: boolean }) {
  if (!data) return null

  const platformColors: Record<string, string> = {
    Zomato: '#e23744',
    Swiggy: '#fc8019',
    EatSure: '#2ecc71',
  }
  const platformName = data.platform || 'Unknown'
  const color = platformColors[platformName] || '#6c63ff'
  const hasError = !!data.error || data.final_total === 0 || data.final_total === undefined

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="glass-card p-5 relative overflow-hidden"
      style={
        hasError
          ? { border: '1px solid rgba(255,107,107,0.2)', opacity: 0.7 }
          : isWinner
          ? { border: '1px solid rgba(0,212,170,0.4)' }
          : {}
      }
    >
      {isWinner && !hasError && (
        <div className="absolute top-3 right-3">
          <span className="winner-badge flex items-center gap-1">
            <Trophy size={12} /> BEST DEAL
          </span>
        </div>
      )}

      {hasError && (
        <div className="absolute top-3 right-3">
          <span className="flex items-center gap-1 text-xs px-2 py-1 rounded-full" style={{ background: 'rgba(255,107,107,0.15)', color: '#ff6b6b' }}>
            <AlertTriangle size={12} /> Unavailable
          </span>
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold"
          style={{ background: `${color}22`, color }}
        >
          {platformName.charAt(0)}
        </div>
        <div>
          <h4 className="text-base font-semibold" style={{ color: '#e8e8ed' }}>
            {platformName}
          </h4>
          {data.membership && (
            <span className="text-xs" style={{ color }}>
              {data.membership} Active
            </span>
          )}
        </div>
      </div>

      {hasError ? (
        <div className="text-sm py-4 text-center" style={{ color: '#ff6b6b' }}>
          <AlertTriangle size={20} className="mx-auto mb-2" />
          <p>Could not fetch prices</p>
          <p className="text-xs mt-1" style={{ color: '#555570' }}>
            {data.error ? data.error.substring(0, 80) : 'Scraping failed or login required'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-2" style={{ color: '#8888a0' }}>
            <CreditCard size={14} />
            <span>Base Price</span>
          </div>
          <div className="text-right font-medium" style={{ color: '#e8e8ed' }}>
            ₹{data.base_price}
          </div>

          <div className="flex items-center gap-2" style={{ color: '#8888a0' }}>
            <Tag size={14} />
            <span>Taxes & Fees</span>
          </div>
          <div className="text-right font-medium" style={{ color: '#e8e8ed' }}>
            +₹{data.taxes}
          </div>

          <div className="flex items-center gap-2" style={{ color: '#00d4aa' }}>
            <BadgePercent size={14} />
            <span>Discount</span>
          </div>
          <div className="text-right font-medium" style={{ color: '#00d4aa' }}>
            -₹{data.discount}
          </div>

          {data.coupon_applied && (
            <>
              <div className="flex items-center gap-2 text-xs" style={{ color: '#555570' }}>
                <span className="ml-5">Coupon: {data.coupon_applied}</span>
              </div>
              <div />
            </>
          )}

          <div
            className="flex items-center gap-2 pt-3 font-semibold"
            style={{ color: isWinner ? '#00d4aa' : '#e8e8ed', borderTop: '1px solid rgba(108,99,255,0.1)' }}
          >
            <span>Final Total</span>
          </div>
          <div
            className="text-right text-lg font-bold pt-3"
            style={{ color: isWinner ? '#00d4aa' : '#e8e8ed', borderTop: '1px solid rgba(108,99,255,0.1)' }}
          >
            ₹{data.final_total}
          </div>

          <div className="flex items-center gap-2" style={{ color: '#8888a0' }}>
            <Clock size={14} />
            <span>Delivery</span>
          </div>
          <div className="text-right font-medium" style={{ color: '#e8e8ed' }}>
            {data.delivery_time}
          </div>
        </div>
      )}
    </motion.div>
  )
}

export default function DecisionCard({ result }: DecisionCardProps) {
  if (!result) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Trophy size={16} style={{ color: '#ffd700' }} />
          <span className="text-sm font-semibold" style={{ color: '#e8e8ed' }}>OmniFood Response</span>
        </div>
        <div className="glass-card flex items-center justify-center h-[420px]">
          <p className="text-sm" style={{ color: '#555570' }}>
            Ask about account details, restaurant offers, or general food questions...
          </p>
        </div>
      </div>
    )
  }

  const mode = result.mode || 'comparison'
  const { zomato, swiggy, eatsure, decision, answer } = result
  const safeDecision = decision || { winner: 'None', savings: 0, rationale: '' }
  const hasSavings = safeDecision.savings > 0 && safeDecision.winner !== 'None'
  const visibleTargets = result.target_platforms?.length ? result.target_platforms.map((p) => p.toLowerCase()) : ['zomato', 'swiggy', 'eatsure']

  if (mode === 'chat' || mode === 'account_summary') {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Trophy size={16} style={{ color: '#ffd700' }} />
          <span className="text-sm font-semibold" style={{ color: '#e8e8ed' }}>OmniFood Response</span>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="glass-card p-5"
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs px-2 py-1 rounded-full" style={{ background: 'rgba(108,99,255,0.12)', color: '#6c63ff' }}>
              {mode === 'account_summary' ? 'Account Summary' : 'Chat Answer'}
            </span>
          </div>
          <p className="text-sm leading-relaxed" style={{ color: '#e8e8ed' }}>
            {answer || 'No response generated.'}
          </p>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
          <Trophy size={16} style={{ color: '#ffd700' }} />
        <span className="text-sm font-semibold" style={{ color: '#e8e8ed' }}>OmniFood Response</span>
      </div>

      <div className="space-y-4">
        {mode === 'platform_summary' && answer && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="glass-card p-4"
          >
            <p className="text-sm leading-relaxed" style={{ color: '#e8e8ed' }}>
              {answer}
            </p>
          </motion.div>
        )}

        {(visibleTargets.includes('zomato') || mode === 'comparison') && (
          <PlatformRow data={zomato} isWinner={safeDecision.winner === 'Zomato'} />
        )}
        {(visibleTargets.includes('swiggy') || mode === 'comparison') && (
          <PlatformRow data={swiggy} isWinner={safeDecision.winner === 'Swiggy'} />
        )}
        {(visibleTargets.includes('eatsure') || mode === 'comparison') && (
          <PlatformRow data={eatsure} isWinner={safeDecision.winner === 'EatSure'} />
        )}

        {/* Savings summary */}
        {hasSavings ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            className="p-5 rounded-2xl text-center"
            style={{
              background: 'linear-gradient(135deg, rgba(0,212,170,0.08), rgba(108,99,255,0.08))',
              border: '1px solid rgba(0,212,170,0.2)',
            }}
          >
            <div className="flex items-center justify-center gap-2 mb-2">
              <Truck size={18} style={{ color: '#00d4aa' }} />
              <span className="text-sm font-semibold" style={{ color: '#00d4aa' }}>
                You save ₹{safeDecision.savings} with {safeDecision.winner}!
              </span>
            </div>
            <p className="text-xs" style={{ color: '#8888a0' }}>
              {safeDecision.rationale}
            </p>
          </motion.div>
        ) : safeDecision.winner !== 'None' ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            className="p-5 rounded-2xl text-center"
            style={{
              background: 'linear-gradient(135deg, rgba(108,99,255,0.08), rgba(0,212,170,0.08))',
              border: '1px solid rgba(108,99,255,0.2)',
            }}
          >
            <p className="text-sm" style={{ color: '#8888a0' }}>
              {safeDecision.rationale}
            </p>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="p-5 rounded-2xl text-center"
            style={{
              background: 'rgba(255,107,107,0.06)',
              border: '1px solid rgba(255,107,107,0.2)',
            }}
          >
            <AlertTriangle size={20} className="mx-auto mb-2" style={{ color: '#ff6b6b' }} />
            <p className="text-sm" style={{ color: '#ff6b6b' }}>
              {safeDecision.rationale || answer || 'No result available.'}
            </p>
          </motion.div>
        )}
      </div>
    </div>
  )
}
