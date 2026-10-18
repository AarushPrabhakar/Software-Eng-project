import { Link } from 'react-router-dom'

export default function AuthShell({ title, lede, children, footer }) {
  return (
    <div className="auth">
      <aside className="auth__panel">
        <Link to="/" className="brand" style={{ color: '#fff' }}>
          <span className="brand__mark" />
          LostLink
        </Link>
        <div>
          <h2>Get it back without anyone guessing.</h2>
          <p>Found items stay hidden until the owner turns up. Report, match, claim, and collect with a one-time code.</p>
          <div className="auth__demo" aria-hidden="true">
            <div className="demo__row">
              <span className="badge badge--found">Found</span>
              <span className="code-chip">LF-20261019-0042</span>
            </div>
            <h3 style={{ fontSize: 20, margin: '12px 0 12px' }}>Backpack or bag found</h3>
            <div className="redact">
              <i />
              <i />
              <i />
            </div>
          </div>
        </div>
        <span style={{ color: '#aab3ff', fontSize: 14 }}>Student project for UCS503P at Thapar. Not an official TIET service.</span>
      </aside>

      <main className="auth__form">
        <div className="auth__card">
          <Link to="/" className="brand auth__mobile-brand">
            <span className="brand__mark" />
            LostLink
          </Link>
          <h1>{title}</h1>
          <p className="muted">{lede}</p>
          {children}
          <p className="muted" style={{ marginTop: 22 }}>{footer}</p>
        </div>
      </main>
    </div>
  )
}
