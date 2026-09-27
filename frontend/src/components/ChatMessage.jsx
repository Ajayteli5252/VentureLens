import './ChatMessage.css';

export default function ChatMessage({
  role,
  content,
  agent,
  agentName,
  agentIcon,
  sources,
  isRevalidation,
}) {
  const isUser = role === 'user';

  // Basic formatting helper for bold text and paragraphs/lists
  const formatContent = (text) => {
    if (!text) return null;
    const lines = text.split('\n');
    return lines.map((line, idx) => {
      // Bold rendering for **text**
      const parts = line.split(/(\*\*[^*]+\*\*)/g);
      const formattedParts = parts.map((part, pIdx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={pIdx}>{part.slice(2, -2)}</strong>;
        }
        return part;
      });

      if (line.trim().startsWith('- ') || line.trim().startsWith('• ')) {
        return (
          <li key={idx} className="message-bullet">
            {formattedParts}
          </li>
        );
      }

      if (line.trim() === '') {
        return <div key={idx} className="message-spacer" />;
      }

      return (
        <p key={idx} className="message-paragraph">
          {formattedParts}
        </p>
      );
    });
  };

  return (
    <div className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--ai'} animate-fade-in-up`}>
      <div className="chat-message-avatar">
        {isUser ? (
          <div className="avatar avatar--user">U</div>
        ) : (
          <div className="avatar avatar--ai">
            {agentIcon ? (
              <span className="avatar-icon">{agentIcon}</span>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="10.5" cy="10.5" r="6.8" />
                <line x1="15.8" y1="15.8" x2="21" y2="21" />
              </svg>
            )}
          </div>
        )}
      </div>

      <div className="chat-message-body">
        {/* Agent attribution badge */}
        {!isUser && agentName && (
          <div className="agent-badge">
            <span className="agent-badge-icon">{agentIcon || '🤖'}</span>
            <span className="agent-badge-name">{agentName}</span>
            <span className={`agent-badge-tag ${isRevalidation ? 'agent-badge-tag--reval' : ''}`}>
              {isRevalidation ? '🔄 Full Validation' : '⚡ Follow-up analysis'}
            </span>
          </div>
        )}

        {isUser && <span className="chat-message-name">You</span>}

        <div className="chat-message-content">
          {formatContent(content)}
        </div>

        {/* Clickable sources list if present */}
        {sources && sources.length > 0 && (
          <div className="chat-sources animate-fade-in">
            <div className="chat-sources-header">
              <span className="chat-sources-icon">🔗</span>
              <span className="chat-sources-title">Sources</span>
            </div>
            <ul className="chat-sources-list">
              {sources.map((src, i) => (
                <li key={i} className="chat-source-item">
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="chat-source-link"
                  >
                    • {src.title || src.url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
