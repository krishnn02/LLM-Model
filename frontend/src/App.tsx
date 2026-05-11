import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Zap,
  ShieldCheck,
  TrendingDown,
  ArrowRight,
  Sparkles,
  Bot,
  Loader2,
  ChefHat,
  BadgePercent,
  Truck,
  ChevronDown,
  AlertCircle,
  RefreshCw,
  Wifi,
  WifiOff,
  History,
  X,
  Trash2,
  Clock,
} from 'lucide-react'
import LiveLogs from './components/LiveLogs'
import DecisionCard from './components/DecisionCard'
import HeroBadge from './components/HeroBadge'
import FeatureCard from './components/FeatureCard'
import { useAgent } from './hooks/useAgent'
import { useHistory } from './hooks/useHistory'

function App() {
  const [query, setQuery] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const historyRef = useRef<HTMLDivElement>(null)
  const { logs, result, status, error, search, reset } = useAgent()
  const { history, addEntry, removeEntry, clearHistory } = useHistory()

  const isSearching = status === 'connecting' || status === 'connected' || status === 'streaming'

  // Keyboard shortcut: Ctrl+K focuses search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
      if (e.key === 'Escape') {
        setShowHistory(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // Close history on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (historyRef.current && !historyRef.current.contains(e.target as Node)) {
        setShowHistory(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Auto-scroll to results when search begins
  useEffect(() => {
    if (status === 'streaming' && showResults) {
      setTimeout(() => {
        document.getElementById('results-section')?.scrollIntoView({ behavior: 'smooth' })
      }, 500)
    }
  }, [status, showResults])

  // Save to history when done
  useEffect(() => {
    if (status === 'done' && result && query.trim()) {
      addEntry(query.trim(), result.decision.winner)
    }
  }, [status, result, query, addEntry])

  const handleSearch = useCallback(() => {
    if (!query.trim() || isSearching) return
    setShowResults(true)
    setShowHistory(false)
    search(query.trim())
  }, [query, isSearching, search])

  const handleHistorySelect = useCallback((q: string) => {
    setQuery(q)
    setShowHistory(false)
    // Auto-search with the selected query
    setShowResults(true)
    search(q)
  }, [search])

  const handleNewSearch = useCallback(() => {
    reset()
    setShowResults(false)
    setQuery('')
    inputRef.current?.focus()
  }, [reset])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  const scrollToResults = () => {
    document.getElementById('results-section')?.scrollIntoView({ behavior: 'smooth' })
  }

  // Connection status indicator
  const StatusBadge = () => {
    const statusConfig = {
      idle: { color: '#555570', icon: <Wifi size={12} />, text: 'Ready' },
      connecting: { color: '#ffd700', icon: <Loader2 size={12} className="animate-spin" />, text: 'Connecting...' },
      connected: { color: '#6c63ff', icon: <Wifi size={12} />, text: 'Connected' },
      streaming: { color: '#00d4aa', icon: <Loader2 size={12} className="animate-spin" />, text: 'Scanning...' },
      done: { color: '#00d4aa', icon: <ShieldCheck size={12} />, text: 'Complete' },
      error: { color: '#ff6b6b', icon: <WifiOff size={12} />, text: 'Error' },
    }
    const cfg = statusConfig[status]
    return (
      <div
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-300"
        style={{ background: `${cfg.color}15`, border: `1px solid ${cfg.color}30`, color: cfg.color }}
      >
        {cfg.icon}
        {cfg.text}
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* ─── NAV ─── */}
      <nav className="fixed top-0 left-0 right-0 z-50 px-6 py-4" style={{ background: 'rgba(10,10,15,0.8)', backdropFilter: 'blur(12px)' }}>
        <div style={{ maxWidth: '1152px', marginLeft: 'auto', marginRight: 'auto' }} className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #6c63ff, #00d4aa)' }}>
              <ChefHat size={20} color="#0a0a0f" strokeWidth={2.5} />
            </div>
            <span className="text-lg font-bold tracking-tight" style={{ color: '#e8e8ed' }}>
              Omni<span style={{ color: '#6c63ff' }}>Food</span>
            </span>
          </div>
          <div className="flex items-center gap-5 text-sm" style={{ color: '#8888a0' }}>
            <a href="#features" className="hover:text-white transition-colors duration-200 hidden sm:block">Features</a>
            <a href="#how-it-works" className="hover:text-white transition-colors duration-200 hidden sm:block">How it works</a>
            <StatusBadge />
          </div>
        </div>
      </nav>

      {/* ─── HERO ─── */}
      <main className="flex-1">
        <section className="flex flex-col items-center justify-center min-h-screen px-6 pt-24 pb-16">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col items-center text-center max-w-3xl"
          >
            <HeroBadge />

            <h1 className="text-5xl md:text-6xl font-extrabold leading-tight mt-6 mb-5" style={{ letterSpacing: '-0.03em' }}>
              <span style={{ color: '#e8e8ed' }}>The Smartest Way to</span>
              <br />
              <span style={{
                background: 'linear-gradient(135deg, #6c63ff 0%, #00d4aa 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}>
                Order Food Online
              </span>
            </h1>

            <p className="text-lg mb-10 max-w-xl leading-relaxed" style={{ color: '#8888a0' }}>
              OmniFood's AI agents scan Zomato, Swiggy & EatSure in real-time — applying your memberships, coupons, and hidden discounts to find the absolute cheapest checkout total.
            </p>

            {/* ─── SEARCH BAR ─── */}
            <motion.div
              className="w-full max-w-2xl relative"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              ref={historyRef}
            >
              <div
                className="glass-card flex items-center gap-3 px-5 py-4 animate-pulse-glow"
                style={{ borderColor: isSearching ? 'rgba(108,99,255,0.6)' : undefined }}
              >
                {isSearching ? (
                  <Loader2 size={22} className="animate-spin" style={{ color: '#6c63ff' }} />
                ) : (
                  <Search size={22} style={{ color: '#8888a0' }} />
                )}
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onFocus={() => { if (history.length > 0 && !isSearching) setShowHistory(true) }}
                  placeholder='Try "2 Butter Chicken + Naan from Punjabi Tadka to 400001"'
                  disabled={isSearching}
                  className="flex-1 bg-transparent outline-none text-base placeholder:text-[#555570]"
                  style={{ color: '#e8e8ed', fontFamily: 'var(--font-sans)' }}
                  id="search-input"
                />

                {/* History toggle */}
                {history.length > 0 && !isSearching && status !== 'done' && (
                  <button
                    onClick={() => setShowHistory((v) => !v)}
                    className="p-1.5 rounded-lg transition-colors duration-200 cursor-pointer"
                    style={{ color: showHistory ? '#6c63ff' : '#555570', background: showHistory ? 'rgba(108,99,255,0.1)' : 'transparent' }}
                    title="Search history"
                    id="history-toggle"
                  >
                    <History size={18} />
                  </button>
                )}

                <div className="hidden md:flex items-center gap-1 px-2 py-1 rounded-md text-xs" style={{ background: 'rgba(108,99,255,0.1)', color: '#8888a0', border: '1px solid rgba(108,99,255,0.15)' }}>
                  Ctrl+K
                </div>
                {status === 'done' || status === 'error' ? (
                  <button
                    onClick={handleNewSearch}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 cursor-pointer"
                    style={{
                      background: 'linear-gradient(135deg, #00d4aa, #00b894)',
                      color: '#0a0a0f',
                    }}
                    id="new-search-button"
                  >
                    <RefreshCw size={16} />
                    New Search
                  </button>
                ) : (
                  <button
                    onClick={handleSearch}
                    disabled={isSearching || !query.trim()}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 disabled:opacity-40 cursor-pointer"
                    style={{
                      background: 'linear-gradient(135deg, #6c63ff, #5a52d5)',
                      color: '#fff',
                    }}
                    id="search-button"
                  >
                    {isSearching ? 'Scanning...' : 'Find Deals'}
                    {!isSearching && <ArrowRight size={16} />}
                  </button>
                )}
              </div>

              {/* ─── SEARCH HISTORY DROPDOWN ─── */}
              <AnimatePresence>
                {showHistory && history.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.98 }}
                    transition={{ duration: 0.2 }}
                    className="absolute left-0 right-0 mt-2 z-50 glass-card overflow-hidden"
                    style={{ maxHeight: '280px', overflowY: 'auto' }}
                  >
                    <div className="flex items-center justify-between px-4 pt-3 pb-2">
                      <span className="text-xs font-semibold" style={{ color: '#8888a0' }}>Recent Searches</span>
                      <button
                        onClick={clearHistory}
                        className="text-xs flex items-center gap-1 cursor-pointer transition-colors duration-200"
                        style={{ color: '#555570' }}
                        id="clear-history-btn"
                      >
                        <Trash2 size={12} /> Clear All
                      </button>
                    </div>
                    {history.map((entry, i) => (
                      <div
                        key={`${entry.timestamp}-${i}`}
                        className="flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors duration-150 group"
                        style={{ borderTop: '1px solid rgba(108,99,255,0.06)' }}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(108,99,255,0.06)' }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                      >
                        <Clock size={14} style={{ color: '#555570' }} />
                        <button
                          onClick={() => handleHistorySelect(entry.query)}
                          className="flex-1 text-left text-sm truncate cursor-pointer"
                          style={{ color: '#e8e8ed', background: 'none', border: 'none', padding: 0 }}
                        >
                          {entry.query}
                        </button>
                        {entry.winner && entry.winner !== 'None' && (
                          <span className="text-xs px-2 py-0.5 rounded-full shrink-0" style={{ background: 'rgba(0,212,170,0.1)', color: '#00d4aa' }}>
                            {entry.winner}
                          </span>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); removeEntry(i) }}
                          className="opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                          style={{ color: '#555570', background: 'none', border: 'none' }}
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Error banner */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="flex items-center gap-2 mt-3 px-4 py-3 rounded-xl text-sm"
                    style={{ background: 'rgba(255,107,107,0.1)', border: '1px solid rgba(255,107,107,0.2)', color: '#ff6b6b' }}
                  >
                    <AlertCircle size={16} />
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="flex items-center justify-center gap-4 mt-4 text-xs" style={{ color: '#555570' }}>
                <span className="flex items-center gap-1"><ShieldCheck size={13} /> Stealth Mode</span>
                <span className="flex items-center gap-1"><Zap size={13} /> Real-time Prices</span>
                <span className="flex items-center gap-1"><TrendingDown size={13} /> Coupon Optimized</span>
              </div>
            </motion.div>
          </motion.div>

          {/* Scroll indicator */}
          {showResults && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1 }}
              onClick={scrollToResults}
              className="mt-12 flex flex-col items-center gap-1 cursor-pointer"
              style={{ color: '#6c63ff' }}
            >
              <span className="text-xs">View Results</span>
              <ChevronDown size={20} className="animate-bounce" />
            </motion.button>
          )}
        </section>

        {/* ─── FEATURES ─── */}
        <section id="features" className="px-6 py-20">
          <div style={{ maxWidth: '1152px', marginLeft: 'auto', marginRight: 'auto' }}>
            <motion.div
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              className="text-center mb-14"
            >
              <h2 className="text-3xl font-bold mb-3" style={{ color: '#e8e8ed' }}>
                Why OmniFood?
              </h2>
              <p className="text-base" style={{ color: '#8888a0' }}>
                Three AI agents working in parallel to save you money on every order.
              </p>
            </motion.div>
            <div className="grid md:grid-cols-3 gap-6">
              <FeatureCard
                icon={<Bot size={28} />}
                title="Multi-Agent AI"
                description="LangGraph orchestrates parallel browser agents that scrape real checkout totals — no estimates, no guesswork."
                delay={0}
              />
              <FeatureCard
                icon={<BadgePercent size={28} />}
                title="Coupon Optimizer"
                description="Automatically applies the best coupon and checks if adding a cheap filler item unlocks a bigger discount tier."
                delay={0.15}
              />
              <FeatureCard
                icon={<Truck size={28} />}
                title="Membership Aware"
                description="Loads your Zomato Gold / Swiggy One session to include your personal member-only benefits in the price comparison."
                delay={0.3}
              />
            </div>
          </div>
        </section>

        {/* ─── RESULTS ─── */}
        <AnimatePresence>
          {showResults && (
            <motion.section
              id="results-section"
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6 }}
              className="px-6 py-16"
            >
              <div style={{ maxWidth: '1024px', marginLeft: 'auto', marginRight: 'auto' }}>
                <div className="flex items-center gap-3 mb-8">
                  <Sparkles size={22} style={{ color: '#6c63ff' }} />
                  <h2 className="text-2xl font-bold" style={{ color: '#e8e8ed' }}>Agent Activity</h2>
                  {isSearching && (
                    <span className="text-xs px-2 py-1 rounded-full animate-pulse" style={{ background: 'rgba(108,99,255,0.15)', color: '#6c63ff' }}>
                      Live
                    </span>
                  )}
                </div>

                <div className="grid lg:grid-cols-2 gap-8">
                  <LiveLogs logs={logs} isSearching={isSearching} />
                  <DecisionCard result={result} />
                </div>

                {/* Optimization suggestion */}
                <AnimatePresence>
                  {result?.optimization?.filler_suggestion && (
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-6 p-5 rounded-2xl"
                      style={{
                        background: 'linear-gradient(135deg, rgba(255,215,0,0.06), rgba(108,99,255,0.06))',
                        border: '1px solid rgba(255,215,0,0.2)',
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-2xl">💡</span>
                        <div>
                          <h4 className="text-sm font-semibold mb-1" style={{ color: '#ffd700' }}>
                            Smart Savings Tip
                          </h4>
                          <p className="text-sm" style={{ color: '#8888a0' }}>
                            {result.optimization.filler_suggestion.suggestion}
                          </p>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.section>
          )}
        </AnimatePresence>

        {/* ─── HOW IT WORKS ─── */}
        <section id="how-it-works" className="px-6 py-20">
          <div style={{ maxWidth: '896px', marginLeft: 'auto', marginRight: 'auto' }}>
            <motion.div
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              className="text-center mb-14"
            >
              <h2 className="text-3xl font-bold mb-3" style={{ color: '#e8e8ed' }}>How It Works</h2>
              <p className="text-base" style={{ color: '#8888a0' }}>From query to savings in seconds.</p>
            </motion.div>
            <div className="space-y-6">
              {[
                { step: '01', title: 'You Describe Your Order', desc: 'Type naturally — "2 Paneer Tikka from Barbeque Nation to Andheri West"' },
                { step: '02', title: 'AI Parses Intent', desc: 'Our LLM extracts the restaurant, items, and delivery address into a structured schema.' },
                { step: '03', title: 'Stealth Browsers Launch', desc: 'Parallel headless Playwright browsers open Zomato, Swiggy & EatSure with your logged-in session.' },
                { step: '04', title: 'Real Totals Captured', desc: 'Each agent navigates to the final checkout page, capturing taxes, fees, and member discounts.' },
                { step: '05', title: 'Optimizer Compares & Suggests', desc: 'The optimizer finds the cheapest option and even recommends filler items for bigger discount tiers.' },
              ].map((item, i) => (
                <motion.div
                  key={item.step}
                  initial={{ opacity: 0, x: -30 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                  className="glass-card flex items-start gap-5 p-5"
                >
                  <div className="shrink-0 w-12 h-12 rounded-xl flex items-center justify-center text-sm font-bold" style={{ background: 'linear-gradient(135deg, rgba(108,99,255,0.2), rgba(0,212,170,0.2))', color: '#6c63ff' }}>
                    {item.step}
                  </div>
                  <div>
                    <h3 className="text-base font-semibold mb-1" style={{ color: '#e8e8ed' }}>{item.title}</h3>
                    <p className="text-sm" style={{ color: '#8888a0' }}>{item.desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* ─── FOOTER ─── */}
      <footer className="px-6 py-8 text-center text-xs" style={{ color: '#555570', borderTop: '1px solid rgba(108,99,255,0.08)' }}>
        <p>OmniFood Agent © 2026 — Built with FastAPI, LangGraph, Playwright & React</p>
      </footer>
    </div>
  )
}

export default App
