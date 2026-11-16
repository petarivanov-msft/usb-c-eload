import sys, re, collections
import xml.etree.ElementTree as ET
t = ET.parse(sys.argv[1]).getroot()
comps = {}
for c in t.find('components'):
    ref = c.get('ref')
    val = c.findtext('value')
    fp = c.findtext('footprint')
    comps[ref] = (val, fp)
nets = collections.OrderedDict()
for nn in t.find('nets'):
    name = nn.get('name')
    nodes = [(x.get('ref'), x.get('pin'), x.get('pinfunction') or '') for x in nn]
    nets[name] = nodes
only = sys.argv[2:] 
print('components:', len(comps), ' nets:', len(nets))
for name, nodes in sorted(nets.items()):
    if only and not any(o == name for o in only):
        continue
    print(f'{name:14} ' + ' '.join(f'{r}.{p}' + (f'({f})' if f and f != p else '') for r, p, f in nodes))
