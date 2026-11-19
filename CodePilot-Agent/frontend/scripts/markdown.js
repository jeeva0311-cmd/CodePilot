/**
 * Markdown renderer for agent responses.
 * Handles: fenced code blocks, inline code, headers, bold/italic, lists, paragraphs.
 */
function renderMarkdown(text) {
  if (!text) return '';

  // 1. Extract fenced code blocks first to protect them from other transformations
  const codeBlocks = [];
  let html = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push({ lang: lang || 'text', code: code.trim() });
    return `\x00CODE${idx}\x00`;
  });

  // 2. Escape HTML in the non-code parts
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // 3. Inline code (backticks) — after HTML escaping
  html = html.replace(/`([^`\n]+)`/g, (_, code) =>
    `<code>${code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</code>`
  );

  // 4. Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm,  '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm,   '<h1>$1</h1>');

  // 5. Bold and italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g,     '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g,          '<strong>$1</strong>');
  html = html.replace(/\*([^*\n]+)\*/g,      '<em>$1</em>');
  html = html.replace(/_([^_\n]+)_/g,        '<em>$1</em>');

  // 6. Unordered lists — group consecutive lines starting with - * +
  html = html.replace(/((?:^[ \t]*[-*+] .+\n?)+)/gm, (block) => {
    const items = block.trim().split('\n')
      .filter(l => l.trim())
      .map(l => `<li>${l.replace(/^[ \t]*[-*+] /, '').trim()}</li>`);
    return '<ul>' + items.join('') + '</ul>';
  });

  // 7. Ordered lists
  html = html.replace(/((?:^[ \t]*\d+\. .+\n?)+)/gm, (block) => {
    const items = block.trim().split('\n')
      .filter(l => l.trim())
      .map(l => `<li>${l.replace(/^[ \t]*\d+\. /, '').trim()}</li>`);
    return '<ol>' + items.join('') + '</ol>';
  });

  // 8. Paragraphs — split on blank lines, wrap plain text blocks
  const sections = html.split(/\n{2,}/);
  html = sections.map(section => {
    section = section.trim();
    if (!section) return '';
    // Don't wrap if it's already a block-level element
    if (/^<(h[1-6]|ul|ol|li|pre|div|blockquote)/.test(section)) return section;
    // Don't wrap placeholder tokens
    if (section.startsWith('\x00CODE')) return section;
    // Convert single newlines to <br> within a paragraph
    return '<p>' + section.replace(/\n/g, '<br>') + '</p>';
  }).join('\n');

  // 9. Restore code blocks
  codeBlocks.forEach((cb, idx) => {
    const escapedCode = cb.code
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    const id = 'cb_' + idx + '_' + Math.random().toString(36).slice(2, 6);
    const block = `<pre><code class="lang-${escHtml(cb.lang)}">${escapedCode}</code>` +
      `<button class="code-copy-btn" data-code="${encodeURIComponent(cb.code)}" onclick="copyCode(this)">Copy</button></pre>`;
    html = html.replace(`\x00CODE${idx}\x00`, block);
  });

  return html;
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function copyCode(btn) {
  const code = decodeURIComponent(btn.getAttribute('data-code') || '');
  navigator.clipboard.writeText(code).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = orig, 1800);
  }).catch(() => {
    // Fallback for browsers without clipboard API
    const ta = document.createElement('textarea');
    ta.value = code;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 1800);
  });
}
