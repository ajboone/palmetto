import { useState } from 'react'
import { askPalmetto } from '../api/palmetto.js'
import EvidenceList from './EvidenceList.jsx'

const examples = [
  'What should I know about flooding today?',
  'I need to be downtown this afternoon.',
  'Are any roads flooded right now?',
]

function renderInline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

const answerSections = {
  'bottom line': { key: 'bottom-line', title: 'Bottom line' },
  'what palmetto found': { key: 'findings', title: 'What PALMETTO found' },
  'recommended action': { key: 'action', title: 'Recommended action' },
  confidence: { key: 'confidence', title: 'Confidence' },
}

function getSectionHeading(line) {
  const isMarkdownHeading = /^#{1,3}\s+/.test(line)
  const heading = line
    .replace(/^#{1,3}\s+/, '')
    .replace(/^\*\*(.+)\*\*$/, '$1')
    .replace(/:$/, '')
    .trim()
  const known = answerSections[heading.toLowerCase()]
  if (known) return known
  return isMarkdownHeading ? { key: 'other', title: heading } : null
}

function renderAnswerBlocks(lines, sectionKey) {
  const blocks = []
  let paragraphs = []
  let bullets = []
  let blockIndex = 0

  const flushParagraph = () => {
    if (!paragraphs.length) return
    blocks.push(<p key={`${sectionKey}-p-${blockIndex++}`}>{renderInline(paragraphs.join(' '))}</p>)
    paragraphs = []
  }
  const flushBullets = () => {
    if (!bullets.length) return
    blocks.push(<ul className="answer-bullets" key={`${sectionKey}-ul-${blockIndex++}`}>{bullets}</ul>)
    bullets = []
  }

  lines.forEach((line, index) => {
    if (!line) {
      flushParagraph()
      flushBullets()
      return
    }
    const bullet = line.match(/^(?:[-*•])\s+(.+)$/)
    if (bullet) {
      flushParagraph()
      bullets.push(<li key={`${sectionKey}-li-${index}`}>{renderInline(bullet[1])}</li>)
      return
    }
    flushBullets()
    paragraphs.push(line)
  })
  flushParagraph()
  flushBullets()
  return blocks
}

function AnswerText({ answer }) {
  const sections = []
  let current = { key: 'intro', title: '', lines: [] }
  const flushSection = () => {
    if (!current.lines.some((line) => line.length)) return
    sections.push(current)
  }

  answer.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim()
    const heading = line ? getSectionHeading(line) : null
    if (heading) {
      flushSection()
      current = { ...heading, lines: [] }
    } else {
      current.lines.push(line)
    }
  })
  flushSection()

  return (
    <div className="answer-copy">
      {sections.map((section, index) => (
        <section className={`answer-section ${section.key}`} key={`${section.key}-${index}`}>
          {section.title && <h4>{section.title}</h4>}
          <div className="answer-section-body">
            {renderAnswerBlocks(section.lines, section.key)}
          </div>
        </section>
      ))}
    </div>
  )
}

export default function AskPalmetto() {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submitQuestion(value = question) {
    const cleaned = value.trim()
    if (!cleaned || loading) return
    setQuestion(cleaned)
    setResult(null)
    setError('')
    setLoading(true)
    try {
      setResult(await askPalmetto(cleaned))
    } catch (requestError) {
      setError(requestError.message || 'PALMETTO could not complete the request.')
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(event) {
    event.preventDefault()
    void submitQuestion()
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submitQuestion()
    }
  }

  return (
    <aside className="ask-panel" id="ask" aria-labelledby="ask-title">
      <div className="ask-panel-head">
        <div className="eyebrow">PALMETTO INTELLIGENCE</div>
        <h2 id="ask-title">Ask PALMETTO</h2>
        <p>Turn Charleston&apos;s flood data into a decision.</p>
      </div>

      <form className="question-form" onSubmit={onSubmit}>
        <label className="visually-hidden" htmlFor="question">Ask about Charleston conditions</label>
        <textarea
          id="question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about today's conditions…"
          rows={3}
          disabled={loading}
        />
        <div className="composer-footer">
          <span className="composer-hint">Enter to ask · Shift + Enter for a new line</span>
          <button className="ask-button" type="submit" disabled={loading || !question.trim()}>
            {loading ? <><span className="button-spinner" /> Analyzing</> : <>Ask <span aria-hidden="true">↗</span></>}
          </button>
        </div>
      </form>

      {!result && !loading && !error && (
        <div className="example-questions">
          <div className="example-label">SUGGESTED QUESTIONS</div>
          {examples.map((example) => (
            <button className="example-chip" key={example} type="button" onClick={() => void submitQuestion(example)}>
              <span>{example}</span><span aria-hidden="true">↗</span>
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="agent-state analyzing" role="status" aria-live="polite">
          <div className="analysis-heading">
            <span className="analysis-orbit" aria-hidden="true"><i /><i /><i /></span>
            <div><strong>PALMETTO is checking Charleston conditions…</strong><p>Reviewing relevant evidence for your question.</p></div>
          </div>
          <div className="analysis-categories-label">EVIDENCE CATEGORIES UNDER REVIEW</div>
          <ul className="analysis-categories">
            {['Harbor water levels', 'Tide predictions', 'Weather and alerts', 'Road impacts', 'Flood-risk assessment'].map((category) => (
              <li key={category}><span aria-hidden="true" />{category}</li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div className="agent-error" role="alert">
          <div className="error-mark" aria-hidden="true">!</div>
          <div><strong>Couldn&apos;t complete that request</strong><p>{error}</p></div>
        </div>
      )}

      {result && (
        <div className="agent-result" aria-live="polite">
          <div className="answer-topline"><span className="answer-status-dot" /> PALMETTO RESPONSE</div>
          <AnswerText answer={result.answer} />
          <EvidenceList tools={result.tools_used} limitations={result.limitations} />
          <div className="response-meta">
            <span>{result.tool_call_count} tool call{result.tool_call_count === 1 ? '' : 's'}</span>
            <span>{result.model}</span>
          </div>
        </div>
      )}

      <div className="ask-panel-foot">
        Decision support, not an official emergency warning system.
      </div>
    </aside>
  )
}