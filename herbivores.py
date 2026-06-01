"""herbivores.py — 초식동물 구체 클래스(토끼·기린·얼룩말·코끼리).

담당: 한시헌(토끼·기린), 심성진(얼룩말·코끼리)
역할: Herbivore 부모를 상속받아 종별 고유 방어 능력을 구현한다.
      - 토끼(Rabbit):   hide()      풀숲에 숨어 일정 시간 포식자를 피함
      - 기린(Giraffe):  neckfight() 넥스윙으로 다가온 포식자를 밀쳐내고 피해를 줌
      - 얼룩말(Zebra):   distract()  일정 확률로 주변 포식자를 산만하게 만듦
      - 코끼리(Elephant): stomp()/tree() 포식자를 짓밟아 기절시키거나 나무를 뽑아 던짐

공통 생존 행동(도망/풀 찾기/배회/번식 게이지)은 부모 Herbivore 가 제공하고,
여기서는 '고유 방어 능력'만 정의한다.

[생성형 AI 활용] 종별 방어 능력 트리거 조건/넉백 효과는 생성형 AI(Claude)의 도움을 받았다.
"""

import random

import physics
from organisms import Herbivore, Carnivore
from plants import Grass
from vector import Vector2


# ── 한시헌 담당 ────────────────────────────────────────────
class Rabbit(Herbivore):
    """토끼 — 약하지만 빠르고, 위험하면 풀숲에 숨는다. 번식이 빠르다."""

    species = "Rabbit"
    radius = 9
    HIDE_DURATION = 60    # 숨어 있는 시간(틱)
    HIDE_RANGE = 130      # 이 거리 안의 풀숲으로만 숨을 수 있다

    def __init__(self, place):
        # 빠른 속력, 낮은 체력, 거의 없는 공격력, 빠른 번식
        super().__init__(place, speed=4.0, hp=45, ap=3, rsp=0.08, rp_rate=0.9)
        self.hide_rate = 90       # 숨기 쿨타임(계획서 속성)
        self.hide_cd = 0
        self.hidden_timer = 0     # >0 이면 숨은 상태(포식자에게 안 보임)
        self._hiding_grass = None  # 지금 숨어 있는 풀(나올 때 rab_num 을 줄이려고 기억)
        self._cooldowns = ("hide_cd", "hidden_timer")

    def hide(self, world, grass):
        """풀숲에 숨는다 — 그 풀로 이동하고, 어느 풀에 숨었는지를 기억한다.
        숨는 동안 hidden_timer 가 켜지고, 포식자는 이 토끼를 표적으로 보지 못한다.
        풀의 토끼 수(rab_num)는 매 틱 world._recount_grass_occupancy 가 실제 숨은 토끼로
        다시 세므로, 여기서 직접 더하거나 빼지 않는다(죽음으로 인한 누수 방지)."""
        self.place = grass.place
        self._hiding_grass = grass
        self.hidden_timer = self.HIDE_DURATION
        self.hide_cd = self.hide_rate
        world.log("\U0001F407 토끼가 풀숲에 숨었다")

    def act(self, world):
        # 숨어 있는 동안은 움직이지 않고 가만히 있는다.
        if self.hidden_timer > 0:
            self.vel = Vector2.zero()
            return

        # 포식자가 가깝고 쿨타임이 다 돌았다면, 비어 있는 근처 풀숲으로 숨는다.
        if self.hide_cd == 0:
            predator = world.nearest(
                self.place, lambda e: isinstance(e, Carnivore) and e.isalive(),
                max_dist=self.flee_radius)
            if predator is not None:
                grass = world.nearest(
                    self.place,
                    lambda e: e.species == "Grass" and not e.eaten and e.alive
                    and e.rab_num < Grass.RAB_CAP,    # 한계(RAB_CAP)까지만 숨을 수 있다
                    max_dist=self.HIDE_RANGE)
                if grass is not None:
                    self.hide(world, grass)
                    return
        # 그 외엔 초식동물 공통 행동(도망/풀 찾기/배회).
        self._herbivore_behavior(world)


# ── 한시헌 담당 ────────────────────────────────────────────
class Giraffe(Herbivore):
    """기린 — 키가 크고 체력이 높다. 넥스윙으로 다가온 포식자를 밀쳐낸다.
    기린끼리 너무 가까우면 일정 확률로 싸움이 난다(interactions 에서 처리)."""

    species = "Giraffe"
    radius = 16
    NECK_RANGE = 95        # 넥스윙이 닿는 거리
    NECK_KNOCKBACK = 70    # 밀려나는 거리
    NECK_DAMAGE = 12       # 포식자에게 주는 피해

    def __init__(self, place):
        super().__init__(place, speed=2.4, hp=140, ap=16, rsp=0.10, rp_rate=0.55)
        self.neckfight_prb = 0.5     # 기린끼리 싸울 확률(계획서 속성)
        self.neckfight_rate = 45     # 싸움/방어 쿨타임(계획서 속성) — 더 자주 방어하도록 단축
        self.neck_cd = 0
        self._cooldowns = ("neck_cd",)

    def neckfight(self, target, world):
        """넥스윙 — 대상을 뒤로 밀쳐낸다. 대상이 포식자면 체력도 깎는다.
        physics.knockback 으로 '나로부터 멀어지는 방향'으로 대상 위치를 밀어낸다."""
        target.place = physics.knockback(target.place, self.place, self.NECK_KNOCKBACK)
        if isinstance(target, Carnivore):
            target.hp -= self.NECK_DAMAGE
            world.log("\U0001F992 기린의 넥스윙! 포식자를 밀어냈다")
        self.neck_cd = self.neckfight_rate

    def act(self, world):
        # 방어: 사거리 안에 포식자가 있고 쿨타임이 돌았으면 넥스윙으로 밀어낸다.
        if self.neck_cd == 0:
            predator = world.nearest(
                self.place, lambda e: isinstance(e, Carnivore) and e.isalive(),
                max_dist=self.NECK_RANGE)
            if predator is not None:
                self.neckfight(predator, world)
                return
        self._herbivore_behavior(world)


