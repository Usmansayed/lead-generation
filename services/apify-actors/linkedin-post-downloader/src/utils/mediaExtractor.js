/**
 * Detect LinkedIn media URLs from intercepted response URL and content-type.
 * Videos: media.licdn.com/dms/video, *.mp4, *.m3u8
 * Images: media.licdn.com (images), *.jpg, *.png, *.webp, image/*
 */

const VIDEO_PATTERNS = [
  (url) => url.includes('licdn.com/dms/video'),
  (url) => url.includes('media.licdn.com') && (url.includes('/video') || url.includes('.mp4') || url.includes('.m3u8')),
  (url) => /\.mp4(\?|$)/i.test(url),
  (url) => /\.m3u8(\?|$)/i.test(url),
  (url) => /\.webm(\?|$)/i.test(url),
];

const IMAGE_PATTERNS = [
  (url) => url.includes('media.licdn.com') && !url.includes('/video') && !url.includes('.mp4'),
  (url) => /\.(jpg|jpeg|png|webp|gif)(\?|$)/i.test(url),
];

const VIDEO_CT = [
  'video/mp4',
  'video/webm',
  'video/quicktime',
  'application/vnd.apple.mpegurl',
  'application/x-mpegurl',
];

const IMAGE_CT = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

/**
 * @param {string} url - Response URL
 * @param {string} [contentType] - Response Content-Type header
 * @returns {{ isVideo: boolean, isImage: boolean }}
 */
export function getMediaType(url, contentType = '') {
  if (!url || typeof url !== 'string') return { isVideo: false, isImage: false };
  const ct = (contentType || '').split(';')[0].trim().toLowerCase();
  const isVideo =
    (ct && VIDEO_CT.some((p) => ct.startsWith(p))) || VIDEO_PATTERNS.some((fn) => fn(url));
  const isImage =
    (ct && IMAGE_CT.some((p) => ct.startsWith(p))) || IMAGE_PATTERNS.some((fn) => fn(url));
  return { isVideo, isImage };
}

/** @deprecated Use getMediaType. True if video or image. */
export function isMediaResponse(url, contentType = '') {
  const { isVideo, isImage } = getMediaType(url, contentType);
  return isVideo || isImage;
}

/**
 * Prefer MP4 over HLS/m3u8 when we have multiple URLs.
 * @param {{ url: string, contentType?: string }[]} captured
 * @returns {string | null}
 */
export function pickBestVideoUrl(captured) {
  if (!captured || captured.length === 0) return null;
  const mp4 = captured.find(
    (c) => c.url.toLowerCase().includes('.mp4') || (c.contentType && c.contentType.toLowerCase().includes('video/mp4'))
  );
  return (mp4 || captured[0]).url;
}
