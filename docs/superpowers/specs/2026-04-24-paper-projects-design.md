# Paper Projects Design

## Goal

Users need a way to distinguish optimization work for different papers. The current workspace shows a flat list of optimization sessions, so multiple papers are mixed together and can only be recognized by date or text preview.

Add a lightweight "paper project" layer above optimization sessions. A paper project represents one article or manuscript, and each project can contain multiple optimization sessions.

## User Experience

The workspace becomes project-centered:

- Users can create a paper project with a title and optional description.
- Users choose an active project before starting an optimization task.
- Each optimization session is attached to the active project.
- The sidebar shows paper projects first, then the active project's session history.
- Old sessions without a project remain visible under an "Unfiled history" fallback.

The first version does not add file storage, rich document editing, collaboration, tags, search, or per-project prompt customization.

## Data Model

Add a new `paper_projects` table:

- `id`: primary key
- `user_id`: owner
- `title`: paper title, required
- `description`: optional note
- `is_archived`: hide from default list when true
- `created_at`
- `updated_at`

Extend `optimization_sessions`:

- `project_id`: nullable foreign key to `paper_projects.id`
- `task_title`: nullable session-level label, for names like "first AI reduction" or "abstract rewrite"

`project_id` is nullable to preserve existing legacy sessions.

## API

Add user-authenticated project endpoints:

- `GET /api/user/projects`: list current user's non-archived projects, newest first.
- `POST /api/user/projects`: create a project.
- `PATCH /api/user/projects/{project_id}`: edit title, description, archived state.
- `DELETE /api/user/projects/{project_id}`: soft archive the project.

Update optimization endpoints:

- `POST /api/optimization/start` accepts optional `project_id` and `task_title`.
- `GET /api/optimization/sessions` accepts optional `project_id`.
- Session responses include `project_id`, `project_title`, and `task_title`.

Authorization rules:

- A user can only list, edit, archive, and attach sessions to their own projects.
- Starting an optimization with another user's project id returns 404.
- Admin APIs are unchanged in this first version.

## Frontend

Update the workspace:

- Add a "Paper Projects" section above history.
- Add a "New paper" action.
- Show active project title near the task form.
- Add optional "task title" input in the task form.
- Filter session history by active project.
- Provide an "Unfiled history" option for sessions without a project.

Keep the existing optimization flow unchanged after the project is selected.

## Migration and Compatibility

Use SQLAlchemy model changes and the existing startup table creation style. For existing SQLite development databases, add a small startup migration that creates the new table and adds missing columns if they do not exist. PostgreSQL deployment should use the same schema definitions; a later dedicated migration system can replace this.

Existing sessions remain usable:

- `project_id = null`
- `task_title = null`
- They appear under "Unfiled history".

## Verification

Backend tests:

- User can create, list, update, and archive own projects.
- User cannot attach a session to another user's project.
- Starting optimization with own project stores `project_id` and `task_title`.
- Listing sessions by project returns only that project's sessions.
- Legacy unfiled sessions still list without errors.

Frontend verification:

- Production build passes.
- User can create a project, start a BYOK optimization under it, and see the completed session inside that project.

## Out of Scope

- Full document editor.
- File upload tied to project.
- Project sharing.
- Tags and full-text search.
- Admin project management.
- Prompt customization per project.
