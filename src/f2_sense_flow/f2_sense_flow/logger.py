# -*- coding: utf-8 -*-
"""기록 — 용기 1개마다 `records.csv` 에 한 줄 (FLOW-02 · SR-16 · TC-12).

열은 SDD §4.2 데이터 사전 그대로다. 순서·이름을 바꾸면 그 문서도 같이 고친다.

주의: 기록이 실패해도 공정은 멈추지 않는다 — 디스크가 차거나 파일이 잠겨도 용기 처리는
   계속돼야 한다. 그래서 이 안에서 예외를 밖으로 내보내지 않고, 부르는 쪽(flow.py)도
   _guard 를 거쳐 부른다. 대신 처음 한 번은 경고를 남긴다(조용히 사라지면 안 된다).

주의: 경로는 상대경로다(AGENTS.md 규칙 7) — `flow.records_path` 의 기본값 `records.csv` 는
   프로그램을 띄운 자리 기준이다. 런치로 띄우면 런치를 부른 자리에 생긴다.
"""
import csv
import os
import time

__all__ = ['COLUMNS', 'Records']

# SDD §4.2 — 이 순서 그대로
COLUMNS = [
    'ts',                # 용기 1개가 끝난 시각 (ISO 8601, 초까지)
    'kind',              # BOWL / CUP
    'zone_id',           # 집어 온 반납 구역
    'attempts',          # 탐색 파지 시도 슬롯 수 (f1.pick)
    'rack_slot',         # 넣은 팔레트 칸 (실패면 빈 칸)
    'weight_before_g',   # 털기 전 잔반 무게 (f2.leftover_loop)
    'weight_after_g',    # 털기 뒤 잔반 무게
    'leftover_rounds',   # 털기 반복 횟수
    'seat_offset_mm',    # 스펀지 홈 안착에서 탐색으로 보정된 거리 (f1.place)
    'wipe_duration_s',   # 닦은 시간 (f3.wipe_*)
    'force_log_path',    # 힘 로그 CSV 상대경로
    'result',            # DONE / ISOLATED / ERROR / SKIPPED
    'code',              # 마지막 실패 코드 (성공이면 OK)
    'duration_s',        # 용기 1개에 걸린 시간
]


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


class Records:
    """`records.csv` 에 한 줄씩 붙여 쓴다.

    파일이 없거나 비어 있으면 머리줄을 먼저 쓴다. 이어 쓰기라 프로그램을 다시 띄워도
    앞 기록이 지워지지 않는다(시연 날 여러 번 돌린다).
    """

    def __init__(self, path, log=None):
        self.path = str(path)
        self._log = log
        self._warned = False        # 같은 경고를 매 줄마다 내지 않는다

    def write(self, row):
        """row(dict) 를 한 줄 붙여 쓴다. 성공하면 True.

        COLUMNS 에 없는 키는 버리고, 없는 값은 빈 칸으로 둔다 —
        열 개수는 항상 같아야 나중에 읽는 쪽(발표 자료·KPI)이 깨지지 않는다.
        """
        try:
            need_header = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
            with open(self.path, 'a', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction='ignore')
                if need_header:
                    w.writeheader()
                w.writerow({k: row.get(k, '') for k in COLUMNS})
            return True
        except OSError as e:                     # noqa: BLE001 — 기록 실패로 공정을 멈추지 않는다
            if not self._warned and self._log:
                self._warned = True
                self._log.warn(f'기록을 못 남긴다 ({self.path}) — {e}. 공정은 계속한다')
            return False


class Consumables:
    """소모품 카운트가 임계에 닿으면 알린다 (FR-14 · SDD §5.5 "임계 도달 시 경고").

    주의: 세는 것은 Flow 가 한다(sponge_uses·soap_dips — /flow/state 로 HMI 에 나간다).
       여기는 임계 판정만 한다. 넘어도 공정을 멈추지 않는다 — 소모품 교체는 사람 일이고,
       한가운데서 멈추면 용기를 든 채 서 있게 된다.
    """

    def __init__(self, limits, log=None):
        self._max = dict(limits or {})
        self._log = log
        self._hit = set()           # 이미 알린 항목 — 용기마다 다시 외치지 않는다

    @staticmethod
    def limit_key(name):
        """카운터 이름 → 설정 키.  sponge_uses → sponge_max_uses · soap_dips → soap_max_dips

        첫 `_` 자리에 `max` 를 끼운다. 카운터(/flow/state 의 FlowState 필드)와 설정
        (flow.consumables)의 이름이 원래 이렇게 짝지어져 있다 — 한쪽을 바꾸면 여기도 본다.
        """
        head, _, tail = str(name).partition('_')
        return f'{head}_max_{tail}' if tail else f'{head}_max'

    def check(self, counts):
        """counts(dict) 를 임계와 견준다. 이번에 새로 넘은 항목 이름들을 돌려준다."""
        newly = []
        for name, used in (counts or {}).items():
            limit = self._max.get(self.limit_key(name))
            if limit is None or name in self._hit:
                continue
            if used >= int(limit):
                self._hit.add(name)
                newly.append(name)
                if self._log:
                    self._log.warn(f'소모품 임계 도달 — {name} {used}/{limit}. 교체를 확인하세요'
                                   ' (공정은 계속합니다)')
        return newly
