/**
 * OmniFood - Connected Accounts Panel
 * Premium UI for connecting/disconnecting food delivery platform accounts.
 * Shows login status, membership badges, and manages authentication flow.
 */

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Unlink,
  Loader2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  ShieldCheck,
  Crown,
  Phone,
  ChevronDown,
  ChevronUp,
  LogIn,
  AlertCircle,
  Fingerprint,
} from 'lucide-react'
import type { PlatformSession, LoginStatus } from '../hooks/useSession'

interface ConnectedAccountsProps {
  sessions: Record<string, PlatformSession>
  loginStatus: Record<string, LoginStatus>
  errors: Record<string, string | null>
  onConnect: (platform: string) => void
  onConfirm: (platform: string) => void
  onCancel: (platform: string) => void
  onDisconnect: (platform: string) => void
}

interface PlatformConfig {
  key: string
  name: string
  color: string
  gradient: string
  bgGlow: string
  icon: string
  description: string
}

const PLATFORMS: PlatformConfig[] = [
  {
    key: 'zomato',
    name: 'Zomato',
    color: '#e23744',
    gradient: 'linear-gradient(135deg, #e23744, #c72032)',
    bgGlow: 'rgba(226, 55, 68, 0.08)',
    icon: '🔴',
    description: 'Access Zomato Gold benefits, personal coupons & offers',
  },
  {
    key: 'swiggy',
    name: 'Swiggy',
    color: '#fc8019',
    gradient: 'linear-gradient(135deg, #fc8019, #e06c0f)',
    bgGlow: 'rgba(252, 128, 25, 0.08)',
    icon: '🟠',
    description: 'Access Swiggy One perks, personal discounts & coupons',
  },
  {
    key: 'eatsure',
    name: 'EatSure',
    color: '#2ecc71',
    gradient: 'linear-gradient(135deg, #2ecc71, #27ae60)',
    bgGlow: 'rgba(46, 204, 113, 0.08)',
    icon: '🟢',
    description: 'Access EatSure exclusive deals & personal offers',
  },
]

