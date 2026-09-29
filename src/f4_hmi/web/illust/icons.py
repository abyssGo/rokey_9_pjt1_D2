# 숫자 패널용 작은 아이콘 — 96 × 96 등각
import math
from iso import Scene, shade, container, ACC, REUSE

def _s(pid, oy=64, k=.62):
    return Scene(pid, 96, 96, 48, oy, k=k)

def bowl(pid):
    s = _s(pid, 70, .7); s.shadow(0, 0, 0, 40, op=.45); container(s, 'BOWL', 0, 0, 0); return s.svg('그릇')

def cup(pid):
    s = _s(pid, 84, .56); s.shadow(0, 0, 0, 34, op=.45); container(s, 'CUP', 0, 0, 0); return s.svg('컵')

def crate(pid):
    s = _s(pid, 66, .5)
    x0, x1, y0, y1, h = -60, 60, -50, 50, 44
    s.shadow(0, 0, 0, 66, op=.45)
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (x0, y0, h)])}" fill="{shade("amber", .55)}"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x0, y1, 0), (x0, y1, h), (x0, y0, h)])}" fill="{shade("amber", .68)}"/>')
    s.vessel(0, 0, 2, 32, 32, 40, mat=REUSE, flange=5, foot=22)
    s.raw(f'<polygon points="{s.pts([(x0, y1, 0), (x1, y1, 0), (x1, y1, h), (x0, y1, h)])}" fill="{shade("amber", .8)}"/>')
    s.raw(f'<polygon points="{s.pts([(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)])}" fill="{shade("amber", .55)}"/>')
    for face in ([(x0, y1, 14), (x1, y1, 14), (x1, y1, 26), (x0, y1, 26)], [(x1, y0, 14), (x1, y1, 14), (x1, y1, 26), (x1, y0, 26)]):
        s.raw(f'<polygon points="{s.pts(face)}" fill="#161616" fill-opacity=".85"/>')
    return s.svg('격리')

def sponge(pid):
    s = _s(pid, 66, .95)
    s.shadow(0, 0, 0, 30, op=.45)
    s.rbox(0, 0, 0, 24, 24, 8, 'scrub', ang=-10)
    s.rbox(0, 0, 8, 24, 24, 20, 'sponge', ang=-10)
    for i in range(10):
        a = i * 2.4; r = 6 + i * 1.5
        X, Y = s.P(r * math.cos(a), r * math.sin(a), 28)
        s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="1.6" ry="1" fill="{shade("sponge", .55)}"/>')
    return s.svg('수세미')

def soap(pid):
    s = _s(pid, 76, .62)
    s.shadow(0, 0, 0, 50, op=.45)
    s.cyl(0, 0, 0, 44, 70, 46, 'glass', top=None, alpha=.35)
    s.cyl(0, 0, 0, 42, 54, 43.5, 'water', top=None, alpha=.7, outline=False)
    X, Y, rx, ry = s.ell(0, 0, 54, 43.5)
    s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#eaf5ff"/>')
    for bx, by, r in ((X - 14, Y - 2, 6), (X + 6, Y + 3, 7), (X + 20, Y - 4, 4.5), (X - 4, Y - 10, 4), (X + 14, Y - 24, 3.5), (X - 20, Y - 30, 3)):
        s.raw(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r}" fill="#fff" fill-opacity=".45" stroke="#fff" stroke-width="1.2"/>')
    Xg, Yg, rxg, ryg = s.ell(0, 0, 70, 46)
    s.raw(f'<ellipse cx="{Xg:.1f}" cy="{Yg:.1f}" rx="{rxg:.1f}" ry="{ryg:.1f}" fill="none" stroke="#dff0ff" stroke-width="1.5"/>')
    return s.svg('세제')

def tank(pid):
    s = _s(pid, 62, .52)
    x0, x1, y0, y1, zt, zw = -66, 66, -50, 50, 58, 42
    s.shadow(0, 0, 0, 70, op=.45)
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x1, y0, 0), (x1, y0, zt), (x0, y0, zt)])}" fill="{shade("glass", .45)}" fill-opacity=".55"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x0, y1, 0), (x0, y1, zt), (x0, y0, zt)])}" fill="{shade("glass", .6)}" fill-opacity=".55"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, zw), (x1, y0, zw), (x1, y1, zw), (x0, y1, zw)])}" fill="{shade("water", .85)}" fill-opacity=".8"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y1, 0), (x1, y1, 0), (x1, y1, zw), (x0, y1, zw)])}" fill="{shade("water", .7)}" fill-opacity=".85"/>')
    s.raw(f'<polygon points="{s.pts([(x1, y0, 0), (x1, y1, 0), (x1, y1, zw), (x1, y0, zw)])}" fill="{shade("water", .5)}" fill-opacity=".85"/>')
    s.raw(f'<polyline points="{s.pts([(x0, y1, zt), (x1, y1, zt), (x1, y0, zt), (x0, y0, zt), (x0, y1, zt)])}" fill="none" stroke="#dff0ff" stroke-width="1.5"/>')
    X, Y, rx, ry = s.ell(0, 0, zw, 20)
    for m, op in ((1, .9), (1.6, .5)):
        s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx * m:.1f}" ry="{ry * m:.1f}" fill="none" stroke="#fff" stroke-opacity="{op}" stroke-width="1.4"/>')
    return s.svg('헹굼 담금')

