"""
Brain channels — automated data ingestion for profile building.

Channels passively observe existing digital artifacts (git repos, email, files)
to build profile depth without requiring the user to answer questions.
This implements the "observe first, ask second" principle.

Available channels:
    pc_scan     — Local filesystem, git history, installed apps
    gmail_read  — Gmail inbox contacts, patterns, topics
"""
