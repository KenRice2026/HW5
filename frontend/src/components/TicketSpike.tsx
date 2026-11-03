import type { Ticket } from '../api'
import { STATUS_LABEL, TICKET_KIND } from '../agents'

interface Props {
  tickets: Ticket[]
  selected: number | null
  justResolved: number | null
  busy: boolean
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

function ask(t: Ticket): string {
  if (t.type === 'customer_order') return `${t.qty} × ${t.sku} · size ${t.size}`
  if (t.type === 'price_override') return `${t.qty} × ${t.sku} · size ${t.size} · bulk discount`
  if (t.type === 'rent_notice') return `Lease ${t.lease_id}`
  return t.subject
}

// The ticket spike: each ticket is a paper slip. A run in progress shows a pulsing pin;
// once the agents have made their call the slip gets a RESOLVED stamp, plus a
// "sign here" flag if a payment is waiting on a person.
export function TicketSpike({ tickets, selected, justResolved, busy, onSelect, onRun }: Props) {
  return (
    <aside className="spike" aria-label="Tickets">
      <h2 className="col-title">Tickets <span>{tickets.filter(t => t.state === 'resolved').length}/{tickets.length} resolved</span></h2>
      {tickets.map(t => {
        const kind = TICKET_KIND[t.type] ?? { label: t.type, icon: '📄' }
        const original = (t.notes ?? '').split('\n')[0]
        const isSel = t.id === selected
        return (
          <article
            key={t.id}
            className={`slip ${isSel ? 'selected' : ''} state-${t.state}`}
            onClick={() => onSelect(t.id)}
            onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onSelect(t.id)}
            tabIndex={0}
            aria-current={isSel}
          >
            <div className="slip-head">
              <span className="slip-no">#{t.id}</span>
              <span className="slip-kind">{kind.icon} {kind.label}</span>
            </div>
            <h3>{t.subject}</h3>
            <p className="slip-from">from <b>{t.requester}</b></p>
            <p className="slip-ask">{ask(t)}</p>
            <p className="slip-note">“{original}”</p>
            <div className="slip-foot">
              <span className={`status-chip s-${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
              {t.pending_approval_ids.length > 0 && (
                <span className="sign-flag" title="A payment on this ticket needs your signature">✍ sign #{t.pending_approval_ids.join(', #')}</span>
              )}
            </div>
            {isSel && (
              <button
                className="run-btn"
                disabled={busy}
                onClick={e => { e.stopPropagation(); onRun(t.id) }}
              >
                {t.state === 'running' ? 'Agents working…' : t.state === 'resolved' ? '↻ Run the team again' : '▶ Start the team'}
              </button>
            )}
            {t.state === 'running' && <span className="pin" aria-label="Agents working" />}
            {t.state === 'resolved' && (
              <span className={`stamp ${justResolved === t.id ? 'thump' : ''}`}>
                Resolved<small>{STATUS_LABEL[t.status] ?? t.status}</small>
              </span>
            )}
          </article>
        )
      })}
    </aside>
  )
}
