# Yostone Knowledge

Yostone Knowledge 是部署在客户服务器上的企业知识库。它提供本地知识库、文档索引、向量检索、客户侧员工管理 API 和知识库授权；员工账号事实仍由 Yostone 云面板统一维护。账号可以由云面板或客户知识库管理界面发起创建和维护，客户知识库只能通过受限 API 操作云端账号。

## 项目定位

- **使用场景**：一套客户知识库对应一个公司，部署在该公司的服务器上。
- **组织边界**：客户知识库不做 SaaS 多租户；公司边界由部署实例承担，不在业务表中增加 tenant 字段。
- **账号边界**：云面板保存员工账号、密码和产品权限；客户知识库只保存员工最小映射和本地知识库 ACL。
- **访问边界**：客户使用知识库内的管理界面创建、查询、修改或停用员工，并配置知识库授权；这些账号操作由知识库后端代理到云面板 API，客户不直接登录云面板或访问云面板数据库。
- **后端栈**：FastAPI、SQLAlchemy、Alembic、Redis、MySQL、ChromaDB 与 OpenAI-compatible API。
- **前端栈**：Vue 3、Vite、TypeScript、Element Plus、Pinia、Vue Router。
- **向量检索**：使用 ChromaDB 本地持久化目录存储向量和文本块索引。
- **模型接入**：使用本地 fastembed 或 OpenAI-compatible embedding endpoint。

## 功能范围

### 保留模块

- 系统管理：本地技术管理员、角色、菜单、字典、参数配置、操作日志。
- 公共能力：认证、RBAC、动态菜单、文件上传、Redis 缓存。
- AI 知识库：知识库管理、文档上传、文本抽取、分块、embedding、Chroma 写入、召回验证。

### 已移除或禁用

- 多租户中间件、组织切换、组织注册、组织运营入口。
- SaaS 订阅、授权售卖、平台运营类需求文档。
- 通知、工单、岗位、监控等可选后台产品入口。

## 目录结构

```txt
.
├── .github/workflows/        # CI（检查）与 CD（构建并推送镜像）
├── docker-compose.yml        # MySQL / Redis / 后端 / 前端
├── .env.example              # compose 环境变量模板
├── backend/                  # FastAPI 后端
│   ├── Dockerfile
│   ├── app/
│   ├── env/                  # 环境变量模板
│   ├── tests/
│   └── pyproject.toml
├── frontend/                  # Vue 3 frontend
│   ├── Dockerfile
│   ├── deploy/nginx.conf     # 前端镜像内 nginx，反代 /api/v1 到后端
│   ├── .env.example          # 本地开发模板，复制为 .env
│   ├── .env.production       # pnpm build / 镜像构建使用
│   └── package.json
└── docs/
```

## 服务依赖

本地开发需要准备：

- Python 3.12+
- uv
- Node.js 20.19+
- pnpm
- MySQL 8+
- Redis 6+
- 向量模型默认使用本地 fastembed；只有选择远程 embedding 时才需要 OpenAI-compatible embedding endpoint

## 后端配置

进入后端目录并复制开发环境配置：

```powershell
cd backend
copy env\.env.dev.example env\.env.dev
```

重点配置项在 `backend/env/.env.dev`：

```env
DATABASE_TYPE = "mysql"
DATABASE_HOST = "localhost"
DATABASE_PORT = 3306
DATABASE_USER = "root"
DATABASE_PASSWORD = "your_database_password"
DATABASE_NAME = "yostone_knowledge"

REDIS_ENABLE = True
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = "your_redis_password"
REDIS_DB_NAME = 1

SECRET_KEY = "dev-only-change-this-secret-before-sharing"

OPENAI_BASE_URL = "https://api.example.com"
OPENAI_API_KEY = "your_api_key"
OPENAI_MODEL = "your_chat_model"
EMBEDDING_PROVIDER = "local"
LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
LOCAL_EMBEDDING_CACHE_DIR = "./data/fastembed"
OPENAI_EMBEDDING_MODEL = ""

CHROMA_PERSIST_DIR = "./data/chroma"
CHROMA_COLLECTION_NAME = "knowledge_base"

# 客户知识库调用云面板员工接口（只放服务端环境变量，不提交真实凭证）
KB_CONTROL_PLANE_API_URL = "https://cloud.example.com/api/v1/platform/client"
KB_CONTROL_PLANE_INSTANCE_ID = 0
KB_CONTROL_PLANE_SERVICE_CREDENTIAL = ""
KB_CONTROL_PLANE_TIMEOUT = 10
KB_BOOTSTRAP_CLOUD_USER_ID = 0
```

首次部署时不需要让客户手工填写环境变量。打开客户知识库登录页，点击“首次使用？绑定云面板”，由客户本地超级管理员填写本地管理员账号和密码，以及云面板登记该知识库实例后生成的实例 ID、服务凭证。知识库后端先校验本地管理员，再通过绑定实例的受限成员接口创建同名的企业超管；创建结果必须是 `owner` 才会保存绑定。云面板服务地址由客户知识库部署配置提供；服务凭证成功后以加密形式保存在客户知识库配置表中，不写入浏览器、不回显，也不直接访问云面板数据库。

