import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
from decision_engine import full_decision_cycle
result = full_decision_cycle()
print('\nDone. Saved to:', result['saved'])
