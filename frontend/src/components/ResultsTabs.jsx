import { useState } from 'react';
import './ResultsTabs.css';

const TABS = [
  { id: 'overview', label: 'Overview', icon: '📋' },
  { id: 'full', label: 'Full Report', icon: '📄' },
];

export default function ResultsTabs({ rawOutput, score, recommendation, justification }) {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="results-tabs animate-fade-in-up">
      <div className="tabs-header">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'tab-btn--active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === 'overview' && (
          <div className="tab-panel animate-fade-in">
            <div className="overview-grid">
              {score != null && (
                <div className="overview-item">
                  <span className="overview-label">Final Score</span>
                  <span className="overview-value overview-score">{score}/10</span>
                </div>
              )}
              {recommendation && (
                <div className="overview-item">
                  <span className="overview-label">Recommendation</span>
                  <span className={`overview-value overview-rec ${
                    recommendation.toLowerCase().includes('no') ? 'overview-rec--nogo' : 'overview-rec--go'
                  }`}>
                    {recommendation}
                  </span>
                </div>
              )}
            </div>

            {justification && (
              <div className="overview-section">
                <h3 className="section-title">Executive Summary</h3>
                <p className="section-text">{justification}</p>
              </div>
            )}

            <div className="overview-section">
              <h3 className="section-title">Pipeline</h3>
              <p className="section-text section-text--muted">
                Coordinator → Market / Competitor / Financial / Risk agents (parallel) → Comparator/Debate agent → Investor-Verdict agent
              </p>
            </div>
          </div>
        )}

        {activeTab === 'full' && (
          <div className="tab-panel animate-fade-in">
            <div className="full-report">
              <pre className="report-pre">{rawOutput}</pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
