import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { startValidation } from '../services/api';
import './LandingPage.css';

const ACTION_SUGGESTIONS = [
  { label: 'Analyze market', icon: '📊', promptPrefix: 'Analyze the market opportunity and demand trends for: ' },
  { label: 'Find competitors', icon: '🔎', promptPrefix: 'Identify existing competitors and market positioning for: ' },
  { label: 'Estimate revenue', icon: '💰', promptPrefix: 'Evaluate financial feasibility and revenue models for: ' },
  { label: 'Challenge assumptions', icon: '⚡', promptPrefix: 'Challenge key assumptions and identify critical risks for: ' },
];

const EXAMPLE_IDEAS = [
  {
    title: 'EV charging network',
    icon: '🚗',
    idea: 'A network of smart EV charging stations with dynamic pricing and route planning',
  },
  {
    title: 'Home cooked food',
    icon: '🍲',
    idea: 'A platform connecting home cooks with local customers for fresh, home-cooked meal delivery',
  },
  {
    title: 'AI tutor for students',
    icon: '🎓',
    idea: 'An AI-powered personalized tutoring platform for K-12 students with adaptive curriculum',
  },
];

export default function LandingPage() {
  const [inputValue, setInputValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleStartValidation = async (ideaText) => {
    const cleanText = ideaText.trim();
    if (!cleanText || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await startValidation(cleanText);
      const sessionId = response.session_id;

      // Navigate to the dedicated Live Validation Pipeline page
      navigate(`/validate/${sessionId}`, {
        state: { startupIdea: cleanText },
      });
    } catch (err) {
      setError(err.message || 'Unable to initiate validation. Please ensure the backend is running.');
      setIsSubmitting(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    handleStartValidation(inputValue);
  };

  const handleSelectExample = (idea) => {
    setInputValue(idea);
    handleStartValidation(idea);
  };

  const handleSelectAction = (action) => {
    if (inputValue.trim()) {
      handleStartValidation(`${action.promptPrefix}${inputValue.trim()}`);
    } else {
      setInputValue(action.promptPrefix);
    }
  };

  return (
    <div className="landing-page animate-fade-in-up">
      <div className="landing-container">
        {/* Hero badge & title */}
        <div className="landing-badge-wrapper">
          <span className="landing-badge">
            <span className="landing-badge-sparkle">✦</span>
            AI Startup Validator
          </span>
        </div>

        <h1 className="landing-title">
          Validate your startup idea
        </h1>

        <p className="landing-subtitle">
          Ask anything. Our multi-agent AI researches, debates, and scores your startup idea.
        </p>

        {/* Suggested action buttons */}
        <div className="action-buttons-row">
          {ACTION_SUGGESTIONS.map((action) => (
            <button
              key={action.label}
              type="button"
              className="action-btn"
              onClick={() => handleSelectAction(action)}
              disabled={isSubmitting}
            >
              <span className="action-btn-icon">{action.icon}</span>
              <span>{action.label}</span>
            </button>
          ))}
        </div>

        {/* Main Input Form */}
        <form className="landing-input-form" onSubmit={handleSubmit}>
          <div className="input-bar-container">
            <input
              type="text"
              className="landing-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Describe your startup idea..."
              disabled={isSubmitting}
              autoFocus
            />
            <button
              type="submit"
              className="landing-send-btn"
              disabled={!inputValue.trim() || isSubmitting}
              title="Validate this startup idea"
            >
              {isSubmitting ? (
                <span className="send-spinner" />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              )}
            </button>
          </div>
        </form>

        {/* Error message */}
        {error && (
          <div className="landing-error animate-fade-in">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Example suggestions */}
        <div className="examples-container">
          <span className="examples-label">Try an example:</span>
          <div className="examples-grid">
            {EXAMPLE_IDEAS.map((ex) => (
              <button
                key={ex.title}
                type="button"
                className="example-card"
                onClick={() => handleSelectExample(ex.idea)}
                disabled={isSubmitting}
              >
                <span className="example-card-icon">{ex.icon}</span>
                <div className="example-card-text">
                  <span className="example-card-title">{ex.title}</span>
                  <span className="example-card-desc">{ex.idea}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Pipeline Architecture Preview Footer */}
        <div className="landing-pipeline-preview">
          <span className="pipeline-pill">7-Agent CrewAI Architecture</span>
          <div className="pipeline-chain">
            <span>Coordinator</span>
            <span className="chain-sep">→</span>
            <span>Market • Competitor • Financial • Risk</span>
            <span className="chain-sep">→</span>
            <span>Comparator / Debate</span>
            <span className="chain-sep">→</span>
            <span>Investor Verdict</span>
          </div>
        </div>
      </div>
    </div>
  );
}
