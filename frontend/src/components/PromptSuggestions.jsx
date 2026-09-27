import './PromptSuggestions.css';

const SUGGESTIONS = [
  { label: 'Analyze Market', icon: '📊' },
  { label: 'Find Competitors', icon: '🔎' },
  { label: 'Estimate Revenue', icon: '💰' },
  { label: 'Challenge Assumptions', icon: '⚡' },
  { label: 'Suggest Improvements', icon: '💡' },
];

const EXAMPLE_IDEAS = [
  'A platform connecting home cooks with local customers for fresh, home-cooked meal delivery',
  'An AI-powered personalized tutoring platform for K-12 students',
  'A network of smart EV charging stations with dynamic pricing and route planning',
];

export default function PromptSuggestions({ onSelectIdea }) {
  return (
    <div className="suggestions animate-fade-in-up stagger-2">
      <div className="suggestion-chips">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            className="suggestion-chip"
            onClick={() => onSelectIdea(s.label)}
          >
            <span className="chip-icon">{s.icon}</span>
            {s.label}
          </button>
        ))}
      </div>
      <div className="example-ideas">
        <p className="example-label">Try an example idea:</p>
        <div className="example-list">
          {EXAMPLE_IDEAS.map((idea, i) => (
            <button
              key={i}
              className="example-btn"
              onClick={() => onSelectIdea(idea)}
            >
              {idea}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
