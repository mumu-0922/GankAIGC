# Paper Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add paper projects so users can group multiple optimization sessions under distinct paper titles.

**Architecture:** Add a `PaperProject` SQLAlchemy model and nullable project linkage on optimization sessions. Expose user-authenticated project CRUD APIs and extend optimization start/list responses with project fields. Update the workspace UI to create/select projects and filter history by project.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite/PostgreSQL-compatible schema, React, Axios, Vite.

---

## File Structure

- Modify `package/backend/app/models/models.py`: add `PaperProject`, relationships, and `OptimizationSession.project_id/task_title`.
- Modify `package/backend/app/schemas.py`: add project request/response schemas and extend optimization schemas.
- Modify `package/backend/app/database.py`: startup migration for missing table/columns in existing SQLite/PostgreSQL deployments.
- Modify `package/backend/app/routes/user.py`: project CRUD endpoints.
- Modify `package/backend/app/routes/optimization.py`: accept project id/task title, validate ownership, filter session list.
- Modify `package/frontend/src/api/index.js`: add project API helpers and pass project filters.
- Modify `package/frontend/src/pages/WorkspacePage.jsx`: project list, create/edit/archive, active project filtering, task title input.
- Add/modify backend tests under `package/backend/tests/`.

---

### Task 1: Backend Project Model and Migration

**Files:**
- Modify: `package/backend/app/models/models.py`
- Modify: `package/backend/app/database.py`
- Test: `package/backend/tests/test_project_api.py`

- [ ] **Step 1: Write failing model/migration smoke test**

Create `package/backend/tests/test_project_api.py`:

```python
from sqlalchemy import inspect

from app.database import engine


def test_project_schema_is_created(client):
    response = client.get("/health")
    assert response.status_code == 200

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "paper_projects" in tables

    session_columns = {column["name"] for column in inspector.get_columns("optimization_sessions")}
    assert "project_id" in session_columns
    assert "task_title" in session_columns
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
cd package\backend
python -m pytest tests/test_project_api.py::test_project_schema_is_created -q
```

Expected: FAIL because `paper_projects`, `project_id`, or `task_title` does not exist.

- [ ] **Step 3: Add model fields**

In `package/backend/app/models/models.py`, add `PaperProject` and relationships:

```python
class PaperProject(Base):
    __tablename__ = "paper_projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_archived = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="paper_projects")
    sessions = relationship("OptimizationSession", back_populates="project")
```

Add to `User`:

```python
paper_projects = relationship("PaperProject", back_populates="user", cascade="all, delete-orphan")
```

Add to `OptimizationSession`:

```python
project_id = Column(Integer, ForeignKey("paper_projects.id"), nullable=True, index=True)
task_title = Column(String(255), nullable=True)
project = relationship("PaperProject", back_populates="sessions")
```

- [ ] **Step 4: Add startup migration**

In `package/backend/app/database.py`, extend the existing init flow with an `ensure_schema_compatibility()` helper that:

```python
from sqlalchemy import inspect, text


def ensure_schema_compatibility():
    inspector = inspect(engine)
    if "optimization_sessions" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("optimization_sessions")}
        with engine.begin() as conn:
            if "project_id" not in columns:
                conn.execute(text("ALTER TABLE optimization_sessions ADD COLUMN project_id INTEGER"))
            if "task_title" not in columns:
                conn.execute(text("ALTER TABLE optimization_sessions ADD COLUMN task_title VARCHAR(255)"))
```

Call it after `Base.metadata.create_all(bind=engine)` in `init_db()`.

- [ ] **Step 5: Run test**

Run:

```powershell
cd package\backend
python -m pytest tests/test_project_api.py::test_project_schema_is_created -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add package/backend/app/models/models.py package/backend/app/database.py package/backend/tests/test_project_api.py
git commit -m "feat: add paper project schema"
```

---

### Task 2: Project CRUD APIs

**Files:**
- Modify: `package/backend/app/schemas.py`
- Modify: `package/backend/app/routes/user.py`
- Test: `package/backend/tests/test_project_api.py`

- [ ] **Step 1: Add failing CRUD tests**

Append to `package/backend/tests/test_project_api.py`:

