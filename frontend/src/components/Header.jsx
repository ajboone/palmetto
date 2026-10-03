function greetingForNow() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning, Charleston'
  if (hour < 17) return 'Good afternoon, Charleston'
  return 'Good evening, Charleston'
}

export default function Header({ apiOnline, refreshing, onRefresh }) {
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow">CHARLESTON · DAILY BRIEFING</div>
        <h1>{greetingForNow()}</h1>
        <p className="header-subtitle">Here&apos;s what the water is doing.</p>
      </div>
      <div className="header-tools">
        <div className="location-label">
          <span className="location-pin" aria-hidden="true">⌖</span>
          <span>Charleston, South Carolina</span>
        </div>
        <div className={`live-indicator ${apiOnline ? 'online' : 'offline'}`} role="status">
          <span className="live-dot" />
          {apiOnline ? 'Live data' : 'API unavailable'}
        </div>
        <button
          className="icon-button refresh-button"
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          aria-label="Refresh dashboard data"
          title="Refresh dashboard data"
        >
          <svg className={refreshing ? 'spin' : ''} viewBox="0 0 24 24" aria-hidden="true">
            <path d="M20 7v5h-5M4 17v-5h5" />
            <path d="M6.2 9A6.5 6.5 0 0 1 17 6l3 6M4 12l3 6a6.5 6.5 0 0 0 10.8-3" />
          </svg>
        </button>
      </div>
    </header>
  )
}