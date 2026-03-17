
import os
import sys
from pathlib import Path

# Add project root to path so we can import promaia
sys.path.append(str(Path(__file__).parent.parent))

from promaia.storage.db_factory import get_db

def normalize_memories():
    db = get_db()
    
    # Define the mapping: Target Domain -> List of source tags to merge
    mapping = {
        'promaia': [
            'promaia', 'promaia_codebase', 'zbrain', 'zBrain', 'zbrain-dev', 'Zbrain platform',
            'promaia_multimodal', 'Promaia Architecture', 'Promaia Development', 
            'Promaia Project History', 'Promaia Project Identity', 'Promaia System', 
            'Promaia Vision', 'system_feedback', 'tech_radar', 'development', 
            'software_development', 'software engineering', 'Software Engineering',
            'technical_architecture', 'Technical Architecture', 'Architecture', 
            'Architecture/Database', 'Database Architecture', 'System Architecture',
            'system_architecture', 'Software Architecture', 'software_architecture',
            'AI Architecture', 'AI architecture', 'AI development', 'AI_development',
            'AI Architecture/Safety', 'AI Behavior', 'AI Model Behavior', 'AI behavior/prompting',
            'AI interaction', 'AI interaction guidelines', 'AI interaction performance',
            'AI interaction protocol', 'AI safety architecture', 'AI safety design philosophy',
            'AI_collaboration_framework', 'AI_performance', 'Agent Orchestration/Technical Architecture',
            'Dashboard Architecture', 'Data Management', 'Data Quality/AI Architecture',
            'Database Migration', 'database migration', 'Development', 'Development Strategy',
            'Development Workflow', 'development_workflow', 'Engineering/AI Development',
            'Engineering/Infrastructure', 'Engineering/Operations', 'Project Documentation',
            'Project Documentation Strategy', 'Project History', 'Project Management',
            'project_management', 'Project Philosophy', 'Software Development',
            'Software Development/AI Collaboration', 'Technical Debt/Codebase Audit',
            'Technical Project Management', 'UI/UX Design', 'UI/UX design', 'UX Design',
            'User Experience Design', 'User Experience/UI Design', 'UI/UX Development',
            'UI/UX', 'interface_design', 'product_design', 'Product/UI Design',
            'ai_collaboration', 'codebase_architecture', 'conversation-synthesis',
            'feature_development', 'logging', 'memory system architecture', 
            'multi-agent workflow', 'multi-model collaboration', 'system_behavior',
            'system_capability', 'system_design', 'system_integration', 'system_maintenance',
            'technical_troubleshooting', 'version_control', 'voice_session',
            'Workflow Optimization', 'workflow_management', 'Working', 'working'
        ],
        'personal': [
            'personal', 'Personal', 'Personal Identity', 'Personal Knowledge Management',
            'Personal Philosophy/Framework', 'Personal Productivity', 'Personal Tech/Troubleshooting',
            'Personal relationships/History', 'Personal/Character', 'Personal/Family',
            'Personal/Status', 'Relationships', 'relationships', 'Family/Project history',
            'Housing/Relationships', 'pet health', 'personal history', 'personal_history',
            'personal_life', 'personal_relationships', 'Zack Profile', 'identity',
            'Identity', 'personal_habits', 'personal_identity', 'lifestyle', 'etymology/culture',
            'Etymology/Culture', 'pet_health'
        ],
        'business': [
            'Entrepreneurship', 'Startup/Venture Capital', 'Startup', 'Finance', 'finance',
            'Market Positioning', 'Market Trends', 'market_analysis', 'economics/technology',
            'Strategic Product Development', 'Product Strategy', 'product_strategy',
            'Product Vision', 'product_vision', 'Product Development', 'product_development',
            'Product Philosophy', 'product_philosophy', 'Product Management', 'product_management',
            'Product Feature Request', 'feature_request'
        ],
        'hvac': ['hvac', 'HVAC'],
        'heatpup': ['heatpup', 'Heatpup'],
        'sedgwick': ['sedgwick', 'Sedgwick']
    }

    print("Starting memory domain normalization...")
    
    total_updated = 0
    
    for target, sources in mapping.items():
        # Build the SQL placeholders
        placeholders = ', '.join(['?'] * len(sources))
        
        # Count how many will be updated
        count_row = db.fetch_one(
            f"SELECT COUNT(*) as c FROM memories WHERE domain IN ({placeholders})",
            sources
        )
        count = count_row['c'] if count_row else 0
        
        if count > 0:
            print(f"Merging {count} memories into '{target}'...")
            db.execute(
                f"UPDATE memories SET domain = ? WHERE domain IN ({placeholders})",
                [target] + sources
            )
            total_updated += count

    # Handle remaining ones as 'general' if they aren't in the target list already
    all_targets = list(mapping.keys())
    target_placeholders = ', '.join(['?'] * len(all_targets))
    
    # Find anything that is NOT in the target domains list and NOT already normalized
    remaining_count_row = db.fetch_one(
        f"SELECT COUNT(*) as c FROM memories WHERE domain NOT IN ({target_placeholders}) OR domain IS NULL",
        all_targets
    )
    remaining_count = remaining_count_row['c'] if remaining_count_row else 0
    
    if remaining_count > 0:
        print(f"Moving {remaining_count} miscellaneous memories to 'general'...")
        db.execute(
            f"UPDATE memories SET domain = 'general' WHERE domain NOT IN ({target_placeholders}) OR domain IS NULL",
            all_targets
        )
        total_updated += remaining_count

    print(f"\nNormalization complete. Total memories updated/verified: {total_updated}")
    
    # Final Audit
    print("\n--- Final Domain Distribution ---")
    final_rows = db.fetch_all("SELECT domain, COUNT(*) as c FROM memories GROUP BY domain ORDER BY c DESC")
    for r in final_rows:
        print(f"{r['domain']}: {r['c']}")

if __name__ == "__main__":
    normalize_memories()
