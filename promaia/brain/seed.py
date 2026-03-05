"""
zBrain seed data — populates brain.domains and brain.contexts with initial data.

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING for domains and
INSERT ... ON CONFLICT (domain_id) DO NOTHING for contexts.

Usage:
    python -m promaia.brain.seed
"""
import logging
import sys

from promaia.storage.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

DOMAINS = [
    {
        "name": "Heatpup",
        "is_project": True,
        "description": "Heat pump comparison tool — Portland market",
    },
    {
        "name": "HVAC Brand",
        "is_project": True,
        "description": "Portland Area Heat Pump Expert — independent marketing brand",
    },
    {
        "name": "PURRfoot",
        "is_project": True,
        "description": "Cat fort pillow / foot comfort product",
    },
    {
        "name": "Promaia",
        "is_project": True,
        "description": "Content management + agent platform — daughter's project",
    },
    {
        "name": "zBrain",
        "is_project": True,
        "description": "Personal AI OS built on Promaia",
    },
    {
        "name": "Catpool",
        "is_project": False,
        "description": "Shared resource between Maybecat and Hopecookie",
    },
    {
        "name": "Hopecookie",
        "is_project": True,
        "description": "Public project",
    },
    {
        "name": "Maybecat",
        "is_project": True,
        "description": "Ask cats for questionable answers — public",
    },
    {
        "name": "HVAC Work",
        "is_project": False,
        "description": "Climate Control Inc day job — HVAC sales",
    },
    {
        "name": "Personal",
        "is_project": False,
        "description": "Personal life, family, health, finances",
    },
]

# Contexts are keyed by domain name (project domains only)
CONTEXTS = [
    {
        "domain_name": "Heatpup",
        "directive": "Working public calculator. Research competitor features and Portland energy rates.",
        "stale_threshold_days": 7,
        "priority": 3,
    },
    {
        "domain_name": "HVAC Brand",
        "directive": "Build independent Portland marketing presence. Draft social posts and track rebate updates.",
        "stale_threshold_days": 14,
        "priority": 4,
    },
    {
        "domain_name": "PURRfoot",
        "directive": "On hold. Research only — packaging materials and suppliers.",
        "stale_threshold_days": 30,
        "priority": 8,
    },
    {
        "domain_name": "Promaia",
        "directive": "Branch & contribute back. Document changes in ZBRAIN.md.",
        "stale_threshold_days": 7,
        "priority": 2,
    },
    {
        "domain_name": "zBrain",
        "directive": "Build brain layer. Current phase: schema + MCP tools.",
        "stale_threshold_days": 3,
        "priority": 1,
    },
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_domains(db) -> dict[str, int]:
    """Insert domains, return dict of {name: id}."""
    domain_ids: dict[str, int] = {}

    for domain in DOMAINS:
        # Upsert-style: insert if not exists, then fetch id
        db.execute(
            """
            INSERT INTO brain.domains (name, is_project, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            (domain["name"], domain["is_project"], domain["description"]),
        )
        row = db.fetch_one(
            "SELECT id FROM brain.domains WHERE name = %s",
            (domain["name"],),
        )
        if row:
            domain_ids[domain["name"]] = row["id"]
            logger.info(f"Domain seeded: {domain['name']} (id={row['id']})")

    return domain_ids


def seed_contexts(db, domain_ids: dict[str, int]) -> int:
    """Insert contexts for project domains. Returns count inserted."""
    inserted = 0

    for ctx in CONTEXTS:
        domain_name = ctx["domain_name"]
        domain_id = domain_ids.get(domain_name)

        if domain_id is None:
            logger.warning(f"Domain not found for context: {domain_name} — skipping")
            continue

        # Check if context already exists for this domain
        existing = db.fetch_one(
            "SELECT id FROM brain.contexts WHERE domain_id = %s",
            (domain_id,),
        )
        if existing:
            logger.info(f"Context already exists for {domain_name} — skipping")
            continue

        db.execute(
            """
            INSERT INTO brain.contexts (domain_id, directive, stale_threshold_days, priority)
            VALUES (%s, %s, %s, %s)
            """,
            (domain_id, ctx["directive"], ctx["stale_threshold_days"], ctx["priority"]),
        )
        logger.info(f"Context seeded: {domain_name} (priority={ctx['priority']})")
        inserted += 1

    return inserted


def main():
    """Run seed data population."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )

    logger.info("Starting zBrain seed data population...")
    db = get_postgres_db()

    # Seed domains
    logger.info(f"Seeding {len(DOMAINS)} domains...")
    domain_ids = seed_domains(db)
    logger.info(f"Domains complete: {len(domain_ids)} total in brain.domains")

    # Seed contexts
    logger.info(f"Seeding {len(CONTEXTS)} contexts...")
    inserted = seed_contexts(db, domain_ids)
    logger.info(f"Contexts complete: {inserted} new, {len(CONTEXTS) - inserted} already existed")

    print(f"Seed complete: {len(domain_ids)} domains, {inserted} new contexts")


if __name__ == "__main__":
    main()
