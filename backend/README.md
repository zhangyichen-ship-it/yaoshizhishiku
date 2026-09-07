# Yostone Knowledge Backend

FastAPI backend for one customer knowledge-base deployment. AI knowledge-base and RAG capabilities are part of the built-in backend.

## Runtime Scope

The backend keeps the admin foundation:

- Auth and current-user APIs
- RBAC permissions and menu authorization
- Local administrator users, roles, menus, dictionaries, params, and audit logs
- Common file upload
- AI knowledge-base metadata and document indexing
- Customer-side employee projection and cloud-synced knowledge-base access projection

This deployment represents one company. Tenant middleware, tenant cache startup, tenant seed models, tenant switching, and cloud-panel customer login are not part of the active application.

## Account Boundary

The cloud panel is the authority for employee usernames, password hashes, account status, product grants, knowledge-base resources, and employee access grants. This backend calls the instance-scoped cloud member API with a server-side credential and stores only safe projections:

- cloud user ID, username, name, email, status, and effective knowledge-base product grant;
- no employee password, cloud service credential, or full cloud directory;
- cloud-authoritative knowledge-base grants projected to `kb_knowledge_base_acl` for local retrieval.

The current batch exposes employee management APIs through this knowledge-base application. The application forwards create/update operations to the cloud panel and then refreshes its local projection. Access changes send the full local resource catalog and selected stable UUIDs to the cloud panel first; the local ACL is updated only after the cloud write succeeds. A knowledge-base request is allowed only when the mapped cloud employee is enabled, has the knowledge-base product grant, and has a non-deleted local projection of the cloud grant. There is no device quota or per-device permission model.

## Knowledge Base Architecture

- MySQL stores knowledge bases, documents, chunks, parse/index status, audit fields, and file metadata.
- ChromaDB stores vectors and chunk documents.
- `chromadb.PersistentClient` stores vectors in the local Chroma persist directory.
- Embeddings default to the local `fastembed` model `BAAI/bge-small-zh-v1.5`; OpenAI-compatible embeddings remain available by setting `EMBEDDING_PROVIDER=openai`.

Key modules:

```txt
app/plugin/module_ai/knowledge/
```

## Environment

Copy and edit the development env file:

```powershell
copy env\.env.dev.example env\.env.dev
```

AI/vector settings are part of the default backend configuration:

```env
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
Embedding indexes use a stable Chroma collection per vector provider, API address, and model. Changing the vector model keeps the old collection and requires reindexing documents before the new collection contains vectors.
`KB_CONTROL_PLANE_API_URL` is the server-side cloud member API endpoint supplied by the knowledge-base deployment configuration; it is not requested on the login page.
`KB_CONTROL_PLANE_SERVICE_CREDENTIAL` is an optional server-side bootstrap fallback. The login page can bind the cloud panel once; the backend then stores the credential only in encrypted form in its protected configuration table and never exposes it to the frontend.
`KB_BOOTSTRAP_CLOUD_USER_ID` is a one-time deployment value for the first customer-side knowledge administrator, which must already be created in the cloud panel as an enterprise owner. Binding never creates a cloud user. After that member is marked `owner` in `kb_member`, removing the environment value does not remove the local role.

The cloud panel pushes the non-secret vector provider, model, and address to this bound customer knowledge base after saving. The customer console has no model-configuration or chat page; it only receives the protected vector snapshot. The push does not copy a Provider Key; remote embedding continues to use the customer server's local `OPENAI_API_KEY`. A model change requires re-indexing or a new Chroma collection.

## Start

```powershell
# Built-in backend with AI knowledge-base and retrieval
uv sync
uv run main.py run --env=dev

```

`requirements.txt` exports the complete backend profile, including AI knowledge-base dependencies.

Application startup applies committed Alembic migrations, then creates any
remaining active ORM tables before seeding data. The customer member/ACL schema
is introduced by `20260903_customer_kb_member_acl.py`. Use `uv run main.py
revision --env=dev` to generate later migrations and review them before
deployment. Multi-replica production deployments should still run one
dedicated migration job.

Application startup seeds base data when tables are empty. AI tables are installed and included in the deployment migration workflow by default.

Uploaded files are stored under the private `storage/upload` directory. Generic
files are served through an authenticated preview route, while avatar and
parameter images use the validated public-image route; API responses expose
root-relative paths instead of server filesystem paths.

## Verification

```powershell
uv run pytest tests\core\test_optional_ai_plugin.py -q
uv run pytest tests\plugin\module_ai -q
python -m compileall -q app tests
uv run ruff check app\plugin\module_ai app\scripts\initialize.py app\api\v1\module_system\__init__.py app\config\setting.py app\init_app.py tests --output-format concise
uv run python -c "import chromadb, fastembed, openai, pypdf, docx"
```

The customer-side permission regression tests cover cloud-member projection,
default-deny ACL checks, and ACL replacement/revocation:

```powershell
uv run pytest tests\plugin\module_ai\knowledge\test_member_access.py -q
```

## Notes

- The Chroma persist directory must be writable for document indexing and retrieval.
- Knowledge document upload supports `.txt`, `.md`, `.pdf`, and `.docx`.
- User-edited model endpoints are blocked when they resolve to local/private networks; configure `MODEL_ALLOWED_HOSTS` only for explicitly trusted provider hosts.
- API keys are not exposed by the model-config endpoint; it only reports whether the key is configured.
- If a built-in AI dependency is missing, startup fails explicitly and reports the missing module; run `uv sync` before starting the backend.
