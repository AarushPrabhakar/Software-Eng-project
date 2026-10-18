import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldCheck, ShieldOff } from 'lucide-react'
import api, { errMsg } from '../api.js'
import EmptyState from '../components/EmptyState.jsx'
import { BlockSkeleton } from '../components/Skeletons.jsx'

export default function Admin() {
  const [stats, setStats] = useState(null)
  const [flags, setFlags] = useState([])
  const [entries, setEntries] = useState([])
  const [error, setError] = useState('')
  const [denied, setDenied] = useState(false)

  async function load() {
    try {
      const [s, f, a] = await Promise.all([api.get('/admin/stats'), api.get('/admin/flags'), api.get('/admin/audit')])
      setStats(s.data)
      setFlags(f.data.flags)
      setEntries(a.data.entries)
    } catch (err) {
      if (err.response?.status === 403) setDenied(true)
      else setError(errMsg(err))
    }
  }
  useEffect(() => {
    load()
  }, [])

  async function resolve(id, action) {
    try {
      await api.patch(`/admin/flags/${id}`, { action })
      load()
    } catch (err) {
      setError(errMsg(err))
    }
  }

  if (denied) {
    return (
      <div className="page page--narrow">
        <EmptyState icon={ShieldOff} title="Administrators only">
          Your account doesn't have admin access.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="page page--narrow" style={{ maxWidth: 860 }}>
      <div className="page-head">
        <div>
          <h1>Moderation</h1>
          <p>Review flagged reports and see what has happened on the platform.</p>
        </div>
      </div>
      {error && <p className="msg msg--error" role="alert">{error}</p>}

      {!stats ? (
        <BlockSkeleton height={90} />
      ) : (
        <div className="stat-grid">
          <div className="stat"><b>{stats.reports.total}</b><span>Reports</span></div>
          <div className="stat"><b>{stats.reports.active}</b><span>Active</span></div>
          <div className="stat"><b>{stats.reports.claimed}</b><span>Claim in progress</span></div>
          <div className="stat"><b>{stats.reports.returned}</b><span>Returned</span></div>
          <div className="stat"><b>{stats.reports.flagged}</b><span>Hidden by flags</span></div>
          <div className="stat"><b>{stats.open_flags}</b><span>Open flags</span></div>
        </div>
      )}

      <h2 className="section-title">Open flags</h2>
      {flags.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="Nothing to review">No reports are waiting for a decision.</EmptyState>
      ) : (
        <div className="panel panel--flush" style={{ marginTop: 10 }}>
          {flags.map((f) => (
            <div key={f.id} className="row-item" style={{ flexWrap: 'wrap' }}>
              <span className="row-item__main">
                <span className="row-item__title">
                  {f.report ? (
                    <Link to={`/item/${f.report.report_code}`} style={{ textDecoration: 'underline' }}>{f.report.report_code}</Link>
                  ) : 'Deleted report'}
                  {' '}flagged: “{f.reason}”
                </span>
                <span className="row-item__sub">Report status: {f.report?.status}</span>
              </span>
              <span style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn--ghost btn--sm" onClick={() => resolve(f.id, 'dismiss')}>Dismiss</button>
                <button className="btn btn--danger btn--sm" onClick={() => resolve(f.id, 'remove')}>Remove report</button>
              </span>
            </div>
          ))}
        </div>
      )}

      <h2 className="section-title">Audit log</h2>
      <p className="section-sub">The latest 50 actions on claims, handovers and flags.</p>
      <div className="panel panel--flush">
        {entries.length === 0 && <p className="muted" style={{ padding: '16px 22px' }}>No actions logged yet.</p>}
        {entries.map((e) => (
          <div key={e.id} className="row-item">
            <span className="row-item__main">
              <span className="row-item__title">{e.action}</span>
              <span className="row-item__sub">{e.entity} {String(e.entity_id).slice(0, 8)}</span>
            </span>
            <span className="muted">{new Date(e.created_at).toLocaleString('en-IN')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
