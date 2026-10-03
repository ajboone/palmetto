import { useEffect, useState } from 'react'
import {
  getCurrentRisk,
  getCurrentWaterLevel,
  getHealth,
  getRoadImpacts,
  getTidePredictions,
} from './api/palmetto.js'
import AskPalmetto from './components/AskPalmetto.jsx'
import ConditionsPanel from './components/ConditionsPanel.jsx'
import Header from './components/Header.jsx'
import Sidebar from './components/Sidebar.jsx'
import StatusCard, { formatCharlestonTime } from './components/StatusCard.jsx'
import TidePanel from './components/TidePanel.jsx'

const initialResource = { loading: true, data: null, error: '' }

function getActiveRisk(resource) {
  if (!resource.data) return null
  return resource.data.risk_level || null
}

function getRoadCount(resource) {
  return Array.isArray(resource.data) ? resource.data.length : null
}

export default function App() {
  const [water, setWater] = useState(initialResource)
  const [risk, setRisk] = useState(initialResource)
  const [roads, setRoads] = useState(initialResource)
  const [tides, setTides] = useState(initialResource)
  const [apiOnline, setApiOnline] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  async function loadResource(fetcher, setter) {
    setter({ loading: true, data: null, error: '' })
    try {
      setter({ loading: false, data: await fetcher(), error: '' })
    } catch (error) {
      setter({ loading: false, data: null, error: error.message || 'Data unavailable' })
    }
  }

  async function refreshDashboard() {
    setRefreshing(true)
    const healthCheck = getHealth().then(() => setApiOnline(true)).catch(() => setApiOnline(false))
    await Promise.all([
      loadResource(getCurrentWaterLevel, setWater),
      loadResource(getCurrentRisk, setRisk),
      loadResource(getRoadImpacts, setRoads),
      loadResource(getTidePredictions, setTides),
      healthCheck,
    ])
    setRefreshing(false)
  }

  useEffect(() => {
    void refreshDashboard()
  }, [])

  const riskLevel = getActiveRisk(risk)
  const riskPartial = risk.data?.evidence_status && risk.data.evidence_status !== 'AVAILABLE'
  const score = risk.data?.score
  const roadsCount = getRoadCount(roads)
  const floodRoadCount = Array.isArray(roads.data)
    ? roads.data.filter((impact) => /flood|high water|standing water|water over roadway/i.test(
      [impact.reason, impact.description, impact.impact_type].filter(Boolean).join(' '),
    )).length
    : null

  return (
    <div className="app-shell" id="overview">
      <Sidebar />
      <main className="dashboard-main">
        <Header apiOnline={apiOnline} refreshing={refreshing} onRefresh={() => void refreshDashboard()} />

        <section className="status-grid" aria-label="Current Charleston status">
          <StatusCard
            eyebrow="WATER LEVEL"
            icon="≈"
            accent="water-card"
            loading={water.loading}
            error={water.error}
            value={water.data ? Number(water.data.value).toFixed(2) : undefined}
            unit={water.data?.unit}
            detail={water.data ? `Charleston Harbor · ${water.data.datum}` : undefined}
            footnote={water.data ? `Observed ${formatCharlestonTime(water.data.timestamp)}` : undefined}
          />
          <StatusCard
            eyebrow="FLOOD ASSESSMENT"
            icon="⌁"
            accent={risk.data && !riskLevel ? 'risk-card partial' : riskLevel && ['HIGH', 'SEVERE'].includes(riskLevel) ? 'risk-card elevated' : 'risk-card'}
            loading={risk.loading}
            error={risk.error}
            value={risk.data ? riskLevel ?? 'PARTIAL' : undefined}
            valueTone={risk.data && !riskLevel ? 'partial-value' : ''}
            detail={risk.data ? (riskLevel ? (riskPartial ? 'Evidence is incomplete' : 'PALMETTO prototype category') : 'Assessment incomplete · category withheld') : undefined}
            footnote={risk.data && Number.isFinite(score) ? `Prototype PALMETTO score · ${score} / ${risk.data.max_score}` : undefined}
          />
          <StatusCard
            eyebrow="ROAD IMPACTS"
            icon="↗"
            accent="road-card"
            loading={roads.loading}
            error={roads.error}
            value={roadsCount ?? undefined}
            unit={roadsCount === 1 ? 'impact' : 'impacts'}
            detail={roads.data ? 'Active road impacts reported' : undefined}
            footnote={roads.data ? (floodRoadCount ? `${floodRoadCount} with explicit flood-related wording` : 'No source records explicitly mention flooding') : undefined}
          />
        </section>

        <ConditionsPanel impacts={roads.data ?? []} loading={roads.loading} error={roads.error} />
        <TidePanel state={tides} />

        <footer className="dashboard-footer">
          <span>Evidence-led decision support for Charleston</span>
          <span>Not an official emergency warning system</span>
        </footer>
      </main>
      <AskPalmetto />
    </div>
  )
}