import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CATEGORIES, CATEGORY_VALUE, LOCATIONS } from '../data/mockItems.js'
import { supabase } from '../supabaseClient.js'
import api, { errMsg } from '../api.js'
import { CheckCircle2, EyeOff, ImagePlus } from 'lucide-react'

export default function ReportForm({ type }) {
  const navigate = useNavigate()
  const isLost = type === 'lost'

  const [form, setForm] = useState({
    category: '',
    brand: '',
    colour: '',
    location: '',
    date: '',
    description: '',
    privateDetail: '',
  })
  const [photoFile, setPhotoFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [submitted, setSubmitted] = useState(false)

  function update(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  function handleFile(e) {
    const file = e.target.files?.[0]
    if (file) {
      setPhotoFile(file)
      setPreview(URL.createObjectURL(file))
    }
  }

  async function uploadPhotoIfPresent() {
    if (!photoFile) return null
    const fileExt = photoFile.name.split('.').pop()
    const fileName = `${crypto.randomUUID()}.${fileExt}`

    const { error: uploadError } = await supabase.storage
      .from('item-photos')
      .upload(fileName, photoFile, { cacheControl: '3600', upsert: false })

    if (uploadError) throw new Error(`Image upload failed: ${uploadError.message}`)

    const { data } = supabase.storage.from('item-photos').getPublicUrl(fileName)
    return data.publicUrl
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!form.category || !form.colour || !form.location || !form.date || !form.description) {
      setError('Please fill in every required field.')
      return
    }

    setSubmitting(true)
    try {
      const image_url = await uploadPhotoIfPresent()

      await api.post('/reports', {
        report_type: type,
        category: CATEGORY_VALUE[form.category],
        // a found item's title is public to everyone, so it must not repeat the description
        title: isLost ? form.description.slice(0, 60) : `${form.category} found`,
        public_description: form.description,
        private_detail: form.privateDetail || null,
        colour: form.colour,
        brand: form.brand || null,
        campus_location: form.location,
        event_date: form.date,
        image_url,
      })

      setSubmitted(true)
    } catch (err) {
      setError(errMsg(err, 'Failed to submit report.'))
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="page page--narrow">
        <div className="empty" style={{ borderStyle: 'solid' }}>
          <div className="empty__icon" style={{ background: 'var(--found-tint)', color: 'var(--found)' }}>
            <CheckCircle2 size={28} />
          </div>
          <h3>{isLost ? 'Lost report filed' : 'Found report filed'}</h3>
          <p>
            {isLost
              ? "We're comparing it against found items now. If one fits, you'll get an alert and the details will open up."
              : "It's in the feed as a title only. If someone's lost report matches, they'll be alerted and can start a claim."}
          </p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button className="btn btn--primary" onClick={() => navigate('/my')}>See my activity</button>
            <button className="btn btn--ghost" onClick={() => navigate('/feed')}>Back to feed</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page page--form">
      <div className="page-head">
        <div>
          <h1>{isLost ? 'Report a lost item' : 'Report a found item'}</h1>
          <p>
            {isLost
              ? 'The more detail you give, the better we can match it. If something fits, you get an alert.'
              : 'Only the item type is public. Your details open up just for people whose own lost report matches.'}
          </p>
        </div>
      </div>

      <form className="form-card" onSubmit={handleSubmit}>
        <section className="form-section">
          <h3>What is it?</h3>
          <div className="form-grid">
            <div className="field full">
              <label htmlFor="category">Category</label>
              <select id="category" className="select" required value={form.category} onChange={update('category')}>
                <option value="" disabled>Select a category</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="brand">Brand <span className="hint">(if known)</span></label>
              <input id="brand" className="input" placeholder="e.g. Sony, Wildcraft" value={form.brand} onChange={update('brand')} />
            </div>
            <div className="field">
              <label htmlFor="colour">Colour</label>
              <input id="colour" className="input" placeholder="e.g. Black" required value={form.colour} onChange={update('colour')} />
            </div>
            <div className="field full">
              <label htmlFor="description">
                {isLost ? 'Describe it' : 'Describe it (shown only to matched owners)'}
              </label>
              <textarea id="description" className="textarea" rows={4} required value={form.description}
                placeholder="Size, marks, stickers, anything a stranger could notice."
                onChange={update('description')} />
            </div>
          </div>
        </section>

        <section className="form-section">
          <h3>{isLost ? 'Where and when did you lose it?' : 'Where and when did you find it?'}</h3>
          <div className="form-grid" style={{ marginTop: 12 }}>
            <div className="field">
              <label htmlFor="location">{isLost ? 'Last seen' : 'Found at'}</label>
              <select id="location" className="select" required value={form.location} onChange={update('location')}>
                <option value="" disabled>Select a location</option>
                {LOCATIONS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="date">Date</label>
              <input id="date" className="input" type="date" required value={form.date} onChange={update('date')} />
            </div>
          </div>
        </section>

        {!isLost && (
          <section className="form-section">
            <h3>One detail only the owner would know</h3>
            <p className="hint">A hidden scratch, what's inside, a sticker under the lid. Nobody sees this but you.</p>
            <textarea id="private-detail" className="textarea" rows={2} aria-label="Private verification detail"
              value={form.privateDetail} onChange={update('privateDetail')} />
            <div className="privacy-note">
              <EyeOff size={20} style={{ flexShrink: 0 }} />
              <span>
                You'll compare this with each claimant's answer before you approve anyone. It is never shown to claimants.
              </span>
            </div>
          </section>
        )}

        <section className="form-section">
          <h3>Photo <span className="hint">(optional)</span></h3>
          <p className="hint">{isLost ? 'A photo helps finders recognise it.' : 'Shown only to matched owners.'}</p>
          <label className="upload" htmlFor="photo">
            {preview ? (
              <img src={preview} alt="Item preview" />
            ) : (
              <span style={{ display: 'grid', gap: 8, placeItems: 'center' }}>
                <ImagePlus size={28} />
                Choose a photo
              </span>
            )}
          </label>
          <input id="photo" type="file" accept="image/*" onChange={handleFile} style={{ display: 'none' }} />
        </section>

        {error && <p className="msg msg--error" role="alert" style={{ marginTop: 22 }}>{error}</p>}

        <div className="form-actions">
          <button type="button" className="btn btn--ghost" onClick={() => navigate(-1)} disabled={submitting}>
            Cancel
          </button>
          <button type="submit" className={`btn btn--${type}`} disabled={submitting}>
            {submitting ? 'Submitting…' : isLost ? 'File lost report' : 'File found report'}
          </button>
        </div>
      </form>
    </div>
  )
}
