import './Header.css';

export default function Header() {
  return (
    <header className="header">
      <div className="header-inner">
        <a href="/" className="header-logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--accent-orange)" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="10.5" cy="10.5" r="6.8" />
            <line x1="15.8" y1="15.8" x2="21" y2="21" />
          </svg>
          <span className="header-brand">VentureLens</span>
        </a>
        <nav className="header-nav">
          <a href="#features" className="header-link">Features</a>
          <a href="#about" className="header-link">About</a>
        </nav>
      </div>
    </header>
  );
}
