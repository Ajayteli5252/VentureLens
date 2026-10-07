import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import MarkdownRenderer from '../components/MarkdownRenderer';
import { getSession, cancelFollowUp, startFollowUp, streamFollowUpEvents } from '../services/api';
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import './FollowUpChatPage.css';

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

export default function FollowUpChatPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const [predictedAgent, setPredictedAgent] = useState({ name: 'Specialist Agent', icon: '⚡' });
  const [streamingActivity, setStreamingActivity] = useState(null);
  const [streamingAnswer, setStreamingAnswer] = useState('');
  const [streamingTiming, setStreamingTiming] = useState(null);
  const [followUpSuggestions, setFollowUpSuggestions] = useState(DEFAULT_FOLLOW_UP_SUGGESTIONS);
  const [error, setError] = useState(null);
  const [stoppedMessage, setStoppedMessage] = useState(null);

  const chatBottomRef = useRef(null);
  // Tracks the active request ID; set to null when stopped/completed
  const currentFollowUpIdRef = useRef(null);
  // Holds the active EventSource so we can close it on stop
  const eventSourceRef = useRef(null);
  const streamingAnswerRef = useRef('');
  const predictedAgentRef = useRef(predictedAgent);
  const currentTimingRef = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }

    setLoading(true);
    getSession(sessionId)
      .then((data) => {
        setSession(data);
        if (data.conversation && Array.isArray(data.conversation)) {
          setMessages(
            data.conversation.map((msg) => ({
              role: msg.role === 'user' ? 'user' : 'ai',
              content: msg.content,
              agent: msg.agent,
              agentName: msg.agent_name || (msg.agent === 'verdict' ? 'Investor Verdict Agent' : undefined),
              agentIcon: msg.agent_icon || (msg.agent === 'verdict' ? '🏆' : undefined),
              sources: msg.sources || [],
              isRevalidation: Boolean(msg.is_revalidation),
            }))
          );
        } else if (data.startup_idea) {
          setMessages([
            { role: 'user', content: data.startup_idea },
            {
              role: 'ai',
              content: data.validation_result?.justification || data.validation_result?.raw || 'Validation completed.',
              agent: 'verdict',
              agentName: 'Investor Verdict Agent',
              agentIcon: '🏆',
            },
          ]);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Unable to load chat session.');
        setLoading(false);
      });

    // Cleanup: close any open SSE stream when page unmounts
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [sessionId, navigate]);

  useEffect(() => {
    if (messages.length > 0 || followUpLoading) {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, followUpLoading, streamingActivity]);

  // ---------------------------------------------------------------------------
  // SSE event handler — scoped to the active requestId
  // ---------------------------------------------------------------------------
  const handleFollowUpSSEEvent = useCallback((event, source, requestId) => {
    // Guard: ignore stale events from a superseded request
    if (currentFollowUpIdRef.current !== requestId) {
      source.close();
      return;
    }

    switch (event.type) {
      case 'timing':
        setStreamingTiming(event);
        currentTimingRef.current = event;
        break;

      case 'followup_started': {
        const agentObj = {
          name: event.agent_name || 'Specialist Agent',
          icon: event.agent_icon || '⚡',
        };
        setPredictedAgent(agentObj);
        predictedAgentRef.current = agentObj;
        setStreamingActivity(event.message || 'Starting analysis...');
        break;
      }

      case 'followup_activity':
        setStreamingActivity(event.message || 'Analyzing...');
        break;

      case 'search_started':
        setStreamingActivity(event.message || 'Searching...');
        break;

      case 'source_found':
        setStreamingActivity(event.message || 'Source found');
        break;

      case 'followup_delta':
        streamingAnswerRef.current = (streamingAnswerRef.current || '') + (event.delta || '');
        setStreamingAnswer(streamingAnswerRef.current);
        break;

      case 'followup_completed':
        source.close();
        eventSourceRef.current = null;
        currentFollowUpIdRef.current = null;
        setFollowUpLoading(false);
        setStreamingActivity(null);
        setStreamingAnswer('');
        streamingAnswerRef.current = '';
        setMessages((prev) => [
          ...prev,
          {
            role: 'ai',
            content: event.answer,
            agent: event.agent,
            agentName: event.agent_name,
            agentIcon: event.agent_icon,
            sources: event.sources || [],
            isRevalidation: Boolean(event.is_revalidation),
            timing: event.timing || currentTimingRef.current,
          },
        ]);
        if (event.suggested_followups?.length) {
          setFollowUpSuggestions(event.suggested_followups);
        }
        if (event.is_revalidation) {
          setSession((prev) => ({
            ...prev,
            validation_result: {
              ...prev?.validation_result,
              score: event.score,
              recommendation: event.recommendation,
              justification: event.justification,
            },
          }));
        }
        break;

      case 'followup_cancelled':
        source.close();
        eventSourceRef.current = null;
        currentFollowUpIdRef.current = null;
        setFollowUpLoading(false);
        setStreamingActivity(null);
        if (streamingAnswerRef.current) {
          setMessages((prev) => [
            ...prev,
            {
              role: 'ai',
              content: streamingAnswerRef.current + '\n\n*(Generation stopped)*',
              agent: predictedAgentRef.current?.name,
              agentName: predictedAgentRef.current?.name,
              agentIcon: predictedAgentRef.current?.icon,
              sources: [],
            },
          ]);
        }
        setStreamingAnswer('');
        streamingAnswerRef.current = '';
        setStoppedMessage('Generation stopped.');
        break;

      case 'followup_error':
        source.close();
        eventSourceRef.current = null;
        currentFollowUpIdRef.current = null;
        setFollowUpLoading(false);
        setStreamingActivity(null);
        setStreamingAnswer('');
        streamingAnswerRef.current = '';
        setError(event.message || 'Follow-up failed. Please try again.');
        break;

      default:
        break;
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Stop handler
  // ---------------------------------------------------------------------------
  const handleStopFollowUp = async () => {
    const reqId = currentFollowUpIdRef.current;
    if (!reqId) return;

    // 1. Close the SSE stream immediately (no more events)
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // 2. Invalidate the active request so stale callbacks are no-ops
    currentFollowUpIdRef.current = null;

    // 3. Preserve any partial streamed content
    if (streamingAnswerRef.current) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: streamingAnswerRef.current + '\n\n*(Generation stopped)*',
          agent: predictedAgent.name,
          agentName: predictedAgent.name,
          agentIcon: predictedAgent.icon,
          sources: [],
        },
      ]);
    }

    // 4. Update UI
    setStreamingAnswer('');
    streamingAnswerRef.current = '';
    setFollowUpLoading(false);
    setStreamingActivity(null);
    setStoppedMessage('Generation stopped.');

    // 5. Tell the backend to stop the background thread
    try {
      await cancelFollowUp(reqId);
    } catch (_) {
      // Optimistic stop — ignore backend errors
    }
  };

  // ---------------------------------------------------------------------------
  // Send handler
  // ---------------------------------------------------------------------------
  const handleSendMessage = async (text) => {
    const questionText = text.trim();
    if (!questionText || followUpLoading) return;

    setInputValue('');
    setError(null);
    setStoppedMessage(null);
    setStreamingActivity(null);
    setStreamingAnswer('');
    streamingAnswerRef.current = '';
    setStreamingTiming(null);
    currentTimingRef.current = null;

    // Optimistic agent prediction for immediate UI feedback
    const optimisticAgent = predictAgentLoading(questionText);
    setPredictedAgent(optimisticAgent);
    setFollowUpLoading(true);

    // Append the user message immediately
    setMessages((prev) => [...prev, { role: 'user', content: questionText }]);

    // Generate a unique requestId on the client so we can call cancelFollowUp
    // even before the SSE stream is opened (race condition safety)
    const requestId = `fu-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    currentFollowUpIdRef.current = requestId;

    try {
      // Non-blocking start: returns immediately with requestId + confirmed agent info
      const startResult = await startFollowUp(
        sessionId,
        questionText,
        session?.startup_idea,
        requestId,
      );

      // If the user pressed Stop before the server responded, bail out
      if (!currentFollowUpIdRef.current) return;

      // Update agent display with server-confirmed info
      setPredictedAgent({
        name: startResult.agent_name || optimisticAgent.name,
        icon: startResult.agent_icon || optimisticAgent.icon,
      });

      // Open the per-request SSE stream
      const source = streamFollowUpEvents(
        startResult.request_id,
        (event) => handleFollowUpSSEEvent(event, source, requestId),
        (_err) => {
          // SSE transport error — if we're still loading, treat as completion failure
          if (currentFollowUpIdRef.current !== requestId) return;
          setFollowUpLoading(false);
          setStreamingActivity(null);
        },
      );
      eventSourceRef.current = source;

    } catch (err) {
      if (!currentFollowUpIdRef.current) return;
      currentFollowUpIdRef.current = null;
      setFollowUpLoading(false);
      setStreamingActivity(null);
      setError(err.message || 'Failed to start follow-up.');
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: `⚠️ ${err.message || 'Unable to start follow-up. Please try again.'}`,
        },
      ]);
    }
  };

  if (loading) {
    return (
      <div className="chat-loading-screen animate-fade-in">
        <div className="chat-spinner" />
        <p>Loading follow-up chat session...</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="chat-error-screen animate-fade-in">
        <div className="chat-page-container">
          <div className="chat-header-bar">
            <Link to={`/report/${sessionId}`} className="back-link">
              ← Back to Report
            </Link>
          </div>
          <div className="chat-error-banner">
            <span className="error-icon">⚠️</span>
            <span>{error || 'Validation session could not be found.'}</span>
          </div>
        </div>
      </div>
    );
  }

  const idea = session?.startup_idea || '';
  const score = session?.validation_result?.score;
  const recommendation = session?.validation_result?.recommendation;

  return (
    <div className="followup-chat-page animate-fade-in-up">
      <div className="chat-page-container">

        {/* Header with Context */}
        <div className="chat-header-bar">
          <div className="header-left-col">
            <Link to={`/result/${sessionId}`} className="back-link">
              ← Back to Result
            </Link>
            <div className="chat-title-group">
              <span className="chat-icon">💬</span>
              <h1 className="chat-main-title">Chat with VentureLens</h1>
              <span className="chat-badge">Fast Agent Routing</span>
            </div>
          </div>

          {score != null && (
            <div className="header-verdict-summary">
              <span className="summary-score">{score} / 10</span>
              <span className={`summary-rec ${(recommendation || '').toLowerCase().includes('no') ? 'rec--nogo' : 'rec--go'}`}>
                {(recommendation || '').toLowerCase().includes('no') ? 'NOT VALIDATED' : 'VALIDATE'}
              </span>
            </div>
          )}
        </div>

        {/* Idea Banner */}
        {idea && (
          <div className="chat-idea-card">
            <span className="idea-tag">Startup Context:</span>
            <p className="idea-quote">"{idea}"</p>
          </div>
        )}

        {/* Message Container */}
        <div className="chat-messages-container">
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
              timing={msg.timing}
            />
          ))}

          {/* Real-time agent loading indicator with live activity + incremental streaming text + Stop button */}
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
                  <span className="followup-loading-tag">
                    {streamingAnswer
                      ? 'is answering…'
                      : streamingActivity
                      ? ''
                      : 'is researching & analyzing…'}
                  </span>
                  {streamingTiming?.elapsed_ms && (
                    <span className="streaming-timing-indicator">
                      ⏱️ {(streamingTiming.elapsed_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>

                {/* Incremental streaming text OR live activity OR typing indicator */}
                {streamingAnswer ? (
                  <div className="streaming-answer-container animate-fade-in">
                    <MarkdownRenderer content={streamingAnswer} className="streaming-markdown" />
                    <span className="streaming-cursor" />
                  </div>
                ) : streamingActivity ? (
                  <div className="streaming-activity animate-fade-in">
                    <span className="activity-pulse">●</span>
                    <span className="activity-text">{streamingActivity}</span>
                  </div>
                ) : (
                  <div className="typing-indicator">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </div>
                )}

                <button
                  type="button"
                  className="followup-stop-btn"
                  onClick={handleStopFollowUp}
                  title="Stop generating this response"
                >
                  ⏹ Stop
                </button>
              </div>
            </div>
          )}

          {/* Stopped message */}
          {stoppedMessage && !followUpLoading && (
            <div className="followup-stopped-banner animate-fade-in">
              <span className="stopped-icon">⏹</span>
              <span>{stoppedMessage}</span>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Suggested Chips */}
        {!followUpLoading && (
          <div className="chat-suggestions-section">
            <span className="suggestions-label">Suggested follow-ups:</span>
            <div className="suggestions-chips-row">
              {followUpSuggestions.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="chat-suggestion-chip"
                  onClick={() => handleSendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="chat-error-banner animate-fade-in">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Fixed Chat Input Bar */}
        <div className="chat-input-wrapper">
          <ChatInput
            onSubmit={handleSendMessage}
            disabled={followUpLoading}
            value={inputValue}
            onChange={setInputValue}
            placeholder={followUpLoading ? 'Generating...' : 'Ask a follow-up question (e.g., Who are my competitors?, What is the TAM?)...'}
          />
        </div>

      </div>
    </div>
  );
}
