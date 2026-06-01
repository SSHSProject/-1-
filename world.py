"""world.py — 생태계 '월드' (전체 관리자).

담당: 심성진(전체 코드 관리)
역할: 모든 구성원(동물·식물·트랙터)을 한 리스트로 담아 두고, 매 틱마다
      ①각 개체 갱신 → ②전역 상호작용 → ③재난 → ④출생/사망 정리 → ⑤종료 판정
      을 순서대로 진행하는 시뮬레이션의 심장부.
      또한 GUI/동물들이 공통으로 쓰는 '이웃 찾기'(nearest/within) 기능을 제공한다.

이유: 개체들이 서로를 직접 참조하면 코드가 얽힌다. 그래서 '월드'를 가운데 두고
      개체는 월드에게만 질문(가장 가까운 포식자는?)하게 하여 결합도를 낮춘다.

[생성형 AI 활용] 갱신 루프 구조와 이웃 질의(nearest/within) 설계는
                 생성형 AI(Claude)의 도움을 받았다.
"""

import random

import config
import disaster
import interactions
from carnivores import Cheetah, Hyena, Lion
from herbivores import Elephant, Giraffe, Rabbit, Zebra
from organisms import Animal
from plants import Grass, Tree
from vector import Vector2

# 종 이름(영문 키) → 클래스. 초기 생성과 개체 수 집계에 쓴다.
SPECIES_CLASSES = {
    "Tree": Tree, "Grass": Grass,
    "Rabbit": Rabbit, "Zebra": Zebra, "Giraffe": Giraffe, "Elephant": Elephant,
    "Lion": Lion, "Cheetah": Cheetah, "Hyena": Hyena,
}