绑定完成后，首次绑定时使用的账号已经成为云面板企业超管；后续员工直接使用云面板创建的企业员工账号和密码登录客户知识库。更新绑定时，表单中的账号和密码按目标实例的企业超管校验，只有成员目录确认账号为 `owner` 且云端密码登录成功后才切换实例和服务凭证。云面板和客户知识库的账号管理仍通过受限 API 完成；`KB_CONTROL_PLANE_*` 环境变量保留为部署自动化和本地开发的兼容回退配置。

说明：

- 后端使用 `chromadb.PersistentClient` 直接读写本地 Chroma 持久化目录。
- AI 默认内置并启用；向量模型默认使用本地 `fastembed` 小模型 `BAAI/bge-small-zh-v1.5`。如需远程 embedding，可将 `EMBEDDING_PROVIDER` 改为 `openai` 并配置 `OPENAI_EMBEDDING_MODEL`。
- `CHROMA_PERSIST_DIR` 是当前向量库数据目录，部署或备份时需要保留。
- `KB_CONTROL_PLANE_SERVICE_CREDENTIAL` 仅作为服务端 bootstrap fallback；页面绑定后服务凭证以加密值保存在客户知识库的受保护配置表中，员工密码不会写入客户知识库数据库。
- `KB_BOOTSTRAP_CLOUD_USER_ID` 只用于兼容指定首个客户知识管理员；新部署优先使用登录页首次绑定流程创建企业超管。
- 客户侧员工最小映射保存在 `kb_member`，云端员工-知识库授权以知识库稳定 `uuid` 保存在云面板，本地 `kb_knowledge_base_acl` 只作为检索执行投影；授权保存先写云端，云端账号停用、产品权限关闭或资源授权撤销后会在下一次成员/身份同步时关闭本地访问。
- 客户知识库不再从“系统管理 → 用户管理”维护企业员工；员工账号和知识库授权统一由云面板维护，客户侧入口只是受限 API 代理。
- 云面板保存向量模型后会向已绑定的客户知识库自动推送来源、模型和地址；客户知识库不展示“模型配置”入口，仅通过受保护的推送接口接收运行时配置。推送不会传递或保存云面板 Provider Key；远程 embedding 使用客户服务器自己的 `OPENAI_API_KEY`。如果模型发生变化，请重新索引或清理旧 Chroma 集合后再检索。
- 不要提交真实数据库密码、Redis 密码或模型 API key。

## 后端启动

```powershell
cd backend
# AI 知识库与检索随默认依赖装配
uv sync
uv run main.py run --env=dev
```

应用启动时会先执行已提交的 Alembic 迁移，再按 ORM 模型补齐缺失表并写入种子数据。修改模型后仍可运行 `uv run main.py revision --env=dev` 生成并审核迁移文件；应用启动不会自动生成迁移。多副本生产部署仍建议使用单独的迁移任务。

`backend/requirements.txt` 已包含后端和 AI 知识库依赖。

默认开发配置中的 API 前缀为 `/api/v1`。Swagger 和 ReDoc 路径由 `backend/env/.env.dev` 中的 `DOCS_URL`、`REDOC_URL` 控制。

上传文件默认保存到后端私有目录 `backend/storage/upload`，不会通过静态文件目录直接暴露。通用文件返回的 `file_url` 走需要登录和下载权限的私有预览路由；头像和站点参数图片走仅允许图片格式的公开预览路由。接口返回的是相对存储路径，不要把服务器绝对路径写入业务数据或前端。

## 前端配置

进入前端目录并安装依赖：

```powershell
cd frontend
pnpm install
```

前端环境模板：

```powershell
copy .env.example .env
```

常用配置项：

```env
VITE_PORT=5180
VITE_APP_BASE_API=/api/v1
VITE_API_BASE_URL=http://127.0.0.1:8004
VITE_APP_WS_ENDPOINT=ws://127.0.0.1:8004
VITE_ACCESS_MODE=mixed
```

如果后端端口不是 `8004`，需要同步调整 `VITE_API_BASE_URL` 和 `VITE_APP_WS_ENDPOINT`。

## 前端启动

```powershell
cd frontend
pnpm run dev
```

常用脚本：

```powershell
pnpm run type-check
pnpm test
pnpm run lint:ci
pnpm run build
```

## Docker 与 CI/CD

本地一键起前后端（含 MySQL、Redis）：

```powershell
copy .env.example .env
docker compose up -d --build
```

默认页面在 `http://localhost:8080`，API 由 nginx 把 `/api/v1/` 转到后端容器 `8004`。后端容器内端口固定为 `8004`，不要改成 8001/8008。

GitHub Actions：

- `.github/workflows/ci.yml`：后端 ruff + pytest；前端 type-check、单测、lint、build；并验证前后端 Docker 镜像能构建。
- `.github/workflows/cd.yml`：推送到 `main`/`master` 或打 `v*` 标签时，构建并推送镜像到 GHCR，再 SSH 部署到服务器 `/www/wwwroot/yaoshizhishiku`：
  - `ghcr.io/zhangyichen-ship-it/yaoshizhishiku/backend`
  - `ghcr.io/zhangyichen-ship-it/yaoshizhishiku/frontend`

