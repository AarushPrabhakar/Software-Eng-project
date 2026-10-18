import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { EyeOff, ShieldCheck, KeyRound, Lock } from 'lucide-react'
import ScoreRing from '../components/ScoreRing.jsx'

// The hero demo: a found item starts blacked out; "Match it" lifts the bars and highlights what fits.
function Redactable({ children, width }) {
  return (
    <span className="reveal" style={{ minWidth: width }}>
      <span className="reveal__bar" />
      {children}
    </span>
  )
}

function HeroDemo() {
  const [open, setOpen] = useState(false)

  useEffect(() => {
    // plays once on load so the idea lands without a click; the button replays it
    const t = setTimeout(() => setOpen(true), 1400)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className={`demo${open ? ' is-open' : ''}`}>
      <div className="demo__row">
        <span className="badge badge--found">Found</span>
        <span className="code-chip">LF-20261019-0042</span>
      </div>
      <h3>Water bottle or tumbler found</h3>

      <div className="demo__line">
        <span>Looks like</span>
        <Redactable width={150}><span className="mark">Blue Milton steel bottle</span></Redactable>
      </div>
      <div className="demo__line">
        <span>Found at</span>
        <Redactable width={110}><span className="mark">Central Library</span></Redactable>
      </div>
      <div className="demo__line">
        <span>Marks</span>
        <Redactable width={170}>Dent near the base</Redactable>
      </div>

      <div className="demo__yours">
        {open
          ? 'Your lost report matched this item. The finder keeps one private detail, which you confirm in your claim.'
          : 'You lost a bottle like this? Only people whose own lost report matches get to see more.'}
      </div>

      <div className="demo__foot">
        {open ? <ScoreRing score={86} /> : <Lock size={26} color="var(--ink-3)" />}
        <button className="btn btn--primary btn--sm" onClick={() => setOpen((o) => !o)}>
          {open ? 'Hide again' : 'Match it'}
        </button>
      </div>
    </div>
  )
}

export default function Landing() {
  return (
    <div className="shell" style={{ background: 'var(--paper)' }}>
      <header className="land-nav">
        <span className="brand">
          <span className="brand__mark" />
          LostLink
        </span>
        <div className="land-nav__links">
          <Link to="/login" className="btn btn--ghost btn--sm">Sign in</Link>
          <Link to="/register" className="btn btn--primary btn--sm">Create account</Link>
        </div>
      </header>

      <main>
        <section className="hero">
          <div>
            <h1>Found items stay blacked out until their owner turns up.</h1>
            <p className="hero__sub">
              LostLink is a lost-and-found for Thapar students. Finders post what they picked up. Only people
              whose own lost report matches ever see the details, so nobody can claim your bottle by guessing.
            </p>
            <div className="hero__cta">
              <Link to="/register" className="btn btn--primary btn--lg">Create your account</Link>
              <Link to="/login" className="btn btn--ghost btn--lg">Sign in</Link>
            </div>
            <p className="hero__fine">Use your @thapar.edu email. It takes under a minute.</p>
          </div>
          <HeroDemo />
        </section>

        <section className="band">
          <div className="band__inner">
            <h2>From lost to back in your hands in four steps</h2>
            <ol className="steps" style={{ padding: 0 }}>
              <li>
                <div className="steps__n">1</div>
                <h3>Report</h3>
                <p>Describe what you lost or found: category, colour, brand, where and when.</p>
              </li>
              <li>
                <div className="steps__n">2</div>
                <h3>Match</h3>
                <p>We score every report against the opposite list and alert likely owners straight away.</p>
              </li>
              <li>
                <div className="steps__n">3</div>
                <h3>Claim</h3>
                <p>Describe what only the owner would know. The finder checks it against a private detail.</p>
              </li>
              <li>
                <div className="steps__n">4</div>
                <h3>Hand over</h3>
                <p>Meet on campus. Show a one-time code and the item is marked returned.</p>
              </li>
            </ol>
          </div>
        </section>

        <section className="safe">
          <h2>Built so a lucky guess never works</h2>
          <div className="safe__list">
            <div className="safe__item">
              <span className="safe__icon"><EyeOff size={22} /></span>
              <div>
                <h3>Details stay hidden by default</h3>
                <p>The public feed shows an item type and nothing else. Photos, colours and places open up only for a matching lost report.</p>
              </div>
            </div>
            <div className="safe__item">
              <span className="safe__icon"><ShieldCheck size={22} /></span>
              <div>
                <h3>Claims are checked by the finder</h3>
                <p>The finder compares your answer with a private detail that nobody else ever sees, then approves or rejects.</p>
              </div>
            </div>
            <div className="safe__item">
              <span className="safe__icon"><KeyRound size={22} /></span>
              <div>
                <h3>One-time handover code</h3>
                <p>The code expires, locks after wrong tries, and is stored only as a hash. Every action is logged.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="cta-band">
          <div className="cta-band__inner">
            <h2>Lost something on campus this week?</h2>
            <Link to="/register" className="btn btn--lg" style={{ background: '#fff', color: 'var(--ink)' }}>
              Report it now
            </Link>
          </div>
        </section>
      </main>

      <footer className="footer">
        A student project for Software Engineering (UCS503P) at Thapar Institute. Not an official TIET service.
      </footer>
    </div>
  )
}