class World:
    def __init__(self):
        self.width = config.WORLD_W
        self.height = config.WORLD_H
        self.tick = 0
        self.entities = []          # 살아 있는 모든 구성원
        self.events = []            # 최근 사건 로그(화면 표시용)
        self.spawn_queue = []       # 이번 틱에 새로 태어난 개체(틱 끝에 합류)
        self.over = False           # 생태계 종료 여부
        self.over_message = ""      # 종료 사유
        self.disaster_active = False  # 트랙터 재난이 진행 중인지
        self._populate()

    # ── 초기 생성 ────────────────────────────────────────
    def _populate(self):
        """계획서의 초기 개체 수(config.INITIAL_COUNTS)대로 초원에 흩뿌린다.
        식물 → 동물 순서로 만들어, 동물이 풀/나무를 처음부터 인식할 수 있게 한다."""
        order = ["Tree", "Grass", "Rabbit", "Zebra", "Giraffe",
                 "Elephant", "Lion", "Cheetah", "Hyena"]
        for species in order:
            cls = SPECIES_CLASSES[species]
            for _ in range(config.INITIAL_COUNTS.get(species, 0)):
                self.entities.append(cls(self._random_place(cls.radius)))

    def _random_place(self, margin):
        """경계에서 margin 만큼 안쪽의 무작위 위치를 고른다(벽에 박혀 생성되는 것 방지)."""
        x = random.uniform(margin, self.width - margin)
        y = random.uniform(margin, self.height - margin)
        return Vector2(x, y)

    # ── 사건 로그 ────────────────────────────────────────
    def log(self, message: str):
        """사건을 기록한다. 화면에는 최근 것만 보이도록 길이를 제한한다."""
        self.events.append(message)
        if len(self.events) > config.MAX_EVENT_LOG:
            # 오래된 줄을 잘라내 최근 MAX_EVENT_LOG 줄만 남긴다.
            self.events = self.events[-config.MAX_EVENT_LOG:]

    # ── 출생 등록 / 개체 수 집계 ─────────────────────────
    def spawn(self, entity):
        """새 개체를 '대기열'에 넣는다. 리스트 순회 도중 추가하면 위험하므로,
        틱이 끝난 뒤(_flush)에 실제 entities 에 합류시킨다."""
        self.spawn_queue.append(entity)

    def count(self, species: str) -> int:
        """해당 종의 현재 개체 수(살아 있는 것 + 이번 틱 출생 대기열 포함)."""
        n = sum(1 for e in self.entities if e.species == species and e.alive)
        n += sum(1 for e in self.spawn_queue if e.species == species)
        return n

    # ── 이웃 질의(물리엔진과 동물 AI가 공통으로 사용) ────
    def nearest(self, place, predicate, max_dist=float("inf")):
        """predicate(조건)를 만족하는 개체 중 place 에서 가장 가까운 것을 반환.
        없으면 None. 거리 비교는 빠른 '제곱거리'로 한다."""
        best = None
        best_d2 = max_dist * max_dist
        for e in self.entities:
            if not predicate(e):
                continue
            d2 = place.distance_sq_to(e.place)
            if d2 <= best_d2:
                best_d2 = d2
                best = e
        return best

    def within(self, place, radius, predicate):
        """place 에서 radius 안에 있으면서 predicate 를 만족하는 개체들의 리스트."""
        r2 = radius * radius
        return [e for e in self.entities
                if predicate(e) and place.distance_sq_to(e.place) <= r2]

    # ── 매 틱 진행 ───────────────────────────────────────
    def step(self):
        """시뮬레이션을 한 틱 진행한다. (GUI 가 프레임마다 호출)"""
        if self.over:
            return
        self.tick += 1

        # ① 각 개체 갱신: 동물은 행동·이동, 식물은 성장, 트랙터는 진격.
        #    list(...) 로 복사해 순회하는 이유: 갱신 중 리스트가 바뀌어도 안전하게.
        for e in list(self.entities):
            if e.alive:
                e.update(self)

        # ② 전역 상호작용(먹기/사냥/약탈/기린싸움/번식).
        interactions.run_all(self)

        # ③ 출생 합류 + 사망/제거 정리.
        self._flush()

        # ④ 풀 은신처 점유 수(rab_num) 재계산.
        self._recount_grass_occupancy()

        # ⑤ 나무 자연 재생(번식터 유지).
        self._regrow_trees()

        # ⑤ 종료 조건 판정.
        self._check_over()

    def _flush(self):
        """출생 대기열을 entities 에 합치고, 죽은(또는 밀려난) 개체를 걸러낸다."""
        if self.spawn_queue:
            self.entities.extend(self.spawn_queue)
            self.spawn_queue = []
        self.entities = [e for e in self.entities if e.alive]

    def _recount_grass_occupancy(self):
        """풀에 숨어 있는 토끼 수(rab_num)를 매 틱 '실제 숨은 토끼'로 다시 센다.
        이유: 토끼가 숨은 채 굶주림이나 트랙터 재난으로 죽으면 rab_num 을 줄일 기회가 없어
        값이 영영 남는 누수가 생긴다. 매 틱 0으로 초기화한 뒤 지금 살아서 숨어 있는 토끼만
        세면, 어떤 죽음/제거 경로에서도 누수 없이 항상 정확한 값이 유지된다."""
        for e in self.entities:
            if e.species == "Grass":
                e.rab_num = 0
        for e in self.entities:
            if getattr(e, "hidden_timer", 0) > 0:
                g = getattr(e, "_hiding_grass", None)
                if g is not None and g.alive:
                    g.rab_num += 1

    def _regrow_trees(self):
        """일정 주기마다 나무가 최소 개체 수(초기값)보다 적으면 한 그루 새로 자란다.
        코끼리의 나무 투척으로 번식터가 모두 사라지는 죽음의 악순환을 막기 위함."""
        if self.disaster_active:
            return   # 재난 중에는 자연 복원하지 않는다(초원이 밀려나가는 중)
        if self.tick % config.TREE_REGROW_INTERVAL != 0:
            return
        if self.count("Tree") < config.INITIAL_COUNTS["Tree"]:
            self.entities.append(Tree(self._random_place(Tree.radius)))
            self.log("\U0001F333 새 나무가 자랐다")

    def _check_over(self):
        """종료 조건 판정.
        ① 재난(트랙터) 중에는 트랙터가 초원을 '완전히' 지나갈 때까지 기다렸다가 종료한다
           (동물이 먼저 다 밀려나도, 초원 전체가 밀리는 장면을 끝까지 보여주기 위함).
        ② 재난이 아닌데 모든 동물이 사라지면 '자연 붕괴'로 종료한다."""
        if self.disaster_active:
            if self.count("Tractor") == 0:
                self.over = True
                self.over_message = "초원이 트랙터에 모두 밀려 사라졌습니다."
            return
        if not any(isinstance(e, Animal) and e.isalive() for e in self.entities):
            self.over = True
            self.over_message = "모든 동물이 사라졌습니다. 생태계가 붕괴했습니다."

    # ── 사용자 재난 발동(종료 조건 트리거) ───────────────
    def trigger_disaster(self):
        """사용자가 [D] 키를 누르면 호출된다. 트랙터 무리를 등장시킨다(중복 발동 방지)."""
        if self.disaster_active:
            return
        self.disaster_active = True
        disaster.spawn_tractors(self)
        self.log("\U0001F69C 트랙터 재난 발생! 초원이 밀려나가기 시작했다")

    # ── 통계(화면 통계판용) ──────────────────────────────
    def stats(self) -> dict:
        """종별로 현재 살아 있는 개체 수를 센다(트랙터 제외)."""
        counts = {}
        for e in self.entities:
            if not e.alive or e.species == "Tractor":
                continue
            counts[e.species] = counts.get(e.species, 0) + 1
        return counts
