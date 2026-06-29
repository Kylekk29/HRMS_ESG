import sys
sys.path.insert(0, '.')
from booth.manager import BoothManager
m = BoothManager()
res = m.match_top5('engineer', {'edu':'phd','exp':'7+','skill':'high','status':'immediate'})
print(f'Top 5 count: {len(res)}')
for r in res:
    print(f'  #{r["rank"]}: {r["candidate_name"]} score={r["match_pct"]} file={r["candidate_file"]}')
