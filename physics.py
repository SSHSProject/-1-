"""physics.py — 직접 만든 2D 물리/조향(steering) 엔진.

담당: 홍순율(GUI · 물리엔진)
역할: 게임 엔진/물리 라이브러리를 쓰지 않고, 동물들이 움직이고 부딪치는 데
      필요한 최소한의 물리 계산(이동 적분, 추격/도망 조향, 충돌 판정, 경계 처리,
      넉백)을 "순수 파이썬"으로 구현한다.
이유: "물리엔진도 파이썬으로 직접 구현하라"는 요구사항을 만족하기 위해,
      외부 의존성 없이 Vector2 만 가지고 물리 동작을 만든다.

핵심 아이디어
  - 모든 동물은 위치(place)와 속도(vel)를 가진다.
  - 매 틱마다 "위치 = 위치 + 속도 × DT" 라는 오일러(Euler) 적분으로 움직인다.
  - '어디로 갈지(속도)'는 추격(seek)/도망(flee) 같은 조향 함수가 정해준다.
  - 충돌은 각 개체를 '원(circle)'으로 보고 두 원이 겹치는지로 판단한다(원-원 충돌).

[생성형 AI 활용] 조향(steering) 기법과 경계 반사 처리 아이디어는
                 생성형 AI(Claude)의 도움을 받아 구현하였다.
"""

import math
import random

from vector import Vector2


# ─────────────────────────────────────────────────────────────
# 조향(steering) — '목표 속도 벡터'를 계산해 돌려준다.
# 실제 위치 이동은 integrate() 가 담당하고, 여기서는 방향/속도만 정한다.
# 이렇게 '결정(조향)'과 '실행(적분)'을 나누면 코드가 읽기 쉽고 재사용하기 좋다.
# ─────────────────────────────────────────────────────────────
def seek(place: Vector2, target: Vector2, max_speed: float) -> Vector2:
    """target 지점을 향해 최대 속력으로 다가가는 속도 벡터.
    (target - place) 는 '나에게서 목표로 향하는 방향'이고,
    그 길이를 max_speed 로 맞춰 '그 방향으로 최대 속력' 을 만든다."""
    return (target - place).with_length(max_speed)


def flee(place: Vector2, threat: Vector2, max_speed: float) -> Vector2:
    """위협(threat)으로부터 정반대 방향으로 도망가는 속도 벡터.
    seek 와 방향만 반대이다((place - threat))."""
    return (place - threat).with_length(max_speed)


def wander(vel: Vector2, max_speed: float, jitter: float = 0.45) -> Vector2:
    """뚜렷한 목표가 없을 때의 '어슬렁거리기'.
    현재 진행 방향에 약간의 무작위 회전(jitter)을 더해, 동물이 멈춰 있지 않고
    자연스럽게 배회하도록 한다. 멈춰 있던(속도 0) 경우엔 무작위 방향을 새로 고른다."""
    if vel.length_sq() < 1e-6:
        ang = random.uniform(0, 2 * math.pi)
        return Vector2(math.cos(ang), math.sin(ang)) * max_speed
    # 현재 방향의 각도에 약간의 흔들림을 더해 새 방향을 만든다.
    ang = math.atan2(vel.y, vel.x) + random.uniform(-jitter, jitter)
    return Vector2(math.cos(ang), math.sin(ang)) * max_speed


# ─────────────────────────────────────────────────────────────
# 적분(integration) — 속도를 위치에 실제로 반영한다.
# ─────────────────────────────────────────────────────────────
def integrate(place: Vector2, vel: Vector2, dt: float) -> Vector2:
    """오일러 적분: 새 위치 = 현재 위치 + 속도 × 시간.
    가장 단순한 수치 적분으로, 이 시뮬레이션처럼 정밀도가 크게 중요하지 않은
    경우에 충분하고 계산도 가볍다."""
    return place + vel * dt


