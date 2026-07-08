"""The local dashboard — everything on one site: board, per-product scorecards with
next steps, advertising/creative pipeline status, budgeting (capital + Etsy POD), and
creator marketplaces. Stdlib only; read-only against the DB."""

from .server import make_server, run

__all__ = ["make_server", "run"]
