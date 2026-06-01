"""vector.py — 2차원 벡터 클래스.

담당: 홍순율(GUI · 물리엔진)
역할: 물리엔진의 가장 밑바탕이 되는 "2D 벡터"를 직접 구현한다.
      위치(place), 속도(vel) 같은 값은 모두 이 Vector2 로 표현한다.
이유: 외부 수학 라이브러리(numpy 등)를 쓰지 않고 "파이썬만으로" 물리엔진을
      만들라는 요구사항이 있어, 벡터 연산을 손수 정의한다.

[생성형 AI 활용] 연산자 오버로딩 구조는 생성형 AI(Claude)의 도움을 받았다.
"""

import math


class Vector2:
    # __slots__ : 인스턴스가 x, y 외의 속성을 갖지 못하게 막아 메모리를 아끼고
    #             오타로 엉뚱한 속성을 만드는 실수를 방지한다.
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = float(x)
        self.y = float(y)

    # ── 사칙연산 오버로딩 ──────────────────────────────
    # 벡터끼리 더하고 빼고, 스칼라(숫자)로 곱하고 나눌 수 있게 만든다.
    # 이렇게 해두면 물리 공식을 "place + vel * DT" 처럼 수식 그대로 쓸 수 있다.
    def __add__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> "Vector2":
        return Vector2(self.x * k, self.y * k)

    __rmul__ = __mul__  # 2 * v 와 v * 2 를 모두 허용

    def __truediv__(self, k: float) -> "Vector2":
        return Vector2(self.x / k, self.y / k)

    # ── 크기(길이) 관련 ───────────────────────────────
    def length_sq(self) -> float:
        # 길이의 제곱. 제곱근(sqrt)은 비싼 연산이라, 단순 비교에는 제곱값을 쓰면 빠르다.
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        return math.sqrt(self.length_sq())

    def normalized(self) -> "Vector2":
        # 방향만 남기고 길이를 1로 만든 단위벡터를 반환한다.
        # 길이가 0인 벡터(제자리)는 방향이 없으므로 (0,0)을 그대로 돌려준다.
        # 0으로 나누면 ZeroDivisionError 가 나기 때문에 반드시 막아야 한다.
        ln = self.length()
        if ln == 0:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / ln, self.y / ln)

    def with_length(self, n: float) -> "Vector2":
        # 방향은 유지하고 길이만 n 으로 바꾼 벡터.
        # "이 방향으로 속도 n 만큼 움직여라" 같은 조향(steering)에 자주 쓴다.
        return self.normalized() * n

    def distance_to(self, other: "Vector2") -> float:
        return (self - other).length()

    def distance_sq_to(self, other: "Vector2") -> float:
        # 거리 비교용(가장 가까운 대상 찾기 등)에는 제곱거리가 더 빠르다.
        return (self - other).length_sq()

    def __repr__(self) -> str:
        return f"Vector2({self.x:.1f}, {self.y:.1f})"

    @classmethod
    def zero(cls) -> "Vector2":
        return cls(0.0, 0.0)
