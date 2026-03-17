import sys, json
sys.path.insert(0, 'c:/Users/Zachary Turner/dev/promaia')
from promaia.storage.signals_db import SignalsDB

db = SignalsDB()
msgs = db.check_inbox('antigravity')
with open('c:/Users/Zachary Turner/dev/promaia/msgs.json', 'w') as f:
    json.dump(msgs, f, indent=2)
