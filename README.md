# Music Mood Matcher

Веб-приложение: фронтенд на React + Vite и Python-бэкенд на FastAPI, который подбирает музыку по эмоции (через Spotify / YouTube / iTunes API).

---

## Гайд: как запустить проект после `git clone` на другом устройстве

### 0. Что должно быть установлено заранее

- **Git** — `git --version`
- **Python 3.11** (или 3.10+) — `python3 --version`
- **Node.js 20+** и npm — `node -v`, `npm -v`

Ключи API для Spotify / YouTube уже лежат в `python-backend/.env` — отдельно их получать не надо.

---

### 1. Клонировать репозиторий

```bash
git clone <ссылка-на-репо>
cd <имя-папки-проекта>
```

---

### 2. Поднять бэкенд (Python / FastAPI)

```bash
cd python-backend

# создать своё виртуальное окружение
python3 -m venv venv

# активировать его
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows (PowerShell/CMD)

# поставить зависимости
pip install --upgrade pip
pip install -r requirements.txt
```

Первый `pip install` будет долгим — `torch`, `sentence-transformers`, `opencv` весят прилично (~1–2 ГБ суммарно). Это нормально.

---

### 3. Запустить бэкенд

```bash
# из python-backend, с активным venv
set -a; source .env; set +a              # macOS / Linux
uvicorn app.main:app --reload --port 8000
```

На Windows (PowerShell) аналог `set -a; source .env`:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#=]+)=(.*)$') {
    [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim())
  }
}
uvicorn app.main:app --reload --port 8000
```

Проверка: открыть <http://localhost:8000/docs> — должна появиться Swagger-страничка с эндпоинтами.

---

### 4. Поднять фронтенд (React / Vite)

В **новом окне терминала** (бэкенд оставляем работать):

```bash
cd <корень-проекта>                # туда, где package.json
npm install
npm run dev
```

Vite выведет адрес типа `http://localhost:5173` — это и есть приложение.

---

### 5. Типичные грабли

| Симптом | Что делать |
|---|---|
| `command not found: uvicorn` | Забыли `source venv/bin/activate` |
| `ModuleNotFoundError` после `pip install` | Активирован не тот venv — проверьте, что в начале строки в терминале есть `(venv)` |
| Бэкенд стартует, но 401/403 от Spotify | Забыли `set -a; source .env; set +a` перед `uvicorn` |
| Фронт стучится в `localhost:8000`, а бэк не запущен | Запустите оба сервера параллельно, в разных терминалах |
| Порт 8000 занят | `--port 8001` у uvicorn + поменять адрес в `src/shared/api/backend.ts` |
| Windows, `source` не работает | Используйте `venv\Scripts\activate` и PowerShell-вариант загрузки `.env` выше |

---

## TL;DR — минимум команд

```bash
git clone <url> && cd <repo>

# backend
cd python-backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
set -a; source .env; set +a        # .env уже в репозитории
uvicorn app.main:app --reload --port 8000

# frontend (в другом терминале)
cd ..
npm install
npm run dev
```

---

## Структура проекта

```
.
├── src/                  # фронтенд (React + Vite + MUI + Zustand)
├── python-backend/       # бэкенд (FastAPI)
│   ├── app/              # код приложения
│   ├── requirements.txt  # python-зависимости
│   ├── .env              # ключи API (Spotify, YouTube)
│   └── README.md         # подробности по бэкенду
├── package.json          # зависимости фронта
└── README.md             # этот файл
```