def clamp_to_bounds(place: Vector2, vel: Vector2, w: float, h: float,
                    radius: float) -> tuple:
    """초원 경계를 벗어나지 않게 하고, 벽에 닿으면 튕겨 나오게(반사) 한다.
    radius 를 고려해 '몸이 화면 밖으로 삐져나가지' 않도록 안쪽에서 막는다.
    벽에 부딪치면 해당 축의 속도 부호를 뒤집어(반사) 안쪽으로 되돌린다.
    반환값: 보정된 (place, vel).
    참고: 마침 그 축의 속도가 정확히 0이면 그 틱엔 밀어내는 힘이 없지만, 위치는 이미 벽
    안쪽(radius)으로 고정되고 다음 틱에 act()가 속도를 다시 정하므로 벽에 끼이지 않는다."""
    x, y = place.x, place.y
    vx, vy = vel.x, vel.y

    if x < radius:                 # 왼쪽 벽
        x = radius
        vx = abs(vx)               # 오른쪽(양수)으로 튕김
    elif x > w - radius:           # 오른쪽 벽
        x = w - radius
        vx = -abs(vx)              # 왼쪽(음수)으로 튕김

    if y < radius:                 # 위쪽 벽
        y = radius
        vy = abs(vy)
    elif y > h - radius:           # 아래쪽 벽
        y = h - radius
        vy = -abs(vy)

    return Vector2(x, y), Vector2(vx, vy)


# ─────────────────────────────────────────────────────────────
# 충돌/거리 판정
# ─────────────────────────────────────────────────────────────
def is_contact(a_place: Vector2, a_radius: float,
               b_place: Vector2, b_radius: float) -> bool:
    """두 개체가 '닿았는지' 판정한다(원-원 충돌).
    중심 사이 거리가 두 반지름의 합보다 작거나 같으면 두 원이 겹친 것이다.
    sqrt 를 피하려고 거리의 제곱끼리 비교한다(성능 최적화)."""
    rsum = a_radius + b_radius
    return a_place.distance_sq_to(b_place) <= rsum * rsum


def within_range(a_place: Vector2, b_place: Vector2, distance: float) -> bool:
    """두 지점이 distance 안쪽에 있는지(능력 사거리 판정 등)."""
    return a_place.distance_sq_to(b_place) <= distance * distance


def knockback(place: Vector2, source: Vector2, distance: float) -> Vector2:
    """source(밀어내는 쪽)로부터 place 를 distance 만큼 바깥으로 밀어낸 위치.
    기린의 넥스윙, 코끼리의 나무 투척처럼 '상대를 밀쳐내는' 효과에 쓴다.
    같은 위치라 방향이 없으면 무작위 방향으로 밀어 0벡터 오류를 피한다."""
    away = place - source
    if away.length_sq() < 1e-6:
        ang = random.uniform(0, 2 * math.pi)
        away = Vector2(math.cos(ang), math.sin(ang))
    return place + away.with_length(distance)


def separate(place: Vector2, neighbors, desired_gap: float, max_speed: float) -> Vector2:
    """가까운 이웃과 겹치지 않게 하는 '거리두기' 조향 벡터.

    seek/flee 처럼 강한 목표가 아니라, 화면에서 동물이 한 점에 포개지는 것을 줄이는
    보조 힘이다. 가까울수록 더 세게 밀어내고, 멀어질수록 영향이 작아지게 했다.
    이렇게 하면 번식터 주변에 여러 개체가 있어도 서로 살짝 자리를 비켜 주므로
    누가 먹고, 쫓고, 번식하는지 눈으로 구분하기 쉬워진다.
    """
    if max_speed <= 0:
        return Vector2.zero()

    force = Vector2.zero()
    gap_sq = desired_gap * desired_gap
    for other in neighbors:
        away = place - other.place
        d2 = away.length_sq()
        if d2 <= 1e-6 or d2 > gap_sq:
            continue
        dist = math.sqrt(d2)
        # 거리 0에 가까울수록 큰 힘을 주고, desired_gap 에 가까우면 거의 0이 된다.
        strength = (desired_gap - dist) / desired_gap
        force = force + away.with_length(strength)

    if force.length_sq() < 1e-6:
        return Vector2.zero()
    return force.with_length(max_speed)


def clamp_point(place: Vector2, w: float, h: float, radius: float) -> Vector2:
    """한 점을 화면 안쪽으로 고정한다.

    번식 목표 지점이나 새끼 출생 위치는 실제 개체가 아니어서 clamp_to_bounds 를 그대로
    쓸 수 없다. 그래서 위치만 경계 안으로 보정하는 작은 도우미를 따로 둔다.
    """
    x = min(max(place.x, radius), w - radius)
    y = min(max(place.y, radius), h - radius)
    return Vector2(x, y)
