"""gui.py — tkinter 기반 화면 출력 · 입력 처리.

담당: 홍순율(GUI · 물리엔진)
역할: 표준 라이브러리 tkinter 만으로 초원 생태계를 그리고, 키 입력을 받아
      시뮬레이션을 조작한다(외부 GUI 라이브러리 없이 '파이썬만으로' 구현).
      - 왼쪽 캔버스: 동물·식물·트랙터를 매 프레임 다시 그린다(애니메이션).
      - 오른쪽 패널: 경과 시간, 종별 개체 수, 최근 사건 로그, 조작법을 보여준다.

게임 루프(중요)
      tkinter 에는 while 무한루프 대신 root.after(ms, 함수) 로 '일정 시간 뒤 다시
      호출'을 예약하는 방식을 쓴다. 매 호출마다 world.step()(시뮬레이션 한 틱) →
      화면 다시 그리기 를 반복해, 시간의 흐름에 따른 생태계 변화를 보여준다.

[생성형 AI 활용] tkinter 캔버스 렌더링/after 루프/키 바인딩 구조는
                 생성형 AI(Claude)의 도움을 받아 구현하였다.
"""

import tkinter as tk
from tkinter import font as tkfont

import config
from organisms import Animal
from world import World

# 화면에 표시할 종의 순서(통계판 정렬용): 포식자 → 초식 → 식물
DISPLAY_ORDER = ["Lion", "Cheetah", "Hyena", "Rabbit", "Zebra",
                 "Giraffe", "Elephant", "Grass", "Tree"]

PANEL_W = 290           # 오른쪽 정보 패널 너비


def _pick_font(candidates, default):
    """설치된 글꼴 중 후보(candidates)에 있는 첫 번째를 고른다(없으면 default).
    이유: 'Apple Color Emoji'·'AppleGothic'은 macOS 전용이라, 다른 OS에서 그대로 쓰면
    한글이 □로 깨지거나 이모지가 안 보일 수 있다. 실행 환경에 있는 글꼴을 자동 선택해
    이식성을 높인다. (이 함수는 Tk 루트가 만들어진 뒤에 호출해야 한다)"""
    available = set(tkfont.families())
    for name in candidates:
        if name in available:
            return name
    return default


# 한글/이모지 글꼴은 OS마다 다르므로, 실제 글꼴 이름은 앱 생성 시점(_resolve_fonts)에 정한다.
EMOJI_FONT = "Apple Color Emoji"   # 기본값(macOS) — 환경에 따라 _resolve_fonts 에서 교체됨
KOR_FONT = "AppleGothic"           # 기본값(macOS) — 환경에 따라 _resolve_fonts 에서 교체됨


