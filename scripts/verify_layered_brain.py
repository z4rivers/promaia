
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from promaia.brain.context_assembly import assemble_brain_context, get_personality_prompt
from promaia.storage.db_factory import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verification")

async def test_silo_isolation():
    logger.info("TEST 1: Silo Isolation (Heatpup domain)")
    # Using a fake chat_id to ensure NO history pollution
    context = await assemble_brain_context(
        user_message="Tell me about the heatpup metaphors.",
        chat_id=9999999, 
        active_domain="heatpup",
        token_budget=1000
    )
    
    # We look for project context blocks specifically
    has_heatpup_proj = "Heatpup:" in context
    # Promaia is the assistant's name, so it will always be in the profile.
    # We check for the Promaia project specifically
    has_promaia_proj = "Promaia: Active development" in context
    
    logger.info(f"  Has Heatpup Project: {has_heatpup_proj}")
    logger.info(f"  Has Promaia Project Leak: {has_promaia_proj}")
    
    # Check for memories
    # The only heatpup memory starts with "[ASIDE] Reference to 'Heatpup'"
    has_heatpup_mem = "Reference to 'Heatpup'" in context
    # A common promaia memory snippet
    has_promaia_mem = "zBrain Phases" in context
    
    logger.info(f"  Has Heatpup Memory: {has_heatpup_mem}")
    logger.info(f"  Has Promaia Memory Leak: {has_promaia_mem}")

    if has_heatpup_proj and not has_promaia_proj and not has_promaia_mem:
        logger.info("  PASS: Silo isolated correctly.")
    else:
        logger.error("  FAIL: Silo isolation failed.")

async def test_ignorance_protocol():
    logger.info("TEST 2: Ignorance Protocol Trigger")
    # Query a domain that definitely has 0 memories/projects
    # We use a LOW budget to force truncation and see if guardrail survives
    context = await assemble_brain_context(
        user_message="What is the status of the antigravity drive?",
        chat_id=9999999,
        active_domain="antigravity",
        token_budget=200
    )
    
    has_guardrail = "CRITICAL: MuninnDB returned ZERO results" in context
    logger.info(f"  Guardrail instruction present: {has_guardrail}")
    
    if has_guardrail:
        logger.info("  PASS: Ignorance protocol triggered.")
    else:
        logger.error(f"  FAIL: Ignorance protocol not found (Length: {len(context)})")
        logger.info(f"Context Head: {context[:200]}...")
        logger.info(f"Context Tail: {context[-200:]}")

async def test_dynamic_prompting():
    logger.info("TEST 3: Dynamic Personality Prompts")
    open_prompt = get_personality_prompt(None)
    silo_prompt = get_personality_prompt("promaia")
    
    is_open_rich = "OPEN MODE ACTIVATED" in open_prompt
    is_silo_focused = "SILO MODE ACTIVATED" in silo_prompt and "promaia" in silo_prompt
    
    logger.info(f"  Open prompt correct: {is_open_rich}")
    logger.info(f"  Silo prompt correct: {is_silo_focused}")
    
    if is_open_rich and is_silo_focused:
        logger.info("  PASS: Dynamic prompts correctly generated.")
    else:
        logger.error("  FAIL: Dynamic prompts incorrect.")

async def test_domain_aliasing():
    logger.info("TEST 4: Domain Aliasing")
    # 'zbrain' should map to 'promaia'
    from promaia.brain.context_assembly import normalize_domain
    normalized = normalize_domain("zbrain")
    logger.info(f"  'zbrain' normalized to: {normalized}")
    
    if normalized == "promaia":
        logger.info("  PASS: Aliasing works.")
    else:
        logger.error("  FAIL: Aliasing failed.")

async def run_all_tests():
    await test_domain_aliasing()
    await test_dynamic_prompting()
    await test_silo_isolation()
    await test_ignorance_protocol()

if __name__ == "__main__":
    asyncio.run(run_all_tests())
