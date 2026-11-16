import json, collections, sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
v = []
for sh in d.get('sheets', []):
    v += sh.get('violations', [])
print('violations:', len(v))
c = collections.Counter((x['type'], x['severity']) for x in v)
for k, nn in c.most_common():
    print(nn, k)
want = sys.argv[2] if len(sys.argv) > 2 else None
lim = int(sys.argv[3]) if len(sys.argv) > 3 else 6
shown = collections.Counter()
for x in v:
    if want and x['type'] != want and want != 'all':
        continue
    shown[x['type']] += 1
    if shown[x['type']] > lim:
        continue
    items = '; '.join(i.get('description', '') for i in x.get('items', []))
    print(' -', x['type'], '|', x['description'], '|', items[:200])