```python
import app.config as config_module
from app.database import SessionLocal
from app.models.models import User
from app.utils.auth import create_user_access_token, get_password_hash


def _create_user(username="alice"):
    db = SessionLocal()
    try:
        user = User(
            username=username,
            password_hash=get_password_hash("Password123!"),
            access_link=f"http://testserver/access/{username}",
            is_active=True,
            credit_balance=0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_user_access_token(user.id, user.username)
        return user.id, {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_user_can_create_list_update_and_archive_projects(client):
    _, headers = _create_user()

    create_response = client.post(
        "/api/user/projects",
        json={"title": "基于大语言模型的教育应用研究", "description": "投稿前版本"},
        headers=headers,
    )
    assert create_response.status_code == 200
    project = create_response.json()
    assert project["title"] == "基于大语言模型的教育应用研究"
    assert project["description"] == "投稿前版本"
    assert project["is_archived"] is False

    list_response = client.get("/api/user/projects", headers=headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [project["id"]]

    update_response = client.patch(
        f"/api/user/projects/{project['id']}",
        json={"title": "新版题目", "description": "二稿"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "新版题目"
    assert update_response.json()["description"] == "二稿"

    archive_response = client.delete(f"/api/user/projects/{project['id']}", headers=headers)
    assert archive_response.status_code == 200
    assert archive_response.json()["is_archived"] is True

    list_after_archive = client.get("/api/user/projects", headers=headers)
    assert list_after_archive.status_code == 200
    assert list_after_archive.json() == []


def test_user_cannot_update_another_users_project(client):
    _, alice_headers = _create_user("alice")
    _, bob_headers = _create_user("bob")
    project = client.post("/api/user/projects", json={"title": "Alice Paper"}, headers=alice_headers).json()

    response = client.patch(
        f"/api/user/projects/{project['id']}",
        json={"title": "Bob Edit"},
        headers=bob_headers,
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
cd package\backend
python -m pytest tests/test_project_api.py -q
```

Expected: FAIL because project endpoints do not exist.

- [ ] **Step 3: Add schemas**

In `package/backend/app/schemas.py`, add:

