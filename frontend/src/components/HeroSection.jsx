import './HeroSection.css';

export default function HeroSection() {
  return (
    <div className="hero animate-fade-in-up">
      <div className="hero-icon-row">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--accent-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="10.5" cy="10.5" r="6.8" />
          <line x1="15.8" y1="15.8" x2="21" y2="21" />
        </svg>
      </div>
      <h1 className="hero-title">VentureLens</h1>
      <div className="hero-accent-line" />
      <p className="hero-subtitle">
        Validate your startup idea. Our multi-agent AI researches,
        debates, and scores your business concept.
      </p>
    </div>
  );
}
