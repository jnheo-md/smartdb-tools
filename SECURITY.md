# Security Policy

## Architecture

SmartDB Tools (YSR3 CLI and MCP Server) connect to the YSR3 API server over **HTTPS only**. There is no direct database access from client tools.

- **Authentication**: JWT-based. Tokens are stored locally at `~/.ysr3/session.json` with `0600` permissions.
- **Session files**: Written atomically (write to `.tmp` then rename) to prevent partial reads.
- **Role-based access**: The API server enforces user-level permissions. Manager and Super Admin roles have additional capabilities.
- **No secrets in repo**: This repository contains no API keys, database credentials, or `.env` files.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue.
2. Email **security@smartstroke.net** with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
3. You will receive an acknowledgment within 48 hours.
4. We aim to release a fix within 7 days of confirmation.

## Security Measures

- All API communication uses HTTPS (TLS 1.2+)
- Session tokens expire after 24 hours
- Session files use restrictive file permissions (`0600`)
- Filenames from server responses are sanitized to prevent path traversal
- SQL queries via the API are restricted to read-only operations
- No direct database credentials are ever stored on the client