### 服务器首次准备（只需做一次）

CD 会自动创建 `/www/wwwroot/yaoshizhishiku`，并上传 `docker-compose.yml`。若还没有 `.env`，会从模板生成一份。你需要提前确认：

1. 服务器已安装 Docker 和 Compose，`HOSTNAME` 用户能执行 `docker`（在 `docker` 组或使用 root）。
2. `HOSTNAME` 对 `/www/wwwroot` 有写权限（宝塔环境通常用 root）。
3. 安全组放行 SSH 22 端口。
4. 首次部署后尽快编辑 `/www/wwwroot/yaoshizhishiku/.env`，把 `SECRET_KEY`、MySQL/Redis 密码改成生产值。

```bash
docker version
docker compose version
sudo mkdir -p /www/wwwroot
# 若 SSH 用户不是 root，需要：
sudo chown -R "$USER:$USER" /www/wwwroot/yaoshizhishiku
```

GitHub Secrets（`HOSTIP`、`HOSTNAME`、`SIYAO`、`GHCR_TOKEN`）配好后即可部署。未配置 `HOSTIP` 时，CD 仍会推送镜像，但会跳过部署。

之后推送到 `main` 会自动：构建镜像 → 推 GHCR → 写入 `/www/wwwroot/yaoshizhishiku` → `docker compose pull && up`。页面默认 `http://服务器IP:8080`。

## AI 知识库流程

先完成 `uv sync` 并配置模型服务，再进行以下操作：

1. 首次使用先在登录页绑定云面板；只需部署管理员完成一次。
2. 使用云面板创建的员工账号登录，再在“AI 知识库 / 知识库管理”创建知识库。
3. 在“AI 知识库 / 员工与知识库权限”中从云面板同步员工，或提交创建、修改、停用请求；这些账号操作由客户知识库后端调用云面板成员 API 完成，再配置该员工可访问的知识库。
4. 在“文档管理”上传 `.txt`、`.md`、`.pdf`、`.docx` 文件。
5. 后端保存文件到 `backend/storage/knowledge`。
6. 后端抽取文档文本并切分 chunk。
7. 后端调用 embedding 模型生成向量。
8. MySQL 保存知识库、文档、chunk 元数据和本地 ACL。
9. ChromaDB 保存向量、chunk 文本和检索 metadata。
10. 已绑定云端员工身份的请求，后端同时校验最近同步的云端员工状态、知识库产品权限和本地 ACL。
11. 在“检索测试”中验证有权访问的知识库召回结果。

核心后端路径：

```txt
backend/app/plugin/module_ai/knowledge/
```

核心前端路径：

```txt
frontend/src/api/module_ai/
frontend/src/views/module_ai/
```

## 验证命令

后端：

```powershell
cd backend
uv run pytest tests\core\test_optional_ai_plugin.py -q
uv run pytest tests\plugin\module_ai -q
python -m compileall -q app tests
uv run ruff check app\plugin\module_ai app\scripts\initialize.py app\api\v1\module_system\__init__.py app\config\setting.py app\init_app.py tests --output-format concise
uv run python -c "import chromadb, openai, pypdf, docx"
```

前端：

```powershell
cd frontend
pnpm vitest run src\__tests__\single-org-user-store.test.ts src\__tests__\knowledge-api.test.ts
pnpm run type-check
```

## 常见问题

### 文档上传后索引失败

检查：

- `CHROMA_PERSIST_DIR` 是否可读写，磁盘空间是否充足。
- `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_EMBEDDING_MODEL` 是否正确。
- 用户编辑的模型地址不能解析到本机或内网；确需使用受控代理域名时，在服务端配置 `MODEL_ALLOWED_HOSTS` 白名单。
- 上传文件是否为 `.txt`、`.md`、`.pdf`、`.docx`。
- 后端日志中的 `error_message` 字段。

### 前端能打开但接口报错

检查：

- 后端是否已启动。
- `VITE_APP_BASE_API` 是否与后端 `ROOT_PATH` 一致。
- `VITE_API_BASE_URL` 是否指向正确后端端口。
- 浏览器网络请求是否命中 `/api/v1`。

### 员工无法访问知识库

检查：

- 登录页的云面板绑定是否成功；如果使用环境变量回退，检查 `KB_CONTROL_PLANE_API_URL`、实例 ID 和服务凭证是否由服务端正确注入。
- 员工是否在云面板处于启用状态，并已开通知识库产品权限。
- 客户知识库的 `kb_member` 是否已同步，以及 `kb_knowledge_base_acl` 是否已授权。

### 启动后看不到旧多组织功能

这是当前代码线的预期状态。本项目是一套客户公司的知识库实例，不提供租户切换或云面板运营入口。

## 文档维护原则

- README 只描述当前分支可运行、可验证的能力。
- 不在 README 中记录历史长需求；过期需求应移出根目录。
- 新增运行依赖、环境变量或验证命令时，需要同步更新本文件。
