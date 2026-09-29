# 등각(아이소메트릭) 일러스트 도구 — 3D 좌표(mm 비슷한 단위)를 화면에 투영해 면마다 빛을 먹여 그린다.
#   HMI 그림(단계 · 팔레트 · 아이콘)의 공용 부품. 그림을 고치면 build.py 를 다시 돌린다(황인재 9/21 — Claude 디자인 시안).
#   화면 x = (x − y)·cos30,  화면 y = (x + y)·sin30 − z   → +x 는 오른쪽 아래, +y 는 왼쪽 아래, +z 는 위
#   빛은 왼쪽 위 앞에서 — 윗면 1.0 · 왼쪽 앞면(+y) .75 · 오른쪽 앞면(+x) .5
import math

C, S = math.cos(math.radians(30)), 0.5
R2 = math.sqrt(2)

def _hx(c): return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
def mix(a, b, t):
    A, B = _hx(a), _hx(b)
    t = max(0.0, min(1.0, t))
    return '#%02x%02x%02x' % tuple(round(A[i] + (B[i] - A[i]) * t) for i in range(3))

MAT = {                       # (그늘 색, 빛 받은 색)
    'ceramic': ('#8a8377', '#ffffff'),
    'pink':    ('#62203a', '#fbc5d3'),        # 다회용기 — 탁한 분홍 플라스틱(황인재 9/22 예시 사진)
    'steel':   ('#4a5462', '#f1f4f8'),
    'alu':     ('#2e353f', '#aab4c1'),
    'graphite': ('#101419', '#707b8b'),
    'robot':   ('#7c848f', '#ffffff'),
    'pedestal': ('#0c1016', '#3b4654'),
    'rack':    ('#12253a', '#7aa7de'),
    'bin':     ('#141d19', '#62806f'),
    'sponge':  ('#80530a', '#ffd978'),
    'scrub':   ('#123f24', '#5cc281'),
    'foam':    ('#262e3a', '#b7c2d0'),
    'amber':   ('#553905', '#f8cb52'),
    'bristle': ('#5e370b', '#eeae54'),
    'handle':  ('#16305a', '#79a5ff'),
    'glass':   ('#35506e', '#dff0ff'),
    'water':   ('#1d4f9a', '#9cc8ff'),
    'dark':    ('#07090d', '#2a323d'),
}
def shade(mat, t):
    d, l = MAT[mat]
    return mix(d, l, t)

def lum(nx, ny, nz):
    return 0.625 - 0.125 * nx + 0.125 * ny + 0.375 * nz

ACC = '#6b9bff'
REUSE = 'pink'                              # 그릇·컵 재질


