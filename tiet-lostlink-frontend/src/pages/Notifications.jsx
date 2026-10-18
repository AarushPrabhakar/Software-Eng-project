import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BadgeCheck, Bell, FileCheck, Inbox, KeyRound, PackageCheck, ShieldAlert, Sparkles } from 'lucide-react'
import api, { errMsg } from '../api.js'
import EmptyState from '../components/EmptyState.jsx'
import { BlockSkeleton } from '../components/Skeletons.jsx'

const ICONS = {
  match: Sparkles,
  claim_submitted: Inbox,
  claim_update: FileCheck,
  claim_approved: BadgeCheck,
  handover_ready: KeyRound,
  returned: PackageCheck,
  moderation: ShieldAlert,
}

export default function Notifications() {
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  async function load() {
    try {
      const res = await api.get('/notifications')
      setItems(res.data.notifications)
    } catch (err) {
      setError(errMsg(err, 'Failed to load alerts.'))
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    load()
  }, [])

  async function open(n) {
    if (!n.is_read) {
      await api.patch(`/notifications/${n.id}/read`).catch(() => {})
      window.dispatchEvent(new Event('notifications-changed'))
    }
    if (n.link) navigate(n.link)
    else load()
  }

  async function readAll() {
    await api.post('/notifications/read-all')
    window.dispatchEvent(new Event('notifications-changed'))
    load()
  }

  return (
    <div className="page page--narrow">
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p>Matches, claims and handover updates.</p>
        </div>
        {items.some((n) => !n.is_read) && (
          <button className="btn btn--ghost btn--sm" onClick={readAll}>Mark all as read</button>
        )}
      </div>
      {error && <p className="msg msg--error" role="alert">{error}</p>}
      {loading ? (
        <BlockSkeleton height={260} />
      ) : items.length === 0 ? (
        <EmptyState icon={Bell} title="No alerts yet">
          You'll be alerted when a found item matches something you lost, or when a claim changes.
        </EmptyState>
      ) : (
        <div className="panel panel--flush" style={{ marginTop: 0 }}>
          {items.map((n) => {
            const Icon = ICONS[n.type] || Bell
            return (
              <button key={n.id} className={`notif${n.is_read ? '' : ' is-unread'}`} onClick={() => open(n)}>
                <span className="notif__icon"><Icon size={20} /></span>
                <span>
                  <div className="notif__msg">{n.message}</div>
                  <div className="notif__time">{new Date(n.created_at).toLocaleString('en-IN')}</div>
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
