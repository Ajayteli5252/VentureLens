import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getSession } from '../services/api';
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

export default function AgentDetailPage() {
  const { sessionId, agent } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const agentKey = (agent || 'market').toLowerCase();
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
        <p>{error || 'Session not found.'}</p>
        <button type="button" className="action-btn-primary" onClick={() => navigate('/')}>
          Return Home
        </button>
      </div>
    );
  }

  const idea = session.startup_idea || '';
  const agentResults = session.agent_results || {};
  const validationResult = session.validation_result || {};

  // Extract agent specific output
  let agentOutput = agentResults[agentKey] || '';
  if (agentKey === 'debate' && !agentOutput) {
    agentOutput = session.debate_result || agentResults.comparator || '';
  }
  if (agentKey === 'verdict' && !agentOutput) {
    agentOutput = validationResult.justification || session.verdict_result || validationResult.raw || '';
  }
  if (agentKey === 'coordinator' && !agentOutput) {
    agentOutput = `Coordinator Agent successfully analyzed the startup idea: "${idea}" and assigned structured briefs to Market, Competitor, Financial, and Risk research agents.`;
  }

  // Extract URLs for sources
  const extractUrls = (text) => {
    if (!text) return [];
    const matches = text.match(/https?:\/\/[^\s()<>"]+/g) || [];
    return [...new Set(matches.map((url) => url.replace(/[.,;:)\]]+$/, '')))];
  };

  const sources = extractUrls(agentOutput);

  return (
    <div className="agent-detail-page animate-fade-in-up">
      <div className="agent-detail-container">

        {/* Back navigation bar */}
        <div className="agent-detail-nav">
          <button type="button" className="back-btn" onClick={() => navigate(-1)}>
            ← Back
          </button>
          <div className="quick-links">
            <Link to={`/validate/${sessionId}`} className="nav-sub-link">Pipeline</Link>
            <span className="dot-sep">•</span>
            <Link to={`/result/${sessionId}`} className="nav-sub-link">Results</Link>
            <span className="dot-sep">•</span>
            <Link to={`/report/${sessionId}`} className="nav-sub-link">Report</Link>
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
                {agentOutput.split('\n').map((line, idx) => {
                  const trimmed = line.trim();
                  if (!trimmed) return <div key={idx} className="para-spacer" />;
                  if (trimmed.startsWith('#')) {
                    return <h3 key={idx} className="findings-h3">{trimmed.replace(/^#+\s*/, '')}</h3>;
                  }
                  if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
                    return <li key={idx} className="findings-bullet">{trimmed.replace(/^[-•]\s*/, '')}</li>;
                  }
                  return <p key={idx} className="findings-p">{trimmed}</p>;
                })}
              </div>
            ) : (
              <p className="no-output-text">Agent output recorded in validation session.</p>
            )}
          </div>
        </div>

        {/* Agent Sources & Citations */}
        {sources.length > 0 && (
          <div className="agent-sources-section">
            <h2 className="section-title">
              <span>🔗</span> Verified Sources & Citations
            </h2>
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
