import { useState } from 'react'
import type { Draft } from '../api'

// Drafts the agents wrote, as envelopes that never leave the desk. Click one to read it.
export function Outbox({ drafts, ticketId }: { drafts: Draft[]; ticketId: number | null }) {
  const [open, setOpen] = useState<number | null>(null)
  const mine = drafts.filter(d => ticketId === null || d.ticket_id === ticketId)
  return (
    <section className="outbox" aria-label="Drafts">
      <h2 className="col-title">Outbox <span>drafts · never sent</span></h2>
      {mine.length === 0 && <p className="tray-empty">No drafts for this ticket yet.</p>}
      {mine.map(d => (
        <article key={d.id} className={`envelope ${open === d.id ? 'open' : ''}`}>
          <button className="envelope-head" onClick={() => setOpen(open === d.id ? null : d.id)} aria-expanded={open === d.id}>
            <span className="env-to">To {d.recipient}</span>
            <span className="env-subj">{d.subject}</span>
            <span className="env-badge">Draft #{d.id}</span>
          </button>
          {open === d.id && <pre className="env-body">{d.body}</pre>}
        </article>
      ))}
    </section>
  )
}
