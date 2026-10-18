import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Check, X, Eye, Mail, PartyPopper, KeyRound, SearchX } from 'lucide-react'
import api, { errMsg } from '../api.js'
import StampBadge from '../components/StampBadge.jsx'
import Stepper from '../components/Stepper.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { BlockSkeleton } from '../components/Skeletons.jsx'

export default function ClaimDetail() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [code, setCode] = useState('')
  const [newCode, setNewCode] = useState(null) // { code, expires_at }, shown once
  const evidenceError = sessionStorage.getItem('evidenceError')

  const load = useCallback(async () => {
    try {
      const res = await api.get(`/claims/${id}`)
      setData(res.data)
      setError('')
    } catch (err) {
      setError(errMsg(err, 'Could not load this claim.'))
    }
  }, [id])

  useEffect(() => {
    load()
    sessionStorage.removeItem('evidenceError')
  }, [load])

  async function act(fn, okMsg) {
    setBusy(true)
    setMsg('')
    setError('')
    try {
      await fn()
      if (okMsg) setMsg(okMsg)
      await load()
    } catch (err) {
      setError(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  const setStatus = (status, okMsg) =>
    act(() => api.patch(`/claims/${id}/status`, { status, note: note || undefined }), okMsg)

  const generate = () =>
    act(async () => {
      const res = await api.post(`/claims/${id}/handover`)
      setNewCode(res.data)
    })

  const confirm = (e) => {
    e.preventDefault()
    act(() => api.post(`/handovers/${data.handover.id}/confirm`, { code }), 'Handover confirmed. The item is marked as returned.')
    setCode('')
  }

  if (error && !data) {
    return (
      <div className="page page--narrow">
        <EmptyState icon={SearchX} title="We couldn't open that claim" action={<Link to="/my" className="btn btn--primary">Back to my activity</Link>}>
          {error}
        </EmptyState>
      </div>
    )
  }
  if (!data) {
    return <div className="page page--narrow"><div className="stack"><BlockSkeleton height={40} /><BlockSkeleton height={120} /><BlockSkeleton height={200} /></div></div>
  }

  const { claim, report, role, contact, handover, private_detail } = data
  const isFinder = role === 'finder'
  const isClaimant = role === 'claimant'
  const open = ['submitted', 'under_review'].includes(claim.status)
  const returned = report.status === 'returned'
  const closedOut = ['rejected', 'withdrawn'].includes(claim.status)
  const current = returned ? 3 : claim.status === 'approved' ? 2 : claim.status === 'under_review' ? 1 : 0

  return (
    <div className="page page--narrow">
      <Link to="/my" className="back-link"><ArrowLeft size={16} />My activity</Link>

      <div className="detail__badges">
        <StampBadge kind={returned ? 'returned' : claim.status} />
        <span className="code-chip">{claim.claim_code}</span>
      </div>
      <h1 style={{ fontSize: 'clamp(26px, 3.4vw, 34px)', margin: '12px 0 8px' }}>
        {isFinder ? 'Claim on your found item' : isClaimant ? 'Your claim' : 'Claim (admin view)'}
      </h1>
      <p className="lede" style={{ fontSize: 16 }}>
        For <Link to={`/item/${report.report_code}`} style={{ textDecoration: 'underline', color: 'var(--ink)' }}>{report.title}</Link>
        {' '}({report.report_code})
      </p>

      {closedOut ? (
        <p className="msg msg--info" style={{ marginTop: 18 }}>
          {claim.status === 'rejected' ? 'This claim was not approved.' : 'This claim was withdrawn.'}
        </p>
      ) : (
        <Stepper current={current} />
      )}

      {error && <p className="msg msg--error" role="alert">{error}</p>}
      {msg && <p className="msg msg--ok" role="status">{msg}</p>}
      {evidenceError && <p className="msg msg--error">Your claim was saved, but the proof photo failed: {evidenceError}</p>}

      <div className={isFinder || role === 'admin' ? 'grid-2' : ''}>
        <div className="panel">
          <h3>{isClaimant ? 'What you said' : 'What the claimant says'}</h3>
          <p style={{ whiteSpace: 'pre-wrap' }}>{claim.answers}</p>
          <p className="muted">Submitted {new Date(claim.created_at).toLocaleString('en-IN')}. Locked, so it can't be edited.</p>
          {claim.evidence_url && <img className="evidence-img" src={claim.evidence_url} alt="Claim evidence" />}
        </div>

        {(isFinder || role === 'admin') && (
          <div className="panel panel--secret">
            <h3>Your private detail</h3>
            <p>{private_detail || <span className="muted">You didn't add a private detail to this report.</span>}</p>
            <p className="muted">Compare it with the claimant's description. Approve only if it clearly fits.</p>
          </div>
        )}
      </div>

      {claim.review_note && (
        <div className="panel"><h3>Note from the finder</h3><p>{claim.review_note}</p></div>
      )}

      {isFinder && open && (
        <div className="panel">
          <h3>Your decision</h3>
          <div className="field">
            <label htmlFor="note">Note to the claimant <span className="hint">(optional)</span></label>
            <input id="note" className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 16, flexWrap: 'wrap' }}>
            {claim.status === 'submitted' && (
              <button className="btn btn--ghost btn--sm" disabled={busy} onClick={() => setStatus('under_review', 'Claim marked under review.')}>
                <Eye size={16} />Mark under review
              </button>
            )}
            <button className="btn btn--found btn--sm" disabled={busy} onClick={() => setStatus('approved', 'Claim approved. The claimant can now generate a handover code.')}>
              <Check size={16} />Approve
            </button>
            <button className="btn btn--danger btn--sm" disabled={busy} onClick={() => setStatus('rejected', 'Claim rejected.')}>
              <X size={16} />Reject
            </button>
          </div>
        </div>
      )}

      {isClaimant && open && (
        <button className="btn btn--ghost btn--sm" style={{ marginTop: 16 }} disabled={busy}
          onClick={() => setStatus('withdrawn', 'Claim withdrawn.')}>
          Withdraw claim
        </button>
      )}

      {claim.status === 'approved' && (
        <div className="panel">
          <h3>Handover</h3>
          {contact && (
            <p style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <Mail size={16} />
              Contact {isFinder ? 'the claimant' : 'the finder'}: <strong>{contact.name}</strong>
              <a href={`mailto:${contact.email}`} style={{ textDecoration: 'underline', color: 'var(--brand-text)' }}>{contact.email}</a>
            </p>
          )}

          {returned && (
            <p className="msg msg--ok" role="status"><PartyPopper size={18} style={{ flexShrink: 0 }} />Handover confirmed. This item has been returned.</p>
          )}

          {!returned && isClaimant && (
            <>
              <p style={{ marginTop: 10 }}>
                Meet the finder in a public spot on campus. Show them your one-time code, and they enter it to
                confirm you got the item.
              </p>
              {newCode ? (
                <>
                  <div className="passcode" aria-label={`Handover code ${newCode.code.split('').join(' ')}`}>
                    <div className="passcode__digits">
                      {newCode.code.split('').map((d, i) => <b key={i}>{d}</b>)}
                    </div>
                  </div>
                  <p className="muted">
                    This is the only time it's shown; we store just a hash. Valid until{' '}
                    {new Date(newCode.expires_at).toLocaleString('en-IN')}. If you lose it, generate a new one.
                  </p>
                </>
              ) : handover && !handover.used ? (
                <p className="muted" style={{ marginTop: 10 }}>
                  A code exists and expires {new Date(handover.expires_at).toLocaleString('en-IN')}
                  {handover.expired ? ' (expired)' : ''}. For safety it can't be shown again.
                </p>
              ) : null}
              <button className="btn btn--primary btn--sm" style={{ marginTop: 14 }} disabled={busy} onClick={generate}>
                <KeyRound size={16} />{handover || newCode ? 'Generate a new code' : 'Generate handover code'}
              </button>
            </>
          )}

          {!returned && isFinder && (
            handover && !handover.used ? (
              <form onSubmit={confirm} style={{ marginTop: 10 }}>
                <p>Ask the claimant for their 6-digit code and enter it to confirm the return.</p>
                <input
                  className="input code-input"
                  style={{ marginTop: 14 }}
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  aria-label="Handover code"
                />
                <p className="muted" style={{ marginTop: 8 }}>
                  {handover.attempts_left} {handover.attempts_left === 1 ? 'attempt' : 'attempts'} left
                  {handover.expired ? '. This code has expired.' : ''}
                </p>
                <button className="btn btn--found" style={{ marginTop: 12 }} disabled={busy || code.length !== 6}>
                  Confirm handover
                </button>
              </form>
            ) : (
              <p className="muted" style={{ marginTop: 10 }}>Waiting for the claimant to generate their handover code.</p>
            )
          )}
        </div>
      )}
    </div>
  )
}
