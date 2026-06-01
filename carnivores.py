"""carnivores.py — 육식동물 구체 클래스(사자·치타·하이에나).

담당: 심준서(상호작용 중심 / 육식동물 클래스)
역할: Carnivore 부모를 상속받아, 계획서가 정한 종별 고유 능력을 구현한다.
      - 사자(Lion):   roar()   포효로 주변 동물에게 광역 둔화 디버프
      - 치타(Cheetah): boost()  일정 시간 폭발적으로 가속
      - 하이에나(Hyena): steal() 사자·치타가 노리는 먹이로 달려가 가로챔

공통 추격 로직은 부모 Carnivore._carnivore_behavior 에 있고, 여기서는
'언제 능력을 쓰는가'와 '능력의 효과'만 정의한다(역할 분리).

[생성형 AI 활용] 쿨타임 기반 능력 발동 패턴은 생성형 AI(Claude)의 도움을 받았다.
"""

import random

import physics
from organisms import Carnivore, Herbivore


class Lion(Carnivore):
    """사자 — 초원의 제왕. 포효(roar)로 주변 동물의 발을 묶는다(둔화 디버프)."""

    species = "Lion"
    radius = 16
    ROAR_RADIUS = 170     # 포효가 미치는 범위
    ROAR_SLOW = 36        # 포효에 맞은 동물이 둔화되는 시간(틱)

    def __init__(self, place):
        # 속력 보통, 체력 높음, 공격력 강함, 회복 보통
        super().__init__(place, speed=3.0, hp=120, ap=34, rsp=0.10, energy=60)
        self.roar_rate = 130    # 포효 쿨타임(계획서 속성): 재사용까지 필요한 틱
        self.roar_cd = 0        # 현재 남은 쿨타임
        self._cooldowns = ("roar_cd",)   # 부모의 _tick_timers 가 자동으로 줄여 줄 타이머

    def roar(self, world):
        """포효 — 사거리 안의 '다른' 동물 모두에게 둔화(slow) 디버프를 건다.
        먹이는 느려져 잡기 쉬워지지만, 다른 포식자도 함께 느려지는 양날의 능력."""
        targets = world.within(self.place, self.ROAR_RADIUS,
                               lambda e: e is not self and hasattr(e, "slow_timer") and e.isalive())
        for t in targets:
            t.slow_timer = max(t.slow_timer, self.ROAR_SLOW)
        self.roar_cd = self.roar_rate
        world.log(f"\U0001F981 사자의 포효! 주변 {len(targets)}마리가 둔해졌다")

    def act(self, world):
        # 가까운 먹이를 추격(부모 공통 로직)하면서,
        # 쿨타임이 다 돌았고 사거리 안에 다른 동물이 있으면 포효한다.
        self._carnivore_behavior(world)
        # 사냥 중(target 존재)이고 쿨타임이 돌았으며 사거리에 먹이가 있을 때만 포효한다.
        if self.target is not None and self.roar_cd == 0:
            near = world.within(self.place, self.ROAR_RADIUS,
                                lambda e: e is not self and isinstance(e, Herbivore) and e.isalive())
            if near:
                self.roar(world)


class Cheetah(Carnivore):
    """치타 — 가장 빠른 사냥꾼. 도약(boost)으로 잠깐 폭발적으로 가속한다."""

    species = "Cheetah"
    radius = 13
    BOOST_DURATION = 24   # 가속 지속 시간(틱)
    BOOST_TRIGGER = 130   # 먹이가 이 거리보다 멀면 도약으로 거리를 좁힌다
    # ※ 치타는 모든 먹이보다 빨라 추격 중 대부분 가까운 거리를 유지하므로, 트리거 거리가
    #   너무 높으면(예: 220) 도약 조건이 거의 성립하지 않는다. 추격 중 실제로 자주 발동되도록
    #   세부 추격 거리(seek 사거리 안)에서 잡히는 값으로 낮췄다.

    def __init__(self, place):
        # 속력 매우 빠름, 체력 낮음, 공격력 보통
        super().__init__(place, speed=4.6, hp=80, ap=26, rsp=0.10, energy=60)
        self.boost_rate = 150   # 고속이동 쿨타임(계획서 속성)
        self.boost_cd = 0
        self._cooldowns = ("boost_cd",)

    def boost(self, world):
        """도약 — 일정 시간 동안 이동 속력이 크게 빨라진다(boost_timer 사용).
        실제 속력 증가는 Animal.effective_speed 가 boost_timer 를 보고 처리한다."""
        self.boost_timer = self.BOOST_DURATION
        self.boost_cd = self.boost_rate
        world.log("\U0001F406 치타가 폭발적으로 가속했다!")

    def act(self, world):
        self._carnivore_behavior(world)
        # 노리는 먹이가 멀리 있고 쿨타임이 다 돌았으면 도약으로 추격 속도를 높인다.
        if (self.boost_cd == 0 and self.target is not None
                and self.place.distance_to(self.target.place) > self.BOOST_TRIGGER):
            self.boost(world)


class Hyena(Carnivore):
    """하이에나 — 직접 사냥보다, 사자·치타가 노리는 먹이로 끼어들어 가로채는 데 능하다.
    계획서 속성 steal_prb(먹이를 뺏을 수 있는 확률)을 가진다."""

    species = "Hyena"
    radius = 13
    JOIN_PROB = 0.8       # 진행 중인 사냥에 끼어들 확률

    def __init__(self, place):
        super().__init__(place, speed=3.4, hp=85, ap=18, rsp=0.10, energy=55)
        self.steal_prb = 0.65   # 먹이를 가로챌 확률(계획서 속성)

    def steal(self, prey, world) -> bool:
        """약탈 — 사자·치타가 막 잡은 먹이를 steal_prb 확률로 가로챈다.
        성공하면 하이에나가 그 먹이를 먹어 기력/체력을 얻는다.
        (호출 시점 판단은 interactions.resolve_predation 이 담당)"""
        if random.random() < self.steal_prb:
            self.energy = min(100.0, self.energy + 30)
            self.eat(40)
            world.log("\U0001F43A 하이에나가 사냥감을 가로챘다!")
            return True
        return False

    def act(self, world):
        # 배가 부르면 하이에나도 쉰다(사냥/약탈 압력을 줄여 균형을 맞춘다).
        if self.hunger < 35:
            self.target = None
            self.vel = physics.wander(self.vel, self.effective_speed * 0.5)
            return
        # ① 사자/치타 중 '지금 실제로 먹이를 쫓고 있는' 사냥꾼을 찾는다.
        #    산만(distract)·기절(stun) 상태인 사냥꾼은 추격을 멈췄는데도 옛 표적(target)이
        #    남아 있을 수 있으므로 제외한다(엉뚱한 먹이로 유인되는 것을 막음).
        hunter = world.nearest(
            self.place,
            lambda e: isinstance(e, (Lion, Cheetah)) and e.isalive()
            and getattr(e, "target", None) is not None and e.target.isalive()
            and e.distract_timer <= 0 and e.stun_timer <= 0)
        # ② 높은 확률로 그 사냥꾼의 먹이로 달려가 가로챌 기회를 노린다.
        if hunter is not None and random.random() < self.JOIN_PROB:
            self.target = hunter.target
            self.vel = physics.seek(self.place, hunter.target.place, self.effective_speed)
        else:
            # ③ 끼어들 사냥이 없으면 스스로 가까운 먹이를 사냥한다(부모 공통 로직).
            self._carnivore_behavior(world)
