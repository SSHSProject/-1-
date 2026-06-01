"""organisms.py — 생태계 구성원의 '부모(Parent) 클래스' 계층.

담당: 심성진(전체 코드 관리 / 공통 부모 설계)
역할: 계획서의 공통 부모 설계표를 그대로 코드로 옮긴 핵심 모듈.
      Animal(동물) / Herbivore(초식) / Carnivore(육식) / Plant(식물) 의
      공통 속성과 공통 메서드를 정의한다. 구체적인 동물(사자·토끼 등)은
      이 클래스들을 상속(extends)받아 자기만의 능력을 덧붙인다.

상속 구조(계획서 그대로):
      Entity(엔진용 최상위)
        ├─ Animal(animal)            ← speed, hp, ap, rsp, place, hunger / move, isalive, eat
        │     ├─ Herbivore(herbivores) ← rp_rate / reproduce
        │     └─ Carnivore(carnivores) ← energy / attack
        └─ Plant(plant)              ← eaten / grow

  ※ Entity 는 계획서에는 없지만, 물리엔진·렌더링이 동물과 식물을 '똑같은 방식으로'
    다루기 위해 홍순율이 추가한 엔진용 최상위 부모이다(공통 위치/충돌/그리기 정보).

OOP 설계 의도
  - '템플릿 메서드 패턴': Animal.update() 가 매 틱 공통 처리(쿨타임·허기·회복·이동·죽음)를
    수행하고, 종마다 다른 '행동 결정'은 추상 메서드 act() 에 맡긴다.
    => 공통 흐름은 부모가, 다른 부분만 자식이 채우므로 코드 중복이 줄고 구조가 명확하다.

[생성형 AI 활용] 클래스 계층/템플릿 메서드 패턴 설계는 생성형 AI(Claude)의 도움을 받았다.
"""

import math
import random
from abc import ABC, abstractmethod

import config
import physics
from vector import Vector2


class Entity(ABC):
    """모든 구성원(동물·식물·트랙터)의 엔진용 최상위 부모.
    물리엔진과 GUI 가 '위치(place)·크기(radius)·그리기 정보'를 일관되게 다루도록
    공통 인터페이스를 제공한다."""

    species = "Entity"   # 종 이름(영문 키). 팔레트/개체수 집계의 식별자로 쓴다.
    radius = 10          # 충돌·렌더링에 쓰는 반지름(원으로 취급)

    def __init__(self, place: Vector2):
        self.place = place          # 2D 위치(계획서의 공통속성 'place')
        self.alive = True           # 살아있음/유효함 여부. 죽거나 제거되면 False.
        emoji, color = config.PALETTE.get(self.species, ("?", "#000000"))
        self.emoji = emoji          # 화면 표시용 이모지
        self.color = color          # 화면 표시용 외곽선 색

    @abstractmethod
    def update(self, world):
        """매 틱마다 월드가 호출하는 갱신 메서드. 자식이 반드시 구현한다."""
        raise NotImplementedError


