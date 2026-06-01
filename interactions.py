"""interactions.py — 동물 간 '전역 상호작용' 처리.

담당: 심준서(상호작용 중심)
역할: 계획서 '동물 간 상호작용 설계'표의 규칙들을, 매 틱 월드 전체를 훑어
      처리한다. 개체 하나가 혼자 결정할 수 없는 '둘 이상이 엮이는 사건'
      (먹기·사냥·약탈·기린 싸움·번식)을 여기서 중재한다.

설계 의도(역할 분리)
  - 개체의 '이동 결정'과 '고유 능력 발동'은 각 동물의 act() 가 담당한다.
  - 반면 '두 개체가 닿았을 때의 결과(누가 먹히고 누가 먹는가)'처럼
    여러 개체를 동시에 봐야 하는 판정은 이 모듈이 모아서 처리한다.

[생성형 AI 활용] 약탈 가로채기/번식 짝짓기 판정 로직은 생성형 AI(Claude)의 도움을 받았다.
"""

import itertools
import math
import random

import config
import physics
from organisms import Animal, Herbivore, Carnivore
from carnivores import Hyena
from vector import Vector2

EAT_RATE = 4.0       # 초식동물이 한 틱에 풀을 뜯어 먹는 양
STEAL_RANGE = 120    # 하이에나가 사냥을 가로챌 수 있는 거리
FIGHT_RANGE = 55     # 기린끼리 이보다 가까우면 싸움이 날 수 있다


def run_all(world):
    """월드가 매 틱 호출하는 상호작용 처리 묶음(아래 순서대로 실행)."""
    feed_herbivores(world)      # ① 초식동물이 풀을 먹음
    resolve_predation(world)    # ②③④ 사자·치타가 먹이를 잡아먹음(+하이에나 약탈)
    giraffe_fights(world)       # ⑤ 기린끼리 싸움
    reproduce_near_trees(world)  # ⑧ 나무 근처에서 번식


def feed_herbivores(world):
    """상호작용①: 얼룩말·토끼 등 초식동물이 닿은 풀을 먹는다.
    체력이 다 차면 더 먹지 않는다(계획서: 'hp가 다 차면 그만 먹게 된다')."""
    grasses = [e for e in world.entities if e.species == "Grass" and e.alive and not e.eaten]
    if not grasses:
        return
    for herb in world.entities:
        if not isinstance(herb, Herbivore) or not herb.isalive():
            continue
        if herb.hp >= herb.max_hp:      # 배가 다 차면(체력 가득) 그만 먹는다
            continue
        for g in grasses:
            if g.eaten:
                continue
            # 초식동물과 풀이 닿았으면, 풀을 조금 뜯어 먹고 그만큼 체력을 회복한다.
            if physics.is_contact(herb.place, herb.radius, g.place, g.radius):
                taken = g.be_eaten(EAT_RATE)
                herb.eat(taken)
                break   # 한 틱에 풀 하나만 먹는다


def resolve_predation(world):
    """상호작용②③④: 사자·치타(·하이에나)가 닿은 먹이를 공격한다.
    먹이를 죽이면 보상(먹기)을 처리하되, 근처 하이에나가 가로챌 수 있다.
    숨은 토끼(hidden_timer>0)는 공격 대상에서 제외된다(토끼 hide 능력 반영)."""
    herbivores = [e for e in world.entities if isinstance(e, Herbivore) and e.isalive()]
    for carn in world.entities:
        if not isinstance(carn, Carnivore) or not carn.isalive():
            continue
        # 기절(코끼리 stomp)·산만(얼룩말 distract) 상태이거나 배가 부르면 제대로 공격하지 못한다.
        # 이 덕분에 코끼리의 stomp/얼룩말의 distract 가 '실제 방어'로서 의미를 갖는다.
        # 공격 허용 기준은 허기 30, 추격 시작 기준은 허기 35(organisms._carnivore_behavior)로
        # 일부러 다르게 뒀다 — 추격을 막 멈춘 직후(30~35)라도 눈앞에 닿은 먹이는 잡도록 하기 위함.
        if carn.stun_timer > 0 or carn.distract_timer > 0 or carn.hunger < 30:
            continue
        for prey in herbivores:
            if not prey.isalive() or getattr(prey, "hidden_timer", 0) > 0:
                continue
            if physics.is_contact(carn.place, carn.radius, prey.place, prey.radius):
                killed = carn.attack(prey)      # 공격(피해만 줌)
                if killed:
                    _award_kill(world, carn, prey)
                break   # 한 틱에 한 마리만 공격


