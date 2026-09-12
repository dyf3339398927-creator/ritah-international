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

Docker 版监控与页面服务可后台运行，网页关闭后仍查询；提示音需要保持页面打开。Docker Desktop 与电脑必须保持运行。容器以非 root 用户运行，服务仅通过宿主机回环地址发布，不提供远程多用户访问。镜像内置 Playwright Chromium，前端默认优先使用“后台加购”；浏览器资料保存在 `stockroom-data` 卷中。

Docker 的后台浏览器与 Mac/Windows 宿主机浏览器是两个独立会话。它会核对目标 SKU、只尝试点击一次加购并检查容器会话的购物袋；不会自动登录、绕过验证码、选择服务/门店或提交付款。前端仍显示“可见助手”，但在 Docker 中标记为仅原生版并禁用；需要登录、验证码或人工选择时请打开“官网商品”，或改用 Mac/Windows 原生包的可见助手。不要把容器报告的购物袋状态当作订单成功。

首次构建会额外下载 Chromium 及其 Linux 运行库，因此镜像和构建时间会明显增加。更新后请使用 `docker compose up -d --build` 重建镜像。

Mac 原生包和 Docker 启动器没有 Apple Developer ID 公证，首次运行可能需要系统确认；没有修改或关闭 Gatekeeper 的脚本。
