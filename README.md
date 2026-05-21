# FormatFlow AI

**Cursor for academic paper formatting** — upload DOCX, watch live AI formatting logs, edit in TipTap, check IEEE compliance, export DOCX.

## Architecture

```
DOCX → Semantic JSON → Rules Engine → Renderer → DOCX/PDF
```

| Layer | Stack |
|-------|--------|
| Web | Next.js 14, TypeScript, Tailwind, Framer Motion, TipTap, Zustand |
| API | FastAPI, python-docx, Pydantic |
| MVP format | IEEE |

## Project structure

```
research formating/
├── web/                 # Next.js 14 app (primary UI)
├── backend/             # FastAPI
└── frontend/            # Legacy Vite app (optional)
```

## Quick start

### Backend

```powershell
cd backend
.\venv\Scripts\activate
# Ensure backend\.env has SKIP_AUTH=true for local demo
python run.py
```

API: http://127.0.0.1:8000

### Web (FormatFlow AI)

```powershell
cd web
npm install
npm run dev
```

App: http://localhost:3000

## User flow

1. **Landing** → Get Started
2. **Upload** → drag `.docx`
3. **Templates** → select IEEE (MVP)
4. **Workspace** → live logs + original | AI actions | editable preview
5. **Export DOCX**

## FormatFlow API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/formatflow/upload` | Upload & parse DOCX to semantic JSON |
| POST | `/formatflow/format/stream` | SSE live formatting steps |
| GET | `/formatflow/documents/{id}` | Get original + formatted HTML |
| PATCH | `/formatflow/documents/{id}` | Save editor HTML |
| GET | `/formatflow/compliance/{id}` | Compliance report |
| GET | `/formatflow/export/{id}` | Download formatted DOCX |

## Environment

**backend/.env**
```
SKIP_AUTH=true
OPENAI_API_KEY=          # optional, enhances suggestions later
```

## MVP scope

- [x] DOCX upload & semantic parsing
- [x] IEEE rules engine & compliance score
- [x] Live SSE formatting logs
- [x] TipTap editable preview
- [x] DOCX export
- [ ] PDF export (Pandoc)
- [ ] ACM, APA, other templates
- [ ] PostgreSQL / Supabase persistence
