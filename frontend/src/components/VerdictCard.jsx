import MarkdownRenderer from './MarkdownRenderer';
import './VerdictCard.css';

export default function VerdictCard({ score, recommendation, justification }) {
  const scoreNum = typeof score === 'number' ? score : parseFloat(score);
  const isGo = recommendation?.toLowerCase()?.includes('go') && !recommendation?.toLowerCase()?.includes('no');

  let scoreColor = '#B8860B';
  if (scoreNum >= 7) scoreColor = 'var(--success-green)';
  else if (scoreNum < 5) scoreColor = 'var(--danger-red)';

  const pillClass = isGo ? 'verdict-pill--go' : 'verdict-pill--nogo';

  return (
    <div className="verdict-card animate-fade-in-up">
      <div className="verdict-header">
        <span className="verdict-icon">🏆</span>
        <span className="verdict-title">Final Validation Result</span>
      </div>

      <div className="verdict-metrics">
        <div className="verdict-score-box">
          <span className="verdict-score-label">Overall Score</span>
          <div className="verdict-score-value" style={{ color: scoreColor }}>
            {isNaN(scoreNum) ? '—' : scoreNum.toFixed(1)}
            <span className="verdict-score-max">/10</span>
          </div>
        </div>

        <div className="verdict-rec-box">
          <span className="verdict-rec-label">Recommendation</span>
          <div className={`verdict-pill ${pillClass}`}>
            {isGo ? 'VALIDATE' : 'NOT VALIDATED'}
          </div>
        </div>
      </div>

      {justification && (
        <div className="verdict-justification" style={{ borderLeftColor: scoreColor }}>
          <span className="verdict-just-label">Investment Verdict Justification</span>
          <div className="verdict-just-text">
            <MarkdownRenderer content={justification} />
          </div>
        </div>
      )}
    </div>
  );
}
