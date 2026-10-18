import { Check } from 'lucide-react'

// A real sequence, so numbered steps are appropriate here.
const STEPS = ['Submitted', 'Under review', 'Approved', 'Returned']

export default function Stepper({ current }) {
  return (
    <ol className="stepper" aria-label="Claim progress" style={{ padding: 0, listStyle: 'none' }}>
      {STEPS.map((label, i) => {
        const state = i < current ? 'is-done' : i === current ? 'is-current' : ''
        return (
          <li key={label} className={`step ${state}`} aria-current={i === current ? 'step' : undefined}>
            <span className="step__dot">{i < current ? <Check size={18} strokeWidth={3} /> : i + 1}</span>
            {label}
          </li>
        )
      })}
    </ol>
  )
}
