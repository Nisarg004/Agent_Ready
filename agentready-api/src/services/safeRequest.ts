import axios, { AxiosRequestConfig, AxiosResponse } from 'axios';
import { lookup } from 'dns/promises';
import { Agent as HttpAgent } from 'http';
import { Agent as HttpsAgent } from 'https';
import { isIP } from 'net';

const MAX_REDIRECTS = 5;

export function isPublicIp(ip: string): boolean {
  const v = ip.toLowerCase().replace(/^\[|\]$/g, '');
  if (v.startsWith('::ffff:')) return isPublicIp(v.slice(7));
  if (isIP(v) === 4) {
    const a = v.split('.').map(Number);
    const [x, y] = a;
    return !(x === 0 || x === 10 || x === 127 || x >= 224 ||
      x === 169 && y === 254 || x === 172 && y >= 16 && y <= 31 ||
      x === 192 && y === 168 || x === 100 && y >= 64 && y <= 127 ||
      x === 192 && y === 0 || x === 192 && y === 88 ||
      x === 198 && (y === 18 || y === 19 || y === 51 || y === 19) ||
      x === 203 && y === 0 || x >= 240);
  }
  if (isIP(v) !== 6) return false;
  // Only global unicast addresses; exclude local, multicast, reserved and documentation.
  const first = parseInt(v.split(':')[0] || '0', 16);
  return first >= 0x2000 && first < 0x4000 && !v.startsWith('2001:db8:');
}

export async function resolvePublicTarget(raw: string): Promise<{ url: URL; address: string; family: 4 | 6 }> {
  const url = new URL(raw);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      (url.port && !['80', '443'].includes(url.port))) {
    throw new Error('Unsafe outbound URL');
  }
  const host = url.hostname.replace(/\.$/, '').replace(/^\[|\]$/g, '');
  if (!host || host === 'localhost' || host.endsWith('.localhost') ||
      host.endsWith('.local') || host.endsWith('.internal')) throw new Error('Unsafe hostname');
  const answers = isIP(host) ? [{ address: host, family: isIP(host) }] : await lookup(host, { all: true, verbatim: true });
  if (!answers.length || answers.some(a => !isPublicIp(a.address))) throw new Error('Unsafe destination IP');
  const chosen = answers[0];
  return { url, address: chosen.address, family: chosen.family as 4 | 6 };
}

/** DNS is resolved and validated before each hop, then pinned for the actual socket. */
export async function safeGet<T = unknown>(raw: string, options: AxiosRequestConfig = {}): Promise<{ response: AxiosResponse<T>; finalUrl: string }> {
  let current = raw;
  for (let redirects = 0; redirects <= MAX_REDIRECTS; redirects++) {
    const target = await resolvePublicTarget(current);
    const pinnedLookup = (_hostname: string, _opts: unknown, cb: (err: NodeJS.ErrnoException | null, address: string, family: number) => void) =>
      cb(null, target.address, target.family);
    const response = await axios.get<T>(target.url.toString(), {
      ...options,
      httpAgent: new HttpAgent({ lookup: pinnedLookup }),
      httpsAgent: new HttpsAgent({ lookup: pinnedLookup }),
      proxy: false,
      maxRedirects: 0,
      validateStatus: () => true,
    });
    if (![301, 302, 303, 307, 308].includes(response.status) || !response.headers.location) {
      return { response, finalUrl: target.url.toString() };
    }
    (response.data as { destroy?: () => void })?.destroy?.();
    if (redirects === MAX_REDIRECTS) throw new Error('Too many redirects');
    current = new URL(response.headers.location, target.url).toString();
  }
  throw new Error('Too many redirects');
}
