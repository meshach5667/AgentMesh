import { securityHeaders } from '../securityHeaders';

const header = (headers: { key: string; value: string }[], key: string) => headers.find((h) => h.key === key)?.value ?? '';

describe('dashboard security headers', () => {
  const prod = securityHeaders('https://api.example.com/api/v1', false);
  const csp = header(prod, 'Content-Security-Policy');

  it('lets the page talk only to itself and the API', () => {
    expect(csp).toContain("connect-src 'self' https://api.example.com;");
    expect(csp).not.toMatch(/connect-src[^;]*\*/);
  });

  it('forbids framing, plugins, base rewriting and eval in production', () => {
    for (const directive of ["frame-ancestors 'none'", "object-src 'none'", "base-uri 'self'", "default-src 'self'"]) {
      expect(csp).toContain(directive);
    }
    expect(csp).not.toContain('unsafe-eval');
    expect(header(prod, 'X-Frame-Options')).toBe('DENY');
  });

  it('sends HSTS and nosniff', () => {
    expect(header(prod, 'Strict-Transport-Security')).toMatch(/max-age=31536000/);
    expect(header(prod, 'X-Content-Type-Options')).toBe('nosniff');
  });

  it('relaxes only what local development needs', () => {
    const dev = header(securityHeaders('http://localhost:8000/api/v1', true), 'Content-Security-Policy');
    expect(dev).toContain("'unsafe-eval'");
    expect(dev).not.toContain('upgrade-insecure-requests');
  });
});
