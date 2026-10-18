import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, SearchX, Plus } from 'lucide-react'
import TagCard from '../components/TagCard.jsx'
import EmptyState from '../components/EmptyState.jsx'
import { CardSkeletons } from '../components/Skeletons.jsx'
import api, { errMsg } from '../api.js'
import { CATEGORIES, LOCATIONS, toViewItem } from '../data/mockItems.js'

export default function Feed() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const [query, setQuery] = useState('')
  const [type, setType] = useState('all')
  const [category, setCategory] = useState('all')
  const [location, setLocation] = useState('all')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError('')

    api
      .get('/reports')
      .then((res) => {
        if (cancelled) return
        setItems(res.data.reports.map(toViewItem))
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(errMsg(err, 'Failed to load reports.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const filtered = useMemo(() => {
    return items.filter((item) => {
      if (type !== 'all' && item.type !== type) return false
      if (category !== 'all' && item.category !== category) return false
      if (location !== 'all' && item.location !== location) return false
      if (query.trim()) {
        const q = query.toLowerCase()
        const haystack = `${item.title} ${item.description} ${item.brand}`.toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [items, query, type, category, location])

  const couldBeYours = items.filter((i) => i.access === 'matched').length
  const filtersOn = query || type !== 'all' || category !== 'all' || location !== 'all'

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Campus feed</h1>
          <p>
            Lost items are public. Found items show only their type until one of your lost reports matches.
          </p>
        </div>
        <div className="page-head__actions">
          <Link to="/report/lost" className="btn btn--lost"><Plus size={18} />I lost something</Link>
          <Link to="/report/found" className="btn btn--found"><Plus size={18} />I found something</Link>
        </div>
      </div>

      {couldBeYours > 0 && (
        <p className="msg msg--info" role="status" style={{ marginTop: 0, marginBottom: 20 }}>
          {couldBeYours === 1 ? 'A found item' : `${couldBeYours} found items`} matched your lost reports. Look for the yellow tag.
        </p>
      )}

      <div className="filters">
        <div className="field">
          <label htmlFor="search">Search</label>
          <div className="input-icon">
            <Search size={18} />
            <input id="search" className="input" placeholder="Brand, colour, keyword" value={query}
              onChange={(e) => setQuery(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="category">Category</label>
          <select id="category" className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="all">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="location">Location</label>
          <select id="location" className="select" value={location} onChange={(e) => setLocation(e.target.value)}>
            <option value="all">All locations</option>
            {LOCATIONS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div className="segmented" role="group" aria-label="Report type">
          {['all', 'lost', 'found'].map((t) => (
            <button key={t} className={type === t ? 'is-active' : ''} onClick={() => setType(t)}>
              {t === 'all' ? 'All' : t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <CardSkeletons />
      ) : loadError ? (
        <EmptyState icon={SearchX} title="Couldn't load the feed">
          {loadError}
        </EmptyState>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title={filtersOn ? 'Nothing matches those filters' : 'No reports yet'}
          action={
            filtersOn ? (
              <button className="btn btn--ghost" onClick={() => { setQuery(''); setType('all'); setCategory('all'); setLocation('all') }}>
                Clear filters
              </button>
            ) : (
              <Link to="/report/lost" className="btn btn--primary">Report the first item</Link>
            )
          }
        >
          {filtersOn ? 'Try removing a filter, or report the item yourself.' : 'Be the first to report something lost or found on campus.'}
        </EmptyState>
      ) : (
        <>
          <p className="result-count">{filtered.length} {filtered.length === 1 ? 'report' : 'reports'}</p>
          <div className="ticket-grid">
            {filtered.map((item) => <TagCard key={item.id} item={item} />)}
          </div>
        </>
      )}
    </div>
  )
}
