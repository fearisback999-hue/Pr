"""Part 4 — Customer Psychology. For each candidate, an LLM pass over top comments and
reviews extracts the single psychological reason the product moves. That paragraph
becomes the spine of every creative brief. Products with one clear trigger convert
harder than products with five vague ones."""

from .analyzer import PsychProfile, analyze, emotion_signal

__all__ = ["PsychProfile", "analyze", "emotion_signal"]