# ════════════════════════════════════════════════════════════════════════
# Animal  (계획서의 부모 클래스 'animal')
# 공통속성: speed, hp, ap, rsp, place, hunger(추상)
# 공통메서드: move(), isalive(), eat()
# ════════════════════════════════════════════════════════════════════════
class Animal(Entity):
    """모든 동물의 부모. 이동·허기·체력회복·죽음 같은 '생물의 공통 생존 로직'을 담는다.
    hunger(허기)는 계획서에서 '추상' 으로 표시되어 있다 → 초식/육식이 의미를 달리하므로
    여기서 구체 수치만 두고, 어떻게 행동에 반영할지는 자식(act)에게 맡긴다."""

    def __init__(self, place, speed, hp, ap, rsp):
        super().__init__(place)
        # ── 계획서가 명시한 animal 공통속성 ──
        self.speed = speed      # 최대 이동 속력(픽셀/틱)
        self.max_hp = hp        # 최대 체력
        self.hp = hp            # 현재 체력
        self.ap = ap            # 공격력(attack power)
        self.rsp = rsp          # 회복 속도(recovery speed): 매 틱 회복하는 체력량
        self.hunger = 0.0       # 허기 0~100. 시간이 지날수록 올라간다(추상 속성의 구체값).

        # ── 이동/상태 효과용 내부 상태 ──
        self.vel = Vector2.zero()   # 현재 속도 벡터(물리엔진이 사용)
        self.stun_timer = 0         # >0 이면 기절(코끼리 stomp 등)로 못 움직임
        self.boost_timer = 0        # >0 이면 가속(치타 boost) 상태
        self.slow_timer = 0         # >0 이면 둔화(사자 roar 디버프) 상태
        self.distract_timer = 0     # >0 이면 산만(얼룩말 distract): 무작위로 움직임
        self.hunger_rate = 0.18     # 틱당 허기 증가량(종마다 자식에서 조정 가능)
        self.repro_cooldown = 0     # >0 이면 방금 번식해서 다시 번식할 수 없는 휴식 시간
        self.disperse_timer = 0     # >0 이면 출산 직후 번식터에서 잠깐 흩어진다

        # 나무 중심으로 전부 돌진하면 개체가 겹친다. 그래서 각 동물에게 나무 둘레의
        # 선호 각도/거리와 선호 나무를 둬서, 같은 번식터를 쓰더라도 서로 다른 자리를 잡게 한다.
        self._gather_tree = None
        self._gather_angle = random.uniform(0, 2 * math.pi)
        self._gather_ring_jitter = random.uniform(-10.0, 10.0)

    # ── 계획서 공통메서드: isalive() ─────────────────────
    def isalive(self) -> bool:
        """살아 있는지 여부. 체력이 0 이하이면 죽은 것으로 본다."""
        return self.alive and self.hp > 0

    # ── 계획서 공통메서드: eat() ─────────────────────────
    def eat(self, amount: float):
        """먹이를 먹어 체력을 회복하고 허기를 낮춘다.
        체력은 최대치를 넘지 않고, 허기는 0 밑으로 내려가지 않게 막는다."""
        self.hp = min(self.max_hp, self.hp + amount)
        self.hunger = max(0.0, self.hunger - amount)

    # ── 상태효과를 반영한 '실효 속력' ───────────────────
    @property
    def effective_speed(self) -> float:
        """둔화/가속 같은 상태효과까지 반영한 실제 이동 속력.
        기절 중이면 0(못 움직임), 둔화면 절반, 가속이면 1.8배.
        배율 0.5/1.8 은 사자 포효(둔화)·치타 도약(가속)의 효과가 눈에 띄게 체감되도록
        고른 밸런스 값이다(너무 작으면 능력이 무의미, 너무 크면 게임이 한쪽으로 쏠림)."""
        if self.stun_timer > 0:
            return 0.0
        s = self.speed
        if self.slow_timer > 0:
            s *= 0.5     # 사자 포효 둔화: 절반 속도
        if self.boost_timer > 0:
            s *= 1.8     # 치타 도약 가속: 1.8배 속도
        return s

    # ── 계획서 공통메서드: move() ────────────────────────
    def move(self):
        """물리엔진을 이용해 현재 속도(vel)대로 한 틱 이동하고, 경계를 처리한다.
        '어디로 갈지(vel)' 는 act() 가 미리 정해 두고, move() 는 그것을 실제 위치에
        반영(적분)만 한다 — 결정과 실행의 분리."""
        if self.stun_timer > 0:
            return  # 기절 상태면 이동하지 않는다.
        self.place = physics.integrate(self.place, self.vel, config.DT)
        self.place, self.vel = physics.clamp_to_bounds(
            self.place, self.vel, config.WORLD_W, config.WORLD_H, self.radius)

    @abstractmethod
    def act(self, world):
        """종마다 다른 '행동 결정'(어디로 갈지, 어떤 능력을 쓸지).
        여기서 self.vel 을 정하고 고유 능력(포효·도약 등)을 발동한다.
        실제 위치 이동은 update() 가 move() 로 처리한다."""
        raise NotImplementedError

    # ── 템플릿 메서드: 매 틱 공통 처리 흐름 ──────────────
    def update(self, world):
        """매 틱 공통 생존 처리. (자식은 act()만 채우면 된다)
        순서: 타이머 감소 → 허기/굶주림 → 종별 행동 결정(act) → 이동 → 죽음 판정."""
        # 1) 상태효과 타이머와 능력 쿨타임을 한 틱씩 줄인다.
        self._tick_timers()

        # 2) 허기 증가. 허기가 가득 차면 굶어서 체력이 깎인다(굶주림).
        self.hunger = min(100.0, self.hunger + self.hunger_rate * config.DT)
        if self.hunger >= 100.0:
            self.hp -= 0.4
        elif self.hunger < 55.0:
            # 배가 어느 정도 차 있으면 회복 속도(rsp)만큼 체력을 회복한다.
            self.hp = min(self.max_hp, self.hp + self.rsp)

        # 3) 종별 행동 결정. 산만(distract) 상태면 본래 의도 대신 무작위로 움직인다.
        if self.distract_timer > 0:
            self.vel = physics.wander(self.vel, self.effective_speed, jitter=1.2)
        else:
            self.act(world)

        # 4) 결정된 속도대로 실제 이동.
        self.move()

        # 5) 죽음 판정.
        if self.hp <= 0:
            self.alive = False

    def _tick_timers(self):
        """모든 카운트다운 타이머를 1씩 줄인다(0 미만으로는 안 내려감).
        쿨타임/상태효과를 가진 동물이 많아, 줄여야 할 타이머를 모아서 처리한다."""
        for name in ("stun_timer", "boost_timer", "slow_timer", "distract_timer",
                     "repro_cooldown", "disperse_timer"):
            v = getattr(self, name)
            if v > 0:
                setattr(self, name, v - 1)
        # 자식이 추가로 등록한 쿨타임 타이머들도 함께 감소시킨다.
        for name in getattr(self, "_cooldowns", ()):
            v = getattr(self, name)
            if v > 0:
                setattr(self, name, v - 1)


