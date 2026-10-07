import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getSession } from '../services/api';
import MarkdownRenderer from '../components/MarkdownRenderer';
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

  // Group URLs by agent
  const agentSources = [
    { id: 'market', name: 'Market Research', icon: '📊', urls: extractUrls(agentResults?.market) },
    { id: 'competitor', name: 'Competitor Analysis', icon: '🔎', urls: extractUrls(agentResults?.competitor) },
    { id: 'financial', name: 'Financial Feasibility', icon: '💰', urls: extractUrls(agentResults?.financial) },
    { id: 'risk', name: 'Risk Assessment', icon: '⚠️', urls: extractUrls(agentResults?.risk) },
  ].filter(group => group.urls.length > 0);
  
  const hasSources = agentSources.length > 0;

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
              <span className={`metric-rec ${(recommendation || '').toLowerCase().includes('no') ? 'metric-rec--nogo' : 'metric-rec--go'}`}>
                {(recommendation || '').toLowerCase().includes('no') ? 'NOT VALIDATED' : (recommendation ? 'VALIDATE' : '—')}
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
                  <span className={`stat-val ${(recommendation || '').toLowerCase().includes('no') ? 'stat-rec--nogo' : 'stat-rec--go'}`}>
                    {(recommendation || '').toLowerCase().includes('no') ? 'NOT VALIDATED' : (recommendation ? 'VALIDATE' : '—')}
                  </span>
                </div>
              </div>

              <div className="report-sub-block">
                <h3 className="block-title">Investment Justification</h3>
                <div className="justification-text">
                  <MarkdownRenderer content={justification || 'No justification text provided.'} />
                </div>
              </div>

              <div className="report-sub-block">
                <h3 className="block-title">Key Domain Summary</h3>
                <div className="domain-summaries-grid">
                  {[
                    { key: 'market', icon: '📊', name: 'Market Demand', fallback: 'Market research completed.' },
                    { key: 'competitor', icon: '🔎', name: 'Competitive Moat', fallback: 'Competitor landscape mapped.' },
                    { key: 'financial', icon: '💰', name: 'Unit Economics', fallback: 'Financial model assessed.' },
                    { key: 'risk', icon: '⚠️', name: 'Key Risks', fallback: 'Critical risks evaluated.' },
                  ].map(({ key, icon, name, fallback }) => {
                    const raw = agentResults[key] || '';
                    return (
                      <div key={key} className="domain-box">
                        <span className="domain-icon">{icon}</span>
                        <span className="domain-name">{name}</span>
                        <div className="domain-preview">
                          {raw ? (
                            <MarkdownRenderer content={raw} className="domain-preview-markdown" />
                          ) : (
                            <p className="domain-preview-fallback">{fallback}</p>
                          )}
                        </div>
                        <Link to={`/agent/${sessionId}/${key}`} className="domain-agent-link">
                          View full findings →
                        </Link>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* 2. Market */}
          {activeTab === 'market' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <div className="section-head-text">
                  <span className="section-badge">Market Research Agent</span>
                  <h2 className="section-headline">Market Size, Target Audience & Demand Dynamics</h2>
                </div>
                <Link to={`/agent/${sessionId}/market`} className="tab-deep-dive-btn">
                  View Full Agent Details & Citations →
                </Link>
              </div>
              <div className="report-text-container">
                {agentResults.market ? <MarkdownRenderer content={agentResults.market} /> : <p className="text-muted-italic">No specific agent output recorded.</p>}
              </div>
            </div>
          )}

          {/* 3. Competitor */}
          {activeTab === 'competitor' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <div className="section-head-text">
                  <span className="section-badge">Competitor Analysis Agent</span>
                  <h2 className="section-headline">Competitor Landscape, Positioning & Moats</h2>
                </div>
                <Link to={`/agent/${sessionId}/competitor`} className="tab-deep-dive-btn">
                  View Full Agent Details & Citations →
                </Link>
              </div>
              <div className="report-text-container">
                {agentResults.competitor ? <MarkdownRenderer content={agentResults.competitor} /> : <p className="text-muted-italic">No specific agent output recorded.</p>}
              </div>
            </div>
          )}

          {/* 4. Financial */}
          {activeTab === 'financial' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <div className="section-head-text">
                  <span className="section-badge">Financial Feasibility Agent</span>
                  <h2 className="section-headline">Revenue Models, Unit Economics & Break-Even</h2>
                </div>
                <Link to={`/agent/${sessionId}/financial`} className="tab-deep-dive-btn">
                  View Full Agent Details & Citations →
                </Link>
              </div>
              <div className="report-text-container">
                {agentResults.financial ? <MarkdownRenderer content={agentResults.financial} /> : <p className="text-muted-italic">No specific agent output recorded.</p>}
              </div>
            </div>
          )}

          {/* 5. Risk */}
          {activeTab === 'risk' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <div className="section-head-text">
                  <span className="section-badge">Risk Assessment Agent</span>
                  <h2 className="section-headline">Technical, Regulatory, Market & Operational Risks</h2>
                </div>
                <Link to={`/agent/${sessionId}/risk`} className="tab-deep-dive-btn">
                  View Full Agent Details & Citations →
                </Link>
              </div>
              <div className="report-text-container">
                {agentResults.risk ? <MarkdownRenderer content={agentResults.risk} /> : <p className="text-muted-italic">No specific agent output recorded.</p>}
              </div>
            </div>
          )}

          {/* 6. Debate */}
          {activeTab === 'debate' && (
            <div className="report-tab-body animate-fade-in">
              <div className="section-head">
                <div className="section-head-text">
                  <span className="section-badge">Comparator / Debate Agent</span>
                  <h2 className="section-headline">Contradiction Analysis & Trade-off Reconciliation</h2>
                </div>
                <Link to={`/agent/${sessionId}/debate`} className="tab-deep-dive-btn">
                  View Full Agent Details & Citations →
                </Link>
              </div>
              <div className="report-text-container">
                <MarkdownRenderer content={debateResult || 'The Comparator Agent reviewed all four specialist reports. No major un-reconciled contradictions were found.'} />
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
              {rawReport ? (
                <div className="report-text-container">
                  <MarkdownRenderer content={rawReport} />
                </div>
              ) : (
                <p className="text-muted-italic">No raw output available.</p>
              )}
            </div>
          )}

        </div>

        {/* Source Citations Section */}
        {hasSources && (
          <div className="sources-card">
            <h3 className="sources-title">
              <span>🔗</span> Research Sources & External Citations
            </h3>
            <div className="sources-grouped-list">
              {agentSources.map((group) => (
                <div key={group.id} className="source-group">
                  <h4 className="source-group-title">
                    <span className="source-group-icon">{group.icon}</span> {group.name}
                  </h4>
                  <ul className="sources-list">
                    {group.urls.map((url, i) => (
                      <li key={i}>
                        <a href={url} target="_blank" rel="noopener noreferrer" className="source-item-link">
                          {url}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Agent Navigation Section */}
        <div className="report-agents-nav-section">
          <h3 className="report-agents-nav-title">
            <span>🔍</span> Explore Individual Agent Reports
          </h3>
          <p className="report-agents-nav-subtitle">
            Click any agent below to view their full research output, activity log, and cited sources.
          </p>
          <div className="report-agents-nav-grid">
            {[
              { key: 'coordinator', icon: '🤖', name: 'Coordinator Agent', desc: 'Task assignment & problem framing' },
              { key: 'market', icon: '📊', name: 'Market Research', desc: 'TAM/SAM/SOM & demand analysis' },
              { key: 'competitor', icon: '🔎', name: 'Competitor Analysis', desc: 'Rivals, moats & positioning' },
              { key: 'financial', icon: '💰', name: 'Financial Feasibility', desc: 'Revenue models & break-even' },
              { key: 'risk', icon: '⚠️', name: 'Risk Assessment', desc: 'Technical, legal & market risks' },
              { key: 'debate', icon: '⚖️', name: 'Debate Agent', desc: 'Contradiction & trade-off resolution' },
              { key: 'verdict', icon: '🏆', name: 'Investor Verdict', desc: 'Final score & Go/No-Go decision' },
            ].map(({ key, icon, name, desc }) => (
              <Link key={key} to={`/agent/${sessionId}/${key}`} className="report-agent-nav-card">
                <span className="report-agent-nav-icon">{icon}</span>
                <div className="report-agent-nav-info">
                  <span className="report-agent-nav-name">{name}</span>
                  <span className="report-agent-nav-desc">{desc}</span>
                </div>
                <span className="report-agent-nav-arrow">→</span>
              </Link>
            ))}
          </div>
        </div>

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