# ── 심성진 담당 ────────────────────────────────────────────
class Zebra(Herbivore):
    """얼룩말 — 무리지어 풀을 먹고, 일정 확률로 주변 포식자를 산만하게 만든다."""

    species = "Zebra"
    radius = 12
    DISTRACT_RANGE = 130    # 교란이 미치는 범위
    DISTRACT_DURATION = 40  # 산만해지는 시간(틱)

    def __init__(self, place):
        super().__init__(place, speed=3.6, hp=70, ap=6, rsp=0.10, rp_rate=1.0)
        self.distract_prb = 0.05    # 주변을 산만하게 만들 확률(계획서 속성)

    def distract(self, world):
        """교란 — 주변 포식자에게 distract_timer 를 걸어, 추격 대신 무작위로 움직이게 한다.
        (산만 효과의 실제 처리는 Animal.update 가 distract_timer 를 보고 한다)"""
        targets = world.within(self.place, self.DISTRACT_RANGE,
                               lambda e: isinstance(e, Carnivore) and e.isalive())
        for t in targets:
            t.distract_timer = max(t.distract_timer, self.DISTRACT_DURATION)
        if targets:
            world.log("\U0001F993 얼룩말이 포식자들을 교란했다!")

    def act(self, world):
        # 포식자가 근처에 있을 때 distract_prb 확률로 교란을 시도한다.
        predator = world.nearest(
            self.place, lambda e: isinstance(e, Carnivore) and e.isalive(),
            max_dist=self.flee_radius)
        if predator is not None and random.random() < self.distract_prb:
            self.distract(world)
        self._herbivore_behavior(world)


# ── 심성진 담당 ────────────────────────────────────────────
class Elephant(Herbivore):
    """코끼리 — 거대하고 강하다. 다가온 포식자를 짓밟아(stomp) 기절시키거나,
    나무를 뽑아(tree) 던져 포식자에게 피해를 준다. 도망치지 않는다."""

    species = "Elephant"
    radius = 20

    def __init__(self, place):
        super().__init__(place, speed=1.8, hp=240, ap=30, rsp=0.12, rp_rate=0.32)
        self.stomp_power = 110      # 밟는 범위(계획서 속성)
        self.stun_time = 50         # 포식자를 멈추는 시간(틱)(계획서 속성)
        self.stomp_rate = 110        # (밸런스용 추가) 밟기 쿨타임 — 더 자주 방어
        self.stomp_cd = 0
        self.tree_rate = 200        # 나무 투척 쿨타임(계획서 속성) — 나무 고갈을 막기 위해 길게
        self.tree_cd = 0
        self.tree_damage = 28
        self.tree_grab_range = 140  # 뽑을 나무를 찾는 거리
        self.defend_range = 120     # 이 거리 안에 포식자가 오면 방어 능력을 쓴다
        self._cooldowns = ("stomp_cd", "tree_cd")

    def stomp(self, world):
        """밟기 — 사거리(stomp_power) 안의 포식자들을 stun_time 동안 기절시킨다."""
        targets = world.within(self.place, self.stomp_power,
                               lambda e: isinstance(e, Carnivore) and e.isalive())
        for t in targets:
            t.stun_timer = max(t.stun_timer, self.stun_time)
        self.stomp_cd = self.stomp_rate
        if targets:
            world.log(f"\U0001F418 코끼리가 발을 굴러 포식자 {len(targets)}마리를 멈춰 세웠다!")

    def tree(self, world, predator):
        """나무 투척 — 근처 나무를 하나 뽑아(사라짐) 포식자에게 던져 피해+넉백을 준다.
        근처에 뽑을 나무가 없으면 아무 일도 일어나지 않는다."""
        tree_obj = world.nearest(self.place,
                                 lambda e: e.species == "Tree" and e.alive,
                                 max_dist=self.tree_grab_range)
        if tree_obj is None:
            return False
        tree_obj.alive = False               # 나무를 뽑음 → 사라진다
        predator.hp -= self.tree_damage      # 포식자에게 피해
        predator.place = physics.knockback(predator.place, self.place, 60)  # 뒤로 밀림
        self.tree_cd = self.tree_rate
        world.log("\U0001F418 코끼리가 나무를 뽑아 던졌다!")
        return True

    def act(self, world):
        # 코끼리는 _herbivore_behavior(도망 포함)를 쓰지 않으므로 번식 게이지를 직접 채운다.
        self.reproduce_gauge = min(100.0, self.reproduce_gauge + self.rp_rate)

        predator = world.nearest(
            self.place, lambda e: isinstance(e, Carnivore) and e.isalive(),
            max_dist=self.defend_range)
        if predator is not None:
            # 1순위 밟기(기절), 2순위 나무 투척. 둘 다 쿨타임이면 방어하지 못한다
            # (이때는 사자/치타가 코끼리를 공격 — 계획서 상호작용 그대로).
            if self.stomp_cd == 0:
                self.stomp(world)
                return
            if self.tree_cd == 0 and self.tree(world, predator):
                return

        # 코끼리는 도망치지 않는다. 위협이 없으면 초식 공통 평상시 이동(풀 찾기/나무로 모이기).
        # _herbivore_behavior 대신 _forage_and_gather 를 직접 부르는 이유: 코끼리는 '도망' 단계를
        # 건너뛰어야 하기 때문(거대해서 도망 대신 자리를 지킨다).
        self._forage_and_gather(world, gather_dist=60, speed_factor=0.7)
