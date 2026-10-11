"""Provider execution adapters. Thin, delegating, provenance-recording.

Each adapter wraps exactly one registered provider. Adapters never install
or download: missing dependencies surface as TOOL_UNAVAILABLE with reason.
"""
