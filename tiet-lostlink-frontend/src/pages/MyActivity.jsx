import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Inbox, PackageOpen, Ticket } from 'lucide-react'
import api, { errMsg } from '../api.js'
import StampBadge from '../components/StampBadge.jsx'
import CategoryIcon from '../components/CategoryIcon.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { BlockSkeleton } from '../components/Skeletons.jsx'

export default function MyActivity() {
  const [reports, setReports] = useState([])
  const [mine, setMine] = useState([])
  const [received, setReceived] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.get('/reports/mine'), api.get('/claims/mine'), api.get('/claims/received')])
      .then(([r, m, rc]) => {
        setReports(r.data.reports)
        setMine(m.data.claims)
        setReceived(rc.data.claims)
      })
      .catch((err) => setError(errMsg(err, 'Failed to load your activity.')))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="page page--narrow"><div className="stack"><BlockSkeleton height={50} /><BlockSkeleton height={220} /><BlockSkeleton height={140} /></div></div>
  }

  return (
    <div className="page page--narrow">
      <div className="page-head">
        <div>
          <h1>My activity</h1>
          <p>Your reports, the claims people made on items you found, and the claims you made.</p>
        </div>
      </div>
      {error && <p className="msg msg--error" role="alert">{error}</p>}

      <h2 className="section-title" style={{ marginTop: 8 }}>My reports</h2>
      {reports.length === 0 ? (
        <EmptyState icon={PackageOpen} title="You haven't reported anything"
          action={<div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link to="/report/lost" className="btn btn--lost btn--sm">I lost something</Link>
            <Link to="/report/found" className="btn btn--found btn--sm">I found something</Link>
          </div>}>
          Reports you file show up here with their status.
        </EmptyState>
      ) : (
        <div className="panel panel--flush" style={{ marginTop: 10 }}>
          {reports.map((r) => (
            <Link key={r.id} to={`/item/${r.report_code}`} className="row-item">
              <span style={{ display: 'flex', gap: 12, alignItems: 'center', minWidth: 0 }}>
                <span className="notif__icon"><CategoryIcon category={r.category} size={20} /></span>
                <span className="row-item__main">
                  <span className="row-item__title">{r.title}</span>
                  <span className="row-item__sub">{r.report_code}</span>
                </span>
              </span>
              <StampBadge kind={r.status === 'active' ? r.report_type : r.status} />
            </Link>
          ))}
        </div>
      )}

      <h2 className="section-title">Claims on items I found</h2>
      {received.length === 0 ? (
        <EmptyState icon={Inbox} title="No claims yet">
          When someone claims an item you found, it appears here and you get an alert.
        </EmptyState>
      ) : (
        <div className="panel panel--flush" style={{ marginTop: 10 }}>
          {received.map((c) => (
            <Link key={c.id} to={`/claim/${c.id}`} className="row-item">
              <span className="row-item__main">
                <span className="row-item__title">Claim {c.claim_code}</span>
                <span className="row-item__sub">On {c.report.report_code}</span>
              </span>
              <StampBadge kind={c.status} />
            </Link>
          ))}
        </div>
      )}

      <h2 className="section-title">Claims I've made</h2>
      {mine.length === 0 ? (
        <EmptyState icon={Ticket} title="You haven't claimed anything">
          If a found item matches something you lost, you can claim it from the feed.
        </EmptyState>
      ) : (
        <div className="panel panel--flush" style={{ marginTop: 10 }}>
          {mine.map((c) => (
            <Link key={c.id} to={`/claim/${c.id}`} className="row-item">
              <span className="row-item__main">
                <span className="row-item__title">{c.report?.title}</span>
                <span className="row-item__sub">Claim {c.claim_code}</span>
              </span>
              <StampBadge kind={c.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
