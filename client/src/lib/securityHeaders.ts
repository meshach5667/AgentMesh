/** HTTP security headers for every dashboard response (wired in next.config.ts).
 *
 * The CSP's main job is containment: even if markup were injected, the page could load scripts only from this
 * origin, could send data (such as stored tokens) only to this origin and the AgentMesh API, could not be framed, and
 * could not load plugins or rewrite the base URL. Scripts still allow 'unsafe-inline' because Next.js and the
 * theme bootstrap emit inline scripts; nonce-based CSP would need every page rendered per request. */
export function securityHeaders(apiUrl: string, dev: boolean): { key: string; value: string }[] {
  const apiOrigin = new URL(apiUrl).origin;
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ''}`,
    "style-src 'self' 'unsafe-inline'",
    // Sponsor logos are https URLs chosen by operators; data: covers inline SVG/PNG icons.
    "img-src 'self' data: https:",
    "font-src 'self' data:",
    `connect-src 'self' ${apiOrigin}${dev ? ' ws: http://localhost:* http://127.0.0.1:*' : ''}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    // Sign-in posts to the API with fetch; provider payment links are plain navigations to external sites.
    "form-action 'self'",
    ...(dev ? [] : ['upgrade-insecure-requests']),
  ].join('; ');
  return [
    { key: 'Content-Security-Policy', value: csp },
    { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'X-Frame-Options', value: 'DENY' },
    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
    { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
  ];
}
