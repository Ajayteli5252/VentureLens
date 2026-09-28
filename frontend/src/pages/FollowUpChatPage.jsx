import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getSession, followUpQuestion, cancelFollowUp } from '../services/api';
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
  const [followUpSuggestions, setFollowUpSuggestions] = useState(DEFAULT_FOLLOW_UP_SUGGESTIONS);
  const [error, setError] = useState(null);
  const [stoppedMessage, setStoppedMessage] = useState(null);

  const chatBottomRef = useRef(null);
  // Ref to track current follow-up request id for cancellation
  const currentFollowUpIdRef = useRef(null);

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }

    setLoading(true);
    getSession(sessionId)
      .then((data) => {
        setSession(data);
        // Load initial conversation history if available
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
          // Fallback initial context message
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
  }, [sessionId, navigate]);

  useEffect(() => {
    if (messages.length > 0 || followUpLoading) {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, followUpLoading]);

  const handleStopFollowUp = async () => {
    const reqId = currentFollowUpIdRef.current;
    if (!reqId) return;
    try {
      await cancelFollowUp(reqId);
    } catch (_) {
      // ignore — optimistic stop
    }
    currentFollowUpIdRef.current = null;
    setFollowUpLoading(false);
    setStoppedMessage('Generation stopped.');
  };

  const handleSendMessage = async (text) => {
    const questionText = text.trim();
    if (!questionText || followUpLoading) return;

    setInputValue('');
    setError(null);
    setStoppedMessage(null);

    const prediction = predictAgentLoading(questionText);
    setPredictedAgent(prediction);
    setFollowUpLoading(true);

    // Append user question
    setMessages((prev) => [...prev, { role: 'user', content: questionText }]);

    // Generate a unique request id for cancellation
    const requestId = `followup-${Date.now()}`;
    currentFollowUpIdRef.current = requestId;

    try {
      const response = await followUpQuestion(sessionId, questionText, session?.startup_idea, requestId);

      // If cancelled while awaiting, do not update messages
      if (!currentFollowUpIdRef.current) return;
      currentFollowUpIdRef.current = null;

      // Append assistant answer
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

      // If revalidation happened, update session state
      if (response.is_revalidation) {
        setSession((prev) => ({
          ...prev,
          validation_result: {
            ...prev?.validation_result,
            score: response.score,
            recommendation: response.recommendation,
            justification: response.justification,
          },
        }));
      }
    } catch (err) {
      // If cancelled, show stopped message instead of error
      if (!currentFollowUpIdRef.current) return;
      currentFollowUpIdRef.current = null;
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
              <span className={`summary-rec ${recommendation?.toLowerCase().includes('no') ? 'rec--nogo' : 'rec--go'}`}>
                {recommendation?.toLowerCase().includes('no') ? 'NOT VALIDATED' : 'VALIDATE'}
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
            />
          ))}

          {/* Real-time agent loading indicator with Stop button */}
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
                  <span className="followup-loading-tag">is researching &amp; analyzing…</span>
                </div>
                <div className="typing-indicator">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
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