function PlatformCard({
  config,
  session,
  loginSt,
  error,
  onConnect,
  onConfirm,
  onCancel,
  onDisconnect,
}: {
  config: PlatformConfig
  session: PlatformSession | undefined
  loginSt: LoginStatus
  error: string | null
  onConnect: () => void
  onConfirm: () => void
  onCancel: () => void
  onDisconnect: () => void
}) {
  const isConnected = session?.connected || false
  const isLoggingIn = loginSt === 'opening' || loginSt === 'waiting' || loginSt === 'confirming'

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="relative overflow-hidden rounded-2xl"
      style={{
        background: isConnected
          ? `linear-gradient(135deg, ${config.bgGlow}, rgba(26,26,46,0.8))`
          : 'rgba(26, 26, 46, 0.6)',
        border: isConnected
          ? `1px solid ${config.color}40`
          : '1px solid rgba(108, 99, 255, 0.12)',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Subtle top accent bar */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px]"
        style={{
          background: isConnected ? config.gradient : 'transparent',
          opacity: isConnected ? 1 : 0,
          transition: 'opacity 0.3s ease',
        }}
      />

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            {/* Platform icon circle */}
            <div
              className="w-11 h-11 rounded-xl flex items-center justify-center text-lg font-bold shrink-0"
              style={{
                background: `${config.color}18`,
                border: `1px solid ${config.color}30`,
                color: config.color,
              }}
            >
              {config.name.charAt(0)}
            </div>
            <div>
              <h4 className="text-base font-semibold flex items-center gap-2" style={{ color: '#e8e8ed' }}>
                {config.name}
                {isConnected && (
                  <span
                    className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider"
                    style={{ background: `${config.color}20`, color: config.color }}
                  >
                    <CheckCircle2 size={10} />
                    Linked
                  </span>
                )}
              </h4>
              <p className="text-xs" style={{ color: '#555570' }}>
                {config.description}
              </p>
            </div>
          </div>
        </div>

        {/* Connected info section */}
        <AnimatePresence>
          {isConnected && session && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 overflow-hidden"
            >
              <div
                className="flex flex-wrap items-center gap-3 px-3 py-2.5 rounded-xl text-xs"
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.05)',
                }}
              >
                {session.phone && (
                  <span className="flex items-center gap-1.5" style={{ color: '#8888a0' }}>
                    <Phone size={12} style={{ color: config.color }} />
                    {session.phone}
                  </span>
                )}

                {session.membership && (
                  <span
                    className="flex items-center gap-1.5 px-2 py-0.5 rounded-full font-semibold"
                    style={{
                      background: 'rgba(255, 215, 0, 0.1)',
                      border: '1px solid rgba(255, 215, 0, 0.2)',
                      color: '#ffd700',
                    }}
                  >
                    <Crown size={11} />
                    {session.membership}
                  </span>
                )}

                <span className="flex items-center gap-1.5" style={{ color: '#555570' }}>
                  <ShieldCheck size={12} style={{ color: '#00d4aa' }} />
                  Session saved
                </span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error message */}
        <AnimatePresence>
          {error && loginSt === 'error' && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="flex items-center gap-2 mb-3 px-3 py-2 rounded-xl text-xs"
              style={{ background: 'rgba(255,107,107,0.08)', border: '1px solid rgba(255,107,107,0.15)', color: '#ff6b6b' }}
            >
              <AlertCircle size={13} />
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Login waiting state */}
        <AnimatePresence>
          {loginSt === 'waiting' && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mb-3 px-4 py-3 rounded-xl"
              style={{
                background: `linear-gradient(135deg, ${config.bgGlow}, rgba(108,99,255,0.04))`,
                border: `1px solid ${config.color}25`,
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <ExternalLink size={14} style={{ color: config.color }} />
                <span className="text-xs font-semibold" style={{ color: config.color }}>
                  Browser Window Open
                </span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: '#8888a0' }}>
                Log in to {config.name} in the browser window that just opened. Enter your phone number, verify via OTP,
                and once you see your account page, click <b style={{ color: '#e8e8ed' }}>"Confirm Login"</b> below.
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {isConnected ? (
            // Disconnect button
            <button
              onClick={onDisconnect}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all duration-200 cursor-pointer"
              style={{
                background: 'rgba(255,107,107,0.08)',
                border: '1px solid rgba(255,107,107,0.2)',
                color: '#ff6b6b',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'rgba(255,107,107,0.15)'
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'rgba(255,107,107,0.08)'
              }}
              id={`disconnect-${config.key}`}
            >
              <Unlink size={13} />
              Disconnect
            </button>
          ) : loginSt === 'waiting' ? (
            // Confirm & Cancel buttons
            <>
              <button
                onClick={onConfirm}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 cursor-pointer"
                style={{
                  background: config.gradient,
                  color: '#fff',
                  boxShadow: `0 4px 15px ${config.color}40`,
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.boxShadow = `0 6px 25px ${config.color}60`
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.boxShadow = `0 4px 15px ${config.color}40`
                }}
                id={`confirm-${config.key}`}
              >
                <CheckCircle2 size={14} />
                Confirm Login
              </button>
              <button
                onClick={onCancel}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 cursor-pointer"
                style={{
                  background: 'rgba(85,85,112,0.15)',
                  border: '1px solid rgba(85,85,112,0.2)',
                  color: '#8888a0',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(85,85,112,0.25)'
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(85,85,112,0.15)'
                }}
                id={`cancel-${config.key}`}
              >
                <XCircle size={13} />
                Cancel
              </button>
            </>
          ) : isLoggingIn ? (
            // Loading state
            <button
              disabled
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold opacity-60 cursor-not-allowed"
              style={{
                background: `${config.color}15`,
                border: `1px solid ${config.color}25`,
                color: config.color,
              }}
            >
              <Loader2 size={13} className="animate-spin" />
              {loginSt === 'opening' ? 'Opening browser...' : 'Saving session...'}
            </button>
          ) : (
            // Connect button
            <button
              onClick={onConnect}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 cursor-pointer"
              style={{
                background: `${config.color}12`,
                border: `1px solid ${config.color}30`,
                color: config.color,
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLElement).style.background = `${config.color}22`
                ;(e.currentTarget as HTMLElement).style.borderColor = `${config.color}50`
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLElement).style.background = `${config.color}12`
                ;(e.currentTarget as HTMLElement).style.borderColor = `${config.color}30`
              }}
              id={`connect-${config.key}`}
            >
              <LogIn size={13} />
              Connect Account
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default function ConnectedAccounts({
  sessions,
  loginStatus,
  errors,
  onConnect,
  onConfirm,
  onCancel,
  onDisconnect,
}: ConnectedAccountsProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  const connectedCount = Object.values(sessions).filter((s) => s.connected).length

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-3 mb-4 cursor-pointer group"
        style={{ background: 'none', border: 'none', padding: 0 }}
        id="accounts-toggle"
      >
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, rgba(108,99,255,0.15), rgba(0,212,170,0.15))',
            }}
          >
            <Fingerprint size={18} style={{ color: '#6c63ff' }} />
          </div>
          <div className="text-left">
            <h3 className="text-base font-semibold flex items-center gap-2" style={{ color: '#e8e8ed' }}>
              Connected Accounts
              {connectedCount > 0 && (
                <span
                  className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                  style={{ background: 'rgba(0,212,170,0.1)', color: '#00d4aa' }}
                >
                  {connectedCount}/3
                </span>
              )}
            </h3>
            <p className="text-xs" style={{ color: '#555570' }}>
              Link your accounts for personalized offers & real prices
            </p>
          </div>
        </div>
        <div
          className="p-1.5 rounded-lg transition-colors duration-200"
          style={{ color: '#555570' }}
        >
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </button>

      {/* Cards */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-3 overflow-hidden"
          >
            {PLATFORMS.map((config) => (
              <PlatformCard
                key={config.key}
                config={config}
                session={sessions[config.key]}
                loginSt={loginStatus[config.key] || 'idle'}
                error={errors[config.key] || null}
                onConnect={() => onConnect(config.key)}
                onConfirm={() => onConfirm(config.key)}
                onCancel={() => onCancel(config.key)}
                onDisconnect={() => onDisconnect(config.key)}
              />
            ))}

            {/* Info banner */}
            <div
              className="flex items-start gap-3 px-4 py-3 rounded-xl text-xs"
              style={{
                background: 'rgba(108,99,255,0.04)',
                border: '1px solid rgba(108,99,255,0.1)',
              }}
            >
              <ShieldCheck size={16} className="shrink-0 mt-0.5" style={{ color: '#6c63ff' }} />
              <div style={{ color: '#555570' }}>
                <span style={{ color: '#8888a0' }}>Your sessions are stored locally</span> on this machine using
                encrypted browser profiles. OmniFood uses these sessions to scrape <b style={{ color: '#8888a0' }}>your personalized prices</b>, 
                coupons, and membership benefits — just like opening the app yourself.
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
