import { useNavigate, Link } from 'react-router-dom'
import { useState } from 'react'
import { supabase } from '../supabaseClient'
import AuthShell from '../components/AuthShell.jsx'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!email.endsWith('@thapar.edu')) {
      setError('Use your institutional @thapar.edu email to continue.')
      return
    }

    setLoading(true)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    setLoading(false)

    if (error) {
      setError('Invalid email or password.')
      return
    }
    navigate('/feed')
  }

  return (
    <AuthShell
      title="Welcome back"
      lede="Sign in with your institute email to report items, check matches and track claims."
      footer={
        <>
          New here?{' '}
          <Link to="/register" style={{ color: 'var(--brand)', fontWeight: 600 }}>Create an account</Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="stack">
        <div className="field">
          <label htmlFor="email">Institutional email</label>
          <input id="email" className="input" type="email" placeholder="yourname@thapar.edu"
            autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" className="input" type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <p className="msg msg--error" role="alert">{error}</p>}
        <button type="submit" className="btn btn--primary btn--block btn--lg" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthShell>
  )
}
