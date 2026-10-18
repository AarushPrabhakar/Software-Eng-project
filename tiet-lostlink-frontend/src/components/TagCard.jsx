import { Link } from 'react-router-dom'
import { Calendar, Lock, MapPin, Sparkles } from 'lucide-react'
import StampBadge from './StampBadge.jsx'
import CategoryIcon from './CategoryIcon.jsx'

export default function TagCard({ item }) {
  const statusKind = item.status === 'active' ? item.type : item.status
  const matched = item.access === 'matched'
  return (
    <Link
      to={`/item/${item.id}`}
      className={`ticket ticket--${item.type}${matched ? ' is-matched' : ''}`}
    >
      <div className="ticket__media">
        {item.redacted ? (
          <div className="ticket__lock">
            <Lock size={22} />
            Details hidden
          </div>
        ) : item.imageUrl ? (
          <img src={item.imageUrl} alt="" loading="lazy" />
        ) : (
          <CategoryIcon category={item.category} size={52} strokeWidth={1.5} />
        )}
      </div>

      <div className="ticket__body">
        <div className="ticket__top">
          <StampBadge kind={statusKind} />
          <span className="ticket__cat">
            <CategoryIcon category={item.category} size={15} />
            {item.category}
          </span>
        </div>

        <h3 className="ticket__title">{item.title}</h3>

        {item.redacted ? (
          <>
            <div className="redact" aria-hidden="true">
              <i />
              <i />
            </div>
            <span className="ticket__hidden-note">Only the owner can see the rest</span>
          </>
        ) : (
          <>
            {item.description && <p className="ticket__desc">{item.description}</p>}
            <div className="ticket__facts">
              {item.location && item.location !== '—' && (
                <span><MapPin size={14} />{item.location}</span>
              )}
              {item.date && (
                <span>
                  <Calendar size={14} />
                  {new Date(item.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                </span>
              )}
            </div>
          </>
        )}

        {matched && (
          <span className="ticket__match">
            <Sparkles size={14} />
            Could be yours: {item.matchScore}% match
          </span>
        )}
      </div>

      <div className="ticket__stub">
        <span className="ticket__code">{item.id}</span>
        <span>View</span>
      </div>
    </Link>
  )
}
