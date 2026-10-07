import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './MarkdownRenderer.css';

/**
 * Reusable Markdown renderer using react-markdown + remark-gfm.
 * Handles bold, italic, headings, bullets, tables, code, links, blockquotes.
 * Used across: Full Report, Agent Details, Result cards, Follow-up Chat.
 *
 * NOTE: In react-markdown v9+, `className` must NOT be passed to <ReactMarkdown>;
 * instead it is applied to the wrapper <div>.
 */
export default function MarkdownRenderer({ content, className = '' }) {
  if (!content) return null;
  const contentStr = typeof content === 'string' ? content : String(content);

  return (
    <div className={`markdown-renderer-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="md-p">{children}</p>,
          h1: ({ children }) => <h1 className="md-h1">{children}</h1>,
          h2: ({ children }) => <h2 className="md-h2">{children}</h2>,
          h3: ({ children }) => <h3 className="md-h3">{children}</h3>,
          h4: ({ children }) => <h4 className="md-h4">{children}</h4>,
          h5: ({ children }) => <h5 className="md-h5">{children}</h5>,
          h6: ({ children }) => <h6 className="md-h6">{children}</h6>,
          ul: ({ children }) => <ul className="md-ul">{children}</ul>,
          ol: ({ children }) => <ol className="md-ol">{children}</ol>,
          li: ({ children }) => <li className="md-li">{children}</li>,
          strong: ({ children }) => <strong className="md-strong">{children}</strong>,
          em: ({ children }) => <em className="md-em">{children}</em>,
          pre: ({ children }) => <pre className="md-code-block">{children}</pre>,
          code: ({ node, className: codeClass, children, ...props }) => {
            const isInline = !codeClass && !String(children).includes('\n');
            if (isInline) {
              return <code className="md-code-inline" {...props}>{children}</code>;
            }
            return <code className={codeClass} {...props}>{children}</code>;
          },
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="md-link">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="md-blockquote">{children}</blockquote>
          ),
          table: ({ children }) => (
            <div className="md-table-wrapper">
              <table className="md-table">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead>{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr>{children}</tr>,
          th: ({ children }) => <th className="md-th">{children}</th>,
          td: ({ children }) => <td className="md-td">{children}</td>,
          hr: () => <hr className="md-hr" />,
        }}
      >
        {contentStr}
      </ReactMarkdown>
    </div>
  );
}
