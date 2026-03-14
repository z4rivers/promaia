import asyncio
import logging
from promaia.storage.db_factory import get_db
from promaia.brain.muninn import get_muninn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_muninn")


async def seed_muninn():
    muninn = await get_muninn()
    if not muninn:
        logger.error("Failed to connect to MuninnDB.")
        return

    db = get_db()
    engrams = []

    # 1. Fetch Profile
    logger.info("Fetching profile...")
    try:
        profile_rows = db.fetch_all("SELECT category, field, value, confidence FROM brain.profile WHERE confidence > 0.4")
        logger.info(f"Found {len(profile_rows)} profile traits")
        for r in profile_rows:
            engrams.append({
                "concept": f"profile {r['category']}: {r['field']}",
                "content": str(r['value']),
                "tags": ["profile", r['category']],
                "confidence": float(r['confidence'])
            })
    except Exception as e:
        logger.error(f"Failed to fetch profile: {e}")

    # 2. Fetch Projects / Contexts
    logger.info("Fetching active projects...")
    try:
        projects = db.fetch_all(
            """
            SELECT d.name, d.description, c.current_state, c.directive
            FROM brain.contexts c
            JOIN brain.domains d ON c.domain_id = d.id
            """ # get all domains with contexts
        )
        logger.info(f"Found {len(projects)} domains/projects")
        for p in projects:
            summary = p["name"]
            if p.get("description"):
                summary += f": {p['description']}"
            if p.get("current_state"):
                summary += f"\nCurrent state: {p['current_state']}"
            if p.get("directive"):
                summary += f"\nDirective: {p['directive']}"

            engrams.append({
                "concept": f"project: {p['name']}",
                "content": summary,
                "tags": ["project", "domain"],
                "confidence": 0.95
            })
    except Exception as e:
        logger.error(f"Failed to fetch projects: {e}")

    # Seed core zbrain identity
    engrams.append({
        "concept": "system identity",
        "content": "You are Promaia, Zack's second brain. You are a conversational mirror and sounding board. Short sentences. Direct. Match his energy: brief when brief, detailed when exploring. Humor sharp and committed. Validate before solving.",
        "tags": ["system", "identity", "zbrain"],
        "confidence": 1.0
    })

    if not engrams:
        logger.warning("No engrams to seed.")
        return

    logger.info(f"Pushing {len(engrams)} engrams to MuninnDB zbrain-vault...")
    results = await muninn.write_batch(engrams)
    
    successes = [r for r in results if r.get("status") == "ok"]
    logger.info(f"Successfully seeded {len(successes)} / {len(engrams)} engrams.")
    
    await muninn.close()

if __name__ == "__main__":
    asyncio.run(seed_muninn())
