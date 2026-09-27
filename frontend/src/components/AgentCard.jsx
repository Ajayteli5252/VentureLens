import './AgentCard.css';

const AGENT_META = {
  market: { icon: '📊', name: 'Market Research Agent', color: '#1E7F5C' },
  competitor: { icon: '🔎', name: 'Competitor Analysis Agent', color: '#3B82F6' },
  financial: { icon: '💰', name: 'Financial Feasibility Agent', color: '#B8860B' },
  risk: { icon: '⚠️', name: 'Risk Assessment Agent', color: '#B3261E' },
};

const STATUS_META = {
  completed: { label: 'Completed', className: 'agent-status--done', icon: '✓' },
  running: { label: 'Analyzing...', className: 'agent-status--running', icon: '⟳' },
  pending: { label: 'Waiting', className: 'agent-status--pending', icon: '○' },
  error: { label: 'Failed', className: 'agent-status--error', icon: '⚠' },
};

export default function AgentCard({ type, completed, status }) {
  const meta = AGENT_META[type] || { icon: '🤖', name: type, color: '#666' };
  const resolvedStatus = status || (completed ? 'completed' : 'running');
  const current = STATUS_META[resolvedStatus] || STATUS_META.running;

  return (
    <div className={`agent-card ${resolvedStatus === 'completed' ? 'agent-card--done' : ''}`}>
      <div className="agent-card-header">
        <span className="agent-card-icon">{meta.icon}</span>
        <span className="agent-card-name">{meta.name}</span>
      </div>
      <div className="agent-card-status">
        <span className={`agent-status ${current.className}`}>
          {resolvedStatus === 'running' ? <span className="agent-spinner" /> : <span className="agent-status-icon">{current.icon}</span>}
          {current.label}
        </span>
      </div>
    </div>
  );
}