# ════════════════════════════════════════════════════════════════════════
# Herbivore  (계획서의 부모 클래스 'herbivores')
# 공통속성: hunger, rp_rate(번식 게이지가 차는 속도)
# 공통메서드: reproduce()
# ════════════════════════════════════════════════════════════════════════
class Herbivore(Animal):
    """초식동물의 부모. 풀을 먹어 살고, 포식자에게서 도망치며, 번식한다.
    공통 행동 흐름(도망 → 풀 찾기 → 배회)은 여기서 정의하고,
    각 종(토끼·기린 등)은 자기 고유 능력만 덧붙인다."""

    def __init__(self, place, speed, hp, ap, rsp, rp_rate):
        super().__init__(place, speed, hp, ap, rsp)
        self.rp_rate = rp_rate          # 번식 게이지가 차는 속도(계획서 속성)
        self.reproduce_gauge = 0.0      # 0~100. 100이 되면 나무 근처에서 번식 가능.
        self.flee_radius = 150          # 이 거리 안에 포식자가 있으면 도망친다.

    # ── 계획서 공통메서드: reproduce() ──────────────────
    def reproduce(self):
        """자신과 같은 종의 새끼 한 마리를 자기 근처에 만들어 돌려준다.
        실제 '언제 번식하는가'(나무 근처에서 만남)는 interactions.py 가 판단하고,
        '어떻게 새 개체를 만드는가'는 이 메서드가 담당한다 — 책임 분리.
        번식하면 게이지를 0으로 되돌린다."""
        self.reproduce_gauge = 0.0
        self.repro_cooldown = config.REPRO_COOLDOWN
        # 부모 바로 옆(무작위 오프셋)에 새끼가 태어나게 한다.
        offset = Vector2(random.uniform(-18, 18), random.uniform(-18, 18))
        # type(self) 로 '자신과 똑같은 종'을 생성한다 → 토끼는 토끼를, 기린은 기린을 낳는다.
        return type(self)(self.place + offset)

    def can_reproduce(self) -> bool:
        """번식 게이지가 가득 찼는지(번식 준비 완료) 여부."""
        return self.repro_cooldown == 0 and self.reproduce_gauge >= 100.0

    def _herbivore_behavior(self, world):
        """초식동물 공통 행동: ①가까운 포식자가 있으면 도망 ②그 외엔 풀 찾기/나무로 모이기.
        번식 게이지도 시간에 따라 차오른다."""
        self.reproduce_gauge = min(100.0, self.reproduce_gauge + self.rp_rate)

        # ① 가장 가까운 포식자를 찾아, 사거리 안이면 반대로 도망친다.
        predator = world.nearest(self.place, lambda e: isinstance(e, Carnivore) and e.isalive(),
                                  max_dist=self.flee_radius)
        if predator is not None:
            self.vel = physics.flee(self.place, predator.place, self.effective_speed)
            return

        # ② 위협이 없으면 평상시 이동(먹이 찾기 / 나무로 모이기).
        self._forage_and_gather(world, gather_dist=55, speed_factor=0.6)

    def _forage_and_gather(self, world, gather_dist, speed_factor):
        """초식동물의 '평상시 이동': 먹기 → 흩어지기 → 준비됐을 때만 번식터 찾기.

        기존 구현은 배가 고프지 않은 모든 초식동물이 항상 가장 가까운 나무 중심으로 갔다.
        그래서 한 쌍이 번식을 시작하면 주변 개체도 같은 나무에 겹쳐, 사냥·도망·번식이
        한 덩어리처럼 보이는 문제가 있었다.

        수정한 흐름은 이렇다.
          1) 배고프면 풀을 찾는다.
          2) 방금 번식했거나 아직 번식 준비가 덜 됐으면 초원에서 배회한다.
          3) 번식 준비가 충분히 됐을 때만 덜 붐비는 나무의 '둘레 자리'로 간다.
        이렇게 해야 번식 조건은 유지하면서도 생태계 상호작용이 여러 지점에 흩어져 보인다.
        """
        # 배가 고프면(허기 40 이상) 가장 가까운 '먹을 수 있는 풀'로 이동한다.
        max_speed = self.effective_speed * speed_factor
        if self.hunger > 40:
            grass = world.nearest(self.place,
                                   lambda e: e.species == "Grass" and not e.eaten and e.alive)
            if grass is not None:
                desired = physics.seek(self.place, grass.place, self.effective_speed)
                self.vel = self._steer_with_spacing(world, desired, self.effective_speed)
                return

        # 출산 직후나 번식 휴식 중에는 번식터를 바로 다시 점유하지 않고 흩어진다.
        # 부모/새끼가 나무에서 빠져나오면 다음 사냥, 도망, 먹이 찾기 장면이 훨씬 잘 보인다.
        if self.disperse_timer > 0 or self.repro_cooldown > 0:
            self._disperse_from_tree(world, max_speed)
            return

        # 번식 준비도가 낮을 때부터 나무에 대기하면 결국 모든 개체가 번식터에 쌓인다.
        # 준비도가 어느 정도 찬 개체만 나무로 향하게 해서 평소에는 초원 전체에 퍼져 있게 한다.
        if self.reproduce_gauge < config.REPRO_GATHER_THRESHOLD:
            desired = physics.wander(self.vel, max_speed)
            self.vel = self._steer_with_spacing(world, desired, max_speed)
            return

        tree = self._select_breeding_tree(world)
        if tree is None:
            desired = physics.wander(self.vel, max_speed)
            self.vel = self._steer_with_spacing(world, desired, max_speed)
            return

        # 목표는 나무 중심이 아니라 나무 둘레의 개인 자리다. 같은 나무를 쓰는 동물도
        # 서로 다른 각도로 접근하므로 한 픽셀에 겹치지 않고 번식 장면이 보인다.
        target = self._breeding_spot(world, tree)
        if self.place.distance_to(target) > gather_dist:
            desired = physics.seek(self.place, target, max_speed)
        else:
            desired = physics.wander(self.vel, max_speed)
        self.vel = self._steer_with_spacing(world, desired, max_speed)

    def _steer_with_spacing(self, world, desired, max_speed):
        """원래 목표 속도에 '서로 겹치지 않기' 힘을 섞는다.

        사냥/도망처럼 급한 행동에는 쓰지 않고, 먹이 찾기·배회·번식터 접근 같은 평상시
        이동에만 적용한다. 그래야 생존 행동은 유지하면서 화면상의 군집만 완화된다.
        """
        if max_speed <= 0:
            return Vector2.zero()
        neighbors = world.within(
            self.place, config.ANIMAL_SEPARATION_RADIUS,
            lambda e: isinstance(e, Animal) and e is not self and e.isalive())
        spacing = physics.separate(self.place, neighbors,
                                   config.ANIMAL_SEPARATION_RADIUS, max_speed)
        if spacing.length_sq() < 1e-6:
            return desired
        if desired.length_sq() < 1e-6:
            return spacing
        mixed = (desired * (1.0 - config.ANIMAL_SEPARATION_WEIGHT)
                 + spacing * config.ANIMAL_SEPARATION_WEIGHT)
        return mixed.with_length(max_speed)

    def _disperse_from_tree(self, world, max_speed):
        """번식 직후 번식터에서 잠깐 빠져나오는 이동.

        새끼가 태어난 바로 다음 틱에 부모가 다시 나무 중심으로 들어가면 같은 자리에서
        번식이 반복되고 화면이 뭉친다. 가까운 나무가 있으면 반대 방향으로, 없으면
        배회하도록 해 번식 이후의 개체 이동을 눈으로 따라갈 수 있게 한다.
        """
        tree = world.nearest(
            self.place, lambda e: e.species == "Tree" and e.alive,
            max_dist=120)
        if tree is not None:
            desired = physics.flee(self.place, tree.place, max_speed)
        else:
            desired = physics.wander(self.vel, max_speed)
        self.vel = self._steer_with_spacing(world, desired, max_speed)

    def _select_breeding_tree(self, world):
        """가까운 나무 몇 개 중 덜 붐비는 번식터를 고른다.

        완전히 가장 가까운 나무만 고르면 모든 개체가 같은 장소로 몰린다. 대신 가까운 후보
        몇 개를 놓고 현재 혼잡도를 점수에 반영한다. 이미 정한 나무가 적당히 비어 있으면
        계속 사용해서 매 틱 목표가 바뀌는 흔들림도 줄인다.
        """
        trees = [e for e in world.entities if e.species == "Tree" and e.alive]
        if not trees:
            self._gather_tree = None
            return None

        if self._gather_tree in trees:
            if self._tree_crowd(world, self._gather_tree) <= config.TREE_CROWD_SOFT_LIMIT:
                return self._gather_tree

        ranked = sorted(trees, key=lambda t: self.place.distance_sq_to(t.place))
        candidates = ranked[:max(1, min(config.BREEDING_TREE_CHOICES, len(ranked)))]
        self._gather_tree = min(candidates, key=lambda t: (
            self._tree_crowd(world, t) * config.TREE_CROWD_SCORE
            + self.place.distance_sq_to(t.place) * 0.12
            + random.random() * 600.0))
        return self._gather_tree

    @staticmethod
    def _tree_crowd(world, tree):
        """나무 번식 반경 안에 있는 동물 수. 나무 선택의 혼잡도 점수로 쓴다."""
        radius_sq = tree.BREED_RADIUS * tree.BREED_RADIUS
        return sum(1 for e in world.entities
                   if isinstance(e, Animal) and e.isalive()
                   and e.place.distance_sq_to(tree.place) <= radius_sq)

    def _breeding_spot(self, world, tree):
        """나무 중심이 아닌 둘레의 목표 지점을 계산한다."""
        # 나무와 동물의 몸집을 고려해 너무 안쪽으로 들어가지 않게 하고,
        # BREED_RADIUS 밖으로 나가지 않게 상한도 둔다.
        min_ring = tree.radius + self.radius + 14
        max_ring = max(min_ring, tree.BREED_RADIUS - self.radius - 6)
        ring = min(max_ring, min_ring + 12 + self._gather_ring_jitter)
        target = tree.place + Vector2(
            math.cos(self._gather_angle) * ring,
            math.sin(self._gather_angle) * ring)
        return physics.clamp_point(target, world.width, world.height, self.radius)