def _award_kill(world, attacker, prey):
    """사냥에 성공했을 때 '누가 먹는가'를 결정한다.
    상호작용⑥: 공격자가 아닌 하이에나가 사거리 안에 있으면 일정 확률로 가로챈다."""
    hyena = world.nearest(
        prey.place,
        lambda e: isinstance(e, Hyena) and e.isalive() and e is not attacker,
        max_dist=STEAL_RANGE)
    if hyena is not None and hyena.steal(prey, world):
        return   # 하이에나가 먹이를 가로챔(보상은 steal() 안에서 처리됨)
    # 가로채는 하이에나가 없으면 공격자 본인이 먹는다(기력 회복 + 허기 감소).
    attacker.energy = min(100.0, attacker.energy + 35)
    attacker.eat(45)
    world.log(f"{attacker.emoji} {config.KOR_NAME.get(attacker.species)}가 "
              f"{config.KOR_NAME.get(prey.species)}을(를) 사냥했다")


def giraffe_fights(world):
    """상호작용⑤: 기린끼리 너무 가까워지면 일정 확률(neckfight_prb)로 싸움이 난다.
    itertools.combinations 로 모든 기린 '쌍'을 한 번씩만 검사한다(중복 판정 방지)."""
    giraffes = [e for e in world.entities if e.species == "Giraffe" and e.isalive()]
    for a, b in itertools.combinations(giraffes, 2):
        # 두 기린 중 한쪽이라도 싸움 쿨타임이면 건너뛴다(한쪽 쿨타임만 보면, 쿨타임 중인
        # 상대를 일방적으로 계속 밀쳐내는 비대칭이 생기므로 양쪽을 모두 확인한다).
        if a.neck_cd > 0 or b.neck_cd > 0:
            continue
        if a.place.distance_to(b.place) <= FIGHT_RANGE and random.random() < a.neckfight_prb:
            a.neckfight(b, world)                              # b를 밀쳐냄
            a.place = physics.knockback(a.place, b.place, 25)  # a도 반동으로 약간 밀림
            b.neck_cd = b.neckfight_rate                       # b도 잠시 재싸움 불가
            world.log("\U0001F992 기린끼리 넥스윙 싸움이 벌어졌다")


