const labels = {
  get_current_water_level: 'NOAA Water Level',
  get_tide_predictions: 'NOAA Tide Predictions',
  get_hourly_weather: 'NWS Hourly Forecast',
  get_precipitation_forecast: 'NWS Precipitation',
  get_weather_alerts: 'NWS Weather Alerts',
  get_road_impacts: 'Charleston Road Impacts',
  get_flood_risk: 'PALMETTO Flood Risk Engine',
}

export default function EvidenceList({ tools = [], limitations = [] }) {
  return (
    <div className="evidence-block">
      <div className="evidence-heading">WHAT PALMETTO CHECKED</div>
      {tools.length ? (
        <ul className="evidence-list">
          {tools.map((tool, index) => (
            <li className="evidence-item" key={`${tool}-${index}`}>
              <span className="evidence-check" aria-hidden="true">✓</span>
              <span>{labels[tool] ?? 'PALMETTO evidence source'}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="evidence-empty">No evidence tools were needed for this answer.</p>
      )}
      {limitations.length > 0 && (
        <div className="limitations" role="note">
          <div className="limitations-title"><span aria-hidden="true">!</span> Evidence limitations</div>
          <ul>
            {limitations.map((limitation, index) => <li key={`${limitation}-${index}`}>{limitation}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}