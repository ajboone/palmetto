const navigation = ['Overview', 'Conditions', 'Ask PALMETTO', 'About']

function PalmettoMark() {
  return (
    <svg className="palmetto-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 14.4C12.2 9.9 8.2 7.2 3.5 6.2c2.1 4.8 6.2 7.4 12.5 8.9" />
        <path d="M16 14.4C11.2 12.4 7.3 11.8 3 12.6c3.3 3.4 7.6 4.4 13 3.1" />
        <path d="M16 14.4C11.1 15 7.4 16.5 4.1 19.3c4.3 1.5 8.5.4 12.2-2.7" />
        <path d="M16 14.4c-2 5.3-2.5 10.2-1.7 15.2 3.4-3.8 4.2-8.7 2.6-14.7" />
        <path d="M16 14.4c2.3-4.7 6.1-7.5 12.5-8.3-2.1 4.5-6.2 7.5-12.5 9.1" />
        <path d="M16 14.4c4.7-2.1 8.9-2.3 13-1.2-2.7 3.2-7 4.3-13 3.5" />
        <path d="M16 14.4c4.9.8 8.6 2.4 11.8 5-4.4 1.2-8.4.1-12.4-3.1" />
        <path d="M14.8 29.5h4.1M15.4 24.8h3.2" />
      </g>
      <circle cx="16" cy="14.3" r="1.4" fill="currentColor" />
    </svg>
  )
}

export default function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Main navigation">
      <a className="brand" href="#overview" aria-label="PALMETTO overview">
        <span className="brand-mark" aria-hidden="true">
          <PalmettoMark />
        </span>
        <span className="brand-name">PALMETTO</span>
        <span className="brand-caption">Flood Decision Intelligence</span>
      </a>

      <div className="nav-label">WORKSPACE</div>
      <nav className="side-nav">
        {navigation.map((item, index) => (
          <a
            className={`nav-item${index === 0 ? ' active' : ''}`}
            href={index === 0 ? '#overview' : '#ask'}
            key={item}
            aria-current={index === 0 ? 'page' : undefined}
          >
            <span className="nav-icon" aria-hidden="true">{['◫', '⌁', '↗', 'i'][index]}</span>
            <span>{item}</span>
          </a>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <div className="coast-mark" aria-hidden="true">
          <span className="coast-line" />
          <span className="coast-dot" />
          <span className="coast-code">SC · 32.78° N</span>
        </div>
        <div className="sidebar-location">CHARLESTON, SOUTH CAROLINA</div>
        <div className="sidebar-footnote">Local evidence. Clear decisions.</div>
      </div>
    </aside>
  )
}