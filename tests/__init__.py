"""Test package.

Made a package so mypy's ``tests.*`` per-module override applies; the strict
settings that guard ``src`` would otherwise demand a ``-> None`` on every test.
"""
