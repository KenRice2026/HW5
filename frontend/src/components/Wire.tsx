import { useEffect, useRef } from 'react'
import { agentMeta } from '../agents'
import type { FeedLine } from '../feed'

const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

// The wire: the live transcript of the run. Each agent writes in its own colour and voice;
// hand-offs read as quoted briefs, tool calls as small receipt chips, refusals in red.
export function Wire({ lines, running }: { lines: FeedLine[]; running: boolean }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { if (running) end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [lines.length, running])

  if (!lines.length)
    return <div className="wire-empty">{running ? 'Waiting for the first word from the Boss…' : 'Pick a ticket and start the team: their conversation shows up here as it happens.'}</div>

  return (
    <ol className="wire-list">
      {lines.map(l => {
        const m = agentMeta(l.agent)
        const who = m?.name ?? l.agent
        return (
          <li key={l.key} className={`line k-${l.kind} a-${l.agent} voice-${m?.voice ?? 'plain'}`} style={{ ['--indent' as string]: l.depth }}>
            <span className="line-time">{time(l.at)}</span>
            <span className="line-who">{who}</span>
            <div className="line-body">
              {l.kind === 'delegate' && <p><b className="handoff">→ {agentMeta(l.target ?? '')?.name}</b> “{l.text}”</p>}
              {l.kind === 'brief' && <p className="muted">took the brief from {agentMeta(l.target ?? '')?.name ?? 'the loop'}</p>}
              {(l.kind === 'say' || l.kind === 'start' || l.kind === 'system') && <p>{l.text}</p>}
              {l.kind === 'report' && <p className="report">{l.text}</p>}
              {l.kind === 'error' && <p className="err">{l.text}</p>}
              {l.kind === 'human' && <p>✍ {l.text}</p>}
              {l.chips && (
                <div className="chips">
                  {l.chips.map((c, i) => (
                    <span key={i} className={`chip ${c.refused ? 'refused' : ''} ${l.kind === 'results' || l.kind === 'human' ? 'result' : ''}`}>
                      {l.kind === 'results' || l.kind === 'human' ? <><b>{c.label}</b> {c.detail}</> : c.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </li>
        )
      })}
      <div ref={end} />
    </ol>
  )
}
