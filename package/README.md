# GankAIGC - 可执行文件打包

本目录包含将前后端项目打包为单个可执行文件 (exe) 的代码和配置。

## 目录结构

```
package/
├── backend/           # 后端代码（修改版，支持 exe 模式）
├── frontend/          # 前端代码（修改版，生产环境配置）
├── main.py            # 统一入口文件
├── app.spec           # PyInstaller 打包配置
├── requirements.txt   # Python 依赖
├── build.sh           # Linux/macOS 构建脚本
├── build.ps1          # Windows 构建脚本
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

**Windows:**
```powershell
cd package
.\build.ps1
```

构建完成后，可执行文件位于 `dist/` 目录。

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

- `GankAIGC-Windows-{version}.zip` - Windows 可执行文件
- `GankAIGC-Linux-{version}.tar.gz` - Linux 可执行文件
- `GankAIGC-macOS-{version}.tar.gz` - macOS 可执行文件

## 运行说明

1. 下载对应平台的可执行文件
2. 解压到任意目录
3. 首次运行会自动创建 `.env` 配置文件模板
4. 编辑 `.env` 文件，填入必要的配置：
   - API Key（OPENAI_API_KEY、POLISH_API_KEY 等）
   - 管理员密码（ADMIN_PASSWORD）
   - JWT 密钥（SECRET_KEY）
5. 再次运行程序
6. 程序会自动打开浏览器访问 http://localhost:9800

### 配置文件说明

`.env` 文件和数据库文件 (`ai_polish.db`) 都会保存在可执行文件同目录下，方便备份和迁移。

### 访问地址

- 用户界面: http://localhost:9800
- 管理后台: http://localhost:9800/admin
- API 文档: http://localhost:9800/docs

## 与原项目的区别

1. **运行方式**：原项目需要分别启动前端和后端服务，exe 版本一键启动
2. **配置位置**：exe 版本的 `.env` 和数据库文件在 exe 同目录
3. **前端访问**：exe 版本前后端在同一端口，无需代理

## 技术细节

### 前端修改
- 修改 `vite.config.js` 添加生产环境构建配置
- 修改 API 配置，生产环境直接使用根路径

### 后端修改
- 修改 `config.py`，支持动态获取 exe 目录下的配置文件
- 数据库路径默认指向 exe 同目录

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