def bin_icon(pid):
    """잔반통 — 털기 장면(scenes.SHAKE)과 같은 통(재질 'bin') 안에 잔반이 쌓여 있다. 소모품 칸의 잔반통 줄과 잔반통 알림창에 쓴다"""
    from scenes import food
    s = _s(pid, 74, .62)
    s.shadow(0, 0, 0, 50, op=.45)
    rim = s.vessel(0, 0, 0, 40, 56, 48, mat='bin', wall=4)
    X, Y, rx, ry = rim
    s.raw(f'<g {s.clip_open(rim)}>')
    food(s, [(X - 20, Y + 8, 4.5), (X - 6, Y + 12, 5), (X + 10, Y + 10, 4.5), (X + 24, Y + 6, 3.5), (X - 12, Y + 2, 3.5),
             (X + 2, Y + 4, 4), (X + 16, Y + 1, 3), (X - 26, Y + 1, 3), (X + 5, Y + 16, 3.5), (X - 1, Y - 2, 3)])
    s.raw('</g>')
    return s.svg('잔반통')

def timer(pid):
    g1, g2 = f'{pid}-a', f'{pid}-b'
    return (f'<svg viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="사이클 타임"><defs>'
            f'<linearGradient id="{g1}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f1f4f8"/><stop offset="1" stop-color="#7d8898"/></linearGradient>'
            f'<radialGradient id="{g2}" cx=".4" cy=".35" r=".7"><stop offset="0" stop-color="#2c3541"/><stop offset="1" stop-color="#11161d"/></radialGradient>'
            f'<filter id="{pid}-f"><feGaussianBlur stdDeviation="3"/></filter></defs>'
            f'<ellipse cx="50" cy="88" rx="26" ry="5" fill="#000" fill-opacity=".45" filter="url(#{pid}-f)"/>'
            f'<rect x="42" y="6" width="12" height="10" rx="3" fill="url(#{g1})"/><rect x="70" y="16" width="9" height="8" rx="2" transform="rotate(40 74 20)" fill="url(#{g1})"/>'
            f'<circle cx="48" cy="52" r="33" fill="url(#{g1})"/><circle cx="48" cy="52" r="27" fill="url(#{g2})"/>'
            f'<path d="M48 52 L48 30 A22 22 0 0 1 67.1 41 Z" fill="{ACC}" fill-opacity=".85"/>'
            + ''.join(f'<line x1="{48 + 23 * math.sin(math.radians(a)):.1f}" y1="{52 - 23 * math.cos(math.radians(a)):.1f}" x2="{48 + 26 * math.sin(math.radians(a)):.1f}" y2="{52 - 26 * math.cos(math.radians(a)):.1f}" stroke="#93a0b3" stroke-width="2"/>' for a in range(0, 360, 30))
            + '<line x1="48" y1="52" x2="61" y2="38" stroke="#fff" stroke-width="3" stroke-linecap="round"/><circle cx="48" cy="52" r="3.5" fill="#fff"/></svg>')

def pallet_icon(pid):
    s = _s(pid, 60, .21)
    s.shadow(0, 0, 0, 190, op=.4, squash=.6)
    s.box(-180, -105, 0, 360, 210, 12, 'rack')
    s.box(-180, -105, 12, 360, 6, 30, 'rack'); s.box(-180, -105, 12, 6, 210, 30, 'rack')
    for x in (45.5, 135.5):
        s.standing_bowl(x, 0, 13)
    for x, y in ((-48.5, -48.5), (-131, 55.5)):
        container(s, 'CUP', x, y, 12)
    s.box(-180, 99, 12, 360, 6, 30, 'rack'); s.box(174, -105, 12, 6, 210, 30, 'rack')
    return s.svg('팔레트')

ALL = {'bowl': bowl, 'cup': cup, 'crate': crate, 'sponge': sponge, 'soap': soap, 'tank': tank, 'bin': bin_icon, 'timer': timer, 'pallet': pallet_icon}
