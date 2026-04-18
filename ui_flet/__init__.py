"""Flet UI package for Tezis — 3 screens + 6 training workspaces.

Entry point: `python -m ui_flet.main`.

Scope (per 2026-04-19 design freeze in
docs/superpowers/specs/2026-04-18-flet-migration-design.md):
- 3 views: tickets, training, settings
- 6 workspaces: reading, plan, cloze, active-recall, state-exam-full, review
- Frozen interface: AppFacade / ui_data dataclasses / domain / db.schema
"""

__all__ = ["main"]
