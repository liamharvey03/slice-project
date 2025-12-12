<!-- 37fb3341-c4b7-4888-ad43-3866c262f8b8 c9e24ca3-ad4b-4a24-8c72-a8f78ecd6d23 -->
# Voyager Rename Verification & Fix Plan

## Phase 0: Fix Missed References (CRITICAL - DO FIRST)

**Issue Found:** Some files have `from src.slice.*` absolute imports that were missed.

### 0.1 Find Remaining Absolute Imports

```bash
grep -r "from src\.slice\." src/ tests/ scripts/ ui/ --include="*.py"
grep -r "import src\.slice" src/ tests/ scripts/ ui/ --include="*.py"
```

### 0.2 Fix All src.slice References

Replace pattern: `from src.slice.` → `from voyager.`

Files to check based on error:

- [src/voyager/api/session_routes.py](src/voyager/api/session_routes.py) (line 4 showed error)
- Any other files found in 0.1

### 0.3 Rename Root Directory

```bash
cd /Users/liamharvey/dev
mv slice voyager
cd voyager
```

**After this step, all subsequent commands assume root is `/Users/liamharvey/dev/voyager`**

---

## Phase 1: Import & Module Resolution

**Goal:** Verify all Python imports resolve correctly to `voyager.*`

### 1.1 Core Module Imports

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from voyager.db import get_engine, ping
from voyager.config import load_settings
from voyager.repositories.thesis_repo import ThesisRepository
from voyager.repositories.observation_repo import ObservationRepository
from voyager.repositories.trade_repo import TradeRepository
from voyager.intelligence.context.data_access import DataAccess
from voyager.sessions.thesis_evaluation_session import ThesisEvaluationSession
from voyager.api.main import app
print('✓ All core imports successful')
"
```

### 1.2 Verify No Remaining References

```bash
grep -r "from slice\." src/ tests/ --include="*.py"
grep -r "import slice" src/ tests/ --include="*.py"
grep -r "src\.slice" src/ tests/ --include="*.py"
```

All should return NO results.

---

## Phase 2: Database & Configuration

**Goal:** Verify database connection and environment variables work

### 2.1 Check VOYAGER_DB_URL

```bash
python -c "
import sys; sys.path.insert(0, 'src')
import os
if not os.getenv('VOYAGER_DB_URL'):
    print('⚠ VOYAGER_DB_URL not set')
else:
    from voyager.config import load_settings
    settings = load_settings()
    print(f'✓ Config loaded successfully')
"
```

### 2.2 Database Connection

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from voyager.db import ping
ping()
print('✓ Database connection successful')
"
```

---

## Phase 3: Repository Layer

**Goal:** Verify repositories work

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from voyager.repositories.thesis_repo import ThesisRepository
from voyager.repositories.observation_repo import ObservationRepository
from voyager.repositories.trade_repo import TradeRepository

thesis_repo = ThesisRepository()
obs_repo = ObservationRepository()
trade_repo = TradeRepository()

print('✓ All repositories instantiated')
print(f'  Theses: {len(thesis_repo.list_all())}')
print(f'  Observations: {len(obs_repo.list_recent(limit=10))}')
print(f'  Trades: {len(trade_repo.list_all())}')
"
```

---

## Phase 4: API Server

**Goal:** Verify FastAPI app starts

### 4.1 API Import & Title

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from voyager.api.main import app
assert app.title == 'Voyager API', f'Wrong title: {app.title}'
print('✓ API imports with correct title')
"
```

### 4.2 Start API (Manual Test)

```bash
export PYTHONPATH=src
uvicorn voyager.api.main:app --reload
```

Then: `curl http://localhost:8000/`

---

## Phase 5: Streamlit UI

**Goal:** Verify UI loads

### 5.1 Launch Streamlit

```bash
export PYTHONPATH=src
streamlit run ui/app.py
```

**Check:** No ModuleNotFoundError, all tabs visible

---

## Phase 6: Test Suite

```bash
export PYTHONPATH=src
pytest tests/phase6 -v --tb=short
```

---

## Phase 7: Scripts

```bash
python scripts/init_db.py --help
```

---

## Success Criteria

**Must Pass:**

- Phase 0: All fixes applied
- Phase 1: Imports work
- Phase 2: DB connects
- Phase 3: Repos work
- Phase 4: API starts
- Phase 5: UI loads

**Should Pass:**

- Phase 6: Tests run

### To-dos

- [ ] Test core module imports resolve to voyager.*
- [ ] Verify database connection and config with VOYAGER_DB_URL
- [ ] Test repository layer instantiation and queries
- [ ] Verify API server starts with Voyager title
- [ ] Test Streamlit UI loads without import errors
- [ ] Run existing test suite to check for breakage
- [ ] Smoke test utility scripts for import errors
- [ ] Optional: Run end-to-end workflow test