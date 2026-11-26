// Layout lint for Clearon poster HTML. Run in the rendered page BEFORE taking the screenshot:
//   issues = page.evaluate(open('tools/qa_dom.js').read())
// Returns a list of strings; an empty list means no layout problems were found.
// Checks every element that directly holds visible text:
//   - text running outside the canvas or into the 40px safe margin
//   - text clipped by its own box (overflow) or its parent card
//   - two text blocks overlapping each other (unless one is a deliberate faded background glyph, opacity < 0.3)
//   - body text smaller than 20px (unreadable on a phone once the image is shown ~360px wide)
//   - text overlapping the logo
(() => {
  const W = document.documentElement.clientWidth, H = document.documentElement.clientHeight;
  const SAFE = 40, MIN_PX = 20;
  const issues = [];
  const label = el => (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40);
  const opacity = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  const textEls = [...document.body.querySelectorAll('*')].filter(el => {
    if (['SCRIPT', 'STYLE', 'svg'].includes(el.tagName) || el.closest('svg')) return false;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden' && opacity(el) >= 0.3;
  });
  const footer = document.querySelector('.footer');
  const rects = textEls.map(el => {
    // tight box around the text itself, not the whole block
    const range = document.createRange(); range.selectNodeContents(el);
    const r = range.getBoundingClientRect();
    return { el, r };
  });
  for (const { el, r } of rects) {
    const inFooter = footer && footer.contains(el);
    const m = inFooter ? 0 : SAFE;
    if (r.left < m - 1 || r.right > W - m + 1 || r.top < m - 1 || r.bottom > H + 1)
      issues.push(`outside safe area: "${label(el)}" (${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.right)},${Math.round(r.bottom)})`);
    if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== 'visible')
      issues.push(`clipped horizontally: "${label(el)}"`);
    if (el.scrollHeight > el.clientHeight + 2 && getComputedStyle(el).overflow !== 'visible')
      issues.push(`clipped vertically: "${label(el)}"`);
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < MIN_PX && !inFooter) issues.push(`text too small (${fs}px): "${label(el)}"`);
    // clipped by an ancestor with overflow hidden/rounded card
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ov = getComputedStyle(p).overflow;
      if (ov === 'hidden' || ov === 'clip') {
        const pr = p.getBoundingClientRect();
        if (r.right > pr.right + 1 || r.bottom > pr.bottom + 1 || r.left < pr.left - 1 || r.top < pr.top - 1)
          issues.push(`cut off by container: "${label(el)}"`);
        break;
      }
    }
  }
  // Overlap test on the visible glyph band of each line: the browser's line boxes include
  // the font's full ascent/descent, which overlap harmlessly with tight line-heights (Anton at ~1.0).
  const glyphLines = el => {
    const fs = parseFloat(getComputedStyle(el).fontSize);
    const range = document.createRange(); range.selectNodeContents(el);
    return [...range.getClientRects()].filter(r => r.width > 0).map(r => {
      const inset = Math.max(0, (r.height - fs) / 2) + 0.12 * fs;
      return { left: r.left, right: r.right, top: r.top + inset, bottom: r.bottom - inset };
    });
  };
  const lines = rects.map(({ el }) => ({ el, ls: glyphLines(el) }));
  for (let i = 0; i < lines.length; i++) for (let j = i + 1; j < lines.length; j++) {
    const a = lines[i], b = lines[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    let hit = false;
    for (const x of a.ls) for (const y of b.ls) {
      const ox = Math.min(x.right, y.right) - Math.max(x.left, y.left);
      const oy = Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top);
      if (ox > 4 && oy > 3) hit = true;
    }
    if (hit) issues.push(`text overlap: "${label(a.el)}" / "${label(b.el)}"`);
  }
  const logo = document.querySelector('img.logo');
  if (logo) {
    const lr = logo.getBoundingClientRect();
    for (const { el, r } of rects) {
      const ox = Math.min(lr.right, r.right) - Math.max(lr.left, r.left);
      const oy = Math.min(lr.bottom, r.bottom) - Math.max(lr.top, r.top);
      if (ox > 2 && oy > 2) issues.push(`text over logo: "${label(el)}"`);
    }
  }
  if (!footer) issues.push('no .footer element (contact footer missing)');
  else {
    const t = footer.innerText.replace(/\s+/g, ' ');
    if (!t.includes('+254 115007849')) issues.push('footer missing phone +254 115007849');
    if (!t.includes('info@clearonlogistics.co.ke')) issues.push('footer missing email');
  }
  return [...new Set(issues)];
})()
