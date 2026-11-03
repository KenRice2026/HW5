// Turns raw /events entries into the lines the desk shows: who is talking, what they
// said or asked, which tools they touched, and what came back.
import type { AgentEvent } from './api'
import { agentMeta, describeCall, describeResult } from './agents'

export type LineKind = 'start' | 'brief' | 'delegate' | 'tools' | 'results' | 'say' | 'report' | 'error' | 'system' | 'human'

export interface FeedLine {
  key: string
  at: string
  agent: string
  kind: LineKind
  depth: number
  text?: string
  target?: string
  chips?: { label: string; refused?: boolean; detail?: string }[]
}

const looksLikeJson = (s: string) => s.trim().startsWith('{')

export function toLines(events: AgentEvent[]): FeedLine[] {
  const out: FeedLine[] = []
  for (const e of events) {
    const base = { at: e.at, agent: e.agent, depth: e.depth }
    switch (e.step_type) {
      case 'prompt':
        if (e.depth === 0) out.push({ ...base, key: `${e.id}`, kind: 'start', text: 'Picked up the ticket.' })
        else out.push({ ...base, key: `${e.id}`, kind: 'brief', target: e.delegated_by ?? undefined, text: e.said ?? '' })
        break
      case 'model_response': {
        if (e.said && !looksLikeJson(e.said)) out.push({ ...base, key: `${e.id}s`, kind: 'say', text: e.said })
        // Tool calls first, hand-offs last: a delegating agent's desk then reads "waiting".
        const calls = e.tools_called.filter(c => c.tool !== 'delegate')
        if (calls.length)
          out.push({ ...base, key: `${e.id}t`, kind: 'tools', chips: calls.map(c => ({ label: describeCall(c.tool, c.args) })) })
        for (const [i, c] of e.tools_called.entries()) {
          if (c.tool !== 'delegate') continue
          const a = (c.args ?? {}) as { to?: string; task?: string }
          out.push({ ...base, key: `${e.id}d${i}`, kind: 'delegate', target: a.to, text: a.task })
        }
        break
      }
      case 'model_request': {
        const res = e.tool_results.filter(r => r.tool !== 'delegate' || r.refused)
        if (res.length)
          out.push({
            ...base, key: `${e.id}r`, kind: 'results',
            chips: res.map(r => ({ label: r.tool, refused: r.refused, detail: describeResult(r.result) })),
          })
        break
      }
      case 'final_output':
        out.push({ ...base, key: `${e.id}`, kind: 'report', text: e.said ?? 'Done.' })
        break
      case 'error':
        out.push({ ...base, key: `${e.id}`, kind: 'error', text: e.said ?? 'The run failed.' })
        break
      case 'ticket_update':
        out.push({ ...base, key: `${e.id}`, kind: 'system', text: 'Wrote the Boss’s decision onto the ticket.' })
        break
      case 'reset':
        out.push({ ...base, key: `${e.id}`, kind: 'system', text: 'Working database reset to the original.' })
        break
      case 'human_decision':
      case 'payment':
        out.push({
          ...base, key: `${e.id}`, kind: 'human',
          text: e.step_type === 'payment' ? 'Paid after signing.' : 'Signed the request.',
          chips: e.tool_results.map(r => ({ label: r.tool, refused: r.refused, detail: describeResult(r.result) })),
        })
        break
    }
  }
  return out
}

export type DeskState = 'idle' | 'thinking' | 'working' | 'done' | 'waiting'

export interface Desk {
  state: DeskState
  bubble?: string
  calls: number
  asked: number   // times this agent was handed a task in the run
  lastTarget?: string
}

// Where each agent stands right now, from the lines so far.
export function desks(lines: FeedLine[], running: boolean): Record<string, Desk> {
  const d: Record<string, Desk> = {}
  const get = (a: string) => (d[a] ??= { state: 'idle', calls: 0, asked: 0 })
  for (const l of lines) {
    if (!agentMeta(l.agent)) continue
    const s = get(l.agent)
    if (l.kind === 'start' || l.kind === 'brief') { s.state = 'thinking'; s.asked += 1; s.bubble = l.kind === 'brief' ? 'On it.' : 'Reading the ticket…' }
    if (l.kind === 'tools') { s.state = 'working'; s.calls += l.chips?.length ?? 0; s.bubble = l.chips?.map(c => c.label).join(' · ') }
    if (l.kind === 'results') { s.state = 'thinking'; const r = l.chips?.find(c => c.refused); if (r) s.bubble = `Refused: ${r.detail}` }
    if (l.kind === 'delegate' && l.target) { s.state = 'waiting'; s.lastTarget = l.target; s.bubble = `Asking ${agentMeta(l.target)?.name}…` }
    if (l.kind === 'say') s.bubble = l.text
    if (l.kind === 'report') { s.state = 'done'; s.bubble = l.text }
    if (l.kind === 'error') { s.state = 'done'; s.bubble = l.text }
  }
  if (!running) for (const s of Object.values(d)) if (s.state !== 'done') s.state = 'done'
  return d
}
