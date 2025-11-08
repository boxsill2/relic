# f1_get_replay_data.py
import sys
import json
import requests
import pandas as pd
import time

apiurl = "https://api.openf1.org/v1"

def api(endpoint, a):
    try:
        url = f"{apiurl}/{endpoint}"
        response = requests.get(url, params=a, timeout=600)
        response.raise_for_status()
        time.sleep(1)  # API 예절상 대기
        return response.json()
    except requests.RequestException as e:
        return {"error": f"API fetching failed for {endpoint}: {str(e)}"}

def  error(session_key, locations):
    # 에러 응답 가드
    if isinstance(locations, dict) and "error" in locations:
        return {"session_key": session_key, "error": "현재 F1 경기가 진행하고 있으므로 데이터를 가져올 수 없습니다."}

    # DataFrame 변환 및 시간 파싱
    loc = pd.DataFrame(locations)
    if 'date' in loc.columns:
        loc['date'] = pd.to_datetime(loc['date'])

    
    frames = {}
    for _, row in loc.iterrows():
        ts = row['date']
        ts_ms = int(ts.timestamp() * 1000)
        screen = frames.setdefault(ts_ms, {"t": ts_ms, "positions": [], "driver_standings": {}})
        screen["positions"].append({
            "driver_number": row.get('driver_number'),
            "x": row.get('x'),
            "y": row.get('y')
        })

    # 정렬 및 검증
    frames = sorted(frames.values(), key=lambda f: f['t'])
    if not frames:
        return {"session_key": session_key, "error": "처리할 유효한 프레임이 없습니다."}

    X = [p["x"] for f in frames for p in f["positions"] if p.get("x") is not None]
    Y = [p["y"] for f in frames for p in f["positions"] if p.get("y") is not None]
    screen = {"minX": min(X), "maxX": max(X), "minY": min(Y), "maxY": max(Y)} if X and Y else None

    # 재생 구간(ms)
    ms = frames[-1]['t'] - frames[0]['t']

    return {"session_key": session_key, "duration_ms": ms, "bbox": screen, "frames": frames}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "session_key 인자가 필요합니다."}, ensure_ascii=False))
        sys.exit(1)

    session_key = sys.argv[1]
    a = {"session_key": session_key}

    # /location 만 호출
    loc = api("location", a)

    replay = process_data(session_key, loc)

    print(json.dumps(replay, ensure_ascii=False))

if __name__ == "__main__":
    main()
