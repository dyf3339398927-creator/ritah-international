# 来源、方法对比与 Fork 记录

核对日期：2026-09-12。更新日期来自 GitHub `pushed_at`，不把收藏等仓库活动当作代码更新。以下研究结果不等于实际购买成功率评测。

| 上游 | 最近推送 | 本账号 Fork | 采用的方法 |
| --- | --- | --- | --- |
| https://github.com/ENCHIGO/apple-pickup-watcher | 2026-09-12 | https://github.com/dyf3339398927-creator/apple-pickup-watcher | 新 pickup-message 接口、未知状态、合并查询、错误退避 |
| https://github.com/suversal/apple-store-inventory-monitor | 2026-09-11 | https://github.com/dyf3339398927-creator/apple-store-inventory-monitor | 多目标工作台、逐轮日志与购买袋状态区分 |
| https://github.com/zero850x-ctrl/hk-iphone-grab | 2026-09-10 | https://github.com/dyf3339398927-creator/hk-iphone-grab | productSelectionData 目录发现、独立浏览器加购会话 |
| https://github.com/LennonChin/AppleStore-Monitor | 2026-07-03 | https://github.com/dyf3339398927-creator/AppleStore-Monitor | 可分发脚本的部署形态；通知适配可作为后续扩展 |
| https://github.com/hteen/apple-store-helper | 2025-09-24 | 与已有 ritah-international 同属 Fork 网络 | 原 Go/Fyne 监听、购物袋跳转思路 |
| https://github.com/Sunbelife/apple-store-helper-15 | 2025-09-11 | GitHub 返回已有 ritah-international | 比较多地区、目录内置的优缺点 |

GitHub 没有创建最后两个同网络的第二份 Fork，不能把它们列为新建成功。原仓库直接上游为 https://github.com/RayJason/apple-store-helper 。

## 最适合本次交付的方法

在原仓库内新增 Python 标准库后端与静态浏览器界面，便于脚本分发及 PyInstaller 打包。库存逻辑参考 ENCHIGO 的公开接口契约，目录字段参考 hk-iphone-grab 的解析方式，保留原有门店数据。所有新业务代码在 monitor/，不需要 Rust/Go 编译环境即可运行源码。

该选择针对低安装门槛，不宣称 Python 客户端在 Apple 风控下优于 Rust/Chromium。网络实际返回是可用性的最终证据；失败始终显示未知。加购依赖用户检查页面选项，未实现自动支付。

## 非 GitHub 来源

- Apple 官方购买目录：https://www.apple.com/shop/buy-iphone
- Apple 官方产品页面：https://www.apple.com/iphone-18-pro/
- Python 标准库服务端：https://docs.python.org/3/library/http.server.html
- Playwright Python 浏览器上下文：https://playwright.dev/python/docs/browser-contexts
- PyInstaller 打包：https://pyinstaller.org/en/stable/usage.html

官网目录优先于仓库里的旧机型快照。未实际从目标地区官网获取的型号不作为已验证库存目标。

## 版权与许可

原项目 hteen/apple-store-helper、RayJason 的修改及其原有版权文件保持不变。ENCHIGO 与 suversal 为 GPL-3.0 系列项目，hk-iphone-grab 与 LennonChin 项目使用 MIT。此次新实现参考公开接口与行为，没有整段复制其实现；现有门店资源与原项目一同按 GPL-3.0 分发。新增实现采用 GPL-3.0-or-later，作者为本项目贡献者（2026）。保留根目录 LICENSE，二进制 ZIP 附上对应源码 ZIP。