# ════════════════════════════════════════════════════════════════════════
# Carnivore  (계획서의 부모 클래스 'carnivores')
# 공통속성: hunger, energy
# 공통메서드: attack()
# ════════════════════════════════════════════════════════════════════════
class Carnivore(Animal):
    """육식동물의 부모. 가장 가까운 먹이를 추격하고, 닿으면 공격한다.
    공통 추격 행동은 여기서, 종 고유 능력(포효·도약·약탈)은 자식에서 정의한다."""

    def __init__(self, place, speed, hp, ap, rsp, energy):
        super().__init__(place, speed, hp, ap, rsp)
        self.energy = energy        # 기력(계획서 속성). 사냥에 성공하면 차오른다.
        self.hunger_rate = 0.12     # 육식동물은 허기가 천천히 오른다.
        self.target = None          # 현재 노리는 먹잇감(상호작용/하이에나 약탈 판단에 사용)

    # ── 계획서 공통메서드: attack() ─────────────────────
    def attack(self, target) -> bool:
        """대상에게 공격력(ap)만큼 피해를 준다. 대상이 죽으면 True 를 반환한다.
        먹는 보상(기력/체력 회복)은 호출 측(interactions)이 처리한다.
        이유: '공격(attack)'과 '먹기(eat)'를 분리해야, 하이에나가 사냥감을 가로채는
              상호작용(누가 공격했든 먹는 쪽은 다를 수 있음)을 자연스럽게 구현할 수 있다."""
        target.hp -= self.ap
        if target.hp <= 0:
            target.alive = False
            return True
        return False

    def _carnivore_behavior(self, world):
        """육식동물 공통 행동: 배가 고플 때만 가장 가까운 초식동물을 추격한다.
        배가 부르면 사냥하지 않고 쉰다(배회). (실제 '닿으면 잡아먹기'는
        interactions.resolve_predation 이 처리한다)

        이유: 포식자가 늘 사냥하면 먹이가 회복할 틈 없이 전멸한다. 실제 사자처럼
        '배고플 때만 사냥, 평소엔 휴식'하게 만들면 포식자-피식자 개체 수가
        오르내리는 자연스러운 균형(순환)이 생긴다."""
        if self.hunger < 35:
            self.target = None
            self.vel = physics.wander(self.vel, self.effective_speed * 0.5)
            return
        # 표적 우선순위(계획서 상호작용 ②③ 반영):
        #  1순위) 잡기 쉬운 얼룩말·토끼   2순위) 그것이 없을 때만 기린
        #  코끼리는 사냥감이 아니라 '장애물'이므로 표적에서 제외한다(달려들면 stomp로
        #  기절하거나 tree 투척에 맞아 큰 피해를 입는다 — 즉사는 아님).
        #  숨은(토끼 hide) 먹이는 보이지 않으므로 제외한다.
        prey = world.nearest(
            self.place,
            lambda e: e.species in ("Rabbit", "Zebra") and e.isalive()
            and getattr(e, "hidden_timer", 0) <= 0)
        if prey is None:
            prey = world.nearest(
                self.place, lambda e: e.species == "Giraffe" and e.isalive())
        self.target = prey
        if prey is not None:
            self.vel = physics.seek(self.place, prey.place, self.effective_speed)
        else:
            self.vel = physics.wander(self.vel, self.effective_speed)

    # ── 번식(계획서 상호작용표 '모든 동물 번식' 구현용 확장) ──
    # 계획서 클래스표에는 reproduce()가 herbivores에만 있지만, 상호작용표는
    # "모든 동물이 나무 근처에서 번식한다"고 규정한다. 이를 만족시키기 위해
    # 육식동물에도 reproduce()를 확장 정의한다(기력 energy 를 소비해 번식).
    def can_reproduce(self) -> bool:
        """기력이 충분할 때만 번식할 수 있다(잘 먹은 포식자가 번식)."""
        return self.repro_cooldown == 0 and self.energy >= 75.0

    def reproduce(self):
        """기력을 크게 소비하며 같은 종의 새끼를 낳아 돌려준다."""
        self.energy -= 55.0
        self.repro_cooldown = config.REPRO_COOLDOWN
        offset = Vector2(random.uniform(-18, 18), random.uniform(-18, 18))
        return type(self)(self.place + offset)


# ════════════════════════════════════════════════════════════════════════
# Plant  (계획서의 부모 클래스 'plant')
# 공통속성: place, eaten(먹힘 여부)
# 공통메서드: grow()
# ════════════════════════════════════════════════════════════════════════
class Plant(Entity):
    """식물의 부모. 움직이지 않으며, 시간이 지나면 다시 자란다(grow)."""

    def __init__(self, place):
        super().__init__(place)
        self.eaten = False      # 먹혔는지 여부(계획서 속성)

    def grow(self):
        """시간이 지나 다시 자라는 동작. 기본은 '아무 것도 안 함'이며,
        풀(Grass)처럼 다시 자라는 식물이 이 메서드를 재정의한다."""
        pass

    def update(self, world):
        # 식물은 움직이지 않으므로, 매 틱 grow() 로 회복/성장 처리만 한다.
        self.grow()
