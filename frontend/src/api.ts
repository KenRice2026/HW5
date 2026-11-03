// Typed client for the Campus Customs backend (backend/main.py).
// The base URL comes from .env (VITE_API_URL), defaulting to the local uvicorn server.

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export type AgentId = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: string
  state: 'open' | 'running' | 'resolved'
  closed: boolean
  pending_approval_ids: number[]
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  notes: string | null
  created_at: string
}

export interface Cash {
  name: string
  balance: number
  date: string
  awaiting_approval_or_payment: number
  requests_outstanding: number
  balance_if_all_outstanding_paid: number
}

export interface ApprovalRequest {
  id: number
  kind: 'invoice_payment' | 'rent_payment' | 'purchase_order'
  ref_id: number
  ticket_id: number | null
  payee: string
  amount: number
  reason: string
  requested_by: string
  status: 'pending' | 'approved' | 'rejected' | 'paid'
  requested_on: string
  decided_by: string | null
  decided_on: string | null
  decision_note: string | null
  payment_id: number | null
}

export interface Draft {
  id: number
  ticket_id: number | null
  audience: string
  recipient: string
  subject: string
  body: string
  created_by: string
  created_on: string
}

export interface AgentEvent {
  id: number
  at: string
  run_id: string
  ticket_id: number | null
  agent: string
  actor_type: 'agent' | 'system' | 'human'
  delegated_by: string | null
  depth: number
  step: number | null
  step_type: string
  said: string | null
  tools_called: { tool: string; args: unknown }[]
  tool_results: { tool: string; refused: boolean; result: string }[]
  usage: { requests: number; tool_calls: number; input_tokens: number; output_tokens: number } | null
}

export interface AgentSummary {
  agent: AgentId
  runs: number
  tools: Record<string, number>
  asked_by: string[]
  summary: string | null
  recommendation: string | null
  actions: string[]
  approval_request_ids: number[]
  draft_ids: number[]
  blockers: string[]
}

export interface BossDecision {
  ticket_id: number
  ticket_type: string
  assigned_to: AgentId[]
  decision: string
  final_status: string
  approval_request_ids: number[]
  draft_ids: number[]
  waiting_on_human: boolean
  reasoning: string
  next_steps: string[]
}

export interface TicketSummary {
  ticket_id: number
  run_id: string | null
  run_ids?: string[]
  first_event_id?: number
  started_at?: string
  finished_at?: string
  running?: boolean
  decision: BossDecision | null
  error?: string | null
  usage?: AgentEvent['usage']
  agents: AgentSummary[]
}

export interface RunStatus {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'error'
  error: string | null
  decision: BossDecision | null
}

export interface Health {
  ok: boolean
  model: string
  running: boolean
  running_ticket: number | null
  shop_date: string
  api_key_set: boolean
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail ?? body)
    throw new ApiError(res.status, detail || res.statusText)
  }
  return body as T
}

export const api = {
  health: () => call<Health>('/health'),
  tickets: () => call<{ tickets: Ticket[]; running_ticket: number | null }>('/tickets'),
  summary: (id: number) => call<TicketSummary>(`/tickets/${id}/summary`),
  run: (id: number) => call<RunStatus>(`/tickets/${id}/run`, { method: 'POST' }),
  runStatus: (runId: string) => call<RunStatus>(`/runs/${runId}`),
  events: (q: { after?: number; run_id?: string; ticket_id?: number; limit?: number }) => {
    const p = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v !== undefined && p.set(k, String(v)))
    return call<{ events: AgentEvent[]; last_id: number; running: boolean }>(`/events?${p}`)
  },
  approvals: (status = 'all') => call<{ requests: ApprovalRequest[] }>(`/approvals?status=${status}`),
  approve: (id: number, approver: string, note = '') =>
    call<{ ok: boolean; pay_result?: { ok: boolean; message?: string }; cash: Cash }>(
      `/approvals/${id}/approve`, { method: 'POST', body: JSON.stringify({ approver, note }) }),
  reject: (id: number, approver: string, note = '') =>
    call<{ ok: boolean; cash: Cash }>(`/approvals/${id}/reject`, {
      method: 'POST', body: JSON.stringify({ approver, note }),
    }),
  cash: () => call<Cash>('/cash'),
  drafts: () => call<{ drafts: Draft[] }>('/drafts'),
  reset: () => call<{ ok: boolean; cash: Cash }>('/reset', { method: 'POST' }),
}
