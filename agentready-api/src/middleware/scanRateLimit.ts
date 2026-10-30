import { timingSafeEqual, createHash } from 'crypto';
import { Request } from 'express';
import rateLimit from 'express-rate-limit';
import { config } from '../config';

/** True when the request carries our own agent's key (see config.scanner.agentApiKey). */
function isTrustedAgent(req: Request): boolean {
  const expected = config.scanner.agentApiKey;
  const given = req.get('x-agent-key');
  if (!expected || !given) return false;
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

/**
 * Spec section 7 said 5 scans per IP per hour; raised to 25 by default (override with SCAN_RATE_LIMIT_PER_HOUR).
 *
 * Shared between POST /api/scan and POST /api/scan/:id/compare so a visitor
 * cannot get an extra crawl for free by routing it through the comparison
 * endpoint.
 *
 * Cached responses still count against the allowance, which is a known
 * unfairness: a visitor who gets a cached result and then presses "Scan again
 * now" spends two of their ten for one actual crawl. It is left alone
 * deliberately — this middleware runs *before* the handler, so at the moment it
 * decides, nobody knows yet whether the result will come from cache. Fixing it
 * needs the counter decremented after the fact, which is a bigger change than
 * the bug it corrects.
 */
export const scanRateLimit = rateLimit({
  windowMs: 60 * 60 * 1000,
  limit: config.scanner.rateLimitPerHour,
  skip: isTrustedAgent,
  // Untrusted forwarding headers are intentionally ignored by Express.
  validate: { xForwardedForHeader: false },
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    success: false,
    error: `You have reached the limit of ${config.scanner.rateLimitPerHour} scans per hour. Try again a little later, or message us and we will run it for you.`,
  },
});

export default scanRateLimit;

// No trusted-agent exemption: report email endpoints are never unlimited.
export const unlockRateLimit = rateLimit({
  windowMs: 60 * 60 * 1000, limit: 5, validate: { xForwardedForHeader: false }, standardHeaders: true, legacyHeaders: false,
  message: { success: false, error: 'Report delivery limit reached. Try again later.' },
});
export const recipientRateLimit = rateLimit({
  windowMs: 60 * 60 * 1000, limit: 3, standardHeaders: true, legacyHeaders: false,
  keyGenerator: (req: Request) => createHash('sha256').update(String(req.body?.email || '').trim().toLowerCase()).digest('hex'),
  message: { success: false, error: 'Report delivery limit reached. Try again later.' },
});
