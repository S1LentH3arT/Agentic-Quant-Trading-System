import sys
sys.path.insert(0, 'F:/working-project/tdx-mcp')
sys.stdout.reconfigure(encoding='utf-8')
from decision_engine import full_decision_cycle
result = full_decision_cycle()
print('\nDone. Saved to:', result['saved'])
