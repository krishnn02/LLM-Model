export interface LogMessage {
  type: 'log' | 'error' | 'done'
  message: string
}

export interface PlatformResult {
  platform: string
  base_price: number
  taxes: number
  discount: number
  final_total: number
  delivery_time: string
  coupon_applied?: string | null
  membership?: string | null
  error?: string | null
}

export interface AgentDecision {
  winner: string
  savings: number
  rationale: string
  base_price?: number
  taxes?: number
  discount?: number
  final_total?: number
  delivery_time?: string
}

export interface Optimization {
  filler_suggestion?: {
    platform: string
    current_total: number
    threshold: number
    gap: number
    suggestion: string
  } | null
}

export interface AgentResult {
  mode?: 'chat' | 'account_summary' | 'platform_summary' | 'comparison'
  answer?: string
  target_platforms?: string[]
  sessions?: Record<string, unknown>
  zomato?: PlatformResult
  swiggy?: PlatformResult
  eatsure?: PlatformResult
  decision?: AgentDecision
  optimization?: Optimization
}

// WebSocket connection status
export type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'streaming' | 'done' | 'error'

// Search history
export interface HistoryEntry {
  query: string
  timestamp: number
  winner?: string
}
