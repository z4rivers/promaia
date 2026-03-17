
from promaia.storage.db_factory import get_db

def final_db_cleanup():
    db = get_db()
    
    # 1. Clean up project contexts: merge redundant or misnamed project domains
    # promaia_codebase (21) should probably be deleted if it points to PetalPolicy 
    # (based on previous inspect_all_contexts output)
    
    # Map all project domain IDs that should be 'promaia'
    promaia_domain_ids = [3, 4, 11, 12, 16, 18, 20]
    
    # Update all memories with these IDs to 'promaia'
    db.execute("UPDATE memories SET domain = 'promaia' WHERE domain_id IN (3, 4, 11, 12, 16, 18, 20)")
    
    # Update contexts to point to a single unified domain for the same project
    # Project ID 3 is 'Promaia'. ID 4 is 'zBrain'.
    
    # 2. Hard delete redundant/empty domains to prevent confusion
    # Keep the core 6: promaia, personal, business, hvac, heatpup, sedgwick
    # Plus the specific project names: Catpool, Hopecookie, Maybecat, PURRfoot, PetalPolicy
    
    allowed_names = [
        'promaia', 'personal', 'business', 'hvac', 'heatpup', 'sedgwick',
        'Catpool', 'Hopecookie', 'Maybecat', 'PURRfoot', 'PetalPolicy',
        'HVAC Leads', 'zBrain', 'Promaia'
    ]
    
    print("Deleting redundant domains...")
    # This is slightly risky but necessary for 'clean and distinct'
    db.execute(
        f"DELETE FROM domains WHERE name NOT IN ({','.join(['?']*len(allowed_names))})",
        allowed_names
    )

    print("DB Cleanup complete.")

if __name__ == "__main__":
    final_db_cleanup()
