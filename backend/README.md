# Yostone Knowledge Backend

FastAPI backend for one customer knowledge-base deployment. AI knowledge-base and RAG capabilities are installed as an optional `ai` extra.

## Runtime Scope

The backend keeps the admin foundation:

- Auth and current-user APIs
- RBAC permissions and menu authorization
- Local administrator users, roles, menus, dictionaries, params, and audit logs
- Common file upload
- AI chat and session history
- AI knowledge-base metadata and document indexing
- Customer-side employee mapping and knowledge-base ACL

This deployment represents one company. Tenant middleware, tenant cache startup, tenant seed models, tenant switching, and cloud-panel customer login are not part of the active application.

## Account Boundary

The cloud panel is the authority for employee usernames, password hashes, account status, and product grants. This backend calls the instance-scoped cloud member API with a server-side credential and stores only the safe projection in `kb_member`:

- cloud user ID, username, name, email, status, and effective knowledge-base product grant;
- no employee password, cloud service credential, or full cloud directory;
- local knowledge-base grants in `kb_knowledge_base_acl`.

The current batch exposes employee management APIs through this knowledge-base application. The application forwards create/update operations to the cloud panel and then refreshes its local projection. A knowledge-base request is allowed only when the mapped cloud employee is enabled, has the knowledge-base product grant, and has a non-deleted local ACL grant. There is no device quota or per-device permission model.

## Knowledge Base Architecture

- MySQL stores knowledge bases, documents, chunks, parse/index status, audit fields, and file metadata.
- ChromaDB stores vectors and chunk documents.
- `chromadb.PersistentClient` stores vectors in the local Chroma persist directory.
- Chat completions use the `openai` client through OpenAI-compatible providers.
- Embeddings default to the local `fastembed` model `BAAI/bge-small-zh-v1.5`; OpenAI-compatible embeddings remain available by setting `EMBEDDING_PROVIDER=openai`.

Key modules:

```txt
app/plugin/module_ai/chat/
app/plugin/module_ai/knowledge/
```

## Environment

Copy and edit the development env file:

```powershell
copy env\.env.dev.example env\.env.dev
```

AI/vector settings are only required after installing the AI extra:

```env
AI_ENABLE=True
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
LOCAL_EMBEDDING_CACHE_DIR=./data/fastembed
OPENAI_EMBEDDING_MODEL=
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_COLLECTION_NAME=knowledge_base
KB_CONTROL_PLANE_API_URL=https://cloud.example.com/api/v1/platform/client
KB_CONTROL_PLANE_INSTANCE_ID=0
KB_CONTROL_PLANE_SERVICE_CREDENTIAL=
KB_CONTROL_PLANE_TIMEOUT=10
KB_BOOTSTRAP_CLOUD_USER_ID=0
```

`CHROMA_PERSIST_DIR` is the active local Chroma data directory. Preserve it during deployment, backup, and migration.
When changing embedding models, clear the existing Chroma collection or use a new `CHROMA_COLLECTION_NAME` to avoid vector dimension conflicts.
`KB_CONTROL_PLANE_SERVICE_CREDENTIAL` is injected only on the customer server. Never store it in the database or expose it to the frontend.
`KB_BOOTSTRAP_CLOUD_USER_ID` is a one-time deployment value for the first customer-side knowledge administrator. After that member is marked `owner` in `kb_member`, removing the environment value does not remove the local role.

Use the customer-side model configuration page to explicitly pull the vector provider, model, and address from the bound cloud-panel instance. The sync action does not copy a Provider Key; remote embedding continues to use the customer server's local `OPENAI_API_KEY`. A model change requires re-indexing or a new Chroma collection.

## Start

```powershell
# Core admin only
uv sync
uv run main.py run --env=dev

# Enable AI knowledge-base and RAG
uv sync --extra ai
# Set AI_ENABLE=True in env/.env.dev
```

`requirements.txt` exports the core backend profile. Use `requirements-ai.txt` for deployments that enable AI.

Application startup applies committed Alembic migrations, then creates any
remaining active ORM tables before seeding data. The customer member/ACL schema
is introduced by `20260903_customer_kb_member_acl.py`. Use `uv run main.py
revision --env=dev` to generate later migrations and review them before
deployment. Multi-replica production deployments should still run one
dedicated migration job.

Application startup seeds base data when tables are empty. Optional AI tables still require the AI models to be installed and included in the deployment migration workflow.

Uploaded files are stored under the private `storage/upload` directory. Generic
files are served through an authenticated preview route, while avatar and
parameter images use the validated public-image route; API responses expose
root-relative paths instead of server filesystem paths.

## Verification

```powershell
uv run pytest tests\core\test_optional_ai_plugin.py -q
uv run --extra ai pytest tests\plugin\module_ai -q
python -m compileall -q app tests
uv run ruff check app\plugin\module_ai app\scripts\initialize.py app\api\v1\module_system\__init__.py app\config\setting.py app\init_app.py tests --output-format concise
uv run --extra ai python -c "import chromadb, fastembed, openai, pypdf, docx"
```

The customer-side permission regression tests cover cloud-member projection,
default-deny ACL checks, and ACL replacement/revocation:

```powershell
uv run --extra ai pytest tests\plugin\module_ai\knowledge\test_member_access.py -q
```

## Notes

- The Chroma persist directory must be writable for document indexing and retrieval.
- Knowledge document upload supports `.txt`, `.md`, `.pdf`, and `.docx`.
- User-edited model endpoints are blocked when they resolve to local/private networks; configure `MODEL_ALLOWED_HOSTS` only for explicitly trusted provider hosts.
- API keys are not exposed by the model-config endpoint; it only reports whether the key is configured.
- When `AI_ENABLE=True` but the `ai` extra is absent, the backend logs the missing modules and starts without the AI plugin.
