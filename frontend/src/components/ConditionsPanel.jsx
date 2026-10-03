export default function ConditionsPanel({ impacts, loading, error }) {
  const floodRelated = Array.isArray(impacts)
    ? impacts.filter((impact) => /flood|high water|standing water|water over roadway/i.test(
      [impact.reason, impact.description, impact.impact_type].filter(Boolean).join(' '),
    )).length
    : null

  return (
    <section className="conditions-panel panel" aria-labelledby="conditions-title">
      <div className="section-heading">
        <div>
          <div className="eyebrow">REGIONAL OVERVIEW</div>
          <h2 id="conditions-title">Charleston Flood Conditions</h2>
        </div>
        <span className="schematic-tag"><span /> Schematic view</span>
      </div>

      <div className="conditions-visual">
        <div className="visual-topline">
          <span>CHARLESTON HARBOR REGION</span>
          <span>32.7765° N&nbsp;&nbsp; 79.9311° W</span>
        </div>
        <svg className="coastal-graphic" viewBox="0 0 920 286" role="img" aria-labelledby="diagram-title diagram-desc" preserveAspectRatio="xMidYMid slice">
          <title id="diagram-title">Illustrative Charleston coastal context</title>
          <desc id="diagram-desc">A schematic shoreline motif. This graphic contains no mapped flood extent or road locations.</desc>
          <path className="water-shape water-one" d="M0 202c99-19 146-64 235-56 80 8 117 48 196 38 88-11 104-71 199-82 95-11 163 24 290 8v176H0z" />
          <path className="shoreline" d="M0 202c99-19 146-64 235-56 80 8 117 48 196 38 88-11 104-71 199-82 95-11 163 24 290 8" />
          <path className="water-shape water-two" d="M0 236c89-15 151-25 225-13 78 13 126 1 194-28 92-40 149-27 231-3 83 24 173 26 270 8v86H0z" />
          <path className="contour" d="M19 103c86 17 132-17 205-6s100 45 179 31 126-60 197-48 116 39 197 22 90-27 137-15" />
          <path className="contour contour-two" d="M-8 135c90 17 136-16 211-4s103 45 182 29 121-56 193-43 120 37 200 17 90-28 149-16" />
          <path className="contour contour-three" d="M78 29c25 39 48 72 35 111s-46 63-54 121m168-212c18 47 39 74 31 118s-36 77-40 127m126-236c14 42 21 72 6 111s-47 62-56 119m177-242c17 44 27 71 13 109s-39 67-46 126m188-235c26 34 48 62 44 99s-22 73-24 126m173-204c-1 48 12 83 42 119s50 54 68 84" />
          <path className="tidal-line" d="M104 65c73 5 103 28 151 59s77 40 124 31 61-55 123-63 98 10 147 30 85 34 166 17" />
          <circle className="map-marker-halo" cx="565" cy="104" r="15" />
          <circle className="map-marker" cx="565" cy="104" r="5" />
          <text className="map-label" x="584" y="99">CHARLESTON</text>
          <text className="map-label-small" x="584" y="115">SOUTH CAROLINA</text>
          <text className="water-label" x="224" y="225">COASTAL WATERS</text>
          <text className="water-label" x="705" y="234">HARBOR</text>
          <g className="north-mark" transform="translate(862 42)">
            <path d="M0 18V0m0 0-5 8m5-8 5 8" />
            <text x="0" y="34" textAnchor="middle">N</text>
          </g>
        </svg>
        <div className="visual-overlay">
          <span className="overlay-mark" aria-hidden="true">≈</span>
          <span>Evidence view, not a flood-extent map</span>
        </div>
        <div className="conditions-footer">
          <div className="conditions-note">
            <span className="note-dot" />
            <span>This schematic shows regional context only; it does not map flooded streets or properties.</span>
          </div>
          <div className="impact-summary" aria-live="polite">
            {loading ? 'Checking road impacts…' : error ? 'Road impact data unavailable' : (
              <><strong>{impacts.length}</strong> active road impacts <span className="summary-divider">·</span> {floodRelated ? `${floodRelated} with explicit flood-related wording` : 'no source records explicitly mention flooding'}</>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}