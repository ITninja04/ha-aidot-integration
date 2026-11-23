"""Makes custom_components importable from the repo root in tests.

Without it, the test plugin ships its own custom_components package, and
which one Python finds first depends on test order. Home Assistant ignores
this file when installing.
"""
