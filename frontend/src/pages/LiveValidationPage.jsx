import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { streamValidationEvents, getSession, cancelValidation } from '../services/api';
import AgentCard from '../components/AgentCard';
import './LiveValidationPage.css';

const EMPTY_PIPELINE_STATE = {
  coordinator: 'running',
  market: 'pending',
  competitor: 'pending',
  financial: 'pending',
  risk: 'pending',
  debate: 'pending',
  verdict: 'pending',
  report: 'pending',
};

export default function LiveValidationPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [startupIdea, setStartupIdea] = useState(location.state?.startupIdea || '');
  const [pipelineStage, setPipelineStage] = useState('coordinator');
  const [agentStatuses, setAgentStatuses] = useState(EMPTY_PIPELINE_STATE);
  const [agentActivities, setAgentActivities] = useState({});
  const [error, setError] = useState(null);
  const [isCompleted, setIsCompleted] = useState(false);
  const [isCancelled, setIsCancelled] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  const eventSourceRef = useRef(null);

  // Sync pipeline state from real SSE events
  const updatePipelineFromEvent = (event) => {
    if (!event || !event.stage) return;

    const normalizedStage = event.stage;

    if (event.type === 'validation_cancelled') {
      setIsCancelled(true);
      setIsCancelling(false);
      return;
    }

    if (event.type === 'pipeline_started') {
      setPipelineStage('coordinator');
      setAgentStatuses((prev) => ({ ...prev, coordinator: 'running' }));
      return;
    }

    if (event.type === 'agent_started') {
      setPipelineStage(normalizedStage);
      setAgentStatuses((prev) => {
        const next = { ...prev };
        if (normalizedStage === 'coordinator') next.coordinator = 'running';
        if (normalizedStage === 'research') {
          if (event.agent && /Market/i.test(event.agent)) next.market = 'running';
          else if (event.agent && /Competitor/i.test(event.agent)) next.competitor = 'running';
          else if (event.agent && /Financial/i.test(event.agent)) next.financial = 'running';
          else if (event.agent && /Risk/i.test(event.agent)) next.risk = 'running';
          else {
            if (next.market === 'pending') next.market = 'running';
            if (next.competitor === 'pending') next.competitor = 'running';
            if (next.financial === 'pending') next.financial = 'running';
            if (next.risk === 'pending') next.risk = 'running';
          }
        }
        if (normalizedStage === 'debate') next.debate = 'running';
        if (normalizedStage === 'verdict') next.verdict = 'running';
        if (normalizedStage === 'report') next.report = 'running';
        return next;
      });
      return;
    }

    if (event.type === 'agent_completed') {
      setPipelineStage(normalizedStage);
      setAgentStatuses((prev) => {
        const next = { ...prev };
        if (normalizedStage === 'coordinator') next.coordinator = 'completed';
        if (normalizedStage === 'research') {
          if (event.agent && /Market/i.test(event.agent)) next.market = 'completed';
          if (event.agent && /Competitor/i.test(event.agent)) next.competitor = 'completed';
          if (event.agent && /Financial/i.test(event.agent)) next.financial = 'completed';
          if (event.agent && /Risk/i.test(event.agent)) next.risk = 'completed';
        }
        if (normalizedStage === 'debate') next.debate = 'completed';
        if (normalizedStage === 'verdict') next.verdict = 'completed';
        if (normalizedStage === 'report') next.report = 'completed';
        return next;
      });
      return;
    }

    if (event.type === 'pipeline_completed') {
      setPipelineStage('report');
      setAgentStatuses({
        coordinator: 'completed',
        market: 'completed',
        competitor: 'completed',
        financial: 'completed',
        risk: 'completed',
        debate: 'completed',
        verdict: 'completed',
        report: 'completed',
      });
      setIsCompleted(true);

      // Fetch final session result
      getSession(sessionId)
        .then((session) => {
          if (session.startup_idea && !startupIdea) {
            setStartupIdea(session.startup_idea);
          }
          setValidationResult(session.validation_result || {});
        })
        .catch(() => {});
    }

    if (event.type === 'agent_error' || event.type === 'pipeline_error') {
      setError(event.message || 'An error occurred during pipeline execution.');
    }

    if (event.type === 'agent_activity') {
      let key = normalizedStage;
      if (normalizedStage === 'research') {
        if (event.agent && /Market/i.test(event.agent)) key = 'market';
        else if (event.agent && /Competitor/i.test(event.agent)) key = 'competitor';
        else if (event.agent && /Financial/i.test(event.agent)) key = 'financial';
        else if (event.agent && /Risk/i.test(event.agent)) key = 'risk';
      }
      setAgentActivities((prev) => ({
        ...prev,
        [key]: event.message,
      }));
    }
  };

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }

    // First check existing session state
    getSession(sessionId)
      .then((session) => {
        if (session.startup_idea) {
          setStartupIdea(session.startup_idea);
        }

        // If session was already cancelled
        if (session.status === 'cancelled') {
          setIsCancelled(true);
          return;
        }

        // If session was already completed
        if (session.status === 'completed' || session.result_ready) {
          setIsCompleted(true);
          setPipelineStage('report');
          setAgentStatuses({
            coordinator: 'completed',
            market: 'completed',
            competitor: 'completed',
            financial: 'completed',
            risk: 'completed',
            debate: 'completed',
            verdict: 'completed',
            report: 'completed',
          });
          setValidationResult(session.validation_result || {});
          return;
        }

        // Reconnect to SSE stream for live updates
        eventSourceRef.current = streamValidationEvents(
          sessionId,
          (event) => {
            updatePipelineFromEvent(event);
          },
          (err) => {
            // If SSE stream closed normally or errored, recheck session state
            getSession(sessionId)
              .then((s) => {
                if (s.status === 'cancelled') {
                  setIsCancelled(true);
                } else if (s.status === 'completed' || s.result_ready) {
                  setIsCompleted(true);
                  setValidationResult(s.validation_result || {});
                }
              })
              .catch(() => {});
          }
        );
      })
      .catch((err) => {
        setError(err.message || 'Unable to retrieve session state.');
      });

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [sessionId, navigate]);

  const handleStop = async () => {
    if (isCancelling || isCancelled || isCompleted) return;
    setIsCancelling(true);
    try {
      await cancelValidation(sessionId);
      // Mark all still-pending/running stages as cancelled
      setAgentStatuses((prev) => {
        const next = { ...prev };
        for (const key of Object.keys(next)) {
          if (next[key] === 'pending' || next[key] === 'running') {
            next[key] = 'cancelled';
          }
        }
        return next;
      });
      setIsCancelled(true);
    } catch (err) {
      setError(err.message || 'Failed to cancel validation.');
    } finally {
      setIsCancelling(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    }
  };

  const allResearchCompleted =
    agentStatuses.market === 'completed' &&
    agentStatuses.competitor === 'completed' &&
    agentStatuses.financial === 'completed' &&
    agentStatuses.risk === 'completed';

  const STEPPER_STAGES = [
    { id: 'coordinator', label: 'Coordinator' },
    { id: 'research', label: 'Research' },
    { id: 'debate', label: 'Debate' },
    { id: 'verdict', label: 'Verdict' },
    { id: 'report', label: 'Report' },
  ];

  const getStepperStatus = (stageId) => {
    if (isCancelled) {
      // If cancelled, completed stages stay completed, others show cancelled
      if (stageId === 'coordinator') return agentStatuses.coordinator === 'completed' ? 'completed' : 'cancelled';
      if (stageId === 'research') return allResearchCompleted ? 'completed' : 'cancelled';
      if (stageId === 'debate') return agentStatuses.debate === 'completed' ? 'completed' : 'cancelled';
      if (stageId === 'verdict') return agentStatuses.verdict === 'completed' ? 'completed' : 'cancelled';
      if (stageId === 'report') return 'cancelled';
    }
    if (stageId === 'coordinator') return agentStatuses.coordinator;
    if (stageId === 'research') return allResearchCompleted ? 'completed' : (pipelineStage === 'research' ? 'running' : (agentStatuses.coordinator === 'completed' ? 'running' : 'pending'));
    if (stageId === 'debate') return agentStatuses.debate;
    if (stageId === 'verdict') return agentStatuses.verdict;
    if (stageId === 'report') return agentStatuses.report;
    return 'pending';
  };

  const getStepperIcon = (status) => {
    if (status === 'completed') return '✓';
    if (status === 'running') return '●';
    if (status === 'cancelled') return '■';
    return '○';
  };

  const isRunning = !isCompleted && !isCancelled && !error;

  return (
    <div className="validation-page animate-fade-in-up">
      <div className="validation-container">

        {/* User Idea & Initial AI Response Card */}
        {startupIdea && (
          <div className="idea-summary-card">
            <div className="user-prompt-row">
              <div className="user-avatar-tag">You</div>
              <p className="user-prompt-text">"{startupIdea}"</p>
            </div>
            <div className="vl-acknowledgement">
              <span className="vl-sparkle">✦</span>
              <div className="vl-ack-content">
                <span className="vl-ack-title">VentureLens Multi-Agent System</span>
                <p className="vl-ack-text">
                  Great! I'll validate this idea using our 7-agent AI system:
                </p>
                <div className="agent-plan-list">
                  <div className="agent-plan-item">
                    <span className="plan-num">1</span>
                    <span>Understand your idea — <strong>Coordinator Agent</strong></span>
                  </div>
                  <div className="agent-plan-item">
                    <span className="plan-num">2</span>
                    <span>Run 4 research agents in parallel — <strong>Market, Competitor, Financial, Risk</strong></span>
                  </div>
                  <div className="agent-plan-item">
                    <span className="plan-num">3</span>
                    <span>Cross-check findings — <strong>Comparator / Debate Agent</strong></span>
                  </div>
                  <div className="agent-plan-item">
                    <span className="plan-num">4</span>
                    <span>Give final score & recommendation — <strong>Investor-Verdict Agent</strong></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Live Pipeline Stepper Header */}
        <div className="pipeline-header-block">
          <div className="pipeline-title-row">
            <div className="header-status-badge">
              <span className={
                isCancelled
                  ? 'badge-dot badge-dot--cancelled'
                  : isCompleted
                  ? 'badge-dot badge-dot--done'
                  : 'badge-dot badge-dot--pulse'
              } />
              <span>
                {isCancelled
                  ? 'Validation stopped by user'
                  : isCompleted
                  ? 'Validation Complete'
                  : 'Validating your idea...'}
              </span>
            </div>

            {/* ONE global Stop button — only show while actively running */}
            {isRunning && (
              <button
                type="button"
                className="global-stop-btn"
                onClick={handleStop}
                disabled={isCancelling}
                title="Stop this validation run"
              >
                {isCancelling ? (
                  <span className="stop-spinner" />
                ) : (
                  <span className="stop-icon">⏹</span>
                )}
                {isCancelling ? 'Stopping...' : 'Stop'}
              </button>
            )}
          </div>

          <h2 className="pipeline-title">
            {isCancelled
              ? 'Validation Stopped'
              : isCompleted
              ? 'All 7 Agents Completed Their Research'
              : 'Our 7-agent AI system is working in parallel'}
          </h2>
          <p className="pipeline-subtitle">
            {isCancelled
              ? 'The validation was stopped. Results from completed agents are preserved below.'
              : 'Specialist agents research the market, competitors, financials, and risks, cross-check their findings, and produce a definitive investment verdict.'}
          </p>

          {/* Stepper */}
          <div className="pipeline-stepper">
            {STEPPER_STAGES.map((s, idx) => {
              const status = getStepperStatus(s.id);
              return (
                <div key={s.id} className={`stepper-step stepper-step--${status}`}>
                  <div className="step-circle">
                    {getStepperIcon(status)}
                  </div>
                  <span className="step-label">{s.label}</span>
                  {idx < STEPPER_STAGES.length - 1 && <div className="step-connector" />}
                </div>
              );
            })}
          </div>
        </div>

        {/* Cancelled Banner */}
        {isCancelled && (
          <div className="cancelled-card animate-fade-in">
            <div className="cancelled-header">
              <div className="cancelled-icon">⏹</div>
              <div>
                <h3 className="cancelled-title">Validation Stopped by User</h3>
                <p className="cancelled-desc">
                  The pipeline was stopped. Any agent results that completed before cancellation are preserved.
                  Start a new validation to get complete results.
                </p>
              </div>
            </div>
            <div className="cancelled-actions">
              {validationResult && validationResult.score != null && (
                <button
                  type="button"
                  className="cta-partial-result"
                  onClick={() => navigate(`/result/${sessionId}`)}
                >
                  View Partial Results →
                </button>
              )}
            </div>
          </div>
        )}

        {/* Completed Banner with primary CTA */}
        {isCompleted && (
          <div className="completion-card animate-fade-in">
            <div className="completion-header">
              <div className="completion-icon">🏆</div>
              <div>
                <h3 className="completion-title">Validation Complete!</h3>
                <p className="completion-desc">
                  All 7 agents have finished their analysis and the final score is ready.
                </p>
              </div>
            </div>

            {validationResult && validationResult.score != null && (
              <div className="completion-preview-row">
                <div className="preview-score-box">
                  <span className="preview-label">Score</span>
                  <span className="preview-score">{validationResult.score} / 10</span>
                </div>
                <div className="preview-rec-box">
                  <span className="preview-label">Verdict</span>
                  <span className={`preview-rec ${validationResult.recommendation?.toLowerCase().includes('no') ? 'preview-rec--nogo' : 'preview-rec--go'}`}>
                    {validationResult.recommendation?.toLowerCase().includes('no') ? 'NOT VALIDATED' : 'VALIDATE'}
                  </span>
                </div>
              </div>
            )}

            <button
              type="button"
              className="view-result-cta-btn"
              onClick={() => navigate(`/result/${sessionId}`)}
            >
              <span>View Final Result & Report</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"/>
                <polyline points="12 5 19 12 12 19"/>
              </svg>
            </button>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="pipeline-error-card animate-fade-in">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Section 1: Coordinator Agent */}
        <div className="agent-stage-section">
          <div className="section-label-row">
            <span className="stage-icon">🤖</span>
            <span className="stage-heading">Phase 1: Problem Formulation & Task Assignment</span>
          </div>
          <AgentCard
            type="coordinator"
            status={agentStatuses.coordinator}
            activity={agentActivities.coordinator}
            sessionId={sessionId}
            responsibility="Understanding your startup idea and assigning structured research briefs to parallel agents."
          />
        </div>

        {/* Section 2: Research Agents Running in Parallel (2x2 Grid) */}
        <div className="agent-stage-section">
          <div className="section-label-row">
            <span className="stage-icon">🔬</span>
            <span className="stage-heading">Phase 2: Specialist Research (4 Agents in Parallel)</span>
          </div>

          <div className="parallel-agents-grid">
            <AgentCard
              type="market"
              status={agentStatuses.market}
              activity={agentActivities.market}
              sessionId={sessionId}
            />
            <AgentCard
              type="competitor"
              status={agentStatuses.competitor}
              activity={agentActivities.competitor}
              sessionId={sessionId}
            />
            <AgentCard
              type="financial"
              status={agentStatuses.financial}
              activity={agentActivities.financial}
              sessionId={sessionId}
            />
            <AgentCard
              type="risk"
              status={agentStatuses.risk}
              activity={agentActivities.risk}
              sessionId={sessionId}
            />
          </div>
        </div>

        {/* Section 3: Comparator / Debate Agent */}
        <div className="agent-stage-section">
          <div className="section-label-row">
            <span className="stage-icon">⚖️</span>
            <span className="stage-heading">Phase 3: Cross-Verification & Contradiction Debate</span>
          </div>
          <AgentCard
            type="debate"
            status={agentStatuses.debate}
            activity={agentActivities.debate}
            sessionId={sessionId}
            responsibility="Cross-checking Market, Competitor, Financial, and Risk reports to identify and resolve contradictions."
          />
        </div>

        {/* Section 4: Investor-Verdict Agent */}
        <div className="agent-stage-section">
          <div className="section-label-row">
            <span className="stage-icon">🏆</span>
            <span className="stage-heading">Phase 4: Investment Committee Decision</span>
          </div>
          <AgentCard
            type="verdict"
            status={agentStatuses.verdict}
            activity={agentActivities.verdict}
            sessionId={sessionId}
            responsibility="Synthesizing all research and debate into a final 1-10 score and definitive Validate/Not Validated verdict."
          />
        </div>

        {/* Bottom Navigation */}
        <div className="pipeline-bottom-actions">
          <button
            type="button"
            className="bottom-nav-btn secondary-btn"
            onClick={() => navigate('/')}
          >
            ← Validate Another Idea
          </button>
          {isCompleted && (
            <button
              type="button"
              className="bottom-nav-btn primary-btn"
              onClick={() => navigate(`/result/${sessionId}`)}
            >
              Continue to Final Results →
            </button>
          )}
        </div>

      </div>
    </div>
  );
}
