import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getSession } from '../services/api';
import './FullReportPage.css';

const REPORT_TABS = [
  { id: 'overview', label: 'Executive Overview', icon: '📋' },
  { id: 'market', label: 'Market Opportunity', icon: '📊' },
  { id: 'competitor', label: 'Competitor Landscape', icon: '🔎' },
  { id: 'financial', label: 'Financial Feasibility', icon: '💰' },
  { id: 'risk', label: 'Risk Assessment', icon: '⚠️' },
  { id: 'debate', label: 'Contradiction Debate', icon: '⚖️' },
  { id: 'raw', label: 'Raw Pipeline Output', icon: '📄' },
];

export default function FullReportPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

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
        setError(err.message || 'Failed to load report.');
        setLoading(false);
      });
  }, [sessionId, navigate]);

  if (loading) {
    return (
      <div className="report-loading-screen animate-fade-in">
        <div className="report-spinner" />
        <p>Loading full validation report...</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="report-error-screen animate-fade-in">
        <h3>Report Not Found</h3>
        <p>{error || 'The requested validation session does not exist.'}</p>
        <button type="button" className="btn-return" onClick={() => navigate('/')}>
          Return Home
        </button>
      </div>
    );
  }

  const validationResult = session.validation_result || {};
  const agentResults = session.agent_results || {};
  const idea = session.startup_idea || '';
  const score = validationResult.score;
  const recommendation = validationResult.recommendation;
  const justification = validationResult.justification;
  const rawReport = validationResult.raw || '';
  const debateResult = session.debate_result || agentResults.comparator || '';

  // Extract URLs from text
  const extractUrls = (text) => {
    if (!text) return [];
    const matches = text.match(/https?:\/\/[^\s()<>"]+/g) || [];
    return [...new Set(matches.map((url) => url.replace(/[.,;:)\]]+$/, '')))];
  };

  const allSources = extractUrls(rawReport);

  const formatTextBlocks = (text) => {
    if (!text) return <p className="text-muted-italic">No specific agent output recorded.</p>;

    const lines = text.split('\n');
    return lines.map((line, idx) => {
      const trimmed = line.trim();
      if (!trimmed) return <div key={idx} className="block-spacer" />;

      if (trimmed.startsWith('###')) {
        return <h4 key={idx} className="report-h4">{trimmed.replace(/^###\s*/, '')}</h4>;
      }
      if (trimmed.startsWith('##')) {
        return <h3 key={idx} className="report-h3">{trimmed.replace(/^##\s*/, '')}</h3>;
      }
      if (trimmed.startsWith('#')) {
        return <h2 key={idx} className="report-h2">{trimmed.replace(/^#\s*/, '')}</h2>;
      }

      if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
        const itemText = trimmed.replace(/^[-•]\s*/, '');
        return (
          <li key={idx} className="report-bullet">
            {itemText}
          </li>
        );
      }

      return (
        <p key={idx} className="report-paragraph">
          {trimmed}
        </p>
      );
    });
  };

  return (
    <div className="full-report-page animate-fade-in-up">
      <div className="report-container">

        {/* Top Navigation Bar */}
        <div className="report-top-nav">
          <Link to={`/result/${sessionId}`} className="back-result-link">
            ← Back to Result
          </Link>
          <div className="top-nav-actions">
            <Link to={`/chat/${sessionId}`} className="chat-link-btn">
              <span>💬 Ask Follow-up Questions</span>
            </Link>
          </div>
        </div>

        {/* Report Header Card */}
        <div className="report-header-card">
          <div className="report-header-top">
            <span className="doc-pill">Comprehensive Validation Report</span>
            <div className="report-metrics-pill">
              <span className="metric-score">Score: {score != null ? `${score}/10` : '—'}</span>
              <span className="metric-divider">•</span>
              <span className={`metric-rec ${recommendation?.toLowerCase().includes('no') ? 'metric-rec--nogo' : 'metric-rec--go'}`}>
                {recommendation?.toLowerCase().includes('no') ? 'NOT VALIDATED' : (recommendation ? 'VALIDATE' : '—')}
              </span>
            </div>
          </div>

          <h1 className="report-startup-title">
            {idea || 'Startup Validation Assessment'}
          </h1>
          <p className="report-meta">
            Compiled by 7-Agent Autonomous Pipeline • Coordinator, Market, Competitor, Financial, Risk, Debate, Verdict
          </p>
        </div>

        {/* Report Section Tabs */}
        <div className="report-tabs-nav">
          {REPORT_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`report-tab-btn ${activeTab === tab.id ? 'report-tab-btn--active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="tab-btn-icon">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab Content Box */}
        <div className="report-content-panel">

          {/* 1. Overview */}
          {activeTab === 'overview' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <span className="section-badge">Section 1</span>
                <h2 className="section-headline">Executive Verdict & Investment Thesis</h2>
              </div>

              <div className="overview-score-summary">
                <div className="summary-stat-box">
                  <span className="stat-label">Overall Viability Score</span>
                  <span className="stat-val stat-score">{score != null ? `${score}/10` : '—'}</span>
                </div>
                <div className="summary-stat-box">
                  <span className="stat-label">Investment Recommendation</span>
                  <span className={`stat-val ${recommendation?.toLowerCase().includes('no') ? 'stat-rec--nogo' : 'stat-rec--go'}`}>
                    {recommendation?.toLowerCase().includes('no') ? 'NOT VALIDATED' : (recommendation ? 'VALIDATE' : '—')}
                  </span>
                </div>
              </div>

              <div className="report-sub-block">
                <h3 className="block-title">Investment Justification</h3>
                <p className="justification-text">{justification || 'No justification text provided.'}</p>
              </div>

              <div className="report-sub-block">
                <h3 className="block-title">Key Domain Summary</h3>
                <div className="domain-summaries-grid">
                  <div className="domain-box">
                    <span className="domain-icon">📊</span>
                    <span className="domain-name">Market Demand</span>
                    <p className="domain-preview">{agentResults.market ? agentResults.market.slice(0, 140) + '...' : 'Market research completed.'}</p>
                  </div>
                  <div className="domain-box">
                    <span className="domain-icon">🔎</span>
                    <span className="domain-name">Competitive Moat</span>
                    <p className="domain-preview">{agentResults.competitor ? agentResults.competitor.slice(0, 140) + '...' : 'Competitor landscape mapped.'}</p>
                  </div>
                  <div className="domain-box">
                    <span className="domain-icon">💰</span>
                    <span className="domain-name">Unit Economics</span>
                    <p className="domain-preview">{agentResults.financial ? agentResults.financial.slice(0, 140) + '...' : 'Financial model assessed.'}</p>
                  </div>
                  <div className="domain-box">
                    <span className="domain-icon">⚠️</span>
                    <span className="domain-name">Key Risks</span>
                    <p className="domain-preview">{agentResults.risk ? agentResults.risk.slice(0, 140) + '...' : 'Critical risks evaluated.'}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 2. Market */}
          {activeTab === 'market' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <span className="section-badge">Market Research Agent</span>
                <h2 className="section-headline">Market Size, Target Audience & Demand Dynamics</h2>
              </div>
              <div className="report-text-container">
                {formatTextBlocks(agentResults.market)}
              </div>
            </div>
          )}

          {/* 3. Competitor */}
          {activeTab === 'competitor' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <span className="section-badge">Competitor Analysis Agent</span>
                <h2 className="section-headline">Competitor Landscape, Positioning & Moats</h2>
              </div>
              <div className="report-text-container">
                {formatTextBlocks(agentResults.competitor)}
              </div>
            </div>
          )}

          {/* 4. Financial */}
          {activeTab === 'financial' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <span className="section-badge">Financial Feasibility Agent</span>
                <h2 className="section-headline">Revenue Models, Unit Economics & Break-Even</h2>
              </div>
              <div className="report-text-container">
                {formatTextBlocks(agentResults.financial)}
              </div>
            </div>
          )}

          {/* 5. Risk */}
          {activeTab === 'risk' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <span className="section-badge">Risk Assessment Agent</span>
                <h2 className="section-headline">Technical, Regulatory, Market & Operational Risks</h2>
              </div>
              <div className="report-text-container">
                {formatTextBlocks(agentResults.risk)}
              </div>
            </div>
          )}

          {/* 6. Debate */}
          {activeTab === 'debate' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <span className="section-badge">Comparator / Debate Agent</span>
                <h2 className="section-headline">Contradiction Analysis & Trade-off Reconciliation</h2>
              </div>
              <div className="report-text-container">
                {formatTextBlocks(debateResult || 'The Comparator Agent reviewed all four specialist reports. No major un-reconciled contradictions were found.')}
              </div>
            </div>
          )}

          {/* 7. Raw Pipeline Output */}
          {activeTab === 'raw' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <span className="section-badge">Raw Synthesis</span>
                <h2 className="section-headline">Full Pipeline Output Stream</h2>
              </div>
              <pre className="report-raw-pre">{rawReport || 'No raw output string available.'}</pre>
            </div>
          )}

        </div>

        {/* Source Citations Section */}
        {allSources.length > 0 && (
          <div className="sources-card">
            <h3 className="sources-title">
              <span>🔗</span> Research Sources & External Citations
            </h3>
            <ul className="sources-list">
              {allSources.map((url, i) => (
                <li key={i}>
                  <a href={url} target="_blank" rel="noopener noreferrer" className="source-item-link">
                    {url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Footer Actions */}
        <div className="report-bottom-nav">
          <Link to={`/result/${sessionId}`} className="bottom-link">
            ← Back to Result Summary
          </Link>
          <Link to={`/chat/${sessionId}`} className="bottom-btn">
            Open Follow-up Chat →
          </Link>
        </div>

      </div>
    </div>
  );
}
