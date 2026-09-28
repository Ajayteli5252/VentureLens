import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getSession } from '../services/api';
import VerdictCard from '../components/VerdictCard';
import './FinalResultPage.css';

export default function FinalResultPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
        setError(err.message || 'Failed to load validation results.');
        setLoading(false);
      });
  }, [sessionId, navigate]);

  if (loading) {
    return (
      <div className="result-loading-screen animate-fade-in">
        <div className="result-spinner" />
        <p className="loading-text">Loading validation results for session...</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="result-error-container animate-fade-in">
        <span className="error-icon">⚠️</span>
        <h3>Session Not Found</h3>
        <p>{error || 'The requested validation session could not be located.'}</p>
        <button type="button" className="action-button primary" onClick={() => navigate('/')}>
          Start New Validation
        </button>
      </div>
    );
  }

  const validationResult = session.validation_result || {};
  const score = validationResult.score;
  const recommendation = validationResult.recommendation;
  const justification = validationResult.justification;
  const idea = session.startup_idea || '';
  const agentResults = session.agent_results || {};

  const RESEARCH_AGENTS = [
    {
      key: 'market',
      title: 'Market Research Agent',
      icon: '📊',
      desc: 'TAM/SAM/SOM market size and customer demand trends.',
    },
    {
      key: 'competitor',
      title: 'Competitor Analysis Agent',
      icon: '🔎',
      desc: 'Direct rivals, alternative substitutes, and competitive moats.',
    },
    {
      key: 'financial',
      title: 'Financial Feasibility Agent',
      icon: '💰',
      desc: 'Pricing strategy, setup costs, unit economics, and break-even.',
    },
    {
      key: 'risk',
      title: 'Risk Assessment Agent',
      icon: '⚠️',
      desc: 'Technical, legal, regulatory, and market feasibility risks.',
    },
  ];

  return (
    <div className="final-result-page animate-fade-in-up">
      <div className="result-container">

        {/* Top Header Banner */}
        <div className="result-header-banner">
          <div className="result-badge">
            <span className="badge-check">✓</span>
            <span>Validation complete!</span>
          </div>
          <h1 className="result-main-title">
            Here are the results from all seven agents.
          </h1>
          {idea && (
            <p className="result-idea-quote">
              Idea: "<span>{idea}</span>"
            </p>
          )}
        </div>

        {/* Main Verdict Card */}
        <div className="verdict-card-wrapper">
          <VerdictCard
            score={score}
            recommendation={recommendation}
            justification={justification}
          />
        </div>

        {/* Action Buttons: View Full Report & Chat with VentureLens */}
        <div className="result-cta-bar">
          <Link to={`/report/${sessionId}`} className="cta-button report-cta">
            <span className="cta-icon">📄</span>
            <div className="cta-text">
              <span className="cta-title">View Full Report</span>
              <span className="cta-sub">Structured analysis from all agents</span>
            </div>
            <span className="cta-arrow">→</span>
          </Link>

          <Link to={`/chat/${sessionId}`} className="cta-button chat-cta">
            <span className="cta-icon">💬</span>
            <div className="cta-text">
              <span className="cta-title">Chat with VentureLens</span>
              <span className="cta-sub">Fast follow-up question routing</span>
            </div>
            <span className="cta-arrow">→</span>
          </Link>
        </div>

        {/* 4 Research Specialist Findings Preview Cards */}
        <div className="specialists-summary-section">
          <div className="specialists-header">
            <h2 className="specialists-title">Specialist Agent Research Findings</h2>
            <p className="specialists-subtitle">
              Click any agent to inspect their full findings, tasks, and source citations.
            </p>
          </div>

          <div className="specialists-grid">
            {RESEARCH_AGENTS.map((agent) => {
              const findings = agentResults[agent.key];
              return (
                <div key={agent.key} className="specialist-preview-card">
                  <div className="specialist-card-top">
                    <span className="specialist-icon">{agent.icon}</span>
                    <div>
                      <h3 className="specialist-name">{agent.title}</h3>
                      <span className="specialist-status-pill">✓ Completed</span>
                    </div>
                  </div>

                  <p className="specialist-desc">{agent.desc}</p>

                  <div className="specialist-findings-snippet">
                    {findings ? (
                      <p>{findings.slice(0, 180)}...</p>
                    ) : (
                      <p className="empty-findings">Research findings recorded in validation session.</p>
                    )}
                  </div>

                  <Link
                    to={`/agent/${sessionId}/${agent.key}`}
                    className="view-agent-btn"
                  >
                    <span>View Agent Details</span>
                    <span>→</span>
                  </Link>
                </div>
              );
            })}
          </div>
        </div>

        {/* Additional Agents: Comparator & Coordinator */}
        <div className="other-agents-row">
          <div className="other-agent-card">
            <div className="other-agent-info">
              <span className="other-icon">🤖</span>
              <div>
                <h4 className="other-name">Coordinator Agent</h4>
                <p className="other-desc">Task assignments and problem framing</p>
              </div>
            </div>
            <Link to={`/agent/${sessionId}/coordinator`} className="other-agent-link">
              Details →
            </Link>
          </div>

          <div className="other-agent-card">
            <div className="other-agent-info">
              <span className="other-icon">⚖️</span>
              <div>
                <h4 className="other-name">Comparator / Debate Agent</h4>
                <p className="other-desc">Contradiction resolution between reports</p>
              </div>
            </div>
            <Link to={`/agent/${sessionId}/debate`} className="other-agent-link">
              Details →
            </Link>
          </div>
        </div>

        {/* Bottom Navigation */}
        <div className="result-footer-nav">
          <Link to={`/validate/${sessionId}`} className="footer-link">
            ← View Pipeline Execution
          </Link>
          <button
            type="button"
            className="footer-btn-primary"
            onClick={() => navigate(`/chat/${sessionId}`)}
          >
            Start Follow-Up Chat →
          </button>
        </div>

      </div>
    </div>
  );
}
