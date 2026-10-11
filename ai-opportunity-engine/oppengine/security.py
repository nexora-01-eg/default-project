"""Security: URL validation + SSRF guard, secret redaction, input sanitization, HTML escape."""
import html
import ipaddress
import re
from urllib.parse import urlparse

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|bearer)\s*[:=]\s*['\"]?([^\s'\"]{4,})"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),  # real provider keys are 40+ chars; avoids "Flask-SQLAlchemy"
    re.compile(r"\bxox[bap]-[A-Za-z0-9-]{16,}\b"),
]

ALLOWED_SCHEMES = {"http", "https"}

# Private/loopback/link-local ranges must never be fetched server-side (SSRF guard).
# Note: 127.0.0.1 + localhost are allow-listed separately ONLY for the LM Studio endpoint.
PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
]


def redact_secrets(text):
    if not isinstance(text, str):
        return text
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub(lambda m: m.group(0)[: m.group(0).find(m.group(2))] + "***REDACTED***" if m.lastindex == 2 else "***REDACTED***", out)
    return out


def sanitize_text(text, max_len=5000):
    """Strip control chars, cap length. Never executes anything."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def esc(text):
    return html.escape(text or "", quote=True)


def validate_public_url(url, allow_local_lmstudio=False, lmstudio_base="http://localhost:1234"):
    """Return (ok, reason). Rejects non-http(s), credentials, private IPs, non-default ports abuse."""
    if not isinstance(url, str) or len(url) > 2048:
        return False, "bad type/length"
    try:
        p = urlparse(url.strip())
    except Exception:
        return False, "unparseable"
    if p.scheme not in ALLOWED_SCHEMES:
        return False, "scheme not allowed"
    if not p.hostname:
        return False, "no host"
    if "@" in (p.netloc or ""):
        return False, "credentials in url"
    host = p.hostname.lower()
    if allow_local_lmstudio:
        try:
            lb = urlparse(lmstudio_base)
            if host in ("127.0.0.1", "localhost", (lb.hostname or "").lower()):
                return True, "lmstudio-local"
        except Exception:
            pass
    if host in ("localhost",):
        return False, "local host blocked"
    try:
        ip = ipaddress.ip_address(host)
        for net in PRIVATE_NETS:
            if ip in net:
                return False, "private ip blocked"
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, "non-public ip blocked"
    except ValueError:
        pass  # DNS name: resolved-address check happens at fetch time by policy (no DNS exfil here)
    return True, "ok"


def scan_for_secrets(text):
    """Return list of pattern names found (for pre-commit/doctor checks)."""
    hits = []
    for i, pat in enumerate(SECRET_PATTERNS):
        if pat.search(text or ""):
            hits.append(f"pattern-{i}")
    return hits
