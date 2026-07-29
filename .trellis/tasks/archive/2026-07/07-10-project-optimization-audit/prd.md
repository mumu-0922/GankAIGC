# Docker / VPS 生产优化审计

## Goal

基于当前代码、配置、测试与运行结构，分阶段实施以单 VPS Docker Compose 生产部署为第一优先级的优化路线，先解决数据安全、运行正确性、发布可回滚和灾备，再处理性能与可维护性。

## Requirements

- 用户已审核方案并明确授权开始任务；允许按 `implement.md` 分阶段修改仓库代码、Docker 配置、测试和文档。
- 不直接操作真实 VPS、1Panel、云防火墙、Registry 或生产数据库；任何生产删除、密钥轮换和不可逆迁移仍需单独确认。
- 第一优先级覆盖 Docker image、Compose、VPS 暴露面、PostgreSQL Schema/备份、app/worker 跨进程链路、Secrets、CI/Release 与回滚。
- 第二优先级覆盖后端性能、前端可靠性、测试、安全、可观测性与仓库维护。
- 每个优化项必须能在源码、配置、测试或运行结构中找到证据，避免通用化建议。
- 按用户收益、故障/安全风险、实施成本和回归面分级，给出推荐执行顺序。
- 区分“已确认问题”“技术债/可维护性改进”“仅在特定部署模式下成立的条件项”。
- 明确哪些现有机制已经足够，不重复提出仓库中已经落实的能力。
- 推荐方案以单 VPS 的最小运维复杂度为约束；跨进程事件优先复用 PostgreSQL durable outbox + `LISTEN/NOTIFY`，暂不为此单独引入 Redis。
- 当前目标为约 100 名注册用户、峰值约 10 名用户同时处理；继续使用 PostgreSQL durable queue，只有多 VPS/几十个 worker 或实测数据库成为瓶颈后才评估 Redis。

## Acceptance Criteria

- [x] 概括项目当前架构、核心运行链和 Docker/VPS 部署模式。
- [x] 输出 P0-P2 优化清单；每项包含证据位置、影响、建议动作、成本、验证和回滚。
- [x] 核查数据库/队列、Docker/CI、备份恢复、VPS 暴露面、安全、后端性能和前端实时链路。
- [x] 对高优先级发现交叉验证，并记录已有保护与条件边界。
- [x] 给出上线前 go-live gate、阶段实施顺序及独立子任务建议。
- [x] 不泄露 `.env`、凭证、Token 或朱雀会话数据。
- [x] Phase 1 完成 Docker context allowlist、uploads 持久化和对应回归验证。
- [x] Phase 2 完成单一 Schema authority，并证明空库安装和历史快照升级安全。
- [x] Phase 3 完成跨进程事件、队列真相和 worker lease/drain。
- [ ] Phase 4–5 完成 Secrets、容器运行、备份恢复和不可变发布门禁。
- [ ] Phase 6 的性能项必须有基准或查询计划证据后才实施。
- [x] v2.1.0 允许管理员在 `5 / 8 / 10` 三档间热切换全站处理容量；降档不杀运行任务，只停止新领取。
- [x] 同一用户最多 1 个运行或外部等待任务、2 个排队任务；平台与 BYOK 同等优先，按最早可运行用户公平领取。
- [x] 浏览器插件等待不占全站处理槽位，但继续占该用户的活跃名额；插件完成/失败后由 PostgreSQL 持久化恢复任务，不依赖原 worker 进程存活。
- [x] AI 请求按脱敏 Key 身份限流，单 Key 并发后台可选 `1 / 2 / 4`（默认 2），不同 BYOK Key 互不阻塞，`429` 退避不得重复扣费或重做已完成段落。
- [x] v2.1.0 Release 自动附带可直接解压安装的 Chrome 插件 ZIP 及 SHA-256，README 与 Release Notes 同步安装、升级和版本要求。
- [x] 加密 restic 异地备份同时覆盖已验证 PostgreSQL dump 与 `package/uploads`，并用隔离目录恢复及 SHA-256 比对证明上传文件可恢复。

## Confirmed Facts

- 默认 Compose 由 `app + worker + postgres + backup` 组成，`app` 同时服务 FastAPI API 与 React 静态资源。
- 实际 VPS 已通过 1Panel 使用用户域名配置反向代理；公网入口并非完全裸奔。剩余上线门是确认 HTTPS 强制跳转、9800 未被公网直连，以及 SSE/上传参数正确。
- PostgreSQL 已承担 durable task queue；抢占使用 `FOR UPDATE SKIP LOCKED`，但 SSE、并发状态和 worker 在线状态仍依赖进程内内存或业务任务心跳。
- `app` 与 `worker` 会同时在启动时执行 `create_all + 手写 DDL`，Compose 未执行 Alembic migration job。
- `uploads` 与默认朱雀状态目录没有持久卷；PostgreSQL 备份也不包含它们。
- `.dockerignore` 未隔离本地 venv、Playwright 浏览器缓存和朱雀 data，Dockerfile 又全量复制 `package/`。
- Compose 默认把 9800 发布到所有宿主机接口；部署文档同时建议用 Nginx 代理到 loopback，二者边界冲突。
- 当前本地密钥/朱雀凭证文件权限为 `0644`；backup 容器通过整份 `env_file` 获得无关业务 Secrets。
- 自动备份与 PostgreSQL volume 位于同一 VPS，dump 直接写最终文件且没有恢复证明。
- CI 能构建前端、执行后端测试并构建 Docker image，但尚无不可变镜像发布、SBOM、签名、provenance 和镜像安全门禁。

## Out of Scope

- 不在本任务中直接部署或删除任何生产资源。
- 不在本轮决定多 VPS、Kubernetes 或 Redis 集群；只有容量证据出现后再升级架构。
- 实时 CVE/SCA、远端 Registry 中既有镜像、VPS 防火墙和 GitHub ruleset 状态尚未联网核验，均记为 `[unverified]`。

## Notes

- 当前用户明确选择 Docker/VPS 生产部署优先，并已授权按路线图进入 implementation。
- 当前仓库支持本地源码、Docker/VPS、Windows 一键包三种模式；条件项需明确适用模式。
- 高影响证据包括：镜像夹带本地凭证、容器状态不持久、Schema 生命周期断裂、默认 Docker worker 与内存 SSE/队列状态跨进程失配、9800 可能绕过既有 1Panel 反代、明文临时 BYOK Key、凭证日志、备份不可证明恢复，以及 Release 身份不可信。
