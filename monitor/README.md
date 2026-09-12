# iPhone 18 Stockroom

本地运行的 iPhone 库存监控工作台。后端 Python 脚本提供门店库存、官网型号目录与购买助手，前端在浏览器显示实时状态。保留原 Go 项目，新增实现位于 `monitor/`。

当前重点为香港与日本的 Apple 官方直营渠道。默认香港地区，型号默认筛选“18”；切换日本后须刷新日本目录，两个地区的 SKU 不可混用。第三方零售、电商、运营商库存尚未接入。

## Windows 便携版

解压整个 `iPhone18Stockroom-windows-x64.zip`，双击 `iPhone18Stockroom.exe`。浏览器自动打开本地页面。无需 Python；购买助手需要已安装 Microsoft Edge。没有 Edge 时可使用已安装的 Playwright Chromium。程序未进行商业代码签名。

也可双击 `Start-Windows.cmd` 一键启动。购买助手现已支持 Microsoft Edge、Google Chrome，按可用性依次选择，最后尝试 Playwright Chromium。

## macOS 一键启动版

- Apple 芯片 M1/M2/M3/M4 等：使用 `iPhone18Stockroom-macos-arm64.zip`。
- Intel Mac：使用 `iPhone18Stockroom-macos-x86_64.zip`。

用系统“归档实用工具”解压整个 ZIP，双击 `Start-Mac.command`。程序自动打开默认浏览器，无需安装 Python、Node 或开发工具。启动器所在终端窗口需要保持打开；关闭窗口停止服务。购买助手需要已安装 Google Chrome 或 Microsoft Edge；Safari 可以打开监控界面，但不作为自动加购浏览器。

Mac 版本在 macOS 15 原生构建，当前支持目标为 macOS 15 及以上，按处理器架构选包。未使用 Apple Developer ID 签名或公证，首次打开可能需要你通过 macOS 的安全确认；我们无法预先消除系统确认。此包不修改系统安全设置。

Mac 配置保存于 `~/Library/Application Support/iPhone18Stockroom`。同一系统下升级时保留该目录即可恢复目标。

## 使用流程

1. 选择地区与门店，点击“刷新官网目录”。只有从 Apple 产品记录解析出的真实零件号才会进入目录，未公布或查询失败不会生成虚构 SKU。
2. 搜索 iPhone 18 / 容量 / 颜色，选择型号并添加监控。也可手动输入从官网确认的 SKU。
3. 点击开始监控。默认每轮 30 秒；请求失败延长间隔，最多 15 分钟。一次轮询耗时另计。
4. 有货时页面更新状态；可启用提示音，声音需要保持网页打开。暂停后未完成请求的结果会丢弃。
5. “购买助手”由后端脚本打开独立 Edge 窗口。检查型号及选项后点击悬浮确认按钮，脚本尝试加入购物袋一次。取货门店、登录和付款由你在官网完成。无法确认商品时显示需要核对，不会报告购买成功。

关闭网页不会停止后台查询；关闭程序后台窗口或 Ctrl+C 停止服务。电脑需要保持联网且不休眠。此版本尚未提供 Bark 推送。

## 数据与部署

服务仅监听 `127.0.0.1`，端口自动选择。启动地址的片段含随机会话凭证；不要分享该完整地址。配置、目录缓存和购买浏览器资料保存在 `%LOCALAPPDATA%/iPhone18Stockroom`。不会写入分发包。多个程序实例建议使用不同 `--data-dir`。

GitHub Pages 只能托管静态网页，不能运行本后端或定时任务。分发 ZIP 给其他人后，每位用户在自己的电脑上启动服务。尚未实现远程服务器多用户部署。

## 源码方式

Python 3.10+。库存与网页服务只依赖标准库，购买助手使用 Playwright。

```powershell
python -m pip install -r monitor/requirements.txt
python monitor/app.py
```

没有 Microsoft Edge 时，可以执行 `python -m playwright install chromium` 安装购买助手的浏览器。

单次查询（需要先通过界面保存目标）：

```powershell
python monitor/app.py --once
```

返回 JSON；退出码 2 表示有查询未知，退出码 0 表示本轮没有未知，并不代表有货。可指定 `--data-dir 路径`、`--port 8765`、`--no-browser`。

测试与 Windows 打包：

```powershell
python -m unittest discover -s monitor -p test_monitor.py -v
python -m pip install pyinstaller==6.22.2
python monitor/build.py
```

macOS 打包同样运行 `python monitor/build.py`，必须在对应 Mac 架构上原生构建。仓库的 `Portable Windows and Mac packages` 工作流分别在 Windows、Apple 芯片 Mac、Intel Mac 上编译并测试启动，产物保留 30 天。源码运行要求 Python 3.10+；分发包已内置 Python。

## 设计与限制

使用 `/shop/retail/pickup-message`，复用 Cookie，会话请求串行且间隔至少 1 秒，同一门店合并型号查询。HTTP 错误、空字段、未知状态、错误门店和 SKU 不一致均不会判成有货。官网接口未承诺稳定，HTTP 541/403 应视为查询失败。目录刷新失败保留最后成功缓存并显示错误。

购买助手是可审查的加购辅助：不更换用户 SKU、不自动选付费服务、不绕过验证码、不提交付款。程序不能预留库存。该流程必须在目标地区与型号上线后实测；本项目测试不通过真实订单来验证。

许可 GPL-3.0-or-later。详细来源及 Fork 记录见 `SOURCES.md`。分发可执行程序时，请同时提供附带的对应源码 ZIP 和许可证。
