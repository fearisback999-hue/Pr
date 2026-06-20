"""Opportunity report + attack packets. The engine does not stop at a score — for each
survivor it emits the full attack packet (economics, psychology spine, supplier pick,
creative kit, distribution + validation plan), because the product is only ~30% of the
outcome (Part 0, truth #2)."""

from .opportunity import AttackPacket, OpportunityReport, render_board, render_report

__all__ = ["AttackPacket", "OpportunityReport", "render_report", "render_board"]
