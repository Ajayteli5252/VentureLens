import { useState, useRef, useEffect } from 'react';
import HeroSection from '../components/HeroSection';
import PromptSuggestions from '../components/PromptSuggestions';
import ChatInput from '../components/ChatInput';
import ChatMessage from '../components/ChatMessage';
import AgentProgress from '../components/AgentProgress';
import AgentCard from '../components/AgentCard';
import VerdictCard from '../components/VerdictCard';
import ResultsTabs from '../components/ResultsTabs';
import { startValidation, streamValidationEvents, getSession, followUpQuestion } from '../services/api';
import './VentureLens.css';

const DEFAULT_FOLLOW_UP_SUGGESTIONS = [
  'Who are my biggest competitors?',
  'How can I differentiate from competitors?',
  'What is the projected market size?',
  'What pricing model should I use?',
  'What are the biggest legal and technical risks?',
];

function predictAgentLoading(question) {
  const q = question.toLowerCase();
  if (/revalidate|validation again|full validation|fresh analysis|update.*score/.test(q)) {
    return { name: 'Full Validation Pipeline', icon: '🔄' };
  }
  if (/competitor|competition|rival|alternative|differentiat|positioning|moat|vs\b/.test(q)) {
    return { name: 'Competitor Analysis Agent', icon: '🔎' };
  }
  if (/revenue|pricing|price|cost|expense|profit|margin|break-even|breakeven|business model|monetiz|cac|ltv|unit economics/.test(q)) {
    return { name: 'Financial Feasibility Agent', icon: '💰' };
  }
  if (/risk|legal|law|regulation|compliance|liability|patent|technical risk|security|operational|hazard|fail/.test(q)) {
    return { name: 'Risk Assessment Agent', icon: '⚠️' };
  }
  if (/market|market size|demand|trend|customer|audience|tam|sam|som|growth|segment/.test(q)) {
    return { name: 'Market Research Agent', icon: '📊' };
  }
  return { name: 'Specialist Agent', icon: '⚡' };
}

const EMPTY_PIPELINE_STATE = {
  coordinator: 'pending',
  market: 'pending',
  competitor: 'pending',
  financial: 'pending',
  risk: 'pending',
  debate: 'pending',
  verdict: 'pending',
  report: 'pending',
};

