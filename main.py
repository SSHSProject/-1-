"""main.py — 프로그램 진입점.

담당: 홍순율(GUI · 물리엔진)
역할: tkinter 창을 만들고 EcosystemApp(생태계 GUI)을 실행한다.
사용법: 터미널에서  python3 main.py  로 실행한다(외부 라이브러리 설치 불필요).

[생성형 AI 활용] 전체 프로그램 골격은 생성형 AI(Claude)의 도움을 받았다.
"""

import tkinter as tk

from gui import EcosystemApp


def main():
    root = tk.Tk()
    root.title("심심한 초원의 제왕 홍순율 — 초원 생태계 시뮬레이션")
    root.resizable(False, False)   # 창 크기 고정(레이아웃이 흐트러지지 않게)
    EcosystemApp(root)
    root.mainloop()                # tkinter 이벤트 루프 시작(창이 닫힐 때까지 실행)


if __name__ == "__main__":
    main()
