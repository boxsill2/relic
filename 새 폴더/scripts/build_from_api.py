import requests
import json
from datetime import datetime
import os
import re
import time

# --- CONFIG ---

jolpiurl = "https://api.jolpi.ca/ergast/f1"
openf1url = "https://api.openf1.org/v1"

outresult1 = "public/data/stats"
outresult2 = "public/data"

schedulefile = "public/data/schedule.json"
year = 2025

teamcolor = "f1_team.json"

# Slug (URL) 수동 수정
slugfix = {
    "de_vries": "nyck-de-vries",
    "hulkenberg": "nico-hulkenberg",
    "kevin_magnussen": "kevin-magnussen"
}

# 이름 수동 수정
namefix = {
    "Nico Hülkenberg": "Nico Hulkenberg"
}

def getrequest(url, retries=3, delay=30):
    for i in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 429:
                print(f"  -> Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[HTTP ERROR] {e}")
            if i < retries - 1:
                print(f"  -> Retrying... ({i+1}/{retries})")
                time.sleep(delay)
            else:
                return None
    return None

def slug(name):
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')

def getdriver():
    url = f"{jolpiurl}/{year}/drivers.json"
    response = getrequest(url)
    if not response or response.status_code != 200:
        print(f"[HTTP ERROR] Failed to fetch current drivers from url: {url}")
        return []
    data = response.json()
    drivers = data['MRData']['DriverTable']['Drivers']

    driverlist = []
    for d in drivers:
        fullname = f"{d['givenName']} {d['familyName']}"
        if fullname in namefix:
            fullname = namefix[fullname]

        # ⬇︎ 함수명(slug)과 겹치지 않도록 지역변수명을 slugstr로 변경
        slugstr = slug(fullname)
        if d['driverId'] in slugfix:
            slugstr = slugfix[d['driverId']]

        drivernum = d.get('permanentNumber', '')

        driverinfo = {
            "driverId": d['driverId'],
            "slug": slugstr,
            "full_name": fullname,
            "number": drivernum,
            "code": d.get('code', ''),
            "nationality": d['nationality'],
            "photo_src": f"/images/drivers/{drivernum}.png" if drivernum else ""
        }
        driverlist.append(driverinfo)
    return driverlist

def driverseason(driver_id, season):
    seasonstat = {}
    url_results = f"{jolpiurl}/{season}/drivers/{driver_id}/results.json"
    res_results = getrequest(url_results)
    if not res_results or res_results.status_code != 200:
        return None, None
    races = res_results.json()['MRData']['RaceTable']['Races']

    if not races:
        return {}, None

    seasonstat['gp_races'] = len(races)
    seasonstat['gp_points'] = sum(float(r['Results'][0]['points']) for r in races)
    seasonstat['gp_podiums'] = sum(1 for r in races if r['Results'][0].get('position') and r['Results'][0]['position'].isdigit() and int(r['Results'][0]['position']) <= 3)
    seasonstat['gp_top10'] = sum(1 for r in races if r['Results'][0].get('position') and r['Results'][0]['position'].isdigit() and int(r['Results'][0]['position']) <= 10)

    dnfs = 0
    for r in races:
        status = r['Results'][0]['status']
        if 'Finished' not in status and '+' not in status:
            dnfs += 1
    seasonstat['dnfs'] = dnfs

    url_standings = f"{jolpiurl}/{season}/drivers/{driver_id}/driverStandings.json"
    res_standings = getrequest(url_standings)
    if res_standings and res_standings.status_code == 200:
        grid = res_standings.json()['MRData']['StandingsTable']['StandingsLists']
        if grid and grid[0].get('DriverStandings'):
            drivergrid = grid[0]['DriverStandings'][0]
            seasonstat['season_position'] = drivergrid.get('position')
            seasonstat['season_points'] = drivergrid.get('points')

    teamname = races[-1]['Results'][0]['Constructor']['name'] if races else None
    return seasonstat, teamname

