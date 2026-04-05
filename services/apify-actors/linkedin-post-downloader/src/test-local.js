/**
 * Local test: run the LinkedIn crawler with the example URL and print result.
 * No Apify dependency. Run: node src/test-local.js
 */

import { PlaywrightCrawler } from 'crawlee';
import { getMediaType, pickBestVideoUrl } from './utils/mediaExtractor.js';
import { extractMetadataFromPage } from './utils/metadataParser.js';

const EXAMPLE_URL =
  'https://www.linkedin.com/posts/usman-sayed-56884735b_big-lesson-from-the-claude-code-security-share-7432040278024286208-pbhV?utm_source=share&utm_medium=member_desktop&rcm=ACoAAFmlxmABgWPPqw3U5gwmO_XaPWU03D9B3CQ';

const results = [];

const crawler = new PlaywrightCrawler({
  maxRequestsPerCrawl: 1,
  maxRequestRetries: 2,
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
  requestHandler: async ({ request, page, log }) => {
    const postUrl = request.url;
    log.info('Processing: ' + postUrl);

    const capturedVideo = [];
    const capturedImage = [];
    const onResponse = (response) => {
      try {
        const url = response.url();
        const contentType = (response.headers() || {})['content-type'] || '';
        const { isVideo, isImage } = getMediaType(url, contentType);
        if (isVideo && !capturedVideo.some((c) => c.url === url)) capturedVideo.push({ url, contentType });
        if (isImage && !capturedImage.includes(url)) capturedImage.push(url);
      } catch (e) {}
    };
    page.on('response', onResponse);

    await page.goto(postUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
    await page.waitForTimeout(5000);

    const metadata = await extractMetadataFromPage(page, { postUrl });
    const videoUrls = capturedVideo.map((c) => c.url);
    const imageUrls = [...new Set(capturedImage)];
    const bestVideoUrl = pickBestVideoUrl(capturedVideo);

    results.push({
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
    log.info(
      'Done. Author: ' + (metadata.author || 'n/a') +
      ', username: ' + (metadata.authorUsername || 'n/a') +
      ', videos: ' + videoUrls.length +
      ', images: ' + imageUrls.length
    );
  },
});

await crawler.run([{ url: EXAMPLE_URL }]);

console.log(JSON.stringify(results, null, 2));
