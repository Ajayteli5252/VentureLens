import { Link, useLocation } from 'react-router-dom';
import './Header.css';

export default function Header() {
  const location = useLocation();

  // Extract sessionId from path if user is inside a session route
  const sessionMatch = location.pathname.match(/\/(validate|result|report|chat|agent)\/([^/]+)/);
  const currentSessionId = sessionMatch ? sessionMatch[2] : null;

  return (
    <header className="header">
      <div className="header-inner">
        <div className="header-left">
          <Link to="/" className="header-logo" title="Back to Home">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-orange)" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="10.5" cy="10.5" r="6.8" />
              <line x1="15.8" y1="15.8" x2="21" y2="21" />
            </svg>
            <span className="header-brand">VentureLens</span>
          </Link>

          {currentSessionId && (
            <div className="header-breadcrumbs">
              <span className="breadcrumb-divider">/</span>
              <nav className="header-session-nav">
                <Link
                  to={`/validate/${currentSessionId}`}
                  className={`breadcrumb-item ${location.pathname.startsWith('/validate') ? 'breadcrumb-item--active' : ''}`}
                >
                  Validation
                </Link>
                <Link
                  to={`/result/${currentSessionId}`}
                  className={`breadcrumb-item ${location.pathname.startsWith('/result') ? 'breadcrumb-item--active' : ''}`}
                >
                  Result
                </Link>
                <Link
                  to={`/report/${currentSessionId}`}
                  className={`breadcrumb-item ${location.pathname.startsWith('/report') ? 'breadcrumb-item--active' : ''}`}
                >
                  Report
                </Link>
                <Link
                  to={`/chat/${currentSessionId}`}
                  className={`breadcrumb-item ${location.pathname.startsWith('/chat') ? 'breadcrumb-item--active' : ''}`}
                >
                  Chat
                </Link>
                <Link
                  to={`/agent/${currentSessionId}/market`}
                  className={`breadcrumb-item ${location.pathname.startsWith('/agent') ? 'breadcrumb-item--active' : ''}`}
                >
                  Agents
                </Link>
              </nav>
            </div>
          )}
        </div>

        <div className="header-right">
          <nav className="header-nav">
            <a href="#features" className="header-link">Features</a>
            <a href="#pricing" className="header-link">Pricing</a>
            <a href="#about" className="header-link">About</a>
          </nav>
          <div className="user-avatar" title="Founder Account">
            <span>VL</span>
          </div>
        </div>
      </div>
    </header>
  );
}
