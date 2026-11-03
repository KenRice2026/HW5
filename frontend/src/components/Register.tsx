import { useEffect, useRef, useState } from 'react'
import type { Cash } from '../api'
import { money } from '../agents'

// The checking balance as a cash-register display. When the balance changes (an approved
// payment), the digits roll down to the new number and the amount paid tears off below.
export function Register({ cash }: { cash: Cash | null }) {
  const [shown, setShown] = useState<number | null>(null)
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null)
  const prev = useRef<number | null>(null)

  useEffect(() => {
    if (!cash) return
    const from = prev.current
    const to = cash.balance
    prev.current = to
    if (from === null || from === to) { setShown(to); return }
    if (to < from) setDrop({ amount: from - to, key: Date.now() })
    const start = performance.now()
    const ms = 1100
    let frame = 0
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms)
      const eased = 1 - Math.pow(1 - k, 3)
      setShown(from + (to - from) * eased)
      if (k < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [cash])

  const committed = cash?.awaiting_approval_or_payment ?? 0
  const pct = cash && cash.balance > 0 ? Math.min(100, (committed / cash.balance) * 100) : 0
  const after = cash?.balance_if_all_outstanding_paid ?? 0

  return (
    <div className="register" aria-label="Checking balance">
      <div className="register-top">
        <span className="register-label">Checking</span>
        <span className="register-led" title="No revenue is modelled: cash only goes out" />
      </div>
      <div className={`register-digits ${drop ? 'flash' : ''}`} key={drop?.key}>
        {shown === null ? '—' : money(shown)}
      </div>
      <div className="register-meter" title={`${money(committed)} requested, waiting on a signature`}>
        <span style={{ width: `${pct}%` }} />
      </div>
      <div className="register-foot">
        <span>{money(committed)} awaiting signature</span>
        <span className={after < 0 ? 'neg' : ''}>{money(after)} if all signed</span>
      </div>
      {drop && (
        <div className="register-receipt" key={drop.key} onAnimationEnd={() => setDrop(null)}>
          −{money(drop.amount)}
        </div>
      )}
    </div>
  )
}
