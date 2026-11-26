# 真人照片 → 卡通动态表情

当用户提供人物照片并要求参考人物制作时使用。沿用内置生图和现有合成脚本，不需要接入第三方模型或创建上传页面。

## 输入与人物设定

1. 先查看用户附件或指定本地图片，再写角色方案。没有图片时请用户附图；多人物且目标不明确时只补问要参考哪位。可先提供默认画风建议，但不要凭空描述未见照片。
2. 建议清楚、无遮挡的正脸或轻微侧脸照片。可接受一张；额外角度用于补充，不强制收集。若照片不足以支持目标，明确哪些特征被遮挡；不虚构服装或身体特征为照片事实。
3. 从可见外观提炼：脸型、发型发色、眉眼形态、眼镜、胡须、服装轮廓和配色等。只描述外观，不识别人物身份，也不从照片推断性格、职业或其他不可见属性。
4. 输出英文角色基底和 16 张动作配字表。用户未指定画风时，默认圆润、简化的 Q 版 3D 卡通，保留辨识特征；服装可沿用可见部分，下半身缺失时明确提出简化设计。肤色忠于照片，不默认美白或更改体型。表情和临时道具放在动作段落，不能写成恒定微笑。

## 先看卡通预览

方案确认后，用内置 imagegen 参考原照片生成一张 `character_preview.png`：单一全身卡通角色、透明底、无字、无标牌、自然中性或轻微微笑、四肢完整。它是对人物的风格化表达，不承诺照片级还原。

提示词框架：

```text
Create ONE full-body stylized cartoon character based on the supplied person photo.
Reference role: visible appearance only, not the photo's pose, expression or background.
Preserve these observed features: [observed face, hairstyle, glasses, facial hair,
skin tone, visible clothing colors].
Style: [approved style]. Outfit completion: [approved invented details if needed].
Relaxed front-facing pose, complete hands and feet, generous margins.
Transparent background, no text, no label, no floor shadow or sticker border.
Do not reproduce other people, scenery or text from the photo.
```

展示预览让用户确认；若用户已明确授权自动完成卡通改编，可自行核对后继续。需要修改时只修预览，不提前生成余下 16 张。不能用未确认的卡通脸批量跑完全套。

## 复用现有流程

- 生成第 1 张九帧分镜时，以卡通预览为主要身份参考；查看后再传入工具。不把照片直接复制成九个静态头像。保留脸型、发型、眼镜和衣服等特征，让表情与动作变化。
- 从第 1 张抽出 `anchor.png`，按主 skill 流程生成其余 15 张。后续主要参考 anchor；需要纠正明显失真时可再次参考原图，记录实际使用的参考路径。
- 生成日志记录照片输入、卡通预览、分镜和 anchor 之间的来源关系。原照片保留在项目私有输入目录，不放入公开仓库、宣传总览或交付 ZIP；示例宣传只使用用户已授权展示的素材。
- 合成仍使用相同 manifest 和打包命令，不要求修改 Python 接口。白帽、白发、举手等不能进入文字牌提取区；必要时调整构图或选择 `label_mode: none` 并检查文字稳定性。
- 检查每张的脸型、发型、眼镜、服装一致性，以及愤怒、困倦、大笑时是否仍像同一个卡通人物。技术校验通过不等于人物相似度检查通过。

## 调用示例

附上照片后输入：

```text
使用 $sticker-studio，参考我上传的人物照片，做一套16张卡通动态表情。
保留发型、眼镜和服装配色，画风用圆润Q版3D。
先给我角色基底和动作配字表，确认后先看单张卡通角色预览，再开始整套制作。
```
