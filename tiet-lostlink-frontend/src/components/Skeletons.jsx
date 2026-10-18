export function CardSkeletons({ count = 6 }) {
  return (
    <div className="ticket-grid" aria-busy="true" aria-label="Loading reports">
      {Array.from({ length: count }).map((_, i) => (
        <div className="skeleton-card" key={i}>
          <div className="skeleton" style={{ height: 150 }} />
          <div style={{ padding: '14px 8px 8px' }}>
            <div className="skeleton" style={{ height: 14, width: '40%', marginBottom: 12 }} />
            <div className="skeleton" style={{ height: 20, width: '85%', marginBottom: 10 }} />
            <div className="skeleton" style={{ height: 14, width: '60%' }} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function BlockSkeleton({ height = 220 }) {
  return <div className="skeleton" style={{ height, width: '100%' }} aria-busy="true" />
}
