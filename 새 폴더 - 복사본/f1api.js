// f1api.js
const fs = require('fs');
const path = require('path');
const express = require('express');
const { spawn } = require('child_process');
const driversData = require('./public/data/drivers.json');
const driverDescriptions = require('./public/data/driver_descriptions.json');
const teamsData = require('./public/data/teams.json'); // 팀 데이터 로드 확인
const router = express.Router();
const ROOT_DIR = __dirname;
const PUBLIC_DIR = path.join(ROOT_DIR, 'public');
const DATA_DIR = path.join(PUBLIC_DIR, 'data');

// readJSON 함수는 동기 함수로 유지
function readJSON(filePath) { try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); } catch { return null; } }
function slugify(text) { return String(text || '').toLowerCase().trim().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-'); }

// --- 라우팅 설정 ---
router.get('/', (req, res) => res.redirect('/schedule'));

router.get('/schedule', (req, res) => { // async 제거
    try {
        const schedule = readJSON(path.join(DATA_DIR, 'schedule.json'));
        res.render('schedule', { year: new Date().getFullYear(), schedule: schedule || [], error: null, currentPage: 'schedule' });
    } catch (e) { res.render('schedule', { year: new Date().getFullYear(), schedule: [], error: '스케줄 데이터를 불러오지 못했습니다.', currentPage: 'schedule' }); }
});

// 드라이버 목록 페이지
router.get('/drivers', (req, res) => { // async 제거
    try {
        const drivers = readJSON(path.join(DATA_DIR, 'drivers.json'));
        res.render('drivers', { drivers: drivers || [], currentPage: 'drivers', error: null });
    } catch (e) {
        res.status(500).render('drivers', { drivers: [], error: '드라이버 데이터를 불러오는 데 실패했습니다.', currentPage: 'drivers' });
    }
});

// 드라이버 상세 페이지
router.get('/drivers/:driverName', (req, res) => { // async 제거
  const driverName = req.params.driverName;
  const driver = driversData.find(d => d.slug === driverName);

  if (driver) {
    const description = driverDescriptions[driver.slug];
    let driverStats = null;
    try {
      const statsFilePath = path.join(DATA_DIR, 'stats', `${driver.slug}.json`);
      driverStats = readJSON(statsFilePath);
    } catch (e) {
      console.error(`Error reading stats file for ${driver.slug}:`, e);
    }
    const driverDetailData = {
      ...driver,
      description: description || "설명 없음",
      stats: driverStats || { season: null, career: null }
    };
    res.render('driver-detail', {
        driver: driverDetailData,
        currentPage: 'drivers',
        error: null
    });
  } else {
    res.status(404).render('driver-detail', {
        driver: null,
        error: 'Driver not found',
        currentPage: 'drivers'
    });
  }
});

// 팀 목록 페이지
router.get('/teams', (req, res) => { // async 제거
    try {
        const teams = readJSON(path.join(DATA_DIR, 'teams.json'));
        res.render('teams', { teams: teams || [], currentPage: 'teams', error: null });
    } catch (e) {
        res.status(500).render('teams', { teams: [], error: '팀 데이터를 불러오는 데 실패했습니다.', currentPage: 'teams' });
    }
});

// --- >>> 팀 상세 페이지 라우트 (디버깅 로그 추가됨) <<< ---
router.get('/teams/:teamName', (req, res) => {
  const teamSlug = req.params.teamName; // URL에서 팀 슬러그 가져오기
  console.log(`\n--- Team Detail Request ---`); // 로그 시작 구분
  console.log(`[Team Detail] Requested team slug: "${teamSlug}"`); // 요청된 슬러그 로그

  // teams.json 데이터에서 slug가 일치하는 팀 찾기
  const team = teamsData.find(t => t.slug === teamSlug);

  if (team) {
    console.log(`[Team Detail] Found team object with name: "${team.name}"`); // 찾은 팀 이름 로그

    // 해당 팀 소속 드라이버 찾기
    console.log(`[Team Detail] Filtering drivers where driver.team_name === "${team.name}"`); // 필터링 조건 로그
    const teamDrivers = driversData.filter(driver => {
         // 각 드라이버 비교 로그 (매우 상세하므로 필요시에만 주석 해제)
         // console.log(`  -> Comparing: Driver "${driver.team_name}" === Team "${team.name}" -> ${driver.team_name === team.name}`);
         return driver.team_name === team.name; // team.name 사용 확인
     });
    console.log(`[Team Detail] Found ${teamDrivers.length} drivers.`); // 찾은 드라이버 수 로그
    if (teamDrivers.length > 0) {
      console.log(`[Team Detail] Driver names: ${teamDrivers.map(d => d.full_name).join(', ')}`); // 찾은 드라이버 이름 목록 로그
    }

    // team-detail.ejs 템플릿 렌더링
    res.render('team-detail', {
      team: team,
      drivers: teamDrivers,
      currentPage: 'teams',
      error: null
    });
  } else {
    console.log(`[Team Detail] Team not found for slug: "${teamSlug}"`); // 팀 못 찾음 로그
    res.status(404).render('team-detail', {
        team: null,
        drivers: [],
        error: 'Team not found',
        currentPage: 'teams'
    });
  }
});

// 용어집 페이지
router.get('/glossary', (req, res) => { // async 제거
    try {
        const terms = readJSON(path.join(ROOT_DIR, 'f1_terms.json'));
        res.render('glossary', { terms: terms || [], currentPage: 'glossary', error: null });
    } catch (e) {
        res.status(500).render('glossary', { terms: [], error: '용어 데이터를 불러오는 데 실패했습니다.', currentPage: 'glossary' });
    }
});

// --- 기존 코드 유지 ---

router.get('/replays/:session_key', (req, res) => { // async 제거
    const { session_key } = req.params;
    try {
        const schedule = readJSON(path.join(DATA_DIR, 'schedule.json'));
        const layouts = readJSON(path.join(DATA_DIR, 'track_layouts.json'));
        const sessionInfo = schedule?.find(s => String(s.session_key) === session_key) || null;

        if (!sessionInfo) {
             return res.status(404).render('race-tracker', { error: '해당 세션 정보를 찾을 수 없습니다.', session_key, driverDirectory: {}, sessionInfo: null, currentPage: 'schedule' });
        }

        const circuitName = sessionInfo.circuit_short_name?.toLowerCase().replace(/\s+/g, '-');
        const layout = layouts?.find(l => l.circuit_short_name === circuitName);

        let trackImageUrl = null;
        if (circuitName) {
            const possibleExtensions = ['avif', 'png', 'webp', 'jpg', 'jpeg'];
            for (const ext of possibleExtensions) {
                const imageName = `${circuitName}.${ext}`;
                const imagePath = path.join(PUBLIC_DIR, 'images', 'tracks', imageName);
                if (fs.existsSync(imagePath)) {
                    trackImageUrl = `/images/tracks/${imageName}`;
                    break;
                }
            }
        }

        const drivers = readJSON(path.join(DATA_DIR, 'drivers.json'));
        // f1_team.json 파일명 확인 필요
        const f1Teams = readJSON(path.join(ROOT_DIR, 'f1_team.json')); // 'f1_team.json'이 맞는지 확인

        const driverDirectory = {};
        if (drivers && f1Teams) {
            // f1_team.json 구조에 'name', 'teamColor' 속성이 있는지 확인 필요
            const teamInfoMap = f1Teams.reduce((acc, team) => { acc[team.name] = { color: team.teamColor }; return acc; }, {});
            drivers.forEach(d => { if (d.number) driverDirectory[d.number] = { full_name: d.full_name, team_colour: teamInfoMap[d.team_name]?.color || '#FFFFFF' }; });
        }

        const finalSessionInfo = { ...sessionInfo, trackImageUrl, layout };

        res.render('race-tracker', {
            session_key,
            driverDirectory,
            sessionInfo: finalSessionInfo,
            currentPage: 'schedule',
            error: null
        });
    } catch (e) {
        console.error(e);
        res.status(500).render('race-tracker', { session_key, driverDirectory: {}, sessionInfo: null, error: '페이지 로드 중 오류 발생', currentPage: 'schedule' });
    }
});

router.get('/api/locations/:session_key/:startTime/:endTime', (req, res) => {
    const { session_key, startTime, endTime } = req.params;
    const scriptPath = path.join(ROOT_DIR, 'get_driver_locations.py');
    if (!fs.existsSync(scriptPath)) {
        return res.status(500).json({ error: 'get_driver_locations.py 스크립트를 찾을 수 없습니다.' });
    }
    const pythonProcess = spawn('python', ['-X', 'utf8', scriptPath, session_key, startTime, endTime]);
    let output = '';
    pythonProcess.stdout.setEncoding('utf8');
    pythonProcess.stdout.on('data', (data) => { output += data.toString(); });
    pythonProcess.stderr.on('data', (data) => { console.error(`[Python STDERR]: ${data.toString('utf8')}`); });
    pythonProcess.on('close', (code) => {
        if (code !== 0) return res.status(500).json({ error: '데이터 조회 중 서버 오류 발생' });
        try { res.json(JSON.parse(output)); } catch (e) { res.status(500).json({ error: '스크립트 결과 파싱 실패' }); }
    });
});

// --- 서버 실행 ---
if (require.main === module) {
    const app = express();
    app.set('view engine', 'ejs');
    app.set('views', path.join(__dirname, 'views'));
    app.use(express.static(path.join(__dirname, 'public')));
    app.use('/', router);
    const PORT = process.env.PORT || 8080;
    app.listen(PORT, () => console.log(`서버가 http://localhost:${PORT} 에서 시작되었습니다.`));
}

module.exports = router;