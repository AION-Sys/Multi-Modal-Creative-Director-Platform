# Multi-Modal Creative Director Platform

A unified workspace for planning, generating, editing, and versioning creative
content (image, video, audio, copy) — with a **director orchestration layer** on
top of raw generation. A *brief* is broken down by a director agent into an
*asset plan*; each asset is generated, self-critiqued, tracked in immutable
*versions*, and surfaced for human approval or regeneration. Multi-tenant from
day one (personal projects and client workspaces).

## Architecture

```
src/creative_director/
  config.py            Central env-driven settings (backend/provider/storage selection)
  domain/              The data model
    enums.py           Canonical status/modality enums (portable string values)
    models.py          Workspace, Project, Asset, Version, PipelineRun
  repositories/        [Step 3] Repository interface + memory & Airtable backends
  providers/           Pluggable generation interface + image providers (stub, OpenAI) + registry
  storage/             Object-storage abstraction (local disk now, S3/R2 later)
  orchestration/       [Step 5+] LangGraph director pipeline (Plan/Generate/Critique/Review)
  api/                 FastAPI CRUD routers + static API-key auth
```

## Data model

| Entity        | Purpose |
|---------------|---------|
| `Workspace`   | Top-level tenant (personal or client); holds brand/style config |
| `Project`     | A brief within a workspace: goal, constraints, target modalities, status |
| `Asset`       | A planned content piece: modality, spec, status, order in plan |
| `Version`     | Immutable generation/edit output; provider, prompt/params, `output_ref`, `parent_version_id` (branching), critique, verdict |
| `PipelineRun` | Persisted director-pipeline state, so a project can resume mid-flight |

**Migration-safety choices** (Airtable now → Postgres later without a rewrite):

- Every entity has a self-minted **UUID `id`**. Relationships reference these
  UUIDs as plain strings — never Airtable's internal `rec…` record IDs — so
  foreign keys survive migration.
- Every non-root entity carries **`workspace_id`** for tenant isolation.
- Media never lives in the DB: `Version.output_ref` is an object-storage key.
- Enums live in Python (not just as Airtable single-selects), so allowed values
  are backend-independent.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env    # fill in keys as needed
pytest -q
```

Configuration is entirely env-driven (see `.env.example`): swap
`BACKEND=memory|airtable`, `IMAGE_PROVIDER=stub|openai`, etc. without code
changes.

### Running the API

```bash
uvicorn creative_director.api.app:app --reload
```

All resource endpoints require the `X-API-Key` header (matching `APP_API_KEY`);
`/health` and `/docs` are open. Resources are nested for tenant isolation:

```
POST   /workspaces
GET    /workspaces/{workspace_id}/projects
POST   /workspaces/{workspace_id}/assets          # body carries project_id
GET    /workspaces/{workspace_id}/versions?asset_id=...
```

### Provisioning Airtable (when BACKEND=airtable)

Set `AIRTABLE_API_KEY` + `AIRTABLE_BASE_ID`, then create the tables from the
schema-as-code definitions (idempotent):

```bash
python -m creative_director.repositories.airtable.bootstrap
```

## Build order / status

1. ✅ Data model + domain layer
2. ✅ Project scaffold (structure, deps, config)
3. ✅ Repository interface + memory & Airtable backends (schema-as-code + bootstrap) + FastAPI CRUD
4. ✅ Provider interface + OpenAI `gpt-image-1` provider (+ keyless stub) + storage abstraction
5. ⬜ Director agent: Plan node (brief → asset plan), verified in isolation
6. ⬜ Generate node → image provider
7. ⬜ Self-critique node
8. ⬜ Review endpoint/CLI (approve / regenerate loop)
9. ⬜ Second modality

## Key decisions locked in

- **Backend:** Airtable via schema-as-code + bootstrap script; portable to Postgres.
- **Image provider:** OpenAI `gpt-image-1` (with a keyless `stub` provider for tests).
- **Auth:** static API key via `X-API-Key` header for the MVP.
