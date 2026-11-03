import { useState } from 'react'
import type { ApprovalRequest } from '../api'
import { agentMeta, amountInWords, money } from '../agents'

interface Props {
  requests: ApprovalRequest[]
  approver: string
  balance: number | null
  onDecide: (id: number, approve: boolean) => Promise<void>
}

const KIND = { invoice_payment: 'Vendor invoice', rent_payment: 'Rent', purchase_order: 'Purchase order' }

// The signature tray: every payment or purchase the agents prepared is a cheque waiting
// for a person. Nothing moves until you sign; signing is what pays and lowers cash.
export function SignatureTray({ requests, approver, balance, onDecide }: Props) {
  const [busy, setBusy] = useState<number | null>(null)
  const pending = requests.filter(r => r.status === 'pending')
  const done = requests.filter(r => r.status !== 'pending').slice(-4).reverse()

  const act = async (id: number, approve: boolean) => {
    setBusy(id)
    try { await onDecide(id, approve) } finally { setBusy(null) }
  }

  return (
    <section className="tray" aria-label="Approvals">
      <h2 className="col-title">Signature tray <span>{pending.length} waiting</span></h2>
      {pending.length === 0 && <p className="tray-empty">Nothing to sign. Agents can only prepare payments; they land here for you.</p>}
      {pending.map(r => {
        const short = balance !== null && r.amount > balance
        return (
          <article key={r.id} className={`cheque ${short ? 'short' : ''}`}>
            <div className="cheque-top">
              <span>Campus Customs · Checking</span>
              <span>No. {String(r.id).padStart(4, '0')}</span>
            </div>
            <div className="cheque-pay">
              <span className="muted">Pay to the order of</span>
              <b>{r.payee}</b>
              <span className="cheque-amt">{money(r.amount)}</span>
            </div>
            <div className="cheque-words">{amountInWords(r.amount)} dollars</div>
            <div className="cheque-memo">
              <span className="muted">Memo · {KIND[r.kind]} · ticket {r.ticket_id} · prepared by {agentMeta(r.requested_by)?.name ?? r.requested_by}</span>
              <p>{r.reason}</p>
            </div>
            {short && <p className="err">Checking can't cover this. Pay will refuse it.</p>}
            <div className="cheque-sign">
              <span className="sig-line">{approver ? <em>{approver}</em> : <span className="muted">enter your name above to sign</span>}</span>
              <button className="btn-reject" disabled={!approver || busy !== null} onClick={() => act(r.id, false)}>Void</button>
              <button className="btn-sign" disabled={!approver || busy !== null} onClick={() => act(r.id, true)}>
                {busy === r.id ? 'Signing…' : 'Sign & pay'}
              </button>
            </div>
          </article>
        )
      })}
      {done.length > 0 && (
        <ul className="tray-done">
          {done.map(r => (
            <li key={r.id}>
              <span className={`done-mark ${r.status}`}>{r.status === 'paid' ? 'PAID' : r.status === 'rejected' ? 'VOID' : 'SIGNED'}</span>
              #{r.id} {r.payee} · {money(r.amount)} <span className="muted">by {r.decided_by}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
