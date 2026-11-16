import json, sys, os
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding='utf-8'))
ns = d['net_settings']
base = ns['classes'][0]
base.update(track_width=0.2, clearance=0.15, via_diameter=0.6, via_drill=0.3)

def cls(name, w, prio):
    c = dict(base)
    c.update(name=name, track_width=w, priority=prio)
    return c

ns['classes'] = [base, cls('Power', 0.8, 0), cls('Mid', 0.4, 1)]
ns['netclass_patterns'] = (
    [{'netclass': 'Power', 'pattern': p} for p in ('VBUS', '/VBUS_USB', '/SH_TOP')] +
    [{'netclass': 'Mid', 'pattern': p} for p in ('+5V', '+3V3', '/SW', '/GATE', '/AMP_OUT')])
ds = d['board']['design_settings']
ds['defaults']['zones'].update(min_clearance=0.3, min_thickness=0.25, thermal_relief_gap=0.3, thermal_relief_spoke_width=0.4)
ds['rules'].update(min_clearance=0.15, min_track_width=0.15, min_via_diameter=0.5, min_through_hole_diameter=0.3,
                   min_via_annular_width=0.1, min_copper_edge_clearance=0.3, min_hole_clearance=0.25, min_hole_to_hole=0.25)
ds['rule_severities']['courtyards_overlap'] = 'warning'
ds['rule_severities']['silk_overlap'] = 'ignore'
ds['rule_severities']['silk_over_copper'] = 'ignore'
json.dump(d, open(dst, 'w'), indent=2)





