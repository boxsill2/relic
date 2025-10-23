# get_driver_locations.py (통합 버전)
import sys
import requests
import json
import pandas as pd
from datetime import datetime

# OpenF1 API 기본 URL
BASE_URL = "https://api.openf1.org/v1"

def get_data(endpoint, params, timeout=30):
    """지정된 엔드포인트에서 데이터를 가져옵니다."""
    try:
        url = f"{BASE_URL}/{endpoint}"
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        data = response.json()
        # 데이터가 단일 객체로 올 경우 리스트로 감싸기
        return data if isinstance(data, list) else [data] if data else []
    except requests.exceptions.Timeout:
        # 타임아웃 발생 시 빈 리스트와 함께 오류 메시지 반환 고려
        print(f"Error: Timeout occurred while fetching {endpoint}", file=sys.stderr)
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {endpoint}: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError as e:
        # 응답 내용을 함께 출력하여 디버깅 용이하게 함
        print(f"Error decoding JSON from {endpoint}: {e}. Response text: '{response.text[:200]}...' ", file=sys.stderr)
        return []
    except Exception as e:
        print(f"An unexpected error occurred while fetching {endpoint}: {e}", file=sys.stderr)
        return []


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(json.dumps({"error": "세션 키, 시작 시간, 종료 시간을 인자로 전달해야 합니다."}))
        sys.exit(1)

    session_key = sys.argv[1]
    start_time_str = sys.argv[2]
    end_time_str = sys.argv[3]

    combined_result = {
        "error": None, # 오류 메시지 필드 추가
        "locations": [],
        "positions": [],
        "car_data": [],
        "race_control": [],
        "timing": [] # 라이브 타이밍 결과 추가
    }

    # --- 1. 시간 범위 데이터 가져오기 (기존 로직) ---
    try:
        time_range_params = {
            "session_key": session_key,
            "date>": start_time_str,
            "date<": end_time_str
        }
        # 각 데이터 병렬 요청 대신 순차 요청 (오류 발생 시 원인 파악 용이)
        combined_result["locations"] = get_data("location", time_range_params)
        combined_result["positions"] = get_data("position", time_range_params)
        combined_result["car_data"] = get_data("car_data", time_range_params)
        combined_result["race_control"] = get_data("race_control", time_range_params)

        # --- 2. 최신 라이브 타이밍 데이터 가져오기 (추가된 로직) ---
        latest_params = {"session_key": session_key, "date>=": "latest"}

        # 최신 포지션 데이터
        latest_position_data = get_data("position", latest_params)
        if latest_position_data:
            pos_df = pd.DataFrame(latest_position_data)
            pos_df['date'] = pd.to_datetime(pos_df['date'])
            # driver_number가 없는 경우 제외 (오류 방지)
            pos_df = pos_df.dropna(subset=['driver_number'])
            pos_df['driver_number'] = pos_df['driver_number'].astype(int) # 정수형으로 변환
            # 각 드라이버의 가장 최신 데이터 선택
            latest_pos_df = pos_df.loc[pos_df.groupby('driver_number')['date'].idxmax()]
            latest_pos_df = latest_pos_df.sort_values(by='position') # 포지션 순 정렬

            # 최신 랩 데이터
            latest_lap_data = get_data("laps", latest_params)
            laps_df = pd.DataFrame(latest_lap_data) if latest_lap_data else pd.DataFrame()
            latest_laps_map = {}
            if not laps_df.empty and 'driver_number' in laps_df.columns:
                laps_df = laps_df.dropna(subset=['driver_number'])
                laps_df['driver_number'] = laps_df['driver_number'].astype(int)
                laps_df['date_start'] = pd.to_datetime(laps_df['date_start'])
                latest_laps = laps_df.loc[laps_df.groupby('driver_number')['date_start'].idxmax()]
                latest_laps_map = latest_laps.set_index('driver_number').to_dict('index')

            # 최신 인터벌 데이터
            latest_interval_data = get_data("intervals", latest_params)
            intervals_df = pd.DataFrame(latest_interval_data) if latest_interval_data else pd.DataFrame()
            latest_intervals_map = {}
            if not intervals_df.empty and 'driver_number' in intervals_df.columns:
                intervals_df = intervals_df.dropna(subset=['driver_number'])
                intervals_df['driver_number'] = intervals_df['driver_number'].astype(int)
                intervals_df['date'] = pd.to_datetime(intervals_df['date'])
                latest_intervals = intervals_df.loc[intervals_df.groupby('driver_number')['date'].idxmax()]
                latest_intervals_map = latest_intervals.set_index('driver_number').to_dict('index')

            # 라이브 타이밍 데이터 취합
            live_timing_result = []
            for index, row in latest_pos_df.iterrows():
                driver_number = int(row['driver_number']) # 정수형 확인
                latest_lap = latest_laps_map.get(driver_number, {})
                latest_interval = latest_intervals_map.get(driver_number, {})

                status = "On Track" # 단순화된 상태

                # interval 또는 gap_to_leader 값이 NaN/None 이 아닌지 확인 후 처리
                interval_val = latest_interval.get('interval')
                gap_val = latest_interval.get('gap_to_leader')
                lap_duration_val = latest_lap.get('lap_duration')

                entry = {
                    "position": int(row['position']) if pd.notna(row['position']) else None,
                    "driver_number": driver_number,
                    "status": status,
                    "interval": float(interval_val) if pd.notna(interval_val) else None,
                    "gap_to_leader": float(gap_val) if pd.notna(gap_val) else None,
                    "lap_time": float(lap_duration_val) if pd.notna(lap_duration_val) else None,
                    "lap_number": int(latest_lap['lap_number']) if pd.notna(latest_lap.get('lap_number')) else None
                }
                live_timing_result.append(entry)
            combined_result["timing"] = live_timing_result

        else:
             combined_result["timing"] = [] # 포지션 데이터 없으면 타이밍 비움

    except Exception as e:
        # 전체 로직에서 발생한 예외 처리
        combined_result["error"] = f"데이터 처리 중 오류 발생: {e}"
        # 오류 발생 시 기존 데이터는 유지될 수 있으나, 부분 데이터일 수 있음
        print(f"Unhandled error in main block: {e}", file=sys.stderr)


    # --- 최종 결과 출력 ---
    # NaN 값을 JSON null로 변환하여 출력
    def handle_nan(obj):
        if isinstance(obj, float) and pd.isna(obj):
            return None
        return obj

    print(json.dumps(combined_result, default=handle_nan, indent=None))