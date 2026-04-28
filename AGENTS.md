# 仓库指南

## 项目结构与模块组织

GankAIGC 是一个打包式 FastAPI 与 React/Vite 应用。运行时打包入口位于 `package/`，其中 `package/main.py` 会在 `9800` 端口提供前后端一体化服务。后端源码在 `package/backend/app/`：`routes/` 放 API 端点，`services/` 放业务逻辑，`models/` 放 SQLAlchemy 模型，`utils/` 放共享工具，`word_formatter/` 放文档格式化功能。后端测试在 `package/backend/tests/`。前端源码在 `package/frontend/src/`，按 `pages/`、`components/`、`api/` 组织；静态示例在 `package/frontend/public/`。`package/frontend/dist/`、`package/static/`、数据库、日志和环境文件都属于生成产物。

## 构建、测试与开发命令

- `cd package/backend; pip install -r requirements.txt` 安装后端与测试依赖。
- `cd package/backend; python -m pytest -q` 使用 `GANKAIGC_TEST_DATABASE_URL` 指向的 PostgreSQL 测试库运行 pytest；测试库名必须包含 `test`。
- `cd package/frontend; npm ci` 根据 `package-lock.json` 安装前端依赖。
- `cd package/frontend; npm run dev` 启动 Vite 开发服务器，并将 `/api` 代理到配置的后端。
- `cd package/frontend; npm run build` 生成生产前端包。
- `cd package; python main.py` 在依赖安装后本地运行一体化应用。
- `cd package; .\build.ps1` 在 Windows 构建可执行包；Linux/macOS 使用 `./build.sh`。
- `docker compose up --build` 启动接近生产环境的容器栈；先配置 `.env.docker`。

## 编码风格与命名约定

Python 使用 4 空格缩进，路由处理函数应保持轻量，把核心逻辑放入 `services/`。测试文件命名为 `test_*.py`，fixture 名称要清晰，并优先采用 `tests/conftest.py` 中那样显式的环境配置。React 代码使用 JSX 文件、2 空格缩进和分号；组件与页面使用 PascalCase，函数使用 camelCase。前端样式优先沿用现有 Tailwind 工具类和 `tailwind.config.js` 中的主题 token。

## 测试指南

后端测试基于 pytest。修改 API、服务、认证、计费、数据库初始化、供应商配置或文档格式化逻辑时，应添加聚焦测试。前端目前没有配置测试运行器；至少运行 `npm run build`，并手动验证受影响的路由或页面。

## 提交与 Pull Request 指南

当前检出目录不包含 Git 历史，因此提交信息建议使用简洁的 Conventional Commit 风格，例如 `feat: add project export` 或 `fix: handle expired credits`。Pull Request 应包含简短摘要、已运行的测试命令、相关 issue 链接、UI 变更截图，以及新增环境变量、数据库变更或打包行为的说明。

## 安全与配置提示

不要提交 `.env`、`.env.docker`、API Key、数据库导出文件或日志。生产部署必须替换默认 `SECRET_KEY` 和 `ADMIN_PASSWORD`，配置有效的模型 API 凭据，并将 `.env.docker.example` 作为文档模板，而不是密钥存储文件。
