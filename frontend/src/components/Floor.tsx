import { AGENTS } from '../agents'
import type { Desk } from '../feed'

interface Props {
  desks: Record<string, Desk>
  active: string | null
  running: boolean
  delegatedTo: Set<string>
}

const STATE_LABEL = { idle: 'At desk', thinking: 'Thinking', working: 'Using tools', waiting: 'Waiting on a teammate', done: 'Done' }

// The floor: the Boss's desk at the head, the four specialists below it. Lines from the
// Boss light up for every teammate it handed work to; the agent speaking right now glows
// and shows what it's doing in a speech bubble.
export function Floor({ desks, active, running, delegatedTo }: Props) {
  const boss = AGENTS[0]
  const team = AGENTS.slice(1)
  const card = (a: (typeof AGENTS)[number]) => {
    const d = desks[a.id]
    const state = d?.state ?? 'idle'
    const isActive = running && active === a.id
    const benched = !d && !running
    return (
      <div key={a.id} className={`desk a-${a.id} st-${state} ${isActive ? 'active' : ''} ${benched ? 'benched' : ''}`}>
        <div className="desk-avatar" aria-hidden>{a.glyph}</div>
        <div className="desk-body">
          <div className="desk-name">{a.name}</div>
          <div className="desk-role">{a.role}</div>
          <div className="desk-state">
            {isActive && <span className="typing"><i /><i /><i /></span>}
            {d ? STATE_LABEL[state] : running ? 'Not called yet' : 'Not on this ticket'}
            {d && d.calls > 0 && <span className="desk-count">{d.calls} tool{d.calls === 1 ? '' : 's'}</span>}
            {d && d.asked > 1 && <span className="desk-count">asked ×{d.asked}</span>}
          </div>
        </div>
        {d?.bubble && <div className={`bubble voice-${a.voice}`}>{d.bubble}</div>}
      </div>
    )
  }
  return (
    <section className="floor" aria-label="Agent floor">
      <div className="floor-head">{card(boss)}</div>
      <svg className="floor-lines" viewBox="0 0 400 40" preserveAspectRatio="none" aria-hidden>
        {team.map((a, i) => {
          const x = 50 + i * 100
          const on = delegatedTo.has(a.id)
          const hot = on && running && active === a.id
          return <path key={a.id} d={`M200 0 C200 22, ${x} 18, ${x} 40`} className={`wire a-${a.id} ${on ? 'on' : ''} ${hot ? 'hot' : ''}`} />
        })}
      </svg>
      <div className="floor-team">{team.map(card)}</div>
    </section>
  )
}
