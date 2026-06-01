"""disaster.py — 사용자 재난재해(거대한 트랙터).

담당: 홍순율(GUI · 물리엔진 · 종료 조건)
역할: 계획서의 종료 조건 '거대한 트랙터 등 인간의 기계가 나타나 초원을 완전히
      밀어버린다'를 구현한다. 사용자가 키([D])를 누르면 트랙터 무리가 왼쪽 끝에서
      나타나 오른쪽으로 직진하며, 닿는 모든 동·식물을 밀어버린다(제거).
      트랙터가 화면을 가로질러 모두 지나가면 생태계가 끝난다.

이유: 단순 객체 생성으로 끝나지 않고 '시간의 흐름 → 변화 → 종료'가 한 흐름으로
      관찰되도록, 종료를 '한순간의 스위치'가 아니라 화면을 가로지르는 사건으로 만든다.

[생성형 AI 활용] 트랙터 무리의 배치/진행 로직은 생성형 AI(Claude)의 도움을 받았다.
"""

import math

import config
import physics
from organisms import Entity
from vector import Vector2


class Tractor(Entity):
    """초원을 밀어버리는 트랙터. 오른쪽으로 직진하며 닿는 생물을 제거한다."""

    species = "Tractor"
    radius = 34
    SPEED = 5.0      # 오른쪽으로 나아가는 속력(픽셀/틱)
    CRUSH = 48       # 이 거리 안의 생물은 깔려 사라진다

    def __init__(self, place):
        super().__init__(place)
        self.vel = Vector2(self.SPEED, 0)   # 오른쪽으로만 이동

    def update(self, world):
        # 1) 오른쪽으로 등속 직진한다(트랙터는 경계에 막히지 않고 화면을 통과해 나간다).
        #    동물(organisms.Animal.move)은 physics.integrate+clamp_to_bounds 로 움직이지만,
        #    트랙터는 등속이고 경계 처리도 필요 없어 매 틱 속도만큼 직접 더한다
        #    (DT=1.0 이라 integrate 와 결과가 같다 — 의도적 단순화).
        self.place = self.place + self.vel
        # 2) 으깨기: 충돌 반경 안의 동·식물을 모두 제거한다(트랙터끼리는 제외).
        for e in world.entities:
            if e is self or e.species == "Tractor" or not e.alive:
                continue
            if physics.within_range(self.place, e.place, self.CRUSH):
                e.alive = False
        # 3) 화면 오른쪽 끝을 완전히 지나가면 트랙터 자신도 사라진다.
        if self.place.x > config.WORLD_W + self.radius:
            self.alive = False


def spawn_tractors(world):
    """왼쪽 끝에 트랙터 무리를 세로로 늘어세워 초원 전체 높이를 덮게 만든다.
    트랙터들이 함께 오른쪽으로 진격하면 초원이 통째로 밀려나간다."""
    # 높이를 빈틈없이 덮도록, 트랙터의 으깨기 지름 간격으로 세로로 배치한다.
    count = math.ceil(config.WORLD_H / (Tractor.CRUSH * 1.6))
    gap = config.WORLD_H / count
    for i in range(count):
        y = gap * (i + 0.5)
        # 화면 왼쪽 바깥(x 음수)에서 출발해 곧 화면 안으로 진입한다.
        world.spawn(Tractor(Vector2(-Tractor.radius, y)))