def reproduce_near_trees(world):
    """상호작용⑧: 같은 종 둘 이상이 '나무의 번식 반경' 안에서 만나면 새끼가 태어난다.
    종별 개체 수 상한(MAX_COUNTS)을 넘지 않도록 막는다(개체 폭발 방지).

    번식 직후에는 부모와 새끼가 번식터에서 잠깐 흩어지게 한다. 그래야 한 번식쌍이
    생긴 곳으로 같은 종이 계속 겹쳐 들어가는 현상이 줄고, 초원 전체의 상호작용이 보인다.
    """
    trees = [e for e in world.entities if e.species == "Tree" and e.alive]
    if not trees:
        return
    animals = [e for e in world.entities if isinstance(e, Animal) and e.isalive()]

    # 종별로 동물을 묶어 둔다.
    by_species = {}
    for a in animals:
        by_species.setdefault(a.species, []).append(a)

    for tree in trees:
        for species, group in by_species.items():
            if world.count(species) >= config.MAX_COUNTS.get(species, 999):
                continue   # 이미 상한이면 번식하지 않는다
            # 이 나무 반경 안에 모인 같은 종을 추린다(짝이 있어야 번식 가능).
            near_tree = [a for a in group
                         if a.place.distance_to(tree.place) <= tree.BREED_RADIUS]
            if len(near_tree) < 2:
                continue
            # 그중 '번식 준비가 된' 개체가 하나라도 있으면, 짝과 함께 새끼를 낳는다.
            # (둘 다 준비될 때까지 기다리면 개체 수가 적은 종은 사실상 번식이 막히므로,
            #  한 마리만 준비돼도 곁의 짝과 번식하도록 완화했다 — 멸종 방지)
            ready = [a for a in near_tree if a.can_reproduce()]
            if ready:
                random.shuffle(ready)
                for parent in ready:
                    # 방금 번식한 개체를 곧바로 다른 짝으로 재사용하면 한 장소에서
                    # 연쇄 번식이 일어난다. 휴식 중이 아닌 가장 가까운 짝을 골라
                    # '한 쌍이 만났다'는 장면이 보이도록 한다.
                    partners = [a for a in near_tree
                                if a is not parent and getattr(a, "repro_cooldown", 0) == 0]
                    if not partners:
                        continue
                    partner = min(partners, key=lambda a: parent.place.distance_sq_to(a.place))
                    child = parent.reproduce()   # 부모가 번식(게이지/기력 초기화)
                    _spend_repro(partner)        # 짝의 번식 준비도도 소모시킨다
                    _place_child_after_birth(child, parent, partner, tree, world)
                    _start_birth_dispersion(parent, partner, child)
                    world.spawn(child)
                    world.log(f"{child.emoji} {config.KOR_NAME.get(species)}가 번식했다")
                    break


def _spend_repro(animal):
    """번식에 참여한 '짝'의 번식 준비도를 소모시킨다.
    초식동물은 번식 게이지를, 육식동물은 기력(energy)을 소모한다.
    짝은 번식 준비가 안 됐어도 선택될 수 있으므로(멸종 방지 완화), 육식동물의 기력은
    max(0, ...)로 0 밑으로 내려가지 않게 막는다(음수 기력 같은 비정상 상태 방지)."""
    if isinstance(animal, Herbivore):
        animal.reproduce_gauge = 0.0
    else:
        animal.energy = max(0.0, animal.energy - 40.0)
    animal.repro_cooldown = config.REPRO_COOLDOWN


def _place_child_after_birth(child, parent, partner, tree, world):
    """새끼를 부모가 겹친 지점이 아니라 나무 바깥쪽으로 조금 떨어뜨려 배치한다.

    기존처럼 부모 바로 옆에만 만들면 부모·짝·새끼가 같은 픽셀에 쌓인다. 두 부모의
    중간 지점에서 나무 반대 방향으로 한 걸음 밀어 새끼를 놓으면 출생 장면도 보이고,
    다음 틱부터 부모와 새끼가 각자 움직이는 모습도 구분된다.
    """
    mid = (parent.place + partner.place) * 0.5
    away = mid - tree.place
    if away.length_sq() < 1e-6:
        angle = random.uniform(0, 2 * math.pi)
        away = Vector2(math.cos(angle), math.sin(angle))
    jitter = Vector2(random.uniform(-10, 10), random.uniform(-10, 10))
    child.place = physics.clamp_point(
        mid + away.with_length(child.radius + 30 + random.uniform(0, 18)) + jitter,
        world.width, world.height, child.radius)


def _start_birth_dispersion(parent, partner, child):
    """번식에 참여한 가족이 일정 시간 번식터를 빠져나오게 표시한다."""
    for animal in (parent, partner, child):
        animal.disperse_timer = max(animal.disperse_timer, config.POST_BIRTH_DISPERSE_TICKS)
        animal.repro_cooldown = max(animal.repro_cooldown, config.REPRO_COOLDOWN)
