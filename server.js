import path from 'path'
import express from 'express'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
const root = path.join(__dirname, '새 폴더')

app.use(express.static(root))

// SPA fallback: 모든 GET 요청을 index.html로
app.get('*', (_, res) => {
  res.sendFile(path.join(root, 'index.html'))
})

const port = process.env.PORT || 5173
app.listen(port, () => console.log(`listening on ${port}`))
