"""Minimal KiCad s-expression + symbol library helpers."""
import re, os, copy

KICAD = r'C:\Program Files\KiCad\10.0\share\kicad'
SYMDIR = os.path.join(KICAD, 'symbols')
FPDIR = os.path.join(KICAD, 'footprints')


class Sym(str):
    """Bare atom (unquoted)."""


def tokenize(text):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            i += 1
        elif c == '(' or c == ')':
            yield c
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == '\\':
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            yield ('s', ''.join(buf))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()':
                j += 1
            yield ('a', text[i:j])
            i = j


def parse(text):
    stack = [[]]
    for t in tokenize(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            done = stack.pop()
            stack[-1].append(done)
        elif t[0] == 's':
            stack[-1].append(t[1])
        else:
            a = t[1]
            stack[-1].append(Sym(a))
    return stack[0][0] if len(stack[0]) == 1 else stack[0]


def fmt_atom(x):
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, (int, float)):
        return repr(x)
    return '"' + x + '"'


def dump(node, indent=0):
    """Serialise with KiCad-ish layout: lists containing sub-lists are multi-line."""
    if not isinstance(node, list):
        return fmt_atom(node)
    if not any(isinstance(c, list) for c in node):
        return '(' + ' '.join(fmt_atom(c) for c in node) + ')'
    pad = '\t' * (indent + 1)
    head = []
    rest = []
    seen_list = False
    for c in node:
        if isinstance(c, list):
            seen_list = True
        (rest if seen_list else head).append(c)
    out = '(' + ' '.join(fmt_atom(c) for c in head)
    for c in rest:
        out += '\n' + pad + dump(c, indent + 1)
    out += '\n' + '\t' * indent + ')'
    return out


_cache = {}


def load_lib(libname):
    if libname not in _cache:
        with open(os.path.join(SYMDIR, libname + '.kicad_sym'), encoding='utf-8') as f:
            _cache[libname] = parse(f.read())
    return _cache[libname]


def find_symbol(libname, symname):
    lib = load_lib(libname)
    for c in lib:
        if isinstance(c, list) and c and c[0] == 'symbol' and c[1] == symname:
            return c
    raise KeyError(f'{libname}:{symname}')


def flatten(libname, symname):
    """Return a deep-copied symbol with 'extends' resolved, named libname:symname."""
    sym = copy.deepcopy(find_symbol(libname, symname))
    ext = [c for c in sym if isinstance(c, list) and c and c[0] == 'extends']
    if ext:
        parent = copy.deepcopy(find_symbol(libname, ext[0][1]))
        pname = parent[1]
        # rename parent's unit sub-symbols to child name
        for c in parent:
            if isinstance(c, list) and c and c[0] == 'symbol':
                c[1] = c[1].replace(pname, symname, 1)
        # take parent's body, override properties with child's
        child_props = {c[1]: c for c in sym if isinstance(c, list) and c and c[0] == 'property'}
        new = [Sym('symbol'), symname]
        parent_names = {c[1] for c in parent if isinstance(c, list) and c and c[0] == 'property'}
        extra_child = [v for k, v in child_props.items() if k not in parent_names]
        last_prop = max(i for i, c in enumerate(parent) if isinstance(c, list) and c and c[0] == 'property')
        for i, c in enumerate(parent[2:], start=2):
            if isinstance(c, list) and c and c[0] == 'property' and c[1] in child_props:
                new.append(child_props[c[1]])
            elif isinstance(c, list) and c and c[0] == 'extends':
                continue
            else:
                new.append(c)
            if i == last_prop:
                new.extend(extra_child)
        sym = new
    return sym


def embed(libname, symname):
    s = flatten(libname, symname)
    s[1] = f'{libname}:{symname}'
    return s


def pins_of(sym):
    """Return list of dicts for every pin: number,name,type,x,y,angle,length,unit."""
    out = []

    def walk(node, unit):
        for c in node:
            if isinstance(c, list) and c:
                if c[0] == 'symbol':
                    m = re.search(r'_(\d+)_(\d+)$', c[1])
                    walk(c, int(m.group(1)) if m else unit)
                elif c[0] == 'pin':
                    d = dict(type=c[1], shape=c[2], unit=unit)
                    for p in c[3:]:
                        if isinstance(p, list):
                            if p[0] == 'at':
                                d['x'], d['y'], d['angle'] = float(p[1]), float(p[2]), float(p[3])
                            elif p[0] == 'length':
                                d['length'] = float(p[1])
                            elif p[0] == 'name':
                                d['name'] = p[1]
                            elif p[0] == 'number':
                                d['number'] = p[1]
                    out.append(d)
    walk(sym, 0)
    return out


if __name__ == '__main__':
    import sys
    lib, name = sys.argv[1], sys.argv[2]
    s = flatten(lib, name)
    for p in sorted(pins_of(s), key=lambda d: (d['unit'], int(re.sub(r'\D', '', d['number']) or 0), d['number'])):
        print(f"u{p['unit']} #{p['number']:<4} {p['name']:<22} {p['type']:<14} at({p['x']},{p['y']}) a{p['angle']:.0f} L{p['length']}")