export default function VentureLens() {
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState([]);
  const [initialLoading, setInitialLoading] = useState(false);
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const [predictedAgent, setPredictedAgent] = useState({ name: 'Specialist Agent', icon: '⚡' });
  const [result, setResult] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [startupIdea, setStartupIdea] = useState('');
  const [error, setError] = useState(null);
  const [followUpSuggestions, setFollowUpSuggestions] = useState(DEFAULT_FOLLOW_UP_SUGGESTIONS);
  const [pipelineStage, setPipelineStage] = useState('coordinator');
  const [agentStatuses, setAgentStatuses] = useState(EMPTY_PIPELINE_STATE);

  const chatBottomRef = useRef(null);
  const eventSourceRef = useRef(null);

  const hasStarted = Boolean(sessionId || messages.length > 0 || initialLoading);
  const isLoading = initialLoading || followUpLoading;

  const updatePipelineFromEvent = (event) => {
    if (!event || !event.stage) return;

    const stageMap = {
      coordinator: 'coordinator',
      research: 'research',
      debate: 'debate',
      verdict: 'verdict',
      report: 'report',
    };

    const normalizedStage = stageMap[event.stage] || event.stage;
    const isAgentEvent = event.type === 'agent_started' || event.type === 'agent_completed' || event.type === 'agent_error';

    if (event.type === 'pipeline_started') {
      setPipelineStage('coordinator');
      setAgentStatuses((prev) => ({ ...EMPTY_PIPELINE_STATE, coordinator: 'running' }));
      return;
    }

    if (event.type === 'agent_started') {
      setPipelineStage(normalizedStage === 'research' ? 'research' : normalizedStage);
      setAgentStatuses((prev) => {
        const next = { ...prev };
        if (normalizedStage === 'coordinator') next.coordinator = 'running';
        if (normalizedStage === 'research') {
          // Set individual research agent to running based on agent name
          if (event.agent && /Market/i.test(event.agent)) next.market = 'running';
          else if (event.agent && /Competitor/i.test(event.agent)) next.competitor = 'running';
          else if (event.agent && /Financial/i.test(event.agent)) next.financial = 'running';
          else if (event.agent && /Risk/i.test(event.agent)) next.risk = 'running';
          else {
            // Fallback: if agent name not recognized, set all to running
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
      setPipelineStage(normalizedStage === 'research' ? 'research' : normalizedStage);
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

    if (event.type === 'agent_error') {
      setAgentStatuses((prev) => {
        const next = { ...prev };
        if (normalizedStage === 'coordinator') next.coordinator = 'error';
        if (normalizedStage === 'research') {
          if (event.agent && /Market/i.test(event.agent)) next.market = 'error';
          if (event.agent && /Competitor/i.test(event.agent)) next.competitor = 'error';
          if (event.agent && /Financial/i.test(event.agent)) next.financial = 'error';
          if (event.agent && /Risk/i.test(event.agent)) next.risk = 'error';
        }
        if (normalizedStage === 'debate') next.debate = 'error';
        if (normalizedStage === 'verdict') next.verdict = 'error';
        if (normalizedStage === 'report') next.report = 'error';
        return next;
      });
      return;
    }

    if (event.type === 'pipeline_completed') {
      setPipelineStage('report');
      setAgentStatuses((prev) => ({
        ...prev,
        report: 'completed',
      }));
    }

    if (isAgentEvent && normalizedStage === 'research') {
      setPipelineStage('research');
    }
  };

  useEffect(() => {
    if (messages.length > 0 || followUpLoading) {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, followUpLoading]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleSubmit = async (userInput) => {
    const text = userInput.trim();
    if (!text || isLoading) return;

    setInputValue('');
    setError(null);

    // Case 1: Initial startup validation (no active session yet)
    if (!sessionId) {
      setStartupIdea(text);
      setInitialLoading(true);
      setPipelineStage('coordinator');
      setAgentStatuses({ ...EMPTY_PIPELINE_STATE, coordinator: 'running' });
      setMessages([{ role: 'user', content: text }]);

      try {
        const startResponse = await startValidation(text);
        const currentSessionId = startResponse.session_id;
        setSessionId(currentSessionId);

        if (eventSourceRef.current) {
          eventSourceRef.current.close();
        }

        eventSourceRef.current = streamValidationEvents(
          currentSessionId,
          (event) => {
            updatePipelineFromEvent(event);

            if (event.type === 'pipeline_completed') {
              getSession(currentSessionId)
                .then((session) => {
                  const resultData = session.validation_result || {};
                  const nextResult = {
                    session_id: currentSessionId,
                    raw: resultData.raw || '',
                    score: resultData.score,
                    recommendation: resultData.recommendation,
                    justification: resultData.justification,
                    agent_results: session.agent_results || {},
                  };

                  setResult(nextResult);
                  setMessages((prev) => [
                    ...prev,
                    {
                      role: 'ai',
                      content: nextResult.justification || nextResult.raw || 'Startup validation completed.',
                      agent: 'verdict',
                      agentName: 'Investor Verdict Agent',
                      agentIcon: '🏆',
                      isRevalidation: false,
                    },
                  ]);
                  setInitialLoading(false);
                })
                .catch((err) => {
                  setError(err.message || 'Unable to load final validation result.');
                })
                .finally(() => {
                  if (eventSourceRef.current) {
                    eventSourceRef.current.close();
                    eventSourceRef.current = null;
                  }
                });
            }
          },
          (err) => {
            setError(err?.message || 'Validation event stream interrupted.');
          },
        );
      } catch (err) {
        setError(err.message || 'Unable to start validation. Please try again.');
        setMessages((prev) => [
          ...prev,
          {
            role: 'ai',
            content: `⚠️ ${err.message || 'Validation pipeline error. Please check your API keys and try again.'}`,
          },
        ]);
        setInitialLoading(false);
      }
      return;
    }

    // Case 2: Follow-up question on existing validation session
    const prediction = predictAgentLoading(text);
    const isRevalRequest = prediction.name === 'Full Validation Pipeline';

    // Add user question to chat history
    setMessages((prev) => [...prev, { role: 'user', content: text }]);

    if (isRevalRequest) {
      setInitialLoading(true);
    } else {
      setFollowUpLoading(true);
      setPredictedAgent(prediction);
    }

    try {
      const response = await followUpQuestion(sessionId, text, startupIdea);

      // If full revalidation was executed, update the score, recommendation, and reports
      if (response.is_revalidation) {
        setResult((prev) => ({
          ...prev,
          score: response.score,
          recommendation: response.recommendation,
          justification: response.justification,
          raw: response.raw || prev?.raw,
        }));
      }

      // Append targeted agent answer
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: response.answer,
          agent: response.agent,
          agentName: response.agent_name,
          agentIcon: response.agent_icon,
          sources: response.sources,
          isRevalidation: response.is_revalidation,
        },
      ]);

      if (response.suggested_followups && response.suggested_followups.length > 0) {
        setFollowUpSuggestions(response.suggested_followups);
      }
    } catch (err) {
      setError(err.message || 'Follow-up query failed.');
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: `⚠️ ${err.message || 'Unable to answer follow-up question. Please try again.'}`,
        },
      ]);
    } finally {
      setFollowUpLoading(false);
      setInitialLoading(false);
    }
  };

  const handleSelectSuggestion = (suggestionText) => {
    handleSubmit(suggestionText);
  };

  return (
    <main className="venturelens-page">
      {/* Landing screen before any idea is submitted */}
      {!hasStarted && (
        <>
          <HeroSection />
          <PromptSuggestions onSelectIdea={(idea) => setInputValue(idea)} />
        </>
      )}

      {/* Initial validation pipeline loading indicator */}
      {initialLoading && (
        <div className="pipeline-section">
          <AgentProgress stage={pipelineStage} agentStatuses={agentStatuses} />

          <div className="parallel-agents">
            <div className="parallel-agents-label">
              <span className="parallel-icon">🔬</span>
              Research Agents Running in Parallel
            </div>
            <div className="agent-grid">
              <AgentCard type="market" status={agentStatuses.market} />
              <AgentCard type="competitor" status={agentStatuses.competitor} />
              <AgentCard type="financial" status={agentStatuses.financial} />
              <AgentCard type="risk" status={agentStatuses.risk} />
            </div>
          </div>
        </div>
      )}

      {/* Main results display once initial validation is completed */}
      {result && !initialLoading && (
        <div className="results-section animate-fade-in-up">
          {/* Completed agent indicators */}
          <div className="parallel-agents parallel-agents--done">
            <div className="parallel-agents-label">
              <span className="parallel-icon">✅</span>
              All Research Agents Completed
            </div>
            <div className="agent-grid">
              <AgentCard type="market" completed={true} />
              <AgentCard type="competitor" completed={true} />
              <AgentCard type="financial" completed={true} />
              <AgentCard type="risk" completed={true} />
            </div>
          </div>

          {/* Verdict Card */}
          <VerdictCard
            score={result.score}
            recommendation={result.recommendation}
            justification={result.justification}
          />

          {/* Overview & Full Report Tabs */}
          <ResultsTabs
            rawOutput={result.raw}
            score={result.score}
            recommendation={result.recommendation}
            justification={result.justification}
          />

          {/* Follow-up Conversation Section */}
          <div className="conversation-section animate-fade-in-up">
            <div className="conversation-header">
              <div className="conversation-title-row">
                <span className="conversation-icon">💬</span>
                <h2 className="conversation-title">Chat with VentureLens</h2>
                <span className="conversation-badge">Fast Agent Routing</span>
              </div>
              <p className="conversation-subtitle">
                Ask targeted follow-ups. Questions are instantly routed to the specialist agent without re-running the full pipeline.
              </p>
            </div>

            {/* Chat history list */}
            <div className="chat-container">
              {messages.map((msg, i) => (
                <ChatMessage
                  key={i}
                  role={msg.role}
                  content={msg.content}
                  agent={msg.agent}
                  agentName={msg.agentName}
                  agentIcon={msg.agentIcon}
                  sources={msg.sources}
                  isRevalidation={msg.isRevalidation}
                />
              ))}

              {/* Fast follow-up loading state */}
              {followUpLoading && (
                <div className="chat-message chat-message--ai chat-message--loading animate-fade-in">
                  <div className="chat-message-avatar">
                    <div className="avatar avatar--ai">
                      <span className="avatar-icon">{predictedAgent.icon}</span>
                    </div>
                  </div>
                  <div className="chat-message-body">
                    <div className="followup-loading-header">
                      <span className="followup-loading-name">{predictedAgent.name}</span>
                      <span className="followup-loading-tag">is researching & analyzing…</span>
                    </div>
                    <div className="typing-indicator">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatBottomRef} />
            </div>

            {/* Dynamic follow-up chips */}
            {!isLoading && (
              <div className="followup-section animate-fade-in">
                <p className="followup-label">Suggested follow-ups:</p>
                <div className="followup-chips">
                  {followUpSuggestions.map((q) => (
                    <button
                      key={q}
                      className="followup-chip"
                      onClick={() => handleSelectSuggestion(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error banner */}
      {error && !isLoading && (
        <div className="error-banner animate-fade-in">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Input bar */}
      <div className="input-section">
        <ChatInput
          onSubmit={handleSubmit}
          disabled={isLoading}
          value={inputValue}
          onChange={setInputValue}
          placeholder={
            sessionId
              ? 'Ask a follow-up question (e.g., Who are my competitors?, What is the market size?)...'
              : 'Enter your business idea (e.g., AI-powered pest detection for greenhouse farmers)...'
          }
        />
      </div>

      {/* Footer */}
      <footer className="vl-footer">
        <p>
          Architecture: 7-Agent Full Pipeline for initial evaluation • Single Specialist Research Agent for fast follow-ups
        </p>
      </footer>
    </main>
  );
}
