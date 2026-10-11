"""Production tool registry + capability router + provider adapters.

Design: capabilities first, providers second. The Director requests a
CAPABILITY; the router scores registered providers against the request
(capability fit, code control, local execution, hardware fit,
determinism, license) and records the decision. Substitution is never
silent: without explicit ``allow_fallback``, an unavailable provider
yields TOOL_UNAVAILABLE / HARDWARE_BLOCKED / LICENSE_BLOCKED.
"""
