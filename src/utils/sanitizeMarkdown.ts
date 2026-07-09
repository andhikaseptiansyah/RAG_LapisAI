import { marked } from 'marked';

marked.setOptions({
  gfm: true,
  breaks: true,
});

const allowedTags = new Set([
  'A',
  'BLOCKQUOTE',
  'BR',
  'CODE',
  'DEL',
  'EM',
  'H1',
  'H2',
  'H3',
  'H4',
  'H5',
  'H6',
  'HR',
  'LI',
  'OL',
  'P',
  'PRE',
  'STRONG',
  'TABLE',
  'TBODY',
  'TD',
  'TH',
  'THEAD',
  'TR',
  'UL',
]);

const dangerousTags = new Set([
  'SCRIPT',
  'STYLE',
  'IFRAME',
  'OBJECT',
  'EMBED',
  'FORM',
  'INPUT',
  'TEXTAREA',
  'SELECT',
  'BUTTON',
  'LINK',
  'META',
]);

function isSafeUrl(value: string): boolean {
  const normalized = value.trim().toLowerCase();

  return (
    normalized.startsWith('https://') ||
    normalized.startsWith('http://') ||
    normalized.startsWith('mailto:') ||
    normalized.startsWith('/') ||
    normalized.startsWith('#')
  );
}

function sanitizeElement(element: Element): void {
  const children = Array.from(element.children);

  children.forEach((child) => {
    if (dangerousTags.has(child.tagName)) {
      child.remove();
      return;
    }

    if (!allowedTags.has(child.tagName)) {
      child.replaceWith(...Array.from(child.childNodes));
      return;
    }

    Array.from(child.attributes).forEach((attribute) => {
      const attributeName = attribute.name.toLowerCase();
      const isAllowedHref =
        child.tagName === 'A' && attributeName === 'href';
      const isAllowedTitle =
        child.tagName === 'A' && attributeName === 'title';
      const isAllowedCodeClass =
        child.tagName === 'CODE' && attributeName === 'class';

      if (!isAllowedHref && !isAllowedTitle && !isAllowedCodeClass) {
        child.removeAttribute(attribute.name);
      }
    });

    if (child.tagName === 'A') {
      const href = child.getAttribute('href');

      if (!href || !isSafeUrl(href)) {
        child.removeAttribute('href');
      } else {
        child.setAttribute('target', '_blank');
        child.setAttribute('rel', 'noopener noreferrer nofollow');
      }
    }

    sanitizeElement(child);
  });
}

export function sanitizeMarkdown(markdown: string): string {
  if (!markdown.trim()) return '';

  const parsed = marked.parse(markdown, { async: false });
  const html = typeof parsed === 'string' ? parsed : '';
  const template = document.createElement('template');

  template.innerHTML = html;
  sanitizeElement(template.content as unknown as Element);

  return template.innerHTML;
}
