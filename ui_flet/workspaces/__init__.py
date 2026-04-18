"""Training mode workspaces — one per mode_key.

Dispatch table is in views/training_view.py; each workspace module exposes
`build_workspace(state, ticket_id) -> ft.Control`.
"""
