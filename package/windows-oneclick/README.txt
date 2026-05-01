GankAIGC Windows 一键整合包
===========================

使用方式：
1. 双击 start.bat
2. 首次运行会自动初始化内置 PostgreSQL，并生成 .env
3. 浏览器打开 http://localhost:9800
4. 后台地址：http://localhost:9800/admin
5. 停止服务请双击 stop.bat

目录说明：
- GankAIGC.exe：应用程序
- postgres/：便携 PostgreSQL 运行文件
- data/：数据库数据，请勿随便删除
- logs/：启动日志、数据库日志和首次生成的后台密码
- .env：配置文件，可修改 API Key、模型、后台密码等

注意：
- 不要删除 data/，否则用户、邀请码、兑换码、会话等数据会丢失。
- 如果忘记首次生成的后台密码，可查看 logs/first-run-admin.txt。
- 如果 9800 端口被占用，请修改 .env 里的 SERVER_PORT。
- 如果 55432 端口被占用，请修改 .env 里的 POSTGRES_PORT，并重新运行 start.bat。
