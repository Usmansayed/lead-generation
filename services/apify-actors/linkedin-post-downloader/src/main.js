/**
 * LinkedIn Post Downloader (Apify Actor)
 *
 * Uses Crawlee + PlaywrightCrawler: open post → wait for JS → capture network
 * (media.licdn.com, .mp4, .m3u8) → extract metadata from DOM → output URLs + metadata.
 *
 * Input: { "urls": ["https://www.linkedin.com/posts/..."] }
 * Output: dataset items with postUrl, metadata (postText, author, ...), videoUrls, bestVideoUrl
 */

import { Actor } from 'apify';
import { PlaywrightCrawler } from 'crawlee';
import { getMediaType, pickBestVideoUrl } from './utils/mediaExtractor.js';
import { extractMetadataFromPage } from './utils/metadataParser.js';

await Actor.init();

const input = await Actor.getInput();
const urls = input?.urls ?? [];
if (!Array.isArray(urls) || urls.length === 0) {
  await Actor.fail('Input must contain "urls" (array of LinkedIn post URLs).');
}

const crawler = new PlaywrightCrawler({
  maxRequestsPerCrawl: urls.length,
  maxRequestRetries: 3,
  requestHandlerTimeoutSecs: 90,
  navigationTimeoutSecs: 60000,
  launchContext: {
    launchOptions: {
      headless: true,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
      ],
    },
  },
  requestHandler: async ({ request, page, pushData, log }) => {
    const postUrl = request.url;
    log.info(`Processing: ${postUrl}`);

    const capturedVideo = [];
    const capturedImage = [];

    const onResponse = (response) => {
      try {
        const url = response.url();
        const contentType = (response.headers() || {})['content-type'] || '';
        const { isVideo, isImage } = getMediaType(url, contentType);
        if (isVideo && !capturedVideo.some((c) => c.url === url)) {
          capturedVideo.push({ url, contentType });
          log.debug(`Captured video: ${url.slice(0, 80)}...`);
        }
        if (isImage && !capturedImage.some((c) => c === url)) {
          capturedImage.push(url);
          log.debug(`Captured image: ${url.slice(0, 80)}...`);
        }
      } catch (e) {
        log.debug('Response handler error', e);
      }
    };

    page.on('response', onResponse);

    await page.goto(postUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(8000);

    const metadata = await extractMetadataFromPage(page, { postUrl });
    const videoUrls = capturedVideo.map((c) => c.url);
    const imageUrls = [...new Set(capturedImage)];
    const bestVideoUrl = pickBestVideoUrl(capturedVideo);

    await pushData({
      postUrl,
      metadata: {
        postText: metadata.postText,
        author: metadata.author,
        authorUsername: metadata.authorUsername ?? null,
        timestamp: metadata.timestamp,
        likes: metadata.likes,
        comments: metadata.comments,
        hashtags: metadata.hashtags,
        mentions: metadata.mentions,
        links: metadata.links,
      },
      videoUrls,
      imageUrls,
      bestVideoUrl: bestVideoUrl || null,
    });

    log.info(`Done: ${postUrl}, videos: ${videoUrls.length}, images: ${imageUrls.length}, bestVideo: ${bestVideoUrl ? 'yes' : 'no'}`);
  },
});

await crawler.run(urls.map((url) => ({ url: url.trim() })));

await Actor.exit();
