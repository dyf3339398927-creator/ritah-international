# Docker 部署（Mac / Windows）

需要先安装并启动 Docker Desktop。Apple 芯片 Mac、Intel Mac 和 Windows Linux 容器模式均可从 Dockerfile 构建，基础镜像支持原生 amd64/arm64。

解压 Docker 专用包后，Mac 双击 `Start-Docker-Mac.command`，Windows 双击 `Start-Docker-Windows.cmd`。首次启动会下载基础镜像并构建；不安装 Python 或 Node 到宿主机。

也可在项目目录执行：

```sh
docker compose up -d --build
docker compose logs --no-log-prefix stockroom
```

打开日志中的完整 `http://127.0.0.1:8765/#...` 地址。`#` 后为随机本地会话凭证，容器重建/重启后使用最新启动日志中的地址。保持映射端口为 8765，使用 127.0.0.1 地址，不改为 localhost；本版进行严格 Host 与 Origin 校验。

停止：`docker compose down`。重新启动保留配置与目录缓存，但出于可控运行考虑，需要在界面重新点击“开始监控”。配置存储在命名卷 `stockroom-data`，不要使用 `down -v`，否则会删除配置。

Docker 版监控与页面服务可后台运行，网页关闭后仍查询；提示音需要保持页面打开。Docker Desktop 与电脑必须保持运行。容器以非 root 用户运行，服务仅通过宿主机回环地址发布，不提供远程多用户访问。

容器无法控制 Mac/Windows 的登录浏览器，因此 Docker 版提供“官网商品”按钮，由宿主机浏览器完成购买。独立浏览器加购助手请使用 Mac/Windows 原生包。未在容器中模拟真实订单或付款。

Mac 原生包和 Docker 启动器没有 Apple Developer ID 公证，首次运行可能需要系统确认；没有修改或关闭 Gatekeeper 的脚本。
