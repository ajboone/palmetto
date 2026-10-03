const API_BASE_URL = import.meta.env.VITE_PALMETTO_API_URL ?? ''

async function request(path, options) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch {
    throw new Error('PALMETTO API is unreachable. Check that the backend is running.')
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Keep the concise status message when the server response is not JSON.
    }
    throw new Error(detail)
  }

  return response.json()
}

export const getHealth = () => request('/api/health')
export const getCurrentWaterLevel = () => request('/api/tides/current')
export const getCurrentRisk = () => request('/api/risk/current')
export const getRoadImpacts = () => request('/api/roads/impacts')
export const getTidePredictions = () => request('/api/tides/today')

export const askPalmetto = (question) => request('/api/agent/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question }),
})