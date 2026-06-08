import config


class World:
    def __init__(self):
        
        self.entities = [] # 현재 월드에 존재하는 모든 동물/식물 객체를 담는 리스트

       
        self.events = [] # 화면 오른쪽 생태계 일지에 보여 줄 사건 기록

    def log(self, message: str):
    # 사건 기록지 함수
        self.events.append(message)

      
        if len(self.events) > config.MAX_EVENT_LOG:
            self.events = self.events[-config.MAX_EVENT_LOG:] # 기록 개수 최대치 이상되면 리스트 중 마지막 최대치 개수만 남기기

 def within(self, place, radius, predicate): #   특정 위치 place를 기준으로 radius 안에 있는 개체 중, predicate 조건을 만족하는 개체들을 리스트로 반환한다. 사자의 표효 가동 범위에 사용
        
        
        r2 = radius * radius

        result = []
        for e in self.entities:
            # predicate(e)가 False면 조건에 맞지 않으므로 건너뛴다.
            if not predicate(e):
                continue

            # 거리의 제곱이 반지름의 제곱보다 작거나 같으면 범위 안이다.
            if place.distance_sq_to(e.place) <= r2:
                result.append(e)

        return result


def nearest(self, place, predicate, max_dist=float("inf")): # 특정 위치 place를 기준으로 가장 가까운 개체 하나를 찾는다. 가장 가까운 먹잇감 인지할 때 사용

     
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
