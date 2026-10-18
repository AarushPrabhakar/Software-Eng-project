// Circular match score. Colour follows the tier: high = green, possible = amber.
export default function ScoreRing({ score, large = false }) {
  const r = 28
  const c = 2 * Math.PI * r
  const color = score >= 75 ? 'var(--found)' : score >= 60 ? '#e0a100' : 'var(--ink-3)'
  return (
    <div className={`ring${large ? ' ring--lg' : ''}`} role="img" aria-label={`${score} percent match`}>
      <svg viewBox="0 0 64 64" width="100%" height="100%">
        <circle className="ring__bg" cx="32" cy="32" r={r} fill="none" strokeWidth="6" />
        <circle
          className="ring__fg"
          cx="32" cy="32" r={r} fill="none" strokeWidth="6"
          stroke={color}
          strokeDasharray={c}
          strokeDashoffset={c - (c * Math.min(score, 100)) / 100}
        />
      </svg>
      <span className="ring__num">{score}</span>
    </div>
  )
}
