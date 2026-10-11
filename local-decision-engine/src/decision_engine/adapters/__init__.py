"""Adapters: optional accelerators for existing projects.

Each adapter wraps DecisionEngine with project-shaped helpers. All adapters
are OFF by default (enabled=False) and degrade to 'review / keep existing
logic' when the engine is unreachable — they never stop the caller.
"""
