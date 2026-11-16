"""Simulated-annealing placement refinement (pure python, uses pre-extracted pad/courtyard geometry)."""
import math, random

FIXED = {'J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'Q1', 'SW1', 'SW2', 'SW3', 'H1', 'H2', 'H3', 'H4'}
NET_W = {'GND': 0.0, 'VBUS': 0.3, '/VBUS_USB': 0.5, '+5V': 0.35, '+3V3': 0.3,
         '/SW': 4.0, '/BST': 3.0, '/SH_TOP': 3.0, '/AMP_FB': 2.5, '/GATE': 2.5, '/VSET': 2.0, '/I_SENSE': 1.5,
         '/AMP_OUT': 2.0, '/KILL': 1.5, '/I_FILT': 2.0, '/NRST': 1.0}
# explicit "keep close" pairs: (a, b, weight)
PAIRS = [('C13', 'U1', 2.5), ('C14', 'U1', 2.0), ('C15', 'U1', 2.0), ('C12', 'U1', 1.0),
         ('C11', 'U5', 2.5), ('C10', 'U5', 2.5), ('C22', 'U3', 2.5), ('C23', 'U3', 1.5), ('C25', 'U6', 2.5),
         ('C4', 'U4', 3.0), ('C5', 'U4', 3.0), ('C6', 'U4', 3.0), ('C7', 'L1', 2.0), ('C8', 'L1', 2.0),
         ('C9', 'L1', 1.5), ('C3', 'U2', 2.5), ('R1', 'U2', 2.0), ('R2', 'D2', 1.5), ('D2', 'U2', 1.0),
         ('L1', 'U4', 3.0), ('R27', 'Q1', 4.0), ('D1', 'F1', 1.5), ('C1', 'F1', 1.5), ('C2', 'F1', 1.0),
         ('C20', 'U3', 1.5), ('C21', 'U1', 1.0), ('C19', 'U1', 1.5)]


INFLATE = {'U1': 1.6, 'U2': 1.2, 'U3': 1.2, 'U6': 1.2, 'U4': 0.8, 'U5': 0.8, 'L1': 0.4}


def rot_vec(x, y, deg):
    t = math.radians(deg)
    c, s = round(math.cos(t), 6), round(math.sin(t), 6)
    return x * c + y * s, -x * s + y * c


class Placer:
    def __init__(self, geom, pos, board, margin=1.0, gap=0.9, fixed_extra=()):
        """geom[ref] = dict(pads=[(net,x,y)], rect=(x1,y1,x2,y2)) at rot 0; pos[ref]=[x,y,rot]"""
        self.g, self.pos = geom, {k: list(v) for k, v in pos.items()}
        self.bw, self.bh, self.m, self.gap = board[0], board[1], margin, gap
        self.fixed = FIXED | set(fixed_extra)
        self.nets = {}
        for ref, g in geom.items():
            for net, x, y in g['pads']:
                if net and NET_W.get(net, 1.0) > 0:
                    self.nets.setdefault(net, []).append(ref)
        self.cache = {}

    def rect(self, ref, p=None):
        x, y, r = p or self.pos[ref]
        x1, y1, x2, y2 = self.g[ref]['rect']
        inf = INFLATE.get(ref, 0.0)
        x1, y1, x2, y2 = x1 - inf, y1 - inf, x2 + inf, y2 + inf
        pts = [rot_vec(a, b, r) for a, b in ((x1, y1), (x2, y1), (x1, y2), (x2, y2))]
        return (x + min(p[0] for p in pts), y + min(p[1] for p in pts), x + max(p[0] for p in pts), y + max(p[1] for p in pts))

    def padxy(self, ref, net, p=None):
        x, y, r = p or self.pos[ref]
        out = []
        for n, px, py in self.g[ref]['pads']:
            if n == net:
                a, b = rot_vec(px, py, r)
                out.append((x + a, y + b))
        return out

    def hpwl(self, net):
        xs, ys = [], []
        for ref in self.nets[net]:
            for (a, b) in self.padxy(ref, net):
                xs.append(a); ys.append(b)
        return (max(xs) - min(xs)) + (max(ys) - min(ys)) if xs else 0.0

    def cost_of_refs(self, refs):
        nets = set()
        for r in refs:
            for n, _, _ in self.g[r]['pads']:
                if n in self.nets:
                    nets.add(n)
        c = sum(NET_W.get(n, 1.0) * self.hpwl(n) for n in nets)
        for a, b, w in PAIRS:
            if a in refs or b in refs:
                ax, ay, _ = self.pos[a]; bx, by, _ = self.pos[b]
                c += w * math.hypot(ax - bx, ay - by)
        return c

    def total(self):
        c = sum(NET_W.get(n, 1.0) * self.hpwl(n) for n in self.nets)
        for a, b, w in PAIRS:
            ax, ay, _ = self.pos[a]; bx, by, _ = self.pos[b]
            c += w * math.hypot(ax - bx, ay - by)
        return c

    def ok(self, ref, rect):
        if rect[0] < self.m or rect[1] < self.m or rect[2] > self.bw - self.m or rect[3] > self.bh - self.m:
            return False
        g = self.gap
        for o, p in self.pos.items():
            if o == ref:
                continue
            r2 = self.rect(o)
            if rect[0] < r2[2] + g and rect[2] + g > r2[0] and rect[1] < r2[3] + g and rect[3] + g > r2[1]:
                return False
        return True

    def run(self, iters=40000, seed=1, t0=2.5, t1=0.03):
        rnd = random.Random(seed)
        movable = [r for r in self.pos if r not in self.fixed]
        cur = self.total()
        best = cur
        acc = 0
        for i in range(iters):
            T = t0 * (t1 / t0) ** (i / iters)
            ref = rnd.choice(movable)
            old = list(self.pos[ref])
            before = self.cost_of_refs({ref})
            spread = 8.0 * (1 - i / iters) + 1.0
            nx = old[0] + rnd.gauss(0, spread)
            ny = old[1] + rnd.gauss(0, spread)
            nr = old[2]
            if rnd.random() < 0.15:
                nr = (old[2] + rnd.choice((90, 180, 270))) % 360
            nx, ny = round(nx * 4) / 4, round(ny * 4) / 4
            new = [nx, ny, nr]
            if not self.ok(ref, self.rect(ref, new)):
                continue
            self.pos[ref] = new
            after = self.cost_of_refs({ref})
            d = after - before
            if d <= 0 or rnd.random() < math.exp(-d / T):
                cur += d
                acc += 1
            else:
                self.pos[ref] = old
        return self.total(), acc

