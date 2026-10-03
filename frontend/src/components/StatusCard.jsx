function Skeleton({ width = '62%' }) {
  return <span className="skeleton" style={{ width }} aria-label="Loading" />
}

export function formatCharlestonTime(value) {
  if (!value) return 'Time unavailable'
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)
  const localTimestamp = value.replace(' ', 'T')
  const date = hasZone
    ? new Date(localTimestamp)
    : new Date(`${localTimestamp.replace(/(\.\d+)?$/, '')}Z`)
  if (Number.isNaN(date.getTime())) return 'Time unavailable'
  return new Intl.DateTimeFormat('en-US', {
    timeZone: hasZone ? 'America/New_York' : 'UTC',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    ...(hasZone ? { timeZoneName: 'short' } : {}),
  }).format(date) + (hasZone ? '' : ' Charleston')
}

export default function StatusCard({
  eyebrow,
  icon,
  accent,
  loading,
  error,
  value,
  unit,
  detail,
  footnote,
  valueTone,
}) {
  return (
    <article className={`status-card ${accent ?? ''}`}>
      <div className="status-card-top">
        <div className="status-eyebrow">{eyebrow}</div>
        <span className="status-icon" aria-hidden="true">{icon}</span>
      </div>
      <div className="status-value-line">
        {loading ? <Skeleton width="46%" /> : error ? (
          <span className="unavailable">Unavailable</span>
        ) : (
          <>
            <span className={`status-value ${valueTone ?? ''}`}>{value}</span>
            {unit && <span className="status-unit">{unit}</span>}
          </>
        )}
      </div>
      <div className="status-detail">
        {loading ? <Skeleton width="72%" /> : error ? error : detail}
      </div>
      {footnote && !error && <div className="status-footnote">{footnote}</div>}
    </article>
  )
}