class Scene:
    def __init__(self, pid, w, h, ox, oy, k=1.0):
        self.pid, self.w, self.h, self.ox, self.oy, self.k = pid, w, h, ox, oy, k
        self.out, self.defs, self.n = [], [], 0
        self.defs.append(f'<filter id="{pid}-blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter>')
        self.defs.append(f'<filter id="{pid}-soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2"/></filter>')

    # ── 기본
    def uid(self, s):
        self.n += 1
        return f'{self.pid}-{s}{self.n}'

    def P(self, x, y, z):
        return (self.ox + (x - y) * C * self.k, self.oy + ((x + y) * S - z) * self.k)

    def pts(self, pts3):
        return ' '.join('%.1f,%.1f' % self.P(*p) for p in pts3)

    def raw(self, s):
        self.out.append(s)

    def ell(self, cx, cy, z, r):
        """수평 원 → 화면 타원 (가운데 x, y, rx, ry)"""
        X, Y = self.P(cx, cy, z)
        return X, Y, r * R2 * C * self.k, r * R2 * S * self.k

    def lgrad(self, stops, x1=0, y1=0, x2=1, y2=0):
        gid = self.uid('g')
        st = ''.join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a != 1 else '') + '/>' for o, c, a in stops)
        self.defs.append(f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{st}</linearGradient>')
        return f'url(#{gid})'

    def rgrad(self, stops, cx=.5, cy=.5, r=.5):
        gid = self.uid('r')
        st = ''.join(f'<stop offset="{o}" stop-color="{c}"' + (f' stop-opacity="{a}"' if a != 1 else '') + '/>' for o, c, a in stops)
        self.defs.append(f'<radialGradient id="{gid}" cx="{cx}" cy="{cy}" r="{r}">{st}</radialGradient>')
        return f'url(#{gid})'

    def side_grad(self, mat, alpha=1):
        """원기둥 옆면 — 왼쪽 밝고 · 앞 조금 반짝 · 오른쪽 어둡게"""
        return self.lgrad([(0, shade(mat, .70), alpha), (.22, shade(mat, .92), alpha), (.5, shade(mat, .74), alpha),
                           (.82, shade(mat, .52), alpha), (1, shade(mat, .40), alpha)])

    # ── 그림자
    def shadow(self, cx, cy, z, r, op=.45, squash=1.0):
        X, Y, rx, ry = self.ell(cx, cy, z, r)
        self.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx:.1f}" ry="{ry * squash:.1f}" fill="#000" fill-opacity="{op}" filter="url(#{self.pid}-blur)"/>')

    # ── 각기둥: 바닥 다각형(반시계) · z0..z1
    def prism(self, fp, z0, z1, mat, top=True, alpha=1, edge=True, top_t=1.0):
        n = len(fp)
        a = f' fill-opacity="{alpha}"' if alpha != 1 else ''
        for i in range(n):
            (x1, y1), (x2, y2) = fp[i], fp[(i + 1) % n]
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy) or 1
            nx, ny = dy / L, -dx / L
            if nx + ny <= 1e-6:
                continue
            col = shade(mat, lum(nx, ny, 0))
            st = f' stroke="{col}" stroke-width=".6" stroke-linejoin="round"' if edge and alpha == 1 else ''
            self.raw(f'<polygon points="{self.pts([(x1, y1, z0), (x2, y2, z0), (x2, y2, z1), (x1, y1, z1)])}" fill="{col}"{a}{st}/>')
        if top:
            col = shade(mat, top_t)
            st = f' stroke="{col}" stroke-width=".6" stroke-linejoin="round"' if edge and alpha == 1 else ''
            self.raw(f'<polygon points="{self.pts([(x, y, z1) for x, y in fp])}" fill="{col}"{a}{st}/>')

    def box(self, x, y, z, w, d, h, mat, **kw):
        self.prism([(x, y), (x + w, y), (x + w, y + d), (x, y + d)], z, z + h, mat, **kw)

    def rbox(self, cx, cy, z, hw, hd, h, mat, ang=0, **kw):
        """가운데 (cx, cy), 반폭 hw · 반깊이 hd, ang 만큼 돌린 상자"""
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        fp = [(cx + ux * ca - uy * sa, cy + ux * sa + uy * ca) for ux, uy in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))]
        self.prism(fp, z, z + h, mat, **kw)

    # ── 수직 원기둥·원뿔대
    def cyl(self, cx, cy, z0, r0, z1, r1, mat, top='solid', alpha=1, outline=True, top_fill=None):
        X0, Y0, rx0, ry0 = self.ell(cx, cy, z0, r0)
        X1, Y1, rx1, ry1 = self.ell(cx, cy, z1, r1)
        g = self.side_grad(mat, alpha)
        ol = f' stroke="{shade(mat, .28)}" stroke-width="1" stroke-opacity=".6"' if outline else ''
        self.raw(f'<path d="M{X0 - rx0:.1f} {Y0:.1f} A{rx0:.1f} {ry0:.1f} 0 0 0 {X0 + rx0:.1f} {Y0:.1f} L{X1 + rx1:.1f} {Y1:.1f} '
                 f'A{rx1:.1f} {ry1:.1f} 0 0 1 {X1 - rx1:.1f} {Y1:.1f} Z" fill="{g}"{ol}/>')
        if top == 'solid':
            f = top_fill or shade(mat, .97)
            self.raw(f'<ellipse cx="{X1:.1f}" cy="{Y1:.1f}" rx="{rx1:.1f}" ry="{ry1:.1f}" fill="{f}"' + (f' fill-opacity="{alpha}"' if alpha != 1 else '') + f'{ol}/>')
        return X1, Y1, rx1, ry1

    def vessel(self, cx, cy, z0, r0, h, r1, mat='ceramic', wall=3.5, inner=None, alpha=1, flange=0, ears=0, foot=0, band=0):
        """열린 그릇·컵 — 겉면 · 테두리 · 안쪽. 돌려주는 값: 입구 타원(안쪽 물건을 가릴 때 씀)
           다회용기 모양(황인재 9/22 예시 사진): flange = 테두리 날개 폭 · ears = 양옆 손잡이 귀 길이 · foot = 받침 굽 반지름
           band = 컵 윗부분 매끈한 띠의 비율(아래는 세로 주름)"""
        z1 = z0 + h
        zt = z1 - 3 if flange else z1                                          # 날개가 있으면 몸통은 날개 밑까지
        if foot:                                                               # 받침 굽
            self.cyl(cx, cy, z0, foot - 2, z0 + 4, foot, mat, top=None, alpha=alpha)
        zs = z0 + 4 if foot else z0
        if band:                                                               # 컵 — 아래 주름 몸통 + 위 띠(살짝 굵다)
            zb = z0 + h * (1 - band)
            rb = r0 + (r1 - r0) * (1 - band)
            self.cyl(cx, cy, zs, r0, zb, rb - 1.5, mat, top=None, alpha=alpha)
            self._ribs(cx, cy, zs, r0, zb, rb - 1.5, mat)
            X1, Y1, rx1, ry1 = self.cyl(cx, cy, zb, rb + .8, zt, r1, mat, top=None, alpha=alpha)
            Xs, Ys, rxs, rys = self.ell(cx, cy, zb, rb + .8)
            self.raw(f'<path d="M{Xs - rxs:.1f} {Ys:.1f} A{rxs:.1f} {rys:.1f} 0 0 0 {Xs + rxs:.1f} {Ys:.1f}" fill="none" stroke="{shade(mat, .3)}" stroke-width="1.2" stroke-opacity=".6"/>')
        else:
            X1, Y1, rx1, ry1 = self.cyl(cx, cy, zs, r0, zt, r1, mat, top=None, alpha=alpha)
        if flange:                                                             # 테두리 날개 + 손잡이 귀
            ea = math.radians(70)                                              # 귀 방향 — 그리퍼가 잡는 쪽(−20°)과 직각
            ux, uy = math.cos(ea), math.sin(ea)
            def ear(sign):
                ex, ey = cx + sign * (r1 + flange + ears / 2 - 2) * ux, cy + sign * (r1 + flange + ears / 2 - 2) * uy
                self.rbox(ex, ey, z1 - 3, ears / 2 + 2, 12, 3, mat, ang=70)
            if ears:
                ear(-1)                                                        # 뒤쪽 귀 — 날개보다 먼저
            self.cyl(cx, cy, z1 - 3, r1 + flange, z1, r1 + flange, mat, top='solid', alpha=alpha, top_fill=shade(mat, .96))
            if ears:
                ear(1)
                Xf, Yf, rxf, ryf = self.ell(cx, cy, z1, r1 + flange)
                self.raw(f'<ellipse cx="{Xf:.1f}" cy="{Yf:.1f}" rx="{rxf:.1f}" ry="{ryf:.1f}" fill="{shade(mat, .96)}"/>')
            X1, Y1, rx1, ry1 = self.ell(cx, cy, z1, r1)
            self.raw(f'<ellipse cx="{X1:.1f}" cy="{Y1:.1f}" rx="{rx1:.1f}" ry="{ry1:.1f}" fill="{shade(mat, .99)}" stroke="{shade(mat, .5)}" stroke-width="1" stroke-opacity=".45"/>')
        else:
            lip = 1.2 if band else 0                                           # 컵 입술 — 살짝 말려 있다
            Xl, Yl, rxl, ryl = self.ell(cx, cy, z1, r1 + lip)
            self.raw(f'<ellipse cx="{Xl:.1f}" cy="{Yl:.1f}" rx="{rxl:.1f}" ry="{ryl:.1f}" fill="{shade(mat, .99)}" stroke="{shade(mat, .45)}" stroke-width="1" stroke-opacity=".5"/>')
        ri = r1 - wall
        Xi, Yi, rxi, ryi = self.ell(cx, cy, z1, ri)
        g = inner or self.lgrad([(0, shade(mat, .50), 1), (.55, shade(mat, .74), 1), (1, shade(mat, .90), 1)], 0, 0, 0, 1)
        self.raw(f'<ellipse cx="{Xi:.1f}" cy="{Yi:.1f}" rx="{rxi:.1f}" ry="{ryi:.1f}" fill="{g}"/>')
        # 바닥 — 안쪽 아래에 밝은 둥근 면
        Xb, Yb, rxb, ryb = self.ell(cx, cy, zs + 4, r0 - wall)
        if h < 60:                                                                 # 얕은 그릇만 바닥이 보인다
            self.raw(f'<ellipse cx="{Xb:.1f}" cy="{min(Yb, Yi + ryi * .45):.1f}" rx="{rxb * .9:.1f}" ry="{ryb * .9:.1f}" fill="{shade(mat, .93)}" fill-opacity=".8"/>')
        # 안쪽 윗가장자리 그늘
        self.raw(f'<path d="M{Xi - rxi:.1f} {Yi:.1f} A{rxi:.1f} {ryi:.1f} 0 0 1 {Xi + rxi:.1f} {Yi:.1f}" fill="none" stroke="{shade(mat, .40)}" stroke-width="2.5" stroke-opacity=".45"/>')
        # 겉면 반짝임 — 플라스틱은 은은하게
        Xa, Ya, rxa, rya = self.ell(cx, cy, zt, r1)
        hx, Y0 = Xa - rxa * .62, self.ell(cx, cy, zs, r0)[1]
        self.raw(f'<path d="M{hx:.1f} {Ya + rya * .75:.1f} Q{hx - 3:.1f} {(Ya + Y0) / 2 + 4:.1f} {hx + 2:.1f} {Y0 + 2:.1f}" '
                 f'stroke="#fff" stroke-opacity="{.3 if mat == REUSE else .55}" stroke-width="3" fill="none" stroke-linecap="round"/>')
        return (X1, Y1, rx1, ry1)

    def inverted_cup(self, cx, cy, z0, r0, h, r1, mat='ceramic', alpha=1, band=.3):
        """뒤집힌 컵(🆕 9/27 황인재: 팔레트에는 컵을 뒤집어 얹는다) — 입구(r1)가 바닥에, 바닥(r0)이 위.
           아래 = 매끈한 띠(입구 쪽) · 위 = 세로 주름 몸통 · 맨 위는 막힌 바닥면(굽 테두리)."""
        lip = 1.2
        zb = z0 + h * band
        rb = r1 + (r0 - r1) * band
        self.cyl(cx, cy, z0, r1 + lip, zb, rb + .8, mat, top=None, alpha=alpha)                     # 아래 띠(입구 쪽)
        Xs, Ys, rxs, rys = self.ell(cx, cy, zb, rb + .8)
        self.raw(f'<path d="M{Xs - rxs:.1f} {Ys:.1f} A{rxs:.1f} {rys:.1f} 0 0 0 {Xs + rxs:.1f} {Ys:.1f}" fill="none" stroke="{shade(mat, .3)}" stroke-width="1.2" stroke-opacity=".6"/>')
        X1, Y1, rx1, ry1 = self.cyl(cx, cy, zb, rb - 1.5, z0 + h, r0, mat, top='solid', alpha=alpha, top_fill=shade(mat, .96))   # 위 주름 몸통 + 막힌 바닥
        self._ribs(cx, cy, zb, rb - 1.5, z0 + h, r0, mat)
        Xt, Yt, rxt, ryt = self.ell(cx, cy, z0 + h, r0 - 4)                                        # 바닥 굽 테두리
        self.raw(f'<ellipse cx="{Xt:.1f}" cy="{Yt:.1f}" rx="{rxt:.1f}" ry="{ryt:.1f}" fill="none" stroke="{shade(mat, .6)}" stroke-width="1" stroke-opacity=".5"/>')
        Xa, Ya, rxa, rya = self.ell(cx, cy, z0 + h, r0)                                            # 겉면 반짝임
        hx, Y0 = Xa - rxa * .62, self.ell(cx, cy, z0, r1)[1]
        self.raw(f'<path d="M{hx:.1f} {Ya + rya * .75:.1f} Q{hx - 3:.1f} {(Ya + Y0) / 2 + 4:.1f} {hx + 2:.1f} {Y0 + 2:.1f}" '
                 f'stroke="#fff" stroke-opacity="{.3 if mat == REUSE else .55}" stroke-width="3" fill="none" stroke-linecap="round"/>')
        return (X1, Y1, rx1, ry1)

    def _ribs(self, cx, cy, za, ra, zb, rb, mat, n=22):
        """컵 아랫부분 세로 주름 — 보이는 앞쪽 반에만 골을 긋는다"""
        for i in range(n):
            phi = math.radians(-45 + 180 * (i + .5) / n)
            (ax, ay), (bx, by) = self.P(cx + ra * math.cos(phi), cy + ra * math.sin(phi), za + 1.5), self.P(cx + rb * math.cos(phi), cy + rb * math.sin(phi), zb - 1)
            face = math.cos(phi - math.radians(45))                           # 1 = 정면
            self.raw(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{shade(mat, .25)}" stroke-opacity="{.22 + .3 * (1 - face):.2f}" stroke-width="1.2"/>')
            (ax2, ay2), (bx2, by2) = self.P(cx + ra * math.cos(phi + .07), cy + ra * math.sin(phi + .07), za + 1.5), self.P(cx + rb * math.cos(phi + .07), cy + rb * math.sin(phi + .07), zb - 1)
            self.raw(f'<line x1="{ax2:.1f}" y1="{ay2:.1f}" x2="{bx2:.1f}" y2="{by2:.1f}" stroke="#ffffff" stroke-opacity="{.25 * face:.2f}" stroke-width=".9"/>')

    def clip_open(self, rim):
        """열린 그릇 안쪽 물건용 클립 — 테두리 타원 안 + 테두리 가운데 줄보다 위"""
        X, Y, rx, ry = rim
        cid = self.uid('c')
        self.defs.append(f'<clipPath id="{cid}"><rect x="-2000" y="-2000" width="4000" height="{2000 + Y:.1f}"/>'
                         f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx - 2:.1f}" ry="{ry - 1.5:.1f}"/></clipPath>')
        return f'clip-path="url(#{cid})"'

    # ── 임의 축 원판(세운 그릇) — 점을 찍어 다각형으로
    def circle3(self, c, u, v, r, n=48):
        return [(c[0] + r * (math.cos(t) * u[0] + math.sin(t) * v[0]),
                 c[1] + r * (math.cos(t) * u[1] + math.sin(t) * v[1]),
                 c[2] + r * (math.cos(t) * u[2] + math.sin(t) * v[2])) for t in [2 * math.pi * i / n for i in range(n)]]

    def hull(self, pts2):
        pts = sorted(set((round(x, 2), round(y, 2)) for x, y in pts2))
        if len(pts) < 3:
            return pts
        def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo, up = [], []
        for p in pts:
            while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
            lo.append(p)
        for p in reversed(pts):
            while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
            up.append(p)
        return lo[:-1] + up[:-1]

    def standing_bowl(self, cx, cy, zb, r1=55, r0=44, depth=40, alpha=1, mat=REUSE, flange=7):
        """세운 그릇 — 입구가 +x(오른쪽 아래)를 본다. zb = 그릇 아래 끝 높이(날개 포함)"""
        zc = zb + r1 + flange
        foot = self.circle3((cx - depth / 2, cy, zc), (0, 1, 0), (0, 0, 1), r0)
        rim = self.circle3((cx + depth / 2, cy, zc), (0, 1, 0), (0, 0, 1), r1)
        rim_in = self.circle3((cx + depth / 2, cy, zc), (0, 1, 0), (0, 0, 1), r1 - 3.5)
        H = self.hull([self.P(*p) for p in foot + rim])
        a = f' fill-opacity="{alpha}" stroke-opacity="{alpha}"' if alpha != 1 else ''
        g = self.lgrad([(0, shade(mat, .92), 1), (.45, shade(mat, .72), 1), (1, shade(mat, .45), 1)], 0, 0, 1, 1)
        self.raw(f'<polygon points="{" ".join("%.1f,%.1f" % p for p in H)}" fill="{g}" stroke="{shade(mat, .3)}" stroke-width="1" stroke-opacity=".5"{a}/>')
        if flange:                                                             # 테두리 날개
            fl = self.circle3((cx + depth / 2, cy, zc), (0, 1, 0), (0, 0, 1), r1 + flange)
            fl2 = self.circle3((cx + depth / 2 - 3, cy, zc), (0, 1, 0), (0, 0, 1), r1 + flange)
            FH = self.hull([self.P(*p) for p in fl + fl2])
            self.raw(f'<polygon points="{" ".join("%.1f,%.1f" % p for p in FH)}" fill="{shade(mat, .6)}"{a}/>')
            self.raw(f'<polygon points="{self.pts(fl)}" fill="{shade(mat, .95)}" stroke="{shade(mat, .45)}" stroke-width=".8" stroke-opacity=".6"{a}/>')
        self.raw(f'<polygon points="{self.pts(rim)}" fill="{shade(mat, .99)}"{a}/>')
        gi = self.lgrad([(0, shade(mat, .66), 1), (.5, shade(mat, .48), 1), (1, shade(mat, .34), 1)], 1, 0, 0, 1)
        self.raw(f'<polygon points="{self.pts(rim_in)}" fill="{gi}" stroke="{shade(mat, .5)}" stroke-width="1"{a}/>')
        fin = self.circle3((cx - depth / 2 + 4, cy, zc), (0, 1, 0), (0, 0, 1), r0 - 4)
        self.raw(f'<polygon points="{self.pts(fin)}" fill="{shade(mat, .9)}" fill-opacity="{.9 * alpha}"/>')
        # 반짝임
        hi = self.circle3((cx + depth / 2, cy, zc), (0, 1, 0), (0, 0, 1), r1 - 9)[26:36]
        self.raw(f'<polyline points="{self.pts(hi)}" fill="none" stroke="#fff" stroke-opacity="{.7 * alpha}" stroke-width="2.5" stroke-linecap="round"/>')

    # ── 화면 위에 얹는 표시(화살표 등) — 어두운 테두리로 밝은/어두운 바탕 모두에서 보이게
    def arrow(self, pts, color=ACC, w=4, head=8):
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        ang = math.atan2(y2 - y1, x2 - x1)
        hx1, hy1 = x2 - head * math.cos(ang - .5), y2 - head * math.sin(ang - .5)
        hx2, hy2 = x2 - head * math.cos(ang + .5), y2 - head * math.sin(ang + .5)
        d = 'M' + ' L'.join('%.1f %.1f' % p for p in pts) + f' M{hx1:.1f} {hy1:.1f} L{x2:.1f} {y2:.1f} L{hx2:.1f} {hy2:.1f}'
        self.raw(f'<path d="{d}" fill="none" stroke="#0b0f15" stroke-opacity=".55" stroke-width="{w + 3}" stroke-linecap="round" stroke-linejoin="round"/>')
        self.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')

    def svg(self, label='', cls=''):
        c = f' class="{cls}"' if cls else ''
        return (f'<svg{c} viewBox="0 0 {self.w} {self.h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}">'
                f'<defs>{"".join(self.defs)}</defs>{"".join(self.out)}</svg>')


# ── 공용 부품 ─────────────────────────────────────────────────────────
def pedestal(s, r=100):
    s.shadow(0, 0, -12, r * 1.02, op=.35)
    s.cyl(0, 0, -10, r, 0, r, 'pedestal', top=None, outline=False)
    X, Y, rx, ry = s.ell(0, 0, 0, r)
    g = s.rgrad([(0, '#3b4654', 1), (.75, '#2c3541', 1), (1, '#252d38', 1)], .45, .4, .7)
    s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{g}" stroke="#4a5666" stroke-width="1"/>')

# 다회용기(황인재 9/22 예시 사진) — 그릇: 둥근 몸통 + 테두리 날개 + 손잡이 귀 + 받침 굽 · 컵: 위 매끈한 띠 + 아래 세로 주름
BOWL = dict(r0=44, h=44, r1=55, flange=7, ears=9, foot=30)
CUP = dict(r0=29, h=98, r1=40, band=.3)

def container(s, kind, cx, cy, z0, alpha=1, upside_down=False):
    """upside_down: 컵을 뒤집어 그린다(팔레트 적재 — 입구가 아래). 그릇에는 쓰지 않는다."""
    if kind == 'CUP' and upside_down:
        d = CUP
        return s.inverted_cup(cx, cy, z0, d['r0'], d['h'], d['r1'], mat=REUSE, alpha=alpha, band=d['band'])
    if kind == 'BOWL':
        d = BOWL
        return s.vessel(cx, cy, z0, d['r0'], d['h'], d['r1'], mat=REUSE, alpha=alpha, flange=d['flange'], ears=d['ears'], foot=d['foot'])
    d = CUP
    return s.vessel(cx, cy, z0, d['r0'], d['h'], d['r1'], mat=REUSE, alpha=alpha, band=d['band'])

def gripper(s, cx, cy, zt, gap, finger=46, ang=-20, part='all', inner_min_z=None, arm=200):
    """RG2 비슷한 그리퍼 — 손가락 끝 높이 zt, 손가락 사이 반간격 gap. part: back|front|top|all
       손가락은 화면 가로에 가까운 축(ang)으로 벌어진다. 뒤 손가락(-) 은 물건 앞에, 앞 손가락(+) 은 물건 뒤에 그린다
       arm = 손목 띠 위로 그릴 로봇 팔 길이(기본은 화면 밖까지). 손목을 꺾는 그림은 짧게 그리고 s.wrist(팔 끝)에 이어 붙인다"""
    a = math.radians(ang)
    ux, uy = math.cos(a), math.sin(a)          # ang = -20° → (0.94, −0.34): 화면 오른쪽 약간 앞
    def finger_at(sign, zmin=None):
        fx, fy = cx + sign * gap * ux, cy + sign * gap * uy
        lo = zt if zmin is None else max(zt, zmin)
        if lo < zt + 12:                                                           # 손끝 패드
            s.rbox(fx, fy, lo, 3.8, 8, zt + 12 - lo, 'graphite', ang=ang)
        s0 = max(lo, zt + 12)
        s.rbox(fx, fy, s0, 3.2, 7.5, zt + finger + 4 - s0, 'alu', ang=ang)
    if part in ('back', 'all'):
        finger_at(-1, inner_min_z)
    if part in ('front', 'all'):
        finger_at(+1)
    if part in ('top', 'all'):
        zb = zt + finger
        bw = min(gap + 13, 25)
        if gap + 3.2 > bw - 4:                                                     # 손가락이 몸통 밖 → 가로 막대로 잇는다
            s.rbox(cx, cy, zb, gap + 3.4, 5, 5, 'graphite', ang=ang)
        s.rbox(cx, cy, zb + 5, bw, 11, 28, 'graphite', ang=ang)                   # 몸통
        s.rbox(cx, cy, zb + 33, bw - 3, 8, 3, 'steel', ang=ang)                    # 윗판
        s.cyl(cx, cy, zb + 36, 15, zb + 44, 15, 'steel')                           # 툴 체인저
        s.cyl(cx, cy, zb + 44, 19, zb + 60, 19, 'dark')                            # 로봇 손목 띠
        s.cyl(cx, cy, zb + 60, 22, zb + 60 + arm, 22, 'robot', top=None if arm >= 120 else 'solid')   # 로봇 팔
        s.wrist = (cx, cy, zb + 60 + arm)
