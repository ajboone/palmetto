import { formatCharlestonTime } from './StatusCard.jsx'

function charlestonTimestamp(value) {
  if (!value) return ''
  if (!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)) {
    return value.replace('T', ' ').replace(/\.\d+$/, '').slice(0, 16)
  }
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value))
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`
}

function charlestonNow() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`
}

function TideEventPlot({ predictions }) {
  if (!predictions.length) return null
  const heights = predictions.map((prediction) => Number(prediction.height)).filter(Number.isFinite)
  if (!heights.length) return null
  const low = Math.min(...heights)
  const high = Math.max(...heights)
  const range = high - low || 1
  const points = predictions.map((prediction, index) => {
    const height = Number(prediction.height)
    return {
      x: 48 + (predictions.length === 1 ? 0 : (index / (predictions.length - 1)) * 664),
      y: 105 - ((height - low) / range) * 58,
      prediction,
    }
  })

  return (
    <svg className="tide-plot" viewBox="0 0 760 142" role="img" aria-label="Discrete NOAA predicted high and low tide events">
      <line className="plot-baseline" x1="38" y1="105" x2="722" y2="105" />
      <line className="plot-guide" x1="38" y1="47" x2="722" y2="47" />
      {points.map(({ x, y, prediction }, index) => {
        const isHigh = prediction.type?.toUpperCase() === 'H'
        return (
          <g key={`${prediction.timestamp}-${index}`}>
            <line className={`plot-stem ${isHigh ? 'high' : 'low'}`} x1={x} y1="105" x2={x} y2={y} />
            <circle className={`plot-point ${isHigh ? 'high' : 'low'}`} cx={x} cy={y} r="5.5" />
            <text className="plot-value" x={x} y={y - 12} textAnchor="middle">{Number(prediction.height).toFixed(1)} ft</text>
            <text className="plot-type" x={x} y="126" textAnchor="middle">{isHigh ? 'HIGH' : 'LOW'}</text>
          </g>
        )
      })}
    </svg>
  )
}

export default function TidePanel({ state }) {
  const predictions = Array.isArray(state.data)
    ? [...state.data].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    : []
  const nowLocal = charlestonNow()
  const nextHigh = predictions.find((prediction) => (
    prediction.type?.toUpperCase() === 'H' && charlestonTimestamp(prediction.timestamp) > nowLocal
  ))
  const nextLow = predictions.find((prediction) => (
    prediction.type?.toUpperCase() === 'L' && charlestonTimestamp(prediction.timestamp) > nowLocal
  ))

  return (
    <section className="tide-panel panel" aria-labelledby="tide-title">
      <div className="section-heading tide-heading">
        <div>
          <div className="eyebrow">NOAA CO-OPS · 8665530</div>
          <h2 id="tide-title">Today&apos;s tide outlook</h2>
        </div>
        {!state.loading && !state.error && <span className="unit-note">Predictions · ft MLLW</span>}
      </div>

      {state.loading ? (
        <div className="tide-loading" role="status">Loading tide predictions…</div>
      ) : state.error ? (
        <div className="inline-unavailable" role="status">Tide predictions unavailable. {state.error}</div>
      ) : predictions.length === 0 ? (
        <div className="inline-unavailable" role="status">No tide predictions were returned for today.</div>
      ) : (
        <>
          <div className="tide-legend"><span><i className="legend-high" /> High water</span><span><i className="legend-low" /> Low water</span><span>Discrete NOAA predictions</span></div>
          <TideEventPlot predictions={predictions} />
          <div className="next-tides" aria-label="Next predicted tide events">
            {[['NEXT HIGH', nextHigh, 'high'], ['NEXT LOW', nextLow, 'low']].map(([label, prediction, tone]) => (
              <div className={`next-tide ${tone}`} key={label}>
                <span className="next-tide-label">{label}</span>
                {prediction ? (
                  <><strong>{Number(prediction.height).toFixed(2)} ft</strong><span>{formatCharlestonTime(prediction.timestamp)}</span></>
                ) : <span>No further prediction today</span>}
              </div>
            ))}
          </div>
          <div className="tide-events">
            {predictions.map((prediction, index) => {
              const isHigh = prediction.type?.toUpperCase() === 'H'
              return (
                <div className="tide-event" key={`${prediction.timestamp}-${index}`}>
                  <span className={`event-marker ${isHigh ? 'high' : 'low'}`} />
                  <span className="event-label">{isHigh ? 'High tide' : 'Low tide'}</span>
                  <span className="event-time">{formatCharlestonTime(prediction.timestamp)}</span>
                  <strong className="event-height">{Number(prediction.height).toFixed(2)} ft</strong>
                </div>
              )
            })}
          </div>
        </>
      )}
    </section>
  )
}