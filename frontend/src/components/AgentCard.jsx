import { Link } from 'react-router-dom';
import './AgentCard.css';

const AGENT_META = {
  coordinator: {
    icon: '🤖',
    name: 'Coordinator Agent',
    color: '#E86F2D',
    responsibility: 'Understands your idea and assigns research tasks to specialists.',
  },
  market: {
    icon: '📊',
    name: 'Market Research Agent',
    color: '#1E7F5C',
    responsibility: 'Analyzing target market size (TAM/SAM/SOM), customer demand, and growth trends...',
  },
  competitor: {
    icon: '🔎',
    name: 'Competitor Analysis Agent',
    color: '#3B82F6',
    responsibility: 'Mapping direct and indirect rivals, differentiation moats, and market positioning...',
  },
  financial: {
    icon: '💰',
    name: 'Financial Feasibility Agent',
    color: '#B8860B',
    responsibility: 'Estimating revenue models, unit economics, startup setup costs, and break-even timelines...',
  },
  risk: {
    icon: '⚠️',
    name: 'Risk Assessment Agent',
    color: '#B3261E',
    responsibility: 'Evaluating critical technical pitfalls, regulatory compliance, and market risks...',
  },
  debate: {
    icon: '⚖️',
    name: 'Comparator / Debate Agent',
    color: '#8B5CF6',
    responsibility: 'Cross-checking findings across all 4 research agents and resolving conflicting claims...',
  },
  verdict: {
    icon: '🏆',
    name: 'Investor Verdict Agent',
    color: '#D97706',
    responsibility: 'Synthesizing all research and debate into a final 1-10 score and Go/No-Go verdict...',
  },
};

const STATUS_META = {
  completed: { label: 'Completed', className: 'agent-status--done', icon: '✓' },
  running: { label: 'In progress', className: 'agent-status--running', icon: '⟳' },
  pending: { label: 'Waiting', className: 'agent-status--pending', icon: '○' },
  error: { label: 'Failed', className: 'agent-status--error', icon: '⚠' },
  cancelled: { label: 'Cancelled', className: 'agent-status--cancelled', icon: '■' },
};

export default function AgentCard({
  type,
  completed,
  status,
  activity,
  sessionId,
  responsibility,
}) {
  const meta = AGENT_META[type] || {
    icon: '🤖',
    name: type,
    color: '#666',
    responsibility: 'Specialist agent research and analysis.',
  };
  const resolvedStatus = status || (completed ? 'completed' : 'running');
  const current = STATUS_META[resolvedStatus] || STATUS_META.running;
  const cardDesc = responsibility || meta.responsibility;

  return (
    <div className={`agent-card ${resolvedStatus === 'completed' ? 'agent-card--done' : ''} ${resolvedStatus === 'running' ? 'agent-card--active' : ''}`}>
      <div className="agent-card-top">
        <div className="agent-card-header">
          <span className="agent-card-icon">{meta.icon}</span>
          <span className="agent-card-name">{meta.name}</span>
        </div>
        <div className="agent-card-status">
          <span className={`agent-status ${current.className}`}>
            {resolvedStatus === 'running' ? (
              <span className="agent-spinner" />
            ) : (
              <span className="agent-status-icon">{current.icon}</span>
            )}
            {current.label}
          </span>
        </div>
      </div>

      <p className="agent-card-desc">
        {resolvedStatus === 'running' && activity ? (
          <span className="live-activity-text animate-fade-in">{activity}</span>
        ) : (
          cardDesc
        )}
      </p>

      {sessionId && (
        <div className="agent-card-actions">
          <Link
            to={`/agent/${sessionId}/${type}`}
            className="agent-details-link"
            title={`View detailed activities and findings for ${meta.name}`}
          >
            <span>View Agent Details</span>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </Link>
        </div>
      )}
    </div>
  );
}
