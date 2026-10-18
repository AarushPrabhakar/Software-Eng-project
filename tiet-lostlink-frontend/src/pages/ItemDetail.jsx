import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Calendar, Flag, Lock, MapPin, Palette, Sparkles, Tag, EyeOff, SearchX } from 'lucide-react'
import api, { errMsg } from '../api.js'
import { useAuth } from '../context/AuthContext.jsx'
import { toViewItem } from '../data/mockItems.js'
import StampBadge from '../components/StampBadge.jsx'
import CategoryIcon from '../components/CategoryIcon.jsx'
import ScoreRing from '../components/ScoreRing.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { BlockSkeleton } from '../components/Skeletons.jsx'

const TIER_LABEL = { high: 'High likelihood', possible: 'Possible match', weak: 'Weak match' }

function ClaimForm({ code, onDone }) {
  const [answers, setAnswers] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (answers.trim().length < 10) {
      setError('Describe the item in at least a sentence: contents, marks, anything only the owner would know.')
      return
    }
    setBusy(true)
    try {
      const res = await api.post(`/reports/${code}/claims`, { answers })
      const claimId = res.data.claim.id
      if (file) {
        const fd = new FormData()
        fd.append('file', file)
        try {
          await api.post(`/claims/${claimId}/evidence`, fd)
        } catch (err) {
          // the claim itself is saved; tell the user on the next screen that the photo failed
          sessionStorage.setItem('evidenceError', errMsg(err))
        }
      }
      onDone(claimId)
    } catch (err) {
      setError(errMsg(err, 'Could not submit the claim.'))
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="panel">
      <h3>Start a claim</h3>
      <p className="muted" style={{ marginBottom: 14 }}>
        The finder kept one detail private. Describe what only the real owner would know: what's inside,
        stickers, scratches, serial numbers. Your answer is locked once you submit it.
      </p>
      <div className="stack">
        <div className="field">
          <label htmlFor="answers">Your description</label>
          <textarea id="answers" className="textarea" value={answers} maxLength={2000}
            onChange={(e) => setAnswers(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="evidence">Proof photo <span className="hint">(optional, JPG, PNG or WebP up to 4 MB, stored privately)</span></label>
          <input id="evidence" type="file" accept="image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </div>
        {error && <p className="msg msg--error" role="alert" style={{ margin: 0 }}>{error}</p>}
        <div>
          <button className="btn btn--primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit claim'}</button>
        </div>
      </div>
    </form>
  )
}

function FlagBox({ code }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [msg, setMsg] = useState({ text: '', ok: false })

  async function send(e) {
    e.preventDefault()
    try {
      await api.post('/flags', { report_ref: code, reason })
      setMsg({ text: 'Thanks. Moderators will take a look.', ok: true })
      setOpen(false)
    } catch (err) {
      setMsg({ text: errMsg(err), ok: false })
    }
  }

  return (
    <div style={{ marginTop: 20 }}>
      {!open && (
        <button className="btn btn--ghost btn--sm" onClick={() => setOpen(true)}>
          <Flag size={15} />Report this listing
        </button>
      )}
      {open && (
        <form onSubmit={send} className="panel">
          <div className="field">
            <label htmlFor="reason">What's wrong with this listing?</label>
            <input id="reason" className="input" value={reason} onChange={(e) => setReason(e.target.value)}
              minLength={5} maxLength={500} required />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn--danger btn--sm">Send report</button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </form>
      )}
      {msg.text && <p className={`msg ${msg.ok ? 'msg--ok' : 'msg--error'}`}>{msg.text}</p>}
    </div>
  )
}

export default function ItemDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [raw, setRaw] = useState(null)
  const [matches, setMatches] = useState([])
  const [claims, setClaims] = useState([]) // claims related to this report (mine or received)
  const [showClaim, setShowClaim] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError('')
    setShowClaim(false)

    async function load() {
      try {
        const res = await api.get(`/reports/${id}`)
        if (cancelled) return
        const report = res.data.report
        setRaw(report)
        const owner = report.reporter_id === user?.id

        if (owner) {
          const m = await api.get(`/reports/${id}/matches`)
          if (!cancelled) setMatches(m.data.matches)
        }
        if (report.report_type === 'found') {
          const list = await api.get(owner ? '/claims/received' : '/claims/mine')
          if (!cancelled) setClaims(list.data.claims.filter((c) => c.report?.report_code === report.report_code))
        }
      } catch (err) {
        if (!cancelled) setLoadError(errMsg(err, 'Failed to load report.'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [id, user?.id])

  if (loading) {
    return (
      <div className="page">
        <div className="detail">
          <BlockSkeleton height={340} />
          <div className="stack"><BlockSkeleton height={30} /><BlockSkeleton height={60} /><BlockSkeleton height={160} /></div>
        </div>
      </div>
    )
  }

  if (loadError || !raw) {
    return (
      <div className="page page--narrow">
        <EmptyState icon={SearchX} title="We couldn't find that report" action={<Link to="/feed" className="btn btn--primary">Back to the feed</Link>}>
          {loadError || 'It may have been removed or the link is wrong.'}
        </EmptyState>
      </div>
    )
  }

  const item = toViewItem(raw)
  const isOwner = raw.reporter_id === user?.id
  const statusKind = item.status === 'active' ? item.type : item.status
  const myLiveClaim = !isOwner && claims.find((c) => ['submitted', 'under_review', 'approved'].includes(c.status))

  return (
    <div className="page">
      <Link to="/feed" className="back-link"><ArrowLeft size={16} />Back to feed</Link>

      <div className="detail">
        <div className={`detail__media${item.type === 'lost' ? ' is-lost' : ''}`}>
          {raw.redacted ? (
            <div className="ticket__lock" style={{ fontSize: 15 }}>
              <Lock size={30} />
              Photo hidden
            </div>
          ) : item.imageUrl ? (
            <img src={item.imageUrl} alt={item.title} />
          ) : (
            <CategoryIcon category={item.category} size={84} strokeWidth={1.25} />
          )}
        </div>

        <div>
          <div className="detail__badges">
            <StampBadge kind={statusKind} />
            <span className="code-chip">{item.id}</span>
          </div>
          <h1 className="detail__title">{item.title}</h1>

          {raw.redacted ? (
            <div className="panel panel--lock" style={{ marginTop: 0 }}>
              <h3 style={{ display: 'flex', gap: 8, alignItems: 'center' }}><EyeOff size={20} />Details are hidden to protect the owner</h3>
              <div className="redact redact--tall" style={{ margin: '14px 0' }} aria-hidden="true"><i /><i /><i /></div>
              <p>
                The finder's description, photo and location open up only for people whose own lost report
                matches this item.
              </p>
              <p className="muted">
                Lost something like this? File a lost report with as much detail as you can. If it matches,
                you'll get an alert and the details open up here.
              </p>
              <Link to="/report/lost" className="btn btn--lost btn--sm" style={{ marginTop: 14 }}>I lost something</Link>
            </div>
          ) : (
            <>
              <p className="lede">{item.description}</p>
              <dl className="facts">
                <div><dt><Tag size={14} />Category</dt><dd>{item.category}</dd></div>
                <div><dt><MapPin size={14} />Location</dt><dd>{item.location}</dd></div>
                <div><dt><Tag size={14} />Brand</dt><dd>{item.brand}</dd></div>
                <div><dt><Palette size={14} />Colour</dt><dd>{item.colour}</dd></div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <dt><Calendar size={14} />Date</dt>
                  <dd>{item.date ? new Date(item.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }) : '—'}</dd>
                </div>
              </dl>
            </>
          )}

          {raw.access === 'matched' && (
            <p className="msg msg--ok" role="status">
              <Sparkles size={18} style={{ flexShrink: 0 }} />
              <span>
                This could be yours. It matches a lost report you filed ({raw.match_score}% match).
                Start a claim and describe what only the owner would know.
              </span>
            </p>
          )}

          {isOwner && raw.private_detail && (
            <div className="panel panel--secret">
              <h3>Your private detail</h3>
              <p>{raw.private_detail}</p>
              <p className="muted">Only you and admins can see this. Claimants never do.</p>
            </div>
          )}

          {/* non-owner actions */}
          {!isOwner && !raw.redacted && item.status === 'active' && item.type === 'found' && (
            myLiveClaim ? (
              <Link to={`/claim/${myLiveClaim.id}`} className="btn btn--primary" style={{ marginTop: 6 }}>
                View my claim ({myLiveClaim.status.replace('_', ' ')})
              </Link>
            ) : showClaim ? (
              <ClaimForm code={item.id} onDone={(claimId) => navigate(`/claim/${claimId}`)} />
            ) : (
              <button className="btn btn--primary btn--lg" onClick={() => setShowClaim(true)}>
                This is mine, start a claim
              </button>
            )
          )}
          {!isOwner && item.status === 'active' && item.type === 'lost' && (
            <Link to="/report/found" className="btn btn--found btn--lg">I found this item</Link>
          )}
          {!isOwner && item.status !== 'active' && (
            <p className="msg msg--info">This item is no longer open for claims.</p>
          )}
          {!isOwner && <FlagBox code={item.id} />}

          {/* owner view of claims on their found item */}
          {isOwner && item.type === 'found' && (
            <div className="panel panel--flush">
              <h3 className="list-title">Claims on this item ({claims.length})</h3>
              {claims.length === 0 && (
                <p className="muted" style={{ padding: '0 22px 18px' }}>
                  No claims yet. You'll get an alert when someone submits one.
                </p>
              )}
              {claims.map((c) => (
                <Link key={c.id} to={`/claim/${c.id}`} className="row-item">
                  <span className="row-item__title">Claim {c.claim_code}</span>
                  <StampBadge kind={c.status} />
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {isOwner && (
        <>
          <h2 className="section-title">Possible matches</h2>
          <p className="section-sub">
            Scored by the server on category, brand, colour, location, date and description. A match is a
            suggestion, not proof of ownership.
          </p>

          {matches.length === 0 ? (
            <EmptyState icon={Sparkles} title="No matches yet">
              We'll send you an alert as soon as a strong match is reported.
            </EmptyState>
          ) : (
            matches.map(({ report: r, score, tier }) => (
              <Link to={`/item/${r.report_code}`} key={r.id} className="match">
                <ScoreRing score={score} />
                <div className="match__body">
                  <div className="match__title">{r.title}</div>
                  <div className="match__sub">{TIER_LABEL[tier]} · {r.report_code}</div>
                </div>
                <StampBadge kind={r.report_type} />
              </Link>
            ))
          )}
        </>
      )}
    </div>
  )
}
