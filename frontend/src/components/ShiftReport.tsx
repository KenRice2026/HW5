import type { TicketSummary } from '../api'
import { STATUS_LABEL, agentMeta } from '../agents'

// After a run: the Boss's call as a pinned memo, then one short card per agent that
// worked the ticket - what it did, which tools it used, and what it left for a person.
export function ShiftReport({ summary }: { summary: TicketSummary | null }) {
  if (!summary?.run_id) return null
  const d = summary.decision
  const tokens = summary.usage ? Math.round((summary.usage.input_tokens + summary.usage.output_tokens) / 1000) : null
  return (
    <section className="report-sheet" aria-label="Shift report">
      <h2 className="col-title">Shift report <span>
        {(summary.run_ids?.length ?? 1) > 1 ? `${summary.run_ids!.length} runs since reset` : `run ${summary.run_id}`}
        {tokens !== null && ` · ${tokens}k tokens · ${summary.usage?.requests} model calls`}
      </span></h2>
      {summary.error && <p className="err">The run stopped: {summary.error}</p>}
      {d && (
        <div className="memo">
          <div className="memo-head">
            <span>From the Boss</span>
            <span className={`status-chip s-${d.final_status}`}>{STATUS_LABEL[d.final_status] ?? d.final_status}</span>
          </div>
          <p className="memo-call">{d.decision}</p>
          {d.next_steps.length > 0 && (
            <ul className="memo-next">{d.next_steps.slice(0, 4).map((s, i) => <li key={i}>{s}</li>)}</ul>
          )}
        </div>
      )}
      <div className="crew">
        {summary.agents.filter(a => a.agent !== 'boss').map(a => {
          const m = agentMeta(a.agent)
          const tools = Object.entries(a.tools).filter(([t]) => t !== 'delegate')
          return (
            <article key={a.agent} className={`crew-card a-${a.agent}`}>
              <header>
                <span className="desk-avatar sm" aria-hidden>{m?.glyph}</span>
                <b>{m?.name}</b>
                <span className="muted">{a.asked_by.length ? `asked by ${a.asked_by.map(x => agentMeta(x)?.name).join(', ')}` : ''}{a.runs > 1 ? ` · ${a.runs} times` : ''}</span>
              </header>
              <p className={`voice-${m?.voice}`}>{a.summary}</p>
              <div className="chips">
                {tools.map(([t, n]) => <span key={t} className="chip">{t}{n > 1 ? ` ×${n}` : ''}</span>)}
              </div>
              {(a.approval_request_ids.length > 0 || a.draft_ids.length > 0 || a.blockers.length > 0) && (
                <ul className="crew-left">
                  {a.approval_request_ids.map(id => (
                    <li key={`r${id}`}>✍ request #{id} {(a.tools.request_payment_approval || a.tools.create_purchase_order) ? 'filed for your signature' : 'noted'}</li>
                  ))}
                  {a.draft_ids.map(id => (
                    <li key={`d${id}`}>✉ draft #{id} {a.tools.draft_message ? 'saved (not sent)' : 'noted'}</li>
                  ))}
                  {a.blockers.slice(0, 2).map((b, i) => <li key={`b${i}`} className="blocker">⚠ {b}</li>)}
                </ul>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
