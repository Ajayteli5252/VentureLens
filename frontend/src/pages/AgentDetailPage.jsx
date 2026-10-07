import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getSession } from '../services/api';
import MarkdownRenderer from '../components/MarkdownRenderer';
import './AgentDetailPage.css';

const AGENT_CONFIGS = {
  coordinator: {
    name: 'Coordinator Agent',
    icon: '🤖',
    color: '#E86F2D',
    role: 'Understands the startup idea and coordinates parallel research briefs.',
    task: 'Formulate research problem statement, scope target domains, and delegate structured research assignments.',
    activityChecklist: [
      'Analyzed submitted startup idea',
      'Structured 4 specialized research domains',
      'Assigned briefs to Market, Competitor, Financial, and Risk agents',
      'Initiated parallel agent pipeline execution',
    ],
    assignedTasks: [
      'Market Research Brief',
      'Competitor Analysis Brief',
      'Financial Feasibility Brief',
      'Risk Assessment Brief',
    ],
  },
  market: {
    name: 'Market Research Agent',
    icon: '📊',
    color: '#1E7F5C',
    role: 'Researches target audience, market size (TAM/SAM/SOM), demand, and industry trends.',
    task: 'Analyze market opportunity, calculate market sizing, assess growth rates, and identify target customer personas.',
    activityChecklist: [
      'Gathered market size indicators and TAM/SAM/SOM estimates',
      'Evaluated target customer demand and willingness-to-pay',
      'Identified key industry tailwinds and market growth drivers',
      'Compiled structured Market Research Report with citations',
    ],
  },
  competitor: {
    name: 'Competitor Analysis Agent',
    icon: '🔎',
    color: '#3B82F6',
    role: 'Maps direct and indirect competitors, market positioning, strengths, weaknesses, and moats.',
    task: 'Identify existing market players, analyze rival features and pricing, pinpoint differentiation moats, and assess market saturation.',
    activityChecklist: [
      'Identified top direct & indirect competitors in the domain',
      'Analyzed competitor strengths, weaknesses, and pricing tiers',
      'Mapped competitive positioning and defensible moats',
      'Generated Competitor Landscape Matrix and sources',
    ],
  },
  financial: {
    name: 'Financial Feasibility Agent',
    icon: '💰',
    color: '#B8860B',
    role: 'Evaluates revenue models, unit economics, startup setup costs, and break-even timelines.',
    task: 'Formulate revenue model recommendations, estimate initial cap-ex and op-ex costs, calculate margin structures, and forecast break-even.',
    activityChecklist: [
      'Designed primary and secondary revenue model streams',
      'Estimated initial infrastructure and operational setup costs',
      'Evaluated unit economics, customer acquisition costs, and margins',
      'Calculated projected break-even timeline and financial assumptions',
    ],
  },
  risk: {
    name: 'Risk Assessment Agent',
    icon: '⚠️',
    color: '#B3261E',
    role: 'Evaluates technical pitfalls, legal & regulatory compliance, market adoption hazards, and operational risks.',
    task: 'Identify critical vulnerabilities across technical feasibility, regulatory obstacles, intellectual property, and market adoption risks.',
    activityChecklist: [
      'Scanned regulatory, legal, and compliance bottlenecks',
      'Assessed technical complexity and feasibility hazards',
      'Identified operational dependencies and execution risks',
      'Formulated risk mitigation strategies for founder',
    ],
  },
  debate: {
    name: 'Comparator / Debate Agent',
    icon: '⚖️',
    color: '#8B5CF6',
    role: 'Cross-checks findings across all 4 research agents and resolves conflicting claims or over-optimistic assumptions.',
    task: 'Perform adversarial cross-verification of Market, Competitor, Financial, and Risk reports to reconcile conflicting data.',
    activityChecklist: [
      'Ingested reports from Market, Competitor, Financial, and Risk agents',
      'Identified cross-domain discrepancies and over-optimistic projections',
      'Reconciled conflicting market size and cost assumptions',
      'Produced finalized balanced research synthesis for Investment Verdict',
    ],
  },
  verdict: {
    name: 'Investor Verdict Agent',
    icon: '🏆',
    color: '#D97706',
    role: 'Synthesizes all research and debated trade-offs into an overall score (/10) and definitive Go/No-Go investment verdict.',
    task: 'Perform final investment committee evaluation, assign weighted viability score out of 10, determine Go/No-Go recommendation, and write detailed verdict justification.',
    activityChecklist: [
      'Reviewed comprehensive findings from all 6 upstream agents',
      'Applied weighted scoring framework across Market, Product, Financials, and Risk',
      'Calculated overall startup viability score out of 10',
      'Issued definitive Go / No-Go investment recommendation and thesis',
    ],
  },
};

// Alias comparator to debate
AGENT_CONFIGS.comparator = AGENT_CONFIGS.debate;

