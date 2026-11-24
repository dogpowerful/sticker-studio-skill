# 表情工坊 · Sticker Studio

用于 Codex 的动态表情包制作 skill：先确认角色基底与 16 张动作配字，再用 Codex 内置生图生成九帧分镜，完成透明 GIF、角色横向对齐、素材打包和检查。

## 安装与使用

将本仓库文件放入 Codex 的 `skills/sticker-studio/` 目录，确保 `SKILL.md` 位于该目录根部。

示例：

```text
使用 $sticker-studio，做一套16张动态表情包。
角色是一只三花猫，先给我角色基底和动作配字表确认。
```

默认使用当前可用的 Codex 内置生图工具；不需要第三方模型、API key 或 OpenAI SDK。脚本只做本地处理，需 Python 3.10+ 和 Pillow。图片生成本身需要会话中可用的生图工具。

## 本地脚本

```sh
python -m pip install Pillow
python scripts/sticker_pipeline.py anchor --sheet /path/to/sheets/01.png --out /path/to/anchor.png
python scripts/sticker_pipeline.py build --manifest /path/to/album.json --out /path/to/album-v1
python scripts/sticker_pipeline.py validate --out /path/to/album-v1/wechat_upload
python scripts/sticker_pipeline.py qa --out /path/to/album-v1/wechat_upload --dest /path/to/album-v1/qa
```

输入格式见 [manifest 说明](references/manifest.md)，生成约束见 [生图说明](references/generation.md)。修复使用新版本目录，保留旧图及生成记录。

产物包括 16 张透明九帧 GIF、缩略图、封面、图标、横幅、预览 HTML、技术校验报告及 ZIP。保留现有 `wechat_upload` 目录名以兼容打包器。

自动校验和逐帧检查不能替代实时播放验收；躯干对齐是启发式处理，仍需查看完整循环。技术配置通过不代表平台审核通过。

## 验证脚本

```sh
python scripts/test_pipeline.py
```
