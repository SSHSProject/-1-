"""plants.py — 식물(풀·나무) 구체 클래스.

담당: 한시헌(동물/식물 클래스 중심)
역할: 계획서의 plant 부모를 상속받는 두 식물, 풀(Grass)과 나무(Tree)를 구현한다.
      - 풀: 초식동물의 먹이가 되고, 토끼가 숨는 은신처가 된다(rab_num 한계 존재).
      - 나무: 번식이 일어나는 '만남의 장소'이며, 코끼리가 뽑아 던질 수 있다.

[생성형 AI 활용] 풀의 재성장(쿨다운) 처리 방식은 생성형 AI(Claude)의 도움을 받았다.
"""

from organisms import Plant


class Grass(Plant):
    """풀 — 얼룩말·토끼가 뜯어 먹는 먹이이자, 토끼의 은신처.
    계획서 속성 rab_num(풀에 들어가 있는 토끼 수: 한계 존재)을 가진다."""

    species = "Grass"
    radius = 10
    REGROW_TIME = 120     # 다 뜯어 먹힌 뒤 다시 자라기까지 걸리는 틱 수
    RAB_CAP = 3           # 한 풀숲에 동시에 숨을 수 있는 토끼 수의 한계

    def __init__(self, place):
        super().__init__(place)
        self.food = 100.0          # 풀의 양(남은 먹이). 0이 되면 'eaten' 상태가 된다.
        self.rab_num = 0           # 지금 이 풀에 숨어 있는 토끼 수(계획서 속성)
        self._regrow_timer = 0     # 재성장까지 남은 시간

    def be_eaten(self, amount: float) -> float:
        """초식동물이 풀을 amount 만큼 뜯어 먹는다. 실제로 먹은 양을 반환한다.
        풀이 바닥나면 eaten=True 로 표시하고 재성장 타이머를 켠다.
        '얼마나 먹혔는가'를 풀 스스로 관리하므로, 먹는 쪽 코드가 단순해진다."""
        if self.eaten or self.food <= 0:
            return 0.0
        taken = min(self.food, amount)
        self.food -= taken
        if self.food <= 0:
            self.eaten = True
            self._regrow_timer = self.REGROW_TIME
        return taken

    def grow(self):
        """다 먹힌 풀이 시간이 지나면 다시 자란다(부모 grow 재정의).
        재성장 타이머가 0이 되는 순간 먹이를 가득 채우고 다시 먹을 수 있게 한다."""
        if self.eaten:
            self._regrow_timer -= 1
            if self._regrow_timer <= 0:
                self.food = 100.0
                self.eaten = False
                self.rab_num = 0   # 풀이 새로 자라면 숨어있던 토끼 수도 초기화


class Tree(Plant):
    """나무 — 번식이 일어나는 '만남의 장소'.
    코끼리가 뽑아 포식자에게 던지면 사라진다(alive=False)."""

    species = "Tree"
    radius = 16
    BREED_RADIUS = 70     # 이 반경 안에서 같은 종이 만나면 번식이 진행된다.

    # 나무는 따로 자라거나 재성장하지 않으므로 grow() 는 부모의 기본(아무 동작 없음)을 쓴다.