export const ALL_AGENTS = [
  { key: 'coordinator', name: 'Coordinator', icon: '🤖' },
  { key: 'market', name: 'Market', icon: '📊' },
  { key: 'competitor', name: 'Competitor', icon: '🔎' },
  { key: 'financial', name: 'Financial', icon: '💰' },
  { key: 'risk', name: 'Risk', icon: '⚠️' },
  { key: 'debate', name: 'Debate', icon: '⚖️' },
  { key: 'verdict', name: 'Verdict', icon: '🏆' },
];

function normalizeAgentKey(param) {
  if (!param) return 'market';
  const clean = param.toLowerCase().trim();
  if (clean === 'comparator' || clean === 'debate') return 'debate';
  if (clean === 'coordinator') return 'coordinator';
  if (clean === 'market') return 'market';
  if (clean === 'competitor') return 'competitor';
  if (clean === 'financial') return 'financial';
  if (clean === 'risk') return 'risk';
  if (clean === 'verdict' || clean === 'investor') return 'verdict';
  return clean;
}

export default function AgentDetailPage() {
  const { sessionId, agent } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const agentKey = normalizeAgentKey(agent);
  const config = AGENT_CONFIGS[agentKey] || AGENT_CONFIGS.market;

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }

    setLoading(true);
    getSession(sessionId)
      .then((data) => {
        setSession(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load agent details.');
        setLoading(false);
      });
  }, [sessionId, navigate]);

  if (loading) {
    return (
      <div className="agent-detail-loading animate-fade-in">
        <div className="agent-spinner" />
        <p>Loading agent details...</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="agent-detail-error animate-fade-in">
        <span className="error-icon">⚠️</span>
        <h3>Agent Details Unavailable</h3>
        <p>
          {error || 'Session not found. The validation session may have expired or the server was restarted.'}
        </p>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Session ID: <code style={{ fontFamily: 'monospace', fontSize: '11px' }}>{sessionId}</code>
        </p>
        <div style={{ display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button type="button" className="action-btn-primary" onClick={() => navigate('/')}>
            Start New Validation
          </button>
          {sessionId && (
            <button type="button" className="action-btn-secondary" onClick={() => navigate(`/result/${sessionId}`)}>
              Try Result Page
            </button>
          )}
        </div>
      </div>
    );
  }

  const idea = session.startup_idea || '';
  const agentResults = session.agent_results || {};
  const validationResult = session.validation_result || {};

  // Extract agent-specific output with multi-key fallback
  let agentOutput = '';

  switch (agentKey) {
    case 'coordinator':
      // Coordinator has no separate output key in agent_results — generate a summary
      agentOutput = agentResults.coordinator
        || `The Coordinator Agent analyzed the submitted startup idea: "${idea}" and delegated structured research briefs to the Market Research, Competitor Analysis, Financial Feasibility, and Risk Assessment agents running in parallel.`;
      break;
    case 'market':
      agentOutput = agentResults.market || agentResults['Market Research Agent'] || '';
      break;
    case 'competitor':
      agentOutput = agentResults.competitor || agentResults['Competitor Analysis Agent'] || '';
      break;
    case 'financial':
      agentOutput = agentResults.financial || agentResults['Financial Feasibility Agent'] || '';
      break;
    case 'risk':
      agentOutput = agentResults.risk || agentResults['Risk Assessment Agent'] || '';
      break;
    case 'debate':
      agentOutput = agentResults.debate
        || agentResults.comparator
        || session.debate_result
        || agentResults['Comparator / Debate Agent']
        || '';
      break;
    case 'verdict':
      agentOutput = agentResults.verdict
        || session.verdict_result
        || validationResult.justification
        || validationResult.raw
        || agentResults['Investor Verdict Agent']
        || '';
      break;
    default:
      agentOutput = agentResults[agentKey] || '';
  }

  // Extract URLs for sources
  const extractUrls = (text) => {
    if (!text) return [];
    const matches = text.match(/https?:\/\/[^\s()<>"]+/g) || [];
    return [...new Set(matches.map((url) => url.replace(/[.,;:)\]]+$/, '')))];
  };

  const sources = extractUrls(agentOutput);

  // Extract search queries from event log
  const eventLog = session.event_log || [];
  const searchQueries = eventLog
    .filter(
      (ev) =>
        ev.type === 'agent_activity' &&
        ev.agent === config.name &&
        ev.message &&
        ev.message.startsWith('Searching: ')
    )
    .map((ev) => ev.message.replace('Searching: ', '').trim())
    .filter((q, idx, arr) => arr.indexOf(q) === idx); // unique

  return (
    <div className="agent-detail-page animate-fade-in-up">
      <div className="agent-detail-container">

        {/* Back navigation bar */}
        <div className="agent-detail-nav">
          <button
            type="button"
            className="back-btn"
            onClick={() => {
              if (window.history.length > 2) {
                navigate(-1);
              } else {
                navigate(`/report/${sessionId}`);
              }
            }}
          >
            ← Back
          </button>
          <div className="quick-links">
            <Link to={`/validate/${sessionId}`} className="nav-sub-link">Pipeline</Link>
            <span className="dot-sep">•</span>
            <Link to={`/result/${sessionId}`} className="nav-sub-link">Results</Link>
            <span className="dot-sep">•</span>
            <Link to={`/report/${sessionId}`} className="nav-sub-link">Report</Link>
            <span className="dot-sep">•</span>
            <Link to={`/chat/${sessionId}`} className="nav-sub-link">Chat</Link>
          </div>
        </div>

        {/* Agent Switcher Pills Bar */}
        <div className="agent-switcher-bar">
          <span className="switcher-label">Select Agent:</span>
          <div className="switcher-pills">
            {ALL_AGENTS.map((item) => (
              <Link
                key={item.key}
                to={`/agent/${sessionId}/${item.key}`}
                className={`switcher-pill ${agentKey === item.key ? 'switcher-pill--active' : ''}`}
              >
                <span className="pill-icon">{item.icon}</span>
                <span className="pill-name">{item.name}</span>
              </Link>
            ))}
          </div>
        </div>

        {/* Agent Header Hero Banner */}
        <div className="agent-hero-card" style={{ borderColor: `${config.color}33` }}>
          <div className="agent-hero-top">
            <div className="agent-hero-identity">
              <span className="agent-hero-icon" style={{ background: `${config.color}15` }}>
                {config.icon}
              </span>
              <div>
                <h1 className="agent-hero-title">{config.name}</h1>
                <span className="agent-hero-type-tag">CrewAI Specialist Agent</span>
              </div>
            </div>
            <div className="agent-hero-status">
              <span className="status-pill status-pill--completed">
                <span className="pill-dot">✓</span>
                <span>Completed</span>
              </span>
            </div>
          </div>

          <p className="agent-hero-role">{config.role}</p>

          <div className="agent-meta-grid">
            <div className="meta-card">
              <span className="meta-label">Target Idea</span>
              <span className="meta-value">"{idea}"</span>
            </div>
            <div className="meta-card">
              <span className="meta-label">Primary Agent Task</span>
              <span className="meta-value">{config.task}</span>
            </div>
          </div>
        </div>

        {/* Execution Activity Checklist */}
        <div className="agent-activity-section">
          <h2 className="section-title">
            <span>⚡</span> Agent Execution Activity
          </h2>
          <div className="activity-checklist">
            {config.activityChecklist.map((item, index) => (
              <div key={index} className="checklist-item">
                <span className="check-icon">✓</span>
                <span className="check-text">{item}</span>
              </div>
            ))}
          </div>

          {config.assignedTasks && (
            <div className="assigned-tasks-subcard">
              <h3 className="tasks-title">Delegated Tasks to Parallel Research Agents:</h3>
              <div className="tasks-tags-row">
                {config.assignedTasks.map((t, idx) => (
                  <span key={idx} className="task-tag">
                    <span className="tag-num">{idx + 1}</span> {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Investor Verdict Summary Box if viewing Verdict Agent */}
        {agentKey === 'verdict' && validationResult.score != null && (
          <div className="verdict-summary-box">
            <div className="verdict-score-col">
              <span className="score-label">Final Viability Score</span>
              <span className="score-val">{validationResult.score} / 10</span>
            </div>
            <div className="verdict-rec-col">
              <span className="rec-label">Verdict Recommendation</span>
              <span className={`rec-badge ${validationResult.recommendation?.toLowerCase().includes('no') ? 'rec-badge--nogo' : 'rec-badge--go'}`}>
                {validationResult.recommendation || 'Go'}
              </span>
            </div>
          </div>
        )}

        {/* Agent Key Findings Output */}
        <div className="agent-findings-section">
          <h2 className="section-title">
            <span>📝</span> Agent Output & Key Findings
          </h2>
          <div className="findings-output-card">
            {agentOutput ? (
              <div className="findings-text-content">
                <MarkdownRenderer content={agentOutput} />
              </div>
            ) : (
              <p className="no-output-text">No findings recorded yet for this agent in this validation session.</p>
            )}
          </div>
        </div>

        {/* Agent Sources & Citations */}
        {sources.length > 0 && (
          <div className="agent-sources-section">
            <h2 className="section-title">
              <span>🔗</span> Verified Sources & Citations
            </h2>
            
            {searchQueries.length > 0 && (
              <div className="agent-search-queries">
                <h4 className="search-queries-title">Search Queries Used:</h4>
                <div className="search-queries-list">
                  {searchQueries.map((query, idx) => (
                    <span key={idx} className="search-query-chip">
                      🔍 {query}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <ul className="agent-sources-list">
              {sources.map((url, i) => (
                <li key={i}>
                  <a href={url} target="_blank" rel="noopener noreferrer" className="agent-source-link">
                    {url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Bottom Actions */}
        <div className="agent-detail-footer-actions">
          <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>
            ← Return to Previous Page
          </button>
          <Link to={`/chat/${sessionId}`} className="btn-primary">
            Chat with VentureLens →
          </Link>
        </div>

      </div>
    </div>
  );
}
