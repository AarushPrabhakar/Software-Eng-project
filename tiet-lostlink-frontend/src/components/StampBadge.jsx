const LABELS = {
  lost: 'Lost',
  found: 'Found',
  claimed: 'Claim in progress',
  returned: 'Returned',
  matched: 'Match found',
  flagged: 'Under review',
  closed: 'Closed',
  submitted: 'Submitted',
  under_review: 'Under review',
  approved: 'Approved',
  rejected: 'Not approved',
  withdrawn: 'Withdrawn',
}

export default function StampBadge({ kind }) {
  return <span className={`badge badge--${kind}`}>{LABELS[kind] || kind}</span>
}
