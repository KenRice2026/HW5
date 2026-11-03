import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  API_URL, ApiError, api,
  type AgentEvent, type ApprovalRequest, type Cash, type Draft, type Health, type Ticket, type TicketSummary,
} from './api'
import { money } from './agents'
import { desks, toLines } from './feed'
import { Floor } from './components/Floor'
import { Outbox } from './components/Outbox'
import { Register } from './components/Register'
import { ShiftReport } from './components/ShiftReport'
import { SignatureTray } from './components/SignatureTray'
import { TicketSpike } from './components/TicketSpike'
import { Wire } from './components/Wire'

const readName = () => { try { return localStorage.getItem('cc.approver') ?? '' } catch { return '' } }
const saveName = (v: string) => { try { localStorage.setItem('cc.approver', v) } catch { /* private mode */ } }

interface Toast { tone: 'ok' | 'warn' | 'err'; text: string }

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [requests, setRequests] = useState<ApprovalRequest[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [offline, setOffline] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [runTicket, setRunTicket] = useState<number | null>(null)
  const [justResolved, setJustResolved] = useState<number | null>(null)
  const [approver, setApprover] = useState(readName)
  const [toast, setToast] = useState<Toast | null>(null)
  const lastId = useRef(-1)
  const runId = useRef<string | null>(null)

  const say = (t: Toast) => { setToast(t); window.setTimeout(() => setToast(null), 5000) }

  const refresh = useCallback(async () => {
    try {
      const [t, c, a, d, h] = await Promise.all([api.tickets(), api.cash(), api.approvals('all'), api.drafts(), api.health()])
      setTickets(t.tickets); setCash(c); setRequests(a.requests); setDrafts(d.drafts); setHealth(h)
      setOffline(false)
      setSelected(s => s ?? t.tickets[0]?.id ?? null)
      if (h.running_ticket !== null) setRunTicket(r => r ?? h.running_ticket)
    } catch {
      setOffline(true)
    }
  }, [])

  // Load the latest run of a ticket (its shift report and its whole transcript).
  const loadTicket = useCallback(async (id: number) => {
    try {
      const s = await api.summary(id)
      setSummary(s)
      if (s.run_id) {
        // The ticket's whole story since the last reset: every run plus the human signatures.
        const ev = await api.events({ ticket_id: id, after: s.first_event_id ?? -1, limit: 500 })
        setEvents(ev.events)
        lastId.current = ev.last_id
      } else {
        setEvents([])
      }
    } catch { /* shown by the offline banner */ }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    if (runTicket !== null) return
    const t = window.setInterval(refresh, 8000)
    return () => window.clearInterval(t)
  }, [refresh, runTicket])
  useEffect(() => { if (selected !== null && runTicket !== selected) loadTicket(selected) }, [selected, loadTicket, runTicket])

  // While agents work: pull new events every second, and finish when the run is done.
  useEffect(() => {
    if (runTicket === null) return
    let stop = false
    const tick = async () => {
      try {
        const q = runId.current ? { run_id: runId.current, after: lastId.current } : { ticket_id: runTicket, after: lastId.current }
        const ev = await api.events(q)
        if (stop) return
        if (ev.events.length) setEvents(prev => [...prev, ...ev.events])
        lastId.current = ev.last_id
        if (!ev.running) {
          stop = true
          const finished = runTicket
          runId.current = null
          setRunTicket(null)
          await refresh()
          await loadTicket(finished)
          setJustResolved(finished)
          window.setTimeout(() => setJustResolved(null), 2500)
          say({ tone: 'ok', text: `Ticket ${finished}: the team has made its call.` })
        }
      } catch { /* keep polling */ }
    }
    const t = window.setInterval(tick, 1000)
    return () => { stop = true; window.clearInterval(t) }
  }, [runTicket, refresh, loadTicket])

  const startRun = async (id: number) => {
    try {
      const before = await api.events({ limit: 1 })
      lastId.current = before.last_id
      setEvents([]); setSummary(null); setSelected(id)
      const r = await api.run(id)
      runId.current = r.run_id
      setRunTicket(id)
      setTickets(ts => ts.map(t => (t.id === id ? { ...t, state: 'running' } : t)))
    } catch (e) {
      say({ tone: 'err', text: e instanceof ApiError ? e.message : 'Could not start the team.' })
    }
  }

  const decide = async (id: number, approve: boolean) => {
    try {
      if (approve) {
        const r = await api.approve(id, approver)
        if (r.pay_result?.ok) say({ tone: 'ok', text: `Signed and paid #${id}. Checking is now ${money(r.cash.balance)}.` })
        else say({ tone: 'warn', text: `Signed #${id}, but pay refused: ${r.pay_result?.message ?? 'unknown reason'}` })
      } else {
        await api.reject(id, approver)
        say({ tone: 'ok', text: `Voided request #${id}. No money moved.` })
      }
    } catch (e) {
      say({ tone: 'err', text: e instanceof ApiError ? e.message : 'Could not record the decision.' })
    }
    await refresh()
    if (selected !== null) await loadTicket(selected)
  }

  const reset = async () => {
    if (!window.confirm('Reset the working database to the original values? All agent work, requests, drafts and payments are undone.')) return
    try {
      await api.reset()
      setEvents([]); setSummary(null); lastId.current = -1
      say({ tone: 'ok', text: 'Fresh start: the desk is back to the original data.' })
    } catch (e) {
      say({ tone: 'err', text: e instanceof ApiError ? e.message : 'Reset failed.' })
    }
    await refresh()
  }

  const running = runTicket !== null
  const shown = running ? runTicket : selected
  const lines = useMemo(() => toLines(events), [events])
  const deskMap = useMemo(() => desks(lines, running), [lines, running])
  const active = useMemo(() => [...lines].reverse().find(l => l.agent !== 'run_loop')?.agent ?? null, [lines])
  const delegatedTo = useMemo(() => new Set(lines.filter(l => l.kind === 'delegate' && l.target).map(l => l.target!)), [lines])
  const ticket = tickets.find(t => t.id === shown) ?? null
  const shopDate = health?.shop_date ? new Date(`${health.shop_date}T12:00:00`) : null

  return (
    <div className="desk-app">
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark" aria-hidden>CC</span>
          <div>
            <h1>Campus Customs</h1>
            <p>Back office · the agent desk</p>
          </div>
        </div>
        {shopDate && (
          <div className="calendar" title="desk.date_today: the shop's today">
            <span className="cal-month">{shopDate.toLocaleString('en-US', { month: 'short' })}</span>
            <span className="cal-day">{shopDate.getDate()}</span>
            <span className="cal-year">{shopDate.getFullYear()}</span>
          </div>
        )}
        <label className="nameplate">
          <span>Signing as</span>
          <input
            value={approver}
            placeholder="Your name"
            onChange={e => { setApprover(e.target.value); saveName(e.target.value) }}
          />
        </label>
        <Register cash={cash} />
        <button className="reset-btn" onClick={reset} disabled={running} title="Reset the working DB to the original">⟲ Fresh start</button>
      </header>

      {offline && (
        <div className="banner err">
          Can't reach the backend at <code>{API_URL}</code>. Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}
      {health && !health.api_key_set && (
        <div className="banner warn">The backend has no <code>ANTHROPIC_API_KEY</code>, so the team can't run. Everything else works.</div>
      )}

      <main className="grid">
        <TicketSpike
          tickets={tickets}
          selected={shown}
          justResolved={justResolved}
          busy={running}
          onSelect={id => !running && setSelected(id)}
          onRun={startRun}
        />

        <div className="center">
          <div className="center-title">
            <h2 className="col-title">
              {ticket ? <>On the floor: ticket #{ticket.id} <span>{ticket.subject}</span></> : 'On the floor'}
            </h2>
            {running && <span className="live"><i /> live</span>}
          </div>
          <Floor desks={deskMap} active={active} running={running} delegatedTo={delegatedTo} />
          <section className="wire-panel" aria-label="Transcript">
            <h2 className="col-title">The wire <span>{lines.length} lines</span></h2>
            <Wire lines={lines} running={running} />
          </section>
          {!running && <ShiftReport summary={summary} />}
        </div>

        <div className="right">
          <SignatureTray requests={requests} approver={approver.trim()} balance={cash?.balance ?? null} onDecide={decide} />
          <Outbox drafts={drafts} ticketId={shown} />
        </div>
      </main>

      {toast && <div className={`toast ${toast.tone}`} role="status">{toast.text}</div>}
    </div>
  )
}
