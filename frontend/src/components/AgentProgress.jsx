import './AgentProgress.css';

const PIPELINE_STAGES = [
  {
    id: 'coordinator',
    label: 'Coordinator Agent',
    icon: '🤖',
    desc: 'Understanding idea and assigning research tasks',
  },
  {
    id: 'research',
    label: 'Parallel Research',
    icon: '🔬',
    desc: 'Four agents analyzing market, competitors, financials, and risks',
  },
  {
    id: 'debate',
    label: 'Comparator / Debate',
    icon: '⚖️',
    desc: 'Cross-checking and resolving contradictions',
  },
  {
    id: 'verdict',
    label: 'Investor Verdict',
    icon: '🏆',
    desc: 'Combining findings into final score and recommendation',
  },
  {
    id: 'report',
    label: 'Final Report',
    icon: '📋',
    desc: 'Generating comprehensive validation report',
  },
];

export default function AgentProgress({ stage = 'coordinator', agentStatuses = {} }) {
  const getStageState = (stageId) => {
    if (agentStatuses[stageId] === 'completed') return 'done';
    if (agentStatuses[stageId] === 'running') return 'active';
    if (agentStatuses[stageId] === 'error') return 'error';
    if (stage === stageId) return 'active';
    return 'pending';
  };

  return (
    <div className="agent-progress animate-fade-in-up">
      <div className="progress-header">
        <div className="progress-dots">
          <span className="progress-dot" />
          <span className="progress-dot" />
          <span className="progress-dot" />
        </div>
        <span className="progress-label">VentureLens is validating your idea…</span>
      </div>

      <div className="pipeline-stages">
        {PIPELINE_STAGES.map((stageItem, i) => {
          const state = getStageState(stageItem.id);

          return (
            <div key={stageItem.id} className={`pipeline-stage pipeline-stage--${state}`}>
              <div className="stage-indicator">
                <div className="stage-line-top" style={{ opacity: i === 0 ? 0 : 1 }} />
                <div className="stage-icon-ring">
                  <span>{stageItem.icon}</span>
                </div>
                <div className="stage-line-bottom" style={{ opacity: i === PIPELINE_STAGES.length - 1 ? 0 : 1 }} />
              </div>
              <div className="stage-content">
                <span className="stage-label">{stageItem.label}</span>
                <span className="stage-desc">{stageItem.desc}</span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="progress-note">
        ⏳ Coordinator → Research → Debate → Verdict → Report
      </p>
    </div>
  );
}
