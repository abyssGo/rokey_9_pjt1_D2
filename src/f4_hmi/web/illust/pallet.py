# 팔레트 입체 그림 — 배치 그림 그대로(위에서 본 배치: 왼쪽 컵 칸[컵 1 오른쪽 위 · 컵 2 왼쪽 아래] · 가운데 그릇 2 · 오른쪽 그릇 1)
#   위에서 본 (u 오른쪽, v 아래) → 3D (x = u − 180, y = v − 105). 칸 상태: 'done'(적재됨) | 'now'(넣는 중) | 'empty'(비어 있음)
#   화면(Pallet)은 칸마다 상태에 맞는 조각을 골라 아래 ORDER 순서(뒤 → 앞)로 겹친다 — 조각은 build.py 가 palletArt.js 로 만든다.
from iso import Scene, shade, container, CUP, ACC

OK, DIM = '#4cc38a', '#93a0b3'
PW, PH = 620, 440
CROP = (50, 16, 520, 416)                                          # 보여 줄 부분 — 둘레의 빈 여백을 뺀다
FLOOR = 10
SLOTS = {  # 칸 이름 → (종류, 넣는 순서 번호, x, y)
    'BOWL-1': ('BOWL', 1, 135.5, 0),
    'BOWL-2': ('BOWL', 2, 45.5, 0),
    'CUP-1': ('CUP', 3, -48.5, -48.5),
    'CUP-2': ('CUP', 4, -131, 55.5),
}
DIVIDERS = {'DIV-1': 0.5, 'DIV-2': 90.5}
ORDER = ['CUP-1', 'CUP-2', 'DIV-1', 'BOWL-2', 'DIV-2', 'BOWL-1']      # 그리는 순서 — 뒤에 있는 것부터
STATES = ('done', 'now', 'empty')


def _scene(pid):
    s = Scene(pid, PW, PH, 310, 272, k=1.0)
    s.badges = []
    return s

def _frag(s):
    return f'<g><defs>{"".join(s.defs)}</defs>{"".join(s.out)}</g>'

def _badge(X, Y, st, n):
    fill, stroke, fg, txt = {'done': ('#14301f', OK, OK, '✓'), 'now': ('#1a2742', ACC, ACC, str(n)), 'empty': ('#222a35', '#56657a', DIM, str(n))}[st]
    return (f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="15" fill="{fill}" stroke="{stroke}" stroke-width="2.5"/>'
            f'<text x="{X:.1f}" y="{Y + 5.5:.1f}" text-anchor="middle" font-family="IBM Plex Sans KR, system-ui, sans-serif" font-size="15" font-weight="700" fill="{fg}">{txt}</text>')

def _footprint(s, kind, x, y, st):
    col = ACC if st == 'now' else '#c9d3e0'
    fill = f' fill="{ACC}" fill-opacity=".22"' if st == 'now' else ' fill="none"'
    if kind == 'BOWL':
        pts = s.pts([(x - 22, y - 60, FLOOR), (x + 22, y - 60, FLOOR), (x + 22, y + 60, FLOOR), (x - 22, y + 60, FLOOR)])
        s.raw(f'<polygon points="{pts}"{fill} stroke="{col}" stroke-opacity=".8" stroke-width="2" stroke-dasharray="7 6" stroke-linejoin="round"/>')
    else:
        X, Y, rx, ry = s.ell(x, y, FLOOR, 44)
        s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}"{fill} stroke="{col}" stroke-opacity=".8" stroke-width="2" stroke-dasharray="7 6"/>')

def _pins(s, x):
    for y in (-78, -52, 52, 78):
        s.cyl(x, y, FLOOR, 2, FLOOR + 18, 2, 'rack')