def drivercareer(driver_id):
    careerstats = {}

    url = f"{jolpiurl}/drivers/{driver_id}/results.json?limit=1000"
    res = getrequest(url)
    if not res or res.status_code != 200:
        return None
    races = res.json()['MRData']['RaceTable']['Races']

    careerstats['gp_entered'] = len(races)
    careerstats['career_points'] = sum(float(r['Results'][0]['points']) for r in races)
    careerstats['podiums'] = sum(1 for r in races if r['Results'][0].get('position') and r['Results'][0]['position'].isdigit() and int(r['Results'][0]['position']) <= 3)

    dnf = 0
    for r in races:
        stats = r['Results'][0]['status']
        if 'Finished' not in stats and '+' not in stats:
            dnf += 1
    careerstats['dnfs'] = dnf

    poles_res = getrequest(f"{jolpiurl}/drivers/{driver_id}/results/1.json")
    if poles_res and poles_res.status_code == 200:
        careerstats['poles'] = int(poles_res.json()['MRData']['total'])
    else:
        careerstats['poles'] = 0

    bestfinish = float('inf')
    for r in races:
        pos_str = r['Results'][0].get('position')
        if pos_str and pos_str.isdigit():
            pos = int(pos_str)
            if pos < bestfinish:
                bestfinish = pos
    careerstats['best_finish'] = bestfinish if bestfinish != float('inf') else '-'

    best_grid_res = getrequest(f"{jolpiurl}/drivers/{driver_id}/qualifying.json?limit=1000")
    if best_grid_res and best_grid_res.status_code == 200:
        quresults = best_grid_res.json()['MRData']['RaceTable']['Races']
        if quresults:
            bestgrid = [int(q['QualifyingResults'][0]['position']) for q in quresults if q.get('QualifyingResults') and q['QualifyingResults'][0].get('position')]
            if bestgrid:
                careerstats['best_grid'] = min(bestgrid)
            else:
                careerstats['best_grid'] = '-'
        else:
            careerstats['best_grid'] = '-'
    else:
        careerstats['best_grid'] = '-'

    seasons_res = getrequest(f"{jolpiurl}/drivers/{driver_id}/seasons.json?limit=100")
    if not seasons_res or seasons_res.status_code != 200:
        return None

    seasons = [s['season'] for s in seasons_res.json()['MRData']['SeasonTable']['Seasons']]

    grid1 = []
    for season in seasons:
        standing_res = getrequest(f"{jolpiurl}/{season}/drivers/{driver_id}/driverStandings.json")
        if standing_res and standing_res.status_code == 200:
            seasongrid = standing_res.json()['MRData']['StandingsTable']['StandingsLists']
            if seasongrid:
                grid1.extend(seasongrid)

    if grid1:
        valid_standings = [
            s['DriverStandings'][0] for s in grid1
            if s.get('DriverStandings') and s['DriverStandings'][0].get('position')
        ]
        if valid_standings:
            careerstats['titles'] = sum(1 for st in valid_standings if st['position'] == '1')
        else:
            careerstats['titles'] = 0
    else:
        careerstats['titles'] = 0

    return careerstats

# OpenF1에서 Race 세션을 받아 schedule.json
def get_race_sessions(years):
    """
    OpenF1 /sessions에서 각 연도의 Race 세션을 모두 가져와
    날짜 내림차순으로 정렬하여 중복 제거 후 반환.
    반환 스키마는 schedule.json에 맞춤.
    """
    # ⬇︎ 정수 하나를 넘겨도 동작하도록 보정
    if isinstance(years, int):
        years = [years]

    sessions = []
    for y in years:
        url = f"{openf1url}/sessions?session_name=Race&year={y}"
        print(f"[OpenF1] fetching: {url}")
        res = getrequest(url)
        if not res or res.status_code != 200:
            print(f"  -> skip (status: {getattr(res, 'status_code', 'N/A')})")
            continue
        try:
            arr = res.json()
        except Exception as e:
            print(f"  -> json parse error: {e}")
            continue

        for s in arr:
            try:
                item = {
                    "session_key": s.get("session_key"),
                    "session_name": s.get("session_name"),
                    "meeting_name": s.get("meeting_name") or s.get("location") or "",
                    "country_name": s.get("country_name") or "",
                    "date_start": s.get("date_start"),
                    "date_end": s.get("date_end")
                }
                if item["session_key"] and item["session_name"] and item["date_start"]:
                    sessions.append(item)
            except Exception:
                pass

    seen = set()
    dedup_sorted = []
    for s in sorted(sessions, key=lambda x: x["date_start"], reverse=True):
        if s["session_key"] in seen:
            continue
        seen.add(s["session_key"])
        dedup_sorted.append(s)
    return dedup_sorted

def write_schedule_json(items, out_path=schedulefile):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} sessions to {out_path}")

def main():
    # 출력 경로 준비
    if not os.path.exists(outresult1):
        os.makedirs(outresult1)
    os.makedirs(outresult2, exist_ok=True)

    # 팀 컬러 로드
    try:
        with open(teamcolor, 'r', encoding='utf-8') as f:
            team_colors_data = json.load(f)
        team_color_map = {team['name']: team['teamColor'] for team in team_colors_data}
    except FileNotFoundError:
        print(f"Error: '{teamcolor}' not found. Team colors will not be added.")
        team_color_map = {}

    # 드라이버 목록
    driverlist = getdriver()

    # 드라이버별 통계 산출/저장
    for driver in driverlist:
        print(f"Processing {driver['full_name']}...")

        seasonstats, team_name = driverseason(driver['driverId'], year)
        careerstats = drivercareer(driver['driverId'])

        if team_name:
            driver['team_name'] = team_name
            driver['team_colour'] = team_color_map.get(team_name, '#FFFFFF')

        driverstats = {
            "info": driver,
            "season": seasonstats,
            "career": careerstats
        }

        output = os.path.join(outresult1, f"{driver['slug']}.json")
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(driverstats, f, ensure_ascii=False, indent=2)

        print(f"  -> Saved stats to {output}")
        time.sleep(1.1)

    driversout = os.path.join(outresult2, "drivers.json")
    with open(driversout, 'w', encoding='utf-8') as f:
        json.dump(driverlist, f, ensure_ascii=False, indent=2)
    print(f"\nSaved all drivers list to {driversout}")

    try:
        sessions = get_race_sessions(year)
        if sessions:
            write_schedule_json(sessions, schedulefile)
        else:
            print("Warning: No sessions fetched from OpenF1; schedule.json not updated.")
    except Exception as e:
        print(f"Schedule update failed: {e}")

if __name__ == "__main__":
    main()
