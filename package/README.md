# GankAIGC - 可执行文件打包

本目录包含将前后端项目打包为单个可执行文件 (exe) 的代码和配置。

当前稳定主线是「账号注册 + 用户登录 + 邀请码注册 + 兑换码充值啤酒 + 啤酒流水 + 降 AI 工作台」。Word 排版相关后端代码仍作为实验模块保留，但默认关闭，前端不暴露排版入口。

## 目录结构

```
package/
├── backend/           # 后端代码（修改版，支持 exe 模式）
├── frontend/          # 前端代码（修改版，生产环境配置）
├── main.py            # 统一入口文件
├── app.spec           # PyInstaller 打包配置
├── requirements.txt   # Python 依赖
├── build.sh           # Linux/macOS 构建脚本
├── build.ps1          # Windows 普通 exe 构建脚本
├── build-oneclick.ps1 # Windows 一键整合包构建脚本
├── windows-oneclick/  # 一键包 start/stop/env 模板
└── README.md          # 本文件
```

## 本地构建

### 前置条件

- Python 3.9+
- Node.js 18+
- pip 和 npm

### 构建步骤

**Linux/macOS:**
```bash
cd package
chmod +x build.sh
./build.sh
```

**Windows 普通 exe:**
```powershell
cd package
.\build.ps1
```

普通 exe 位于 `dist/GankAIGC.exe`，运行时仍需要外部 PostgreSQL。

**Windows 一键整合包（内置便携 PostgreSQL）:**
```powershell
cd package

# 传入已解压 PostgreSQL 目录
.\build-oneclick.ps1 -PostgresRoot C:\pgsql -CreateZip

# 或传入 PostgreSQL Windows binaries ZIP
.\build-oneclick.ps1 -PostgresZip C:\Downloads\postgresql-windows-x64-binaries.zip -CreateZip
```

一键包位于 `dist/GankAIGC-Windows/`，压缩包位于 `dist/GankAIGC-Windows-OneClick.zip`。

## GitHub Actions 自动构建

项目配置了 GitHub Actions 工作流，可以自动构建 Windows、Linux 和 macOS 版本的可执行文件。

### 触发方式

1. **打标签触发**: 推送以 `v` 开头的标签时自动触发构建并创建 Release
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **手动触发**: 在 GitHub Actions 页面手动运行工作流

### 构建产物

- `GankAIGC-Windows-{version}.zip` - Windows 普通可执行文件，需要外部 PostgreSQL
- `GankAIGC-Windows-OneClick.zip` - Windows 一键整合包，内置便携 PostgreSQL
- `GankAIGC-Linux-{version}.tar.gz` - Linux 可执行文件
- `GankAIGC-macOS-{version}.tar.gz` - macOS 可执行文件

## 运行说明

普通 exe：

1. 下载对应平台的可执行文件。
2. 解压到任意目录。
3. 首次运行会自动创建 `.env` 配置文件模板。
4. 编辑 `.env`，填入 PostgreSQL `DATABASE_URL`、API Key、管理员密码和密钥。
5. 再次运行程序。

Windows 一键整合包：

1. 解压 `GankAIGC-Windows-OneClick.zip`。
2. 双击 `start.bat`。
3. 首次运行会自动初始化 `data/` 下的 PostgreSQL，并生成 `.env`。
4. 后台密码会显示在窗口中，并保存到 `logs/first-run-admin.txt`。
5. 停止服务双击 `stop.bat`。

### 配置文件说明

`.env` 文件会保存在可执行文件同目录下。数据库只支持 PostgreSQL，请在 `.env` 中配置 `DATABASE_URL`。

源码运行时降 AI 任务会先进入 PostgreSQL 队列。exe / `python main.py` 默认启用 inline worker；Docker 部署则由独立 worker 服务消费队列。worker 会定期刷新心跳，长时间无心跳的处理中任务会自动恢复为排队状态。

### 访问地址

- 用户界面: http://localhost:9800
- 管理后台: http://localhost:9800/admin
- API 文档: http://localhost:9800/docs

## 与原项目的区别

1. **运行方式**：原项目需要分别启动前端和后端服务，exe 版本一键启动
2. **配置位置**：exe 版本的 `.env` 在 exe 同目录，数据库连接由 `DATABASE_URL` 指向 PostgreSQL
3. **前端访问**：exe 版本前后端在同一端口，无需代理

## 技术细节

### 前端修改
- 修改 `vite.config.js` 添加生产环境构建配置
- 修改 API 配置，生产环境直接使用根路径

### 后端修改
- 修改 `config.py`，支持动态获取 exe 目录下的配置文件
- 数据库统一使用 PostgreSQL

### 统一入口
- `main.py` 创建 FastAPI 应用
- 挂载静态文件服务前端页面
- 处理 SPA 路由（admin、workspace 等）
- 自动打开浏览器

### PyInstaller 配置
- 包含所有必要的隐式导入
- 包含前端静态文件
- 包含后端应用代码
- 排除不必要的大型库
