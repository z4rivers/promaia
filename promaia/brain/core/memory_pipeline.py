"""
Unified Capture Pipeline

Provides the core logic for capturing a memory, extracting intelligence, and writing to Postgres and MuninnDB.
Used by both the MCP server and the realtime Voice Agent.
"""
import json
import logging
import numpy as np
from typing import Optional, Dict, Any

from pgvector.psycopg2 import register_vector
from promaia.storage.postgres_db import PostgresDB
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.extraction import extract_actions, extract_insights
from promaia.brain.muninn import get_muninn

logger = logging.getLogger(__name__)

def _get_or_create_domain_id(db: PostgresDB, domain_name: str) -> int:
    """Return the domain.id for domain_name, creating it if absent."""
    existing = db.fetch_one(
        "SELECT id FROM brain.domains WHERE name = %s",
        (domain_name,),
    )
    if existing:
        return existing['id']

    return db.insert_returning(
        "INSERT INTO brain.domains (name) VALUES (%s) RETURNING id",
        (domain_name,),
    )


async def capture_memory(
    db: PostgresDB,
    vector_mgr: VectorDBManager,
    content: str,
    session_id: str,
    domain_name: Optional[str] = None,
    confidence: float = 0.9,
    image_paths: Optional[List[str]] = None,
    audio_paths: Optional[List[str]] = None,
    document_paths: Optional[List[str]] = None,
    source: str = "capture",
) -> Dict[str, Any]:
    """
    Insert memory, generate embedding, extract actions + conversation intelligence.
    Dual-writes to MuninnDB.
    
    Returns a dict with extraction metrics:
    {
        "memory_id": int,
        "action_count": int,
        "intel_counts": {"decisions": int, "insights": int, "preferences": int, "asides": int}
    }
    """
    content = content.strip()
    if not content:
        raise ValueError("content is required")

    import json
    assets_combined = []
    if image_paths:
        assets_combined.extend(image_paths)
    if audio_paths:
        assets_combined.extend(audio_paths)
    if document_paths:
        assets_combined.extend(document_paths)
    
    asset_paths_json = json.dumps(assets_combined)

    # 1. Insert memory row (without embedding first)
    memory_id = db.insert_returning(
        """
        INSERT INTO brain.memories (content, domain, source, source_id, asset_paths)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (content, domain_name, source, session_id, asset_paths_json),
    )

    # 2. Generate embedding and update row
    try:
        if assets_combined:
            embedding = vector_mgr.generate_multimodal_embedding(
                text=content, 
                image_paths=image_paths, 
                audio_paths=audio_paths,
                document_paths=document_paths
            )
        else:
            embedding = vector_mgr.generate_embedding(content)
            
        embedding_array = np.array(embedding)
        with db.get_connection() as conn:
            from pgvector.psycopg2 import register_vector
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE brain.memories SET embedding = %s WHERE id = %s",
                    (embedding_array, memory_id),
                )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Embedding generation failed for memory {memory_id}: {e}")
        # Non-fatal — memory is stored, just without embedding

    # 3. Extract actions
    action_count = 0
    try:
        extraction_result = extract_actions(content)
        if extraction_result.has_actions:
            domain_id = _get_or_create_domain_id(db, domain_name) if domain_name else None
            for action in extraction_result.actions:
                db.execute(
                    """
                    INSERT INTO brain.actions (memory_id, domain_id, description)
                    VALUES (%s, %s, %s)
                    """,
                    (memory_id, domain_id, action.description),
                )
            action_count = len(extraction_result.actions)
    except Exception as e:
        logger.warning(f"Action extraction/insert failed: {e}")

    # 4. Conversation Intelligence extraction (the "Along For The Ride" engine)
    intel_counts = {"decisions": 0, "insights": 0, "preferences": 0, "asides": 0}
    try:
        intel = extract_insights(content)
        if intel.has_intelligence:
            sub_captures = []

            for d in intel.decisions:
                sub_captures.append((
                    f"[DECISION] {d.description}",
                    d.domain or domain_name,
                    ["decision", str(d.confidence)],
                ))
            intel_counts["decisions"] = len(intel.decisions)

            for i in intel.insights:
                sub_captures.append((
                    f"[INSIGHT] {i.description}",
                    i.domain or domain_name,
                    ["insight", i.category],
                ))
            intel_counts["insights"] = len(intel.insights)

            for p in intel.preferences:
                sub_captures.append((
                    f"[PREFERENCE] {p.description}",
                    domain_name,
                    ["preference", p.profile_category or "general"],
                ))
            intel_counts["preferences"] = len(intel.preferences)

            for a in intel.asides:
                sub_captures.append((
                    f"[ASIDE] {a.description}",
                    a.domain or domain_name,
                    ["aside"],
                ))
            intel_counts["asides"] = len(intel.asides)

            # Write sub-captures to Postgres + MuninnDB
            for sub_content, sub_domain, sub_tags in sub_captures:
                try:
                    sub_id = db.insert_returning(
                        """
                        INSERT INTO brain.memories (content, domain, source, source_id)
                        VALUES (%s, %s, 'intelligence', %s)
                        RETURNING id
                        """,
                        (sub_content, sub_domain, session_id),
                    )
                    try:
                        sub_embedding = vector_mgr.generate_embedding(sub_content)
                        sub_array = np.array(sub_embedding)
                        with db.get_connection() as conn:
                            register_vector(conn)
                            with conn.cursor() as cur:
                                cur.execute(
                                    "UPDATE brain.memories SET embedding = %s WHERE id = %s",
                                    (sub_array, sub_id),
                                )
                    except Exception:
                        pass

                    # MuninnDB write for sub-capture
                    try:
                        muninn = await get_muninn()
                        if muninn:
                            # Pass confidence down, defaulting to higher for sub-captures if needed
                            await muninn.write(
                                concept=sub_content[:100],
                                content=sub_content,
                                tags=([sub_domain] if sub_domain else []) + sub_tags,
                                confidence=confidence
                            )
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"Sub-capture insert failed: {e}")
    except Exception as e:
        logger.warning(f"Intelligence extraction failed (non-fatal): {e}")

    # 5. Log capture event
    try:
        db.execute(
            """
            INSERT INTO brain.events (type, payload, source, session_id)
            VALUES ('capture', %s::jsonb, %s, %s)
            """,
            (json.dumps({
                "memory_id": memory_id,
                "action_count": action_count,
                "intelligence": intel_counts,
            }), source, session_id),
        )
    except Exception as e:
        logger.warning(f"Could not log capture event: {e}")

    # 6. MuninnDB dual-write for primary memory
    try:
        muninn = await get_muninn()
        if muninn:
            tags = [domain_name] if domain_name else []
            await muninn.write(
                concept=content[:100],
                content=content,
                tags=tags,
                confidence=confidence
            )
    except Exception as e:
        logger.warning(f"MuninnDB write failed (non-fatal): {e}")

    return {
        "memory_id": memory_id,
        "action_count": action_count,
        "intel_counts": intel_counts
    }
