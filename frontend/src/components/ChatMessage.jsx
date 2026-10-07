import MarkdownRenderer from './MarkdownRenderer';
import './ChatMessage.css';

export default function ChatMessage({
  role,
  content,
  agent,
  agentName,
  agentIcon,
  sources,
  isRevalidation,
  timing,
}) {
  const isUser = role === 'user';

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
          <MarkdownRenderer content={content} />
        </div>

        {/* Clickable sources list — with domain + open link */}
        {sources && sources.length > 0 && (
          <div className="chat-sources animate-fade-in">
            <div className="chat-sources-header">
              <span className="chat-sources-icon">🔗</span>
              <span className="chat-sources-title">Sources</span>
            </div>
            <ul className="chat-sources-list">
              {sources.map((src, i) => {
                let domain = '';
                try {
                  domain = new URL(src.url).hostname.replace('www.', '');
                } catch (_) {
                  domain = src.title || src.url;
                }
                return (
                  <li key={i} className="chat-source-item">
                    <div className="source-meta">
                      <span className="source-num">[{i + 1}]</span>
                      <div className="source-info">
                        <span className="source-title">{src.title || domain}</span>
                        <span className="source-domain">{domain}</span>
                      </div>
                    </div>
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="chat-source-link"
                    >
                      Open ↗
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* Latency timing badge */}
        {timing && (
          <div className="chat-timing-meta">
            <span>⏱️ {timing.total_seconds ? `${timing.total_seconds}s` : (timing.total_ms ? `${(timing.total_ms / 1000).toFixed(1)}s` : '')}</span>
          </div>
        )}
      </div>
    </div>
  );
}
