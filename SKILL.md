---
name: sticker-studio
description: Create 16-image animated sticker albums from character ideas or real-person photo references, including cartoon character design, nine-frame sprite sheets, transparent GIFs, frame alignment and upload packaging.
---

# 表情工坊 · Sticker Studio

从角色方案到 16 张透明 GIF 与 `wechat_upload` 素材文件夹。默认使用 Codex 内置生图；脚本仅负责本地处理，不调用模型接口。依赖 Python 3.10+、Pillow。脚本相对本 skill 目录运行，产物写入用户项目。

## 方案与授权

先读取项目已有 README、生成及打包脚本（可能在 ZIP 中），尊重用户指定的阶段。角色尚未明确时只补问角色身份；已有角色先核对参考图片，不能仅凭名字猜测。没有参考图也可以设计原创角色。

先交付英文角色基底、16 张「含义词 / 中文配字 / 单一循环动作」表供确认。覆盖收到、好的、谢谢、疑问、无语、哈哈、委屈、生气、裂开、加油、抱抱、摸鱼、下班、早安、晚安等日常语义，按主题调整；不要声称这些是后台搜索量排名。已确认的方案无需重复审批。用户仅要设计时停在方案阶段。

## 生成与锁定

用户附上真人照片、要求参考照片制作卡通表情时，先读取 [references/photo-to-cartoon.md](references/photo-to-cartoon.md)。使用聊天附件或用户指定的本地图片作为输入，不需要另建上传网站。先确认卡通角色预览，再进入下面的九帧生成流程；已明确确认的形象不重复审批。

读取 [references/generation.md](references/generation.md)。使用当前可用内置 imagegen 工具；不要默认读取 API key、接第三方或调用旧脚本内硬编码模型。遵守工具的参考图查看、透明背景和保存路径规则。

1. 先生成第 1 张 3×3 九帧透明分镜，每格同尺寸、固定视角、相同行进顺序。内置生图输出是静态分镜，不能称作原生 GIF。
2. 复制图片到项目 `sheets/01.png`，检查角色、配字及九帧动作。用下面 anchor 命令抽取第一帧；后续明确以该锚点为身份参考，改变动作和配字。锚点能约束外观，不能保证绝对一致。
3. 逐张生成其余 15 张，并保存每次提示词、源图片、来源参考及实际输出路径。不要让正式产物依赖全局生成目录。每次只处理一个素材；单次超时可重试一次，持续失败时保留进度、报告失败，不自动切换模型。
4. 单独生成透明无字封面、不透明无字横幅；图标由脚本从封面裁切。检查不同表情确实表达对应情绪，不能把开心锚点表情复制到生气、委屈等全部动作里。

续跑时先核对 manifest、anchor、提示词和现存源图，复用已确认角色和合格图片，只补缺失或失败项。每项记录提示词路径、参考路径、工具实际输出路径、项目副本、状态及失败原因到项目 `generation_log.json`。修复用 `04-v2.png` 等新路径并更新 manifest，保留旧源图。“文件存在”不等于验收通过。

```text
python <skill>/scripts/sticker_pipeline.py anchor --sheet <project>/sheets/01.png --out <project>/anchor.png
```

## 对齐、合成、打包

读取 [references/manifest.md](references/manifest.md)，写项目级 manifest。脚本会规范化分镜单格为 418px，固定标牌，按稳定躯干校正横向位移，并调用随附 `pack_wechat.py` 的 `package_album()`。

```text
python <skill>/scripts/sticker_pipeline.py build --manifest <project>/album.json --out <project>/build/album-v1
python <skill>/scripts/sticker_pipeline.py validate --out <project>/build/album-v1/wechat_upload
python <skill>/scripts/sticker_pipeline.py qa --out <project>/build/album-v1/wechat_upload --dest <project>/build/album-v1/qa
```

- **等宽切格不等于对齐。** 比较每帧稳定躯干的位置，不能用受挥手、道具影响的全身包围盒中心。原地全身站姿可选 `torso`；它只校正横向平移，保留头部、四肢及纵向运动。
- 躯干算法是启发式，不能普适于侧躺、半身、被道具遮挡的角色。用 `manual` 提供九个稳定支点横坐标，或 `none` 保留预期行走/摇摆轨迹。它们不自动获得「无抖动」结论，必须逐帧及播放复核。当前脚本按完整角色留白；半身贴底需要调整布局并重新验收。
- 固定白色顶部标牌时选 `white_placard`；仅在顶部干净区域有白底黑字牌、且与橘子/耳朵/道具分离时适用。检测异常应报错并检查源图。无牌用 `none`；红印章、透明文字等不能强套白牌检测，可重新生成受支持版式或实现并验证对应提取器。
- 中文牌复用一张已核对的源牌，避免逐帧变字与摇摆。字有误时先修正源图再重跑；不能用 manifest 的正确文字假装图面也正确。
- 保留真实 alpha，GIF 使用单阈值透明及原前景 RGB，禁止与白背景预混。不要把白色身体、眼白或牌内部挖透明。不要通过逐帧独立缩放、旋转或冻结身体消除抖动。

## 验收与交付

脚本检查：16 张、240×240 GIF89a、每张 9 帧、无限循环、透明背景、6px 留白、≤500KB；120px 缩略图≤200KB；240px 封面≤500KB、50px 图标≤100KB；750×400 横幅≤500KB。以上是随附打包器技术配置；上传时若要确认当前平台规范，应查官方资料，不把历史脚本注释当作平台实时规则。

自动校验之外，打开 `preview.html` 查看每张动画在深浅背景下的完整循环，检查文字、缩放变形、手脚、透明边缘、循环接缝与动作语义。`contact_sheet.jpg` 只能辅助静态审查，不能代替播放。`motion_report.json` 的躯干误差也不能代替视觉审查。保留验证未覆盖的局限，失败时不标记可交付。

修复已有 GIF 时保留旧版并写新版本目录，重建压缩包；预览 GIF URL 包含内容哈希以避开旧缓存。交付 `wechat_upload/`、ZIP、预览、anchor、提示词记录及简短验证结果。表述为「素材已按配置打包」，未经平台实际审核不声称审核通过。上传、发布需有用户授权。

`qa` 从最终 GIF 解码，导出每张九帧在深浅两种背景下的检查图，并创建待填写的 `review_status.json`。对照源图核查文字牌提取是否截断耳尖、头饰或举手；尺寸和留白检查无法发现内部截断。逐帧核对全部 144 帧，尤其是极值动作与首尾帧。

分别记录自动校验、逐帧审查、实时播放和平台审核。播放受工具或安全策略限制时，不绕过限制，保留 `playback_review: pending`；可交付已打包素材供用户复核，同时说明已完成范围和本机预览入口，不能宣称完整视觉验收或“完全无晃动”。