```python
class PaperProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class PaperProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_archived: Optional[bool] = None


class PaperProjectResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Add project routes**

In `package/backend/app/routes/user.py`, import `PaperProject` and the schemas. Add:

```python
@router.get("/projects", response_model=List[PaperProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    return (
        db.query(PaperProject)
        .filter(PaperProject.user_id == current_user.id, PaperProject.is_archived.is_(False))
        .order_by(PaperProject.updated_at.desc(), PaperProject.created_at.desc())
        .all()
    )


@router.post("/projects", response_model=PaperProjectResponse)
async def create_project(
    payload: PaperProjectCreate,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    project = PaperProject(user_id=current_user.id, title=payload.title.strip(), description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/projects/{project_id}", response_model=PaperProjectResponse)
async def update_project(
    project_id: int,
    payload: PaperProjectUpdate,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    project = db.query(PaperProject).filter(PaperProject.id == project_id, PaperProject.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="论文项目不存在")
    if payload.title is not None:
        project.title = payload.title.strip()
    if payload.description is not None:
        project.description = payload.description
    if payload.is_archived is not None:
        project.is_archived = payload.is_archived
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", response_model=PaperProjectResponse)
async def archive_project(
    project_id: int,
    current_user: User = Depends(get_current_user_from_bearer),
    db: Session = Depends(get_db),
):
    project = db.query(PaperProject).filter(PaperProject.id == project_id, PaperProject.user_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="论文项目不存在")
    project.is_archived = True
    db.commit()
    db.refresh(project)
    return project
```

- [ ] **Step 5: Run tests**

Run:

```powershell
cd package\backend
python -m pytest tests/test_project_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add package/backend/app/schemas.py package/backend/app/routes/user.py package/backend/tests/test_project_api.py
git commit -m "feat: add paper project api"
```

---

### Task 3: Attach Optimization Sessions to Projects

**Files:**
- Modify: `package/backend/app/schemas.py`
- Modify: `package/backend/app/routes/optimization.py`
- Test: `package/backend/tests/test_project_api.py`

- [ ] **Step 1: Add failing optimization linkage tests**

Append:

```python
def test_start_optimization_stores_project_and_task_title(client):
    _, headers = _create_user()
    project = client.post("/api/user/projects", json={"title": "Paper A"}, headers=headers).json()

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_enhance",
            "billing_mode": "platform",
            "project_id": project["id"],
            "task_title": "摘要降 AI",
        },
        headers=headers,
    )

    assert response.status_code == 402


def test_start_optimization_rejects_another_users_project(client):
    _, alice_headers = _create_user("alice")
    _, bob_headers = _create_user("bob")
    project = client.post("/api/user/projects", json={"title": "Alice Paper"}, headers=alice_headers).json()

    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_enhance",
            "billing_mode": "byok",
            "project_id": project["id"],
            "task_title": "bad attach",
        },
        headers=bob_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "论文项目不存在"
```

Then adjust the first test to give the user credits and use BYOK or platform depending existing billing rules. The final expected behavior is:

```python
def test_start_optimization_stores_project_and_task_title(client):
    from app.database import SessionLocal
    from app.models.models import OptimizationSession, User

    user_id, headers = _create_user()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        user.credit_balance = 1
        db.commit()
    finally:
        db.close()

    project = client.post("/api/user/projects", json={"title": "Paper A"}, headers=headers).json()
    response = client.post(
        "/api/optimization/start",
        json={
            "original_text": "test paragraph",
            "processing_mode": "paper_enhance",
            "billing_mode": "platform",
            "project_id": project["id"],
            "task_title": "摘要降 AI",
        },
        headers=headers,
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        session = db.query(OptimizationSession).filter(OptimizationSession.id == response.json()["id"]).one()
        assert session.project_id == project["id"]
        assert session.task_title == "摘要降 AI"
    finally:
        db.close()
```

- [ ] **Step 2: Run failing tests**

Run:

```powershell
cd package\backend
python -m pytest tests/test_project_api.py::test_start_optimization_stores_project_and_task_title tests/test_project_api.py::test_start_optimization_rejects_another_users_project -q
```

Expected: FAIL because schemas and routes do not accept `project_id`.

- [ ] **Step 3: Extend schemas**

In `OptimizationCreate` add:

```python
project_id: Optional[int] = None
task_title: Optional[str] = Field(default=None, max_length=255)
```

In `SessionResponse` add:

```python
project_id: Optional[int] = None
project_title: Optional[str] = None
task_title: Optional[str] = None
```

- [ ] **Step 4: Update optimization start**

In `package/backend/app/routes/optimization.py`:

- Import `PaperProject`.
- Before creating the session, if `data.project_id` is present, query it with `PaperProject.id == data.project_id` and `PaperProject.user_id == user.id` and `is_archived == False`.
- If missing, raise `HTTPException(status_code=404, detail="论文项目不存在")`.
- Set `project_id=data.project_id` and `task_title=data.task_title.strip() if data.task_title else None` on `OptimizationSession`.

- [ ] **Step 5: Update session list/detail serialization**

Where sessions are returned, include project fields. If responses rely on Pydantic from_attributes only, add properties on `OptimizationSession`:

```python
@property
def project_title(self):
    return self.project.title if self.project else None
```

Use `joinedload(OptimizationSession.project)` in session listing/detail queries if needed.

- [ ] **Step 6: Add project filter**

In list sessions endpoint, accept:

```python
project_id: Optional[int] = None
```

Filter:

```python
if project_id is not None:
    if project_id == 0:
        query = query.filter(OptimizationSession.project_id.is_(None))
    else:
        query = query.filter(OptimizationSession.project_id == project_id)
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd package\backend
python -m pytest tests/test_project_api.py tests/test_optimization_billing.py tests/test_provider_config_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add package/backend/app/schemas.py package/backend/app/routes/optimization.py package/backend/app/models/models.py package/backend/tests/test_project_api.py
git commit -m "feat: attach sessions to paper projects"
```

---

### Task 4: Frontend Project APIs and Workspace UI

**Files:**
- Modify: `package/frontend/src/api/index.js`
- Modify: `package/frontend/src/pages/WorkspacePage.jsx`

- [ ] **Step 1: Inspect workspace state and API patterns**

Read:

```powershell
Get-Content package/frontend/src/api/index.js
Get-Content package/frontend/src/pages/WorkspacePage.jsx
```

Confirm how `optimizationAPI.start`, `listSessions`, auth headers, and form state are implemented.

- [ ] **Step 2: Add API helpers**

In `package/frontend/src/api/index.js`, add:

```javascript
export const projectAPI = {
  list: () => api.get('/user/projects'),
  create: (data) => api.post('/user/projects', data),
  update: (projectId, data) => api.patch(`/user/projects/${projectId}`, data),
  archive: (projectId) => api.delete(`/user/projects/${projectId}`),
};
```

Update `optimizationAPI.listSessions` to accept `projectId` and pass `params`.

- [ ] **Step 3: Add workspace state**

In `WorkspacePage.jsx`, add:

```javascript
const [projects, setProjects] = useState([]);
const [activeProjectId, setActiveProjectId] = useState(null);
const [showProjectForm, setShowProjectForm] = useState(false);
const [projectTitle, setProjectTitle] = useState('');
const [projectDescription, setProjectDescription] = useState('');
const [taskTitle, setTaskTitle] = useState('');
```

- [ ] **Step 4: Add project loading and creation functions**

Add:

```javascript
const loadProjects = useCallback(async () => {
  const response = await projectAPI.list();
  setProjects(response.data);
  if (activeProjectId === null && response.data.length > 0) {
    setActiveProjectId(response.data[0].id);
  }
}, [activeProjectId]);

const handleCreateProject = async (e) => {
  e.preventDefault();
  if (!projectTitle.trim()) {
    toast.error('请输入论文题目');
    return;
  }
  const response = await projectAPI.create({
    title: projectTitle.trim(),
    description: projectDescription.trim() || null,
  });
  setProjects((current) => [response.data, ...current]);
  setActiveProjectId(response.data.id);
  setProjectTitle('');
  setProjectDescription('');
  setShowProjectForm(false);
  toast.success('论文项目已创建');
};
```

- [ ] **Step 5: Filter sessions by active project**

Change `loadSessions` to call:

```javascript
const response = await optimizationAPI.listSessions(activeProjectId);
```

Use `activeProjectId === 0` to mean unfiled sessions.

- [ ] **Step 6: Send project data on optimization start**

When building the start payload, include:

```javascript
project_id: activeProjectId && activeProjectId !== 0 ? activeProjectId : null,
task_title: taskTitle.trim() || null,
```

Clear `taskTitle` after a successful start.

- [ ] **Step 7: Render project list**

Above history, render:

```jsx
<button onClick={() => setShowProjectForm(true)}>新建论文</button>
<button onClick={() => setActiveProjectId(0)}>未归档历史</button>
{projects.map(project => (
  <button key={project.id} onClick={() => setActiveProjectId(project.id)}>
    <div>{project.title}</div>
    {project.description && <div>{project.description}</div>}
  </button>
))}
```

Keep styling consistent with existing sidebar cards.

- [ ] **Step 8: Render task title input**

Near the textarea, render:

```jsx
<input
  type="text"
  value={taskTitle}
  onChange={(e) => setTaskTitle(e.target.value)}
  placeholder="本次处理标题，例如：摘要降 AI、二稿润色"
/>
```

In `SessionItem`, display `session.task_title || session.project_title || session.preview_text`.

- [ ] **Step 9: Build**

Run:

```powershell
cd package\frontend
npm run build
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add package/frontend/src/api/index.js package/frontend/src/pages/WorkspacePage.jsx
git commit -m "feat: add paper projects to workspace"
```

---

### Task 5: End-to-End Verification

**Files:**
- No required code changes unless verification finds bugs.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
cd package\backend
python -m pytest tests -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd package\frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Browser smoke test**

With local services running:

1. Log in as `alice`.
2. Create a project titled `基于大语言模型的教育应用研究`.
3. Select the project.
4. Enter task title `摘要降 AI`.
5. Run BYOK `paper_enhance` on a short paragraph.
6. Confirm the completed session appears under that project.
7. Select `未归档历史` and confirm older sessions still appear there.

- [ ] **Step 4: Commit fixes if needed**

If smoke test finds issues, fix them with targeted commits.

---

## Self-Review

- Spec coverage: project CRUD, session linkage, legacy unfiled sessions, ownership checks, workspace UI, verification are covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: `project_id`, `project_title`, `task_title`, `PaperProject*` schema names are consistent.
