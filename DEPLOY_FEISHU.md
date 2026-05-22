# 飞书同步脚本部署指南 (Physical Machine Deployment)

由于 Agent VM 环境的安全策略限制，`feishu_sync_loop.py` 无法在 VM 内部直接运行。请按照以下步骤在您的物理机（本地电脑）上部署。

## 1. 文件准备
请将以下文件夹完整拷贝到您的物理机：
`F:\working-project\integrations\feishu\`

确保文件夹中包含以下三个文件：
- `client.py` (已修复 Bug 且路径兼容)
- `feishu_sync_loop.py` (已修复 Bug 且路径兼容)
- `config.json` (已填写 App ID, Secret 和 Chat ID)

## 2. 环境安装
在物理机的终端（CMD / PowerShell / Terminal）中执行：
```bash
pip install requests
```

## 3. 启动运行
进入该文件夹路径，运行脚本：
```bash
python feishu_sync_loop.py
```

## 4. 预期效果
- **拉取消息**：脚本会从飞书群中拉取最新消息并保存到本地的 `inbox.json`。
- **推送指令**：脚本会检查同步目录下的 `meta-evolution/storage/state.json`，如果发现状态为 `verified` 的提案，将自动推送到飞书群。

## 5. 常见问题排查
- **ModuleNotFoundError**: 如果报错找不到 `integrations.feishu`，请在根目录运行或将 `PYTHONPATH` 设置为项目根目录。
- **401 Unauthorized**: 脚本已内置 Token 自动刷新机制，无需手动干预。
- **网络超时**: 确保物理机能够正常访问 `open.feishu.cn`。