class EcosystemApp:
    """초원 생태계 시뮬레이터의 메인 GUI 애플리케이션."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.world = World()
        self.paused = False

        self._resolve_fonts()   # 패널을 만들기 전에 환경에 맞는 글꼴부터 결정한다

        # ── 화면 구성: 왼쪽 월드 캔버스 + 오른쪽 정보 패널 ──
        self.canvas = tk.Canvas(root, width=config.WORLD_W, height=config.WORLD_H,
                                bg=config.BG_COLOR, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT)

        panel = tk.Frame(root, width=PANEL_W, height=config.WORLD_H, bg="#2e2e2e")
        panel.pack(side=tk.RIGHT, fill=tk.Y)
        panel.pack_propagate(False)   # 자식 위젯 크기에 패널이 줄어들지 않게 고정
        self._build_panel(panel)

        # ── 키 입력 연결 ──
        # 캔버스가 포커스를 가져야 키 입력을 받으므로 focus_set 한다.
        self.canvas.focus_set()
        root.bind("<Key>", self._on_key)

        # ── 게임 루프 시작 ──
        self._loop()

    def _resolve_fonts(self):
        """실행 환경(OS)에 설치된 한글/이모지 글꼴을 골라 모듈 전역(KOR_FONT/EMOJI_FONT)에 반영.
        macOS 전용 글꼴이 없는 환경에서도 한글·이모지가 최대한 표시되도록 한다."""
        global EMOJI_FONT, KOR_FONT
        KOR_FONT = _pick_font(
            ["AppleGothic", "Apple SD Gothic Neo", "Malgun Gothic", "NanumGothic",
             "Noto Sans CJK KR", "Noto Sans KR"], "TkDefaultFont")
        EMOJI_FONT = _pick_font(
            ["Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji"], KOR_FONT)

    # ── 패널(오른쪽 정보창) 구성 ─────────────────────────
    def _build_panel(self, panel):
        """제목/상태/통계/로그/조작법 라벨을 세로로 쌓는다.
        값이 바뀌는 라벨(상태·통계·로그)은 멤버로 저장해 매 프레임 갱신한다."""
        def header(text, size=15, fg="#ffd54f"):
            tk.Label(panel, text=text, bg="#2e2e2e", fg=fg,
                     font=(KOR_FONT, size, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

        header("\U0001F981 심심한 초원의 제왕", 16)
        header("네이처 빌더 · 초원 생태계", 11, "#bdbdbd")

        self.lbl_info = tk.Label(panel, bg="#2e2e2e", fg="white", justify="left",
                                 font=(KOR_FONT, 12))
        self.lbl_info.pack(anchor="w", padx=12, pady=(6, 4))

        header("개체 수", 13)
        self.lbl_stats = tk.Label(panel, bg="#2e2e2e", fg="white", justify="left",
                                  font=(KOR_FONT, 12))
        self.lbl_stats.pack(anchor="w", padx=12)

        header("생태계 일지", 13)
        self.lbl_log = tk.Label(panel, bg="#2e2e2e", fg="#c8e6c9", justify="left",
                                font=(KOR_FONT, 10), wraplength=PANEL_W - 24)
        self.lbl_log.pack(anchor="w", padx=12)

        # 조작법(고정 안내)
        controls = ("\n[D] 트랙터 재난 발생\n[Space] 일시정지/재개\n"
                    "[R] 다시 시작\n[Q] 종료")
        tk.Label(panel, text=controls, bg="#2e2e2e", fg="#90caf9", justify="left",
                 font=(KOR_FONT, 11)).pack(anchor="w", side=tk.BOTTOM, padx=12, pady=12)

    # ── 게임 루프 ────────────────────────────────────────
    def _loop(self):
        """프레임마다: (일시정지/종료가 아니면) 시뮬레이션 한 틱 진행 → 다시 그리기.
        그리고 FRAME_MS 뒤에 자기 자신을 다시 호출하도록 예약한다."""
        if not self.paused and not self.world.over:
            self.world.step()
        self._render()
        self.root.after(config.FRAME_MS, self._loop)

    # ── 화면 그리기 ──────────────────────────────────────
    def _render(self):
        c = self.canvas
        c.delete("all")   # 이전 프레임을 모두 지우고 새로 그린다(가장 단순한 애니메이션 방식)
        # 그리는 순서: 식물(바닥) → 동물 → 트랙터(맨 위)가 되도록 정렬한다.
        for e in sorted(self.world.entities, key=self._z_order):
            self._draw_entity(e)
        if self.world.over:
            self._draw_gameover()
        self._update_panel()

    @staticmethod
    def _z_order(e):
        """그리기 깊이(작을수록 먼저=아래에 그려짐): 식물 0, 동물 1, 트랙터 2."""
        if e.species in ("Grass", "Tree"):
            return 0
        if e.species == "Tractor":
            return 2
        return 1

    def _draw_entity(self, e):
        c = self.canvas
        x, y, r = e.place.x, e.place.y, e.radius

        # 나무의 번식 반경을 옅은 점선으로 보여 준다.
        # 번식터가 여러 곳에 분산되는지 눈으로 확인할 수 있어 상호작용 설명에 도움이 된다.
        breed_radius = getattr(e, "BREED_RADIUS", None)
        if breed_radius is not None:
            c.create_oval(x - breed_radius, y - breed_radius,
                          x + breed_radius, y + breed_radius,
                          outline="#9ccc65", width=1, dash=(4, 5))

        # 숨은 토끼는 풀에 가려 거의 안 보이게(작은 회색 점) 표현한다.
        if isinstance(e, Animal) and getattr(e, "hidden_timer", 0) > 0:
            c.create_text(x, y, text="•", fill="#9e9e9e", font=(KOR_FONT, 10))
            return

        # 존재/충돌 범위를 나타내는 옅은 원과, 종을 알려주는 이모지.
        c.create_oval(x - r, y - r, x + r, y + r, outline=e.color, width=2)
        c.create_text(x, y, text=e.emoji, font=(EMOJI_FONT, max(11, int(r * 1.35))))

        # 기절(코끼리 stomp)당한 포식자는 노란 고리로 표시해 방어가 통한 것을 보여준다.
        if getattr(e, "stun_timer", 0) > 0:
            c.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3,
                          outline="#fff176", width=2)

        # 동물은 체력바를 머리 위에 그린다(시간에 따른 상태 변화를 눈으로 확인).
        if isinstance(e, Animal):
            self._draw_hp_bar(e, x, y - r - 6)

    def _draw_hp_bar(self, animal, cx, cy):
        """동물 체력바: 회색 배경 위에 (현재 체력/최대 체력) 비율만큼 초록 막대를 그린다."""
        ratio = max(0.0, min(1.0, animal.hp / animal.max_hp))
        w = animal.radius * 2
        x0, y0 = cx - animal.radius, cy
        self.canvas.create_rectangle(x0, y0, x0 + w, y0 + 3, fill="#555", width=0)
        self.canvas.create_rectangle(x0, y0, x0 + w * ratio, y0 + 3,
                                     fill="#66bb6a", width=0)

    def _draw_gameover(self):
        """종료 화면: 반투명 검은 막 위에 종료 사유와 재시작 안내를 띄운다."""
        c = self.canvas
        cx, cy = config.WORLD_W / 2, config.WORLD_H / 2
        # stipple='gray50' 로 빗금 반투명 효과를 낸다(tkinter 에는 실제 알파가 없음).
        c.create_rectangle(0, 0, config.WORLD_W, config.WORLD_H,
                           fill="#000000", stipple="gray50", width=0)
        c.create_text(cx, cy - 24, text="\U0001F69C  " + self.world.over_message,
                      fill="white", font=(KOR_FONT, 20, "bold"))
        c.create_text(cx, cy + 20, text="[R] 다시 시작        [Q] 종료",
                      fill="#ffd54f", font=(KOR_FONT, 15))

    def _update_panel(self):
        """오른쪽 패널의 변하는 값(시간/상태/개체 수/로그)을 갱신한다."""
        secs = self.world.tick * config.FRAME_MS // 1000   # 틱 → 초 환산(0나눗셈 없이 정확)
        if self.world.over:
            status = "☠ 종료"
        elif self.paused:
            status = "⏸ 일시정지"
        else:
            status = "▶ 진행 중"
        disaster = "  (트랙터 진격 중)" if self.world.disaster_active and not self.world.over else ""
        self.lbl_info.config(text=f"경과 시간: {secs}초   (tick {self.world.tick})\n"
                                  f"상태: {status}{disaster}")

        stats = self.world.stats()
        lines = [f"{config.PALETTE[sp][0]} {config.KOR_NAME[sp]} : {stats.get(sp, 0)}"
                 for sp in DISPLAY_ORDER]
        self.lbl_stats.config(text="\n".join(lines))

        self.lbl_log.config(text="\n".join(self.world.events) or "(아직 조용한 초원...)")

    # ── 키 입력 처리 ─────────────────────────────────────
    def _on_key(self, event):
        """키보드 조작: D=재난, Space=일시정지, R=재시작, Q/Esc=종료."""
        k = event.keysym.lower()
        if k == "d":
            self.world.trigger_disaster()
        elif k == "space":
            self.paused = not self.paused
        elif k == "r":
            self._restart()
        elif k in ("q", "escape"):
            self.root.destroy()

    def _restart(self):
        """생태계를 처음부터 다시 시작한다(새 World 생성)."""
        self.world = World()
        self.paused = False
