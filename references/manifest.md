# 输入与输出

依赖：Python 3.10+、Pillow。运行 `python -m pip install Pillow` 仅在缺依赖且安装获授权时进行。无需 OpenAI SDK、API key 或网络服务。

JSON manifest 的所有源图路径相对 manifest 文件所在目录，也可用绝对路径。脚本拒绝覆盖已有输出目录，修复时用 `album-v2` 等新目录。脚本不负责生成图片。

顶层字段：

| 字段 | 含义 |
|---|---|
| title | 专辑标题 |
| character_base | 已确认的英文角色描述，供复现记录 |
| cover | 透明无字封面源 PNG 路径，必填 |
| banner | 不透明无字横幅源图片路径，必填 |
| duration_ms | 每帧毫秒数，默认120；至少20且为10的倍数 |
| items | 必须16项，顺序对应01至16输出编号 |

每项示例（实际 manifest 必须写满16项，不要复制成相同动作）：

```json
{
  "slug": "01_received",
  "caption": "收到啦",
  "meaning": "收到",
  "action": "raise one paw and wave twice",
  "sheet": "sheets/01.png",
  "label_mode": "white_placard",
  "align": "torso"
}
```

`slug` 只允许字母、数字、下划线、短横线，16项不可重复。`caption` 必须与图面逐字核对，`meaning` 用于后台填写，`action` 用于记录。

`align`：

- `torso`（默认）：以规范化单格下部80%至88%高度带的前景左右中点中位数锁定躯干横坐标。适用于全身站姿。该带可能被挎包、浴桶影响，需检查实际角色支点，不能只看报告通过。
- `manual`：增加 `anchors` 数组，长度9。各数值为源单格内稳定支点的横坐标除以该格宽度，范围0至1。脚本只平移，使该支点对齐；不要选择正在摆动的手、橘子或耳朵。记录选择依据。若刻意横向移动，使用 `none`。
- `none`：不做横向平移，用于预期位移或需要另行设计对齐的构图。

`label_mode`：`white_placard` 默认检测规范化418px单格顶部85px、横向40至378px内的白面板。该区域若有白帽子、耳朵、文字以外的白道具会误检，须看提取效果。`none` 保留原图，不固定标牌。脚本目前不支持红色方印自动固定。

目前统一归一化每格为418×418；只适用于等大正方形3×3格。不规则格应重新生成或先明确裁切坐标。脚本不会推断未知网格。

产物：

```text
album-v1/
  input_manifest.json
  sources/                 中间GIF及封面/横幅源图
  motion_report.json       torso模式坐标检查记录
  contact_sheet.jpg        静态总览
  wechat_upload.zip
  wechat_upload/
    main/01.gif ... 16.gif
    thumb/01.png ... 16.png
    cover.png
    icon.png
    banner.png
    manifest.json
    meanings.csv
    preview.html
    validation.json
```

报告中的无抖动仅代表指定启发式支点的水平坐标稳定；脸部、尺度、纵向漂移、首尾接缝仍须视觉验收。`manual`、`none` 无自动运动评分。验证出错时进程返回非零，不生成成功ZIP；修正输入后选择新版本目录重新运行。
