
from promaia.storage.db_factory import get_db

def refine_normalization():
    db = get_db()
    
    # Keyword-based cleanup for the 'general' bucket
    refinements = {
        'promaia': [
            '%Promaia%', '%Maia%', '%Muninn%', '%Zbrain%', '%zbrain%', '%Gemini%', 
            '%Claude%', '%codebase%', '%implementation%', '%VAD%', '%Voice%',
            '%dashboard%', '%briefing%', '%personality%', '%memory%', '%pipeline%',
            '%system instructions%'
        ],
        'heatpup': ['%Heatpup%', '%heatpup%'],
        'hvac': ['%HVAC%', '%hvac%'],
        'sedgwick': ['%Sedgwick%', '%sedgwick%']
    }

    print("Refining 'general' bucket based on content keywords...")
    
    total_refined = 0
    for target, keywords in refinements.items():
        for kw in keywords:
            # Only update if current domain is 'general'
            count_row = db.fetch_one(
                "SELECT COUNT(*) as c FROM memories WHERE domain = 'general' AND content LIKE ?",
                (kw,)
            )
            count = count_row['c'] if count_row else 0
            
            if count > 0:
                print(f"Moving {count} memories from 'general' to '{target}' based on keyword '{kw}'...")
                db.execute(
                    "UPDATE memories SET domain = ? WHERE domain = 'general' AND content LIKE ?",
                    (target, kw)
                )
                total_refined += count

    print(f"\nRefinement complete. Total memories moved: {total_refined}")
    
    # Final Audit
    print("\n--- Final Domain Distribution ---")
    final_rows = db.fetch_all("SELECT domain, COUNT(*) as c FROM memories GROUP BY domain ORDER BY c DESC")
    for r in final_rows:
        print(f"{r['domain']}: {r['c']}")

if __name__ == "__main__":
    refine_normalization()