def _item(s, kind, x, y, st, n):
    """칸 하나 — 돌려주는 값: 번호표 (X, Y)"""
    lift = 30 if st == 'now' else 0
    if st != 'done':
        _footprint(s, kind, x, y, st)
    if st == 'empty':
        return s.P(x, y, FLOOR + (34 if kind == 'BOWL' else 12))
    if st == 'now':                                                # 넣는 중 = 파란 반투명(유령) + 화살표
        s.raw(f'<g filter="url(#{s.pid}-ghost)">')
    if kind == 'BOWL':
        if st == 'done':
            s.shadow(x, y, FLOOR, 26, op=.45, squash=.7)
        s.standing_bowl(x, y, FLOOR + 1 + lift)
        X, Y = s.P(x + 20, y, FLOOR + 1 + lift + 124)
    else:
        if st == 'done':
            s.shadow(x, y, FLOOR, 36, op=.45)
        container(s, 'CUP', x, y, FLOOR + lift, upside_down=True)      # 팔레트의 컵은 뒤집어 얹는다
        X, Y = s.P(x, y, FLOOR + lift + CUP['h'])
    if st == 'now':
        s.raw('</g>')
        s.arrow([(X, Y - 58), (X, Y - 22)])
        return X + 30, Y - 44
    return X, Y - 26


def base_part():
    s = _scene('pal-base')
    s.shadow(0, 0, -2, 190, op=.38, squash=.62)
    s.box(-180, -105, 0, 360, 210, FLOOR, 'rack')
    for i in range(1, 18):                                         # 바닥 격자
        u = -180 + 360 * i / 18
        (ax, ay), (bx, by) = s.P(u, -105, FLOOR), s.P(u, 105, FLOOR)
        s.raw(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{shade("rack", .74)}" stroke-width="1"/>')
    for i in range(1, 10):
        v = -105 + 210 * i / 10
        (ax, ay), (bx, by) = s.P(-180, v, FLOOR), s.P(180, v, FLOOR)
        s.raw(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{shade("rack", .74)}" stroke-width="1"/>')
    s.box(-180, -105, FLOOR, 360, 5, 26, 'rack')                  # 뒤 벽
    s.box(-180, -105, FLOOR, 5, 210, 26, 'rack')
    return _frag(s)

def divider_part(name):
    s = _scene(f'pal-{name.lower()}')
    x = DIVIDERS[name]
    s.box(x - 2.5, -105, FLOOR, 5, 210, 46, 'rack')               # 칸막이 — 밀어 넣으면 걸리는 벽
    return _frag(s)

def front_part():
    s = _scene('pal-front')
    s.box(-180, 100, FLOOR, 360, 5, 26, 'rack')
    s.box(175, -105, FLOOR, 5, 210, 26, 'rack')
    return _frag(s)

def slot_part(name, st):
    """칸 조각과 번호표 조각"""
    kind, n, x, y = SLOTS[name]
    s = _scene(f'pal-{name.lower()}-{st}')
    s.defs.append(f'<filter id="{s.pid}-ghost"><feColorMatrix type="matrix" values="0.25 0 0 0 0.16  0 0.35 0 0 0.3  0 0 0.45 0 0.62  0 0 0 0.7 0"/></filter>')
    if kind == 'BOWL':
        _pins(s, x - 24)
    X, Y = _item(s, kind, x, y, st, n)
    if kind == 'BOWL':
        _pins(s, x + 24)
    return _frag(s), _badge(X, Y, st, n)

def parts():
    out = {'base': base_part(), 'front': front_part(), 'div': {k: divider_part(k) for k in DIVIDERS}, 'slot': {}, 'badge': {}}
    for name in SLOTS:
        out['slot'][name], out['badge'][name] = {}, {}
        for st in STATES:
            out['slot'][name][st], out['badge'][name][st] = slot_part(name, st)
    return out

def pallet_svg(states, cls='', p=None):
    """칸 상태(그릇 1 · 그릇 2 · 컵 1 · 컵 2 순) → 완성 그림 한 장 — 화면의 Pallet 과 같은 순서로 겹친다"""
    p = p or parts()
    st = dict(zip(['BOWL-1', 'BOWL-2', 'CUP-1', 'CUP-2'], states))
    body = [p['base']]
    body += [p['div'][k] if k.startswith('DIV') else p['slot'][k][st[k]] for k in ORDER]
    body += [p['front']] + [p['badge'][k][st[k]] for k in SLOTS]
    c = f' class="{cls}"' if cls else ''
    return f'<svg{c} viewBox="{" ".join(map(str, CROP))}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="팔레트 적재 상태">{"".join(body)}</svg>'
