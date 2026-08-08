# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in eovpanel, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, email the maintainers directly:

- **Email:** [your-security-email@example.com] _(replace with actual contact)_
- **Subject line:** `[SECURITY] eovpanel — brief description`

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to expect

- **Acknowledgement** within 48 hours
- **Initial assessment** within 1 week
- **Fix or mitigation** released as a patch version if the issue is confirmed
- Credit in the release notes (unless you prefer anonymity)

## Scope

The following are in scope:

- Authentication/authorization bypasses
- Remote code execution
- SQL injection or other injection attacks
- Path traversal leading to file disclosure
- Privilege escalation (e.g., non-sudo admin accessing sudo-only endpoints)
- Subscription token leakage or prediction
- Docker/container escape

The following are out of scope:

- Denial of service (rate limiting is in place)
- Social engineering
- Issues in third-party dependencies (report upstream)

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Security Hardening (as of v0.1.0)

- Login rate limiting: 5 failed attempts per minute per IP
- Username validation: restricted to `[a-zA-Z0-9_-]`, max 64 characters
- CSP headers: `Content-Security-Policy`, `Referrer-Policy`, `Permissions-Policy`
- Subscription tokens: 32-byte random URL-safe tokens, not exposed in admin API responses
- Admin isolation: non-sudo admins can only access their own users (enforced server-side)
- Passwords: never returned in API responses (excluded from Pydantic schemas)
- Job locks: `threading.Lock` guards on background jobs prevent concurrent execution
