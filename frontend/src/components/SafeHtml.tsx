import DOMPurify from 'dompurify';

interface SafeHtmlProps {
  content: string;
  className?: string;
}

/**
 * Renders HTML content safely by sanitizing it with DOMPurify.
 * Prevents XSS attacks from server-provided HTML content.
 */
export default function SafeHtml({ content, className }: SafeHtmlProps) {
  const sanitized = DOMPurify.sanitize(content, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'b', 'i', 'u', 'a', 'ul', 'ol', 'li',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div', 'table', 'thead',
      'tbody', 'tr', 'th', 'td', 'blockquote', 'pre', 'code', 'hr',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
    ALLOW_DATA_ATTR: false,
    ADD_ATTR: ['target'],
    FORBID_ATTR: ['style'],
  });

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: sanitized }}
    />
  );
}
