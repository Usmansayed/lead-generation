/**
 * Extract post metadata from LinkedIn DOM after React has rendered.
 * Includes author display name and authorUsername (profile slug / handle).
 */

/**
 * Extract author username from LinkedIn post URL.
 * e.g. .../posts/usman-sayed-56884735b_big-lesson-...-7432040278024286208-pbhV → usman-sayed-56884735b
 * @param {string} postUrl
 * @returns {string | null}
 */
export function authorUsernameFromPostUrl(postUrl) {
  if (!postUrl || !postUrl.includes('linkedin.com/posts/')) return null;
  try {
    const match = postUrl.match(/linkedin\.com\/posts\/([^/_]+)/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

/**
 * @param {import('playwright').Page} page
 * @param {{ postUrl?: string }} [opts] - postUrl for username fallback from URL
 * @returns {Promise<{ postText?: string, author?: string, authorUsername?: string, timestamp?: string, likes?: string, comments?: string, hashtags?: string[], mentions?: string[], links?: string[] }>}
 */
export async function extractMetadataFromPage(page, opts = {}) {
  const out = { hashtags: [], mentions: [], links: [] };
  const postUrl = opts.postUrl || (await page.url());

  // ---- 0) Author username from post URL (reliable for /posts/ URLs) ----
  out.authorUsername = authorUsernameFromPostUrl(postUrl);

  // ---- 1) Meta tags and title ----
  try {
    const ogTitle = await page.locator('meta[property="og:title"]').getAttribute('content');
    const ogDesc = await page.locator('meta[property="og:description"]').getAttribute('content');
    const title = await page.title();
    if (ogTitle) {
      const pipe = ogTitle.lastIndexOf(' | ');
      if (pipe > 0) out.author = ogTitle.slice(pipe + 3).trim();
      else out.author = ogTitle.replace(/'s Post$/i, '').trim();
    }
    if (ogDesc && !out.postText) out.postText = ogDesc;
    if (title && !out.author) {
      const m = title.match(/\|\s*(.+?)\s*$/);
      if (m) out.author = m[1].trim();
      else {
        const m2 = title.match(/^(.+?)'s Post/i) || title.match(/^(.+?) \| LinkedIn/);
        if (m2) out.author = m2[1].trim();
      }
    }
  } catch {}

  // ---- 2) DOM: main feed / activity card ----
  try {
    const cardSelectors = [
      '[data-test-id="main-feed-activity-card"]',
      '[data-chameleon-result-urn]',
      'article.feed-shared-update-v2',
      'section.feed-shared-update-v2',
      '.scaffold-feed__main',
    ];
    let card = null;
    for (const sel of cardSelectors) {
      const loc = page.locator(sel).first();
      if ((await loc.count()) > 0) {
        card = loc;
        break;
      }
    }

    if (card) {
      const commentarySelectors = [
        '[data-test-id="main-feed-activity-card__commentary"]',
        '.feed-shared-inline-show-more-text',
        '.feed-shared-text span[dir="ltr"]',
        '[dir="ltr"]',
      ];
      for (const sel of commentarySelectors) {
        try {
          const el = card.locator(sel).first();
          if ((await el.count()) > 0) {
            const t = await el.innerText();
            if (t && t.length > 20) {
              out.postText = (out.postText ? out.postText + '\n' : '') + t;
              break;
            }
          }
        } catch {}
      }
      if (!out.postText) {
        const t = await card.innerText().catch(() => '');
        if (t && t.length > 20) out.postText = t.slice(0, 5000);
      }
    }
  } catch (e) {}

  // ---- 3) Author name and username from DOM (profile link href contains /in/username) ----
  if (!out.author) {
    const authorSelectors = [
      '.feed-shared-actor__name',
      '[data-test-id="feed-actor-name"]',
      'a.app-aware-link[href*="/in/"]',
      'h2 a',
      '.update-components-actor__name',
    ];
    for (const sel of authorSelectors) {
      try {
        const el = page.locator(sel).first();
        if ((await el.count()) > 0) {
          const name = await el.innerText();
          if (name && name.length < 100 && !name.includes('Sign in')) {
            out.author = name.trim();
            break;
          }
        }
      } catch {}
    }
  }
  // Author username from first profile link in the card (e.g. /in/usman-sayed-56884735b/)
  if (!out.authorUsername) {
    try {
      const profileHref = await page
        .locator('a[href*="linkedin.com/in/"]')
        .first()
        .getAttribute('href')
        .catch(() => null);
      if (profileHref) {
        const m = profileHref.match(/linkedin\.com\/in\/([^/?]+)/);
        if (m) out.authorUsername = m[1];
      }
    } catch {}
  }

  // ---- 4) Timestamp ----
  try {
    const timeEl = page.locator('time, [data-test-id="feed-timestamp"], .feed-shared-actor__sub-description, .update-components-actor__sub-description').first();
    if ((await timeEl.count()) > 0) {
      out.timestamp = (await timeEl.getAttribute('datetime')) || (await timeEl.innerText());
    }
  } catch {}

  // ---- 5) Social counts ----
  try {
    const socialSelectors = [
      '[data-test-id="social-actions"]',
      '.social-details-social-counts',
      '.social-details-social-actions',
      '.feed-shared-social-actions',
    ];
    for (const sel of socialSelectors) {
      const el = page.locator(sel).first();
      if ((await el.count()) > 0) {
        const text = await el.innerText().catch(() => '');
        const likeMatch = text.match(/(\d+)\s*(reaction|like)/i);
        const commentMatch = text.match(/(\d+)\s*comment/i);
        if (likeMatch) out.likes = likeMatch[1];
        if (commentMatch) out.comments = commentMatch[1];
        if (out.likes || out.comments) break;
      }
    }
    if (!out.likes) {
      const bodyText = await page.locator('body').innerText().catch(() => '');
      const numMatch = bodyText.match(/\b(\d+)\s*(?:Like|Comment|Share)/);
      if (numMatch) out.likes = numMatch[1];
    }
  } catch {}

  // ---- 6) Hashtags and mentions ----
  const text = out.postText || '';
  out.hashtags = [...(text.match(/#(\w+)/g) || [])].map((h) => h.slice(1));
  out.mentions = [...(text.match(/@(\w+)/g) || [])].map((m) => m.slice(1));

  // ---- 7) External links ----
  try {
    const links = await page.locator('a[href^="http"]').evaluateAll((as) =>
      as.map((a) => a.href).filter((h) => !h.includes('linkedin.com') && !h.includes('licdn.com'))
    );
    out.links = [...new Set(links)].slice(0, 20);
  } catch {
    out.links = [];
  }

  if (out.postText) out.postText = out.postText.trim().slice(0, 10000);
  return out;
}
