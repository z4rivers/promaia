import asyncio
import traceback

async def test():
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()
        db.execute("SELECT 1")
        print("Success!")
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
