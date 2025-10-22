// 간단한 BrowserRouter 구현
const routes = []
function route(path, handler){ routes.push({ path, handler }) }
function match(pathname){
  for(const r of routes){
    // 동적 파라미터 지원: /drivers/:name
    const keys = []
    const regex = new RegExp('^' + r.path.replace(/:[^/]+/g, m => {keys.push(m.slice(1)); return '([^/]+)'}) + '$')
    const m = pathname.match(regex)
    if(m){
      const params = {}; keys.forEach((k,i)=>params[k]=decodeURIComponent(m[i+1]))
      return { handler: r.handler, params }
    }
  }
  return null
}

const drivers = [{name:'홍길동'},{name:'임꺽정'}]

function navigate(to){
  history.pushState({}, '', to)
  render()
}

function render(){
  const m = match(location.pathname)
  const listEl = document.getElementById('list')
  const detailEl = document.getElementById('detail')
  listEl.innerHTML = ''
  detailEl.innerHTML = ''

  if(!m){
    // 홈 또는 /drivers 목록
    const ul = document.getElementById('list')
    drivers.forEach(d=>{
      const li=document.createElement('li')
      const a=document.createElement('a')
      a.href=`/drivers/${encodeURIComponent(d.name)}`
      a.textContent=d.name
      a.addEventListener('click', (e)=>{ e.preventDefault(); navigate(a.getAttribute('href')) })
      li.appendChild(a)
      ul.appendChild(li)
    })
    return
  }

  // 상세
  const { params:{name} } = m
  detailEl.innerHTML = `<h2>Driver: ${name}</h2><p><a id="back" href="/drivers">목록으로</a></p>`
  const back=document.getElementById('back')
  back.addEventListener('click', (e)=>{ e.preventDefault(); navigate('/drivers') })
}

// 라우트 등록
route('/drivers/:name', ()=>{})
route('/drivers', ()=>{})
route('/', ()=>{})

window.addEventListener('popstate', render)

// 최초 렌더
render()
