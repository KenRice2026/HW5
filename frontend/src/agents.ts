// How each agent looks and sounds on the desk. Each role has its own colour, monogram,
// and "voice" (a typeface class), so you can tell who's talking at a glance.
import type { AgentId } from './api'

export interface AgentMeta {
  id: AgentId
  name: string
  role: string
  glyph: string
  voice: 'serif' | 'mono' | 'ledger' | 'sturdy' | 'warm'
}

export const AGENTS: AgentMeta[] = [
  { id: 'boss', name: 'Boss', role: 'Routes tickets · makes the call', glyph: 'B', voice: 'serif' },
  { id: 'inventory', name: 'Inventory', role: 'Stock, sizes, vendors', glyph: 'In', voice: 'mono' },
  { id: 'accounting', name: 'Accounting', role: 'Cash, invoices, margins', glyph: '$', voice: 'ledger' },
  { id: 'facilities', name: 'Facilities', role: 'Lease & rent', glyph: 'Fa', voice: 'sturdy' },
  { id: 'customer_service', name: 'Customer Service', role: 'Drafts every message', glyph: 'CS', voice: 'warm' },
]

export const agentMeta = (id: string): AgentMeta | undefined => AGENTS.find(a => a.id === id)

export const TICKET_KIND: Record<string, { label: string; icon: string }> = {
  customer_order: { label: 'Customer order', icon: '🧺' },
  rent_notice: { label: 'Rent notice', icon: '🏠' },
  price_override: { label: 'Discount request', icon: '🏷️' },
}

export const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  awaiting_approval: 'Needs your signature',
  waiting_on_vendor: 'Waiting on vendor',
  resolved: 'Closed',
  declined: 'Declined',
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

// "Eight hundred forty and 00/100" for the cheque-style approvals.
export function amountInWords(n: number): string {
  const ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven',
    'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
  const tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
  const under1000 = (x: number): string => {
    const parts: string[] = []
    if (x >= 100) { parts.push(`${ones[Math.floor(x / 100)]} hundred`); x %= 100 }
    if (x >= 20) { parts.push(tens[Math.floor(x / 10)] + (x % 10 ? `-${ones[x % 10]}` : '')); x = 0 }
    if (x > 0) parts.push(ones[x])
    return parts.join(' ')
  }
  const dollars = Math.floor(n)
  const cents = Math.round((n - dollars) * 100)
  let words = ''
  if (dollars === 0) words = 'zero'
  else {
    const th = Math.floor(dollars / 1000), rest = dollars % 1000
    words = [th ? `${under1000(th)} thousand` : '', rest ? under1000(rest) : ''].filter(Boolean).join(' ')
  }
  const s = `${words} and ${String(cents).padStart(2, '0')}/100`
  return s.charAt(0).toUpperCase() + s.slice(1)
}

// One short line describing a tool call, e.g. check_stock(CC-TEE-WHITE, S).
export function describeCall(tool: string, args: unknown): string {
  if (!args || typeof args !== 'object') return `${tool}()`
  const a = args as Record<string, unknown>
  if (tool === 'delegate') return `→ ${agentMeta(String(a.to))?.name ?? a.to}`
  const skip = new Set(['requested_by', 'created_by', 'agent', 'reason', 'body', 'note'])
  const vals = Object.entries(a).filter(([k]) => !skip.has(k)).map(([, v]) => String(v))
  const inner = vals.join(', ')
  return `${tool}(${inner.length > 48 ? inner.slice(0, 46) + '…' : inner})`
}

// The headline of a tool result: the refusal message, or the most telling field.
export function describeResult(raw: string): string {
  try {
    const r = JSON.parse(raw)
    if (typeof r === 'string') return r.length > 90 ? r.slice(0, 88) + '…' : r
    if (r.message) return String(r.message)
    if ('qty' in r && 'sku' in r) return `${r.qty} on hand`
    if ('balance' in r) return `balance ${money(r.balance)}`
    if (r.request?.id) return `request #${r.request.id} · ${money(r.request.amount)} · ${r.request.status}`
    if (r.draft?.id) return `draft #${r.draft.id} saved (not sent)`
    if ('monthly_rent' in r) return `${money(r.monthly_rent)} due ${r.next_due}`
    if ('unit_price' in r) return `${r.discount_pct}% → ${money(r.unit_price)}/unit, ${r.margin_pct}% margin`
    if ('can_ship_new_product' in r) return r.can_ship_new_product ? 'can ship' : 'blocked by open invoice'
    if ('count' in r) return `${r.count} rows`
    return 'ok'
  } catch {
    return raw.length > 90 ? raw.slice(0, 88) + '…' : raw
  }
}
