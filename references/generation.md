# 内置生图提示词与分镜约束

一张分镜是一个表情，不要把 16 种不同含义拼成一张大图。九格按从左到右、从上到下播放，每格留足边距，不画网格线或数字。

角色基底英文描述应固定物种、头身比、毛色/肤色、耳朵、眼睛、鼻口、标志物、服装、材质及渲染风格。将表情和动作放在独立段落，避免把「永远微笑」当成人设不变量。

示例提示词结构（将方括号内容替换为实际已确认内容后发送）：

```text
Use case: stylized-concept.
Asset: one transparent 3x3 animation sprite sheet for one WeChat sticker.
Reference role: approved character identity anchor, not a pose constraint.
Identity: [approved English character base]. Preserve colors, proportions,
clothing and distinguishing accessories. Change facial expression as needed.
Nine equal square cells, row-major sequence, no visible grid or cell numbers.
Action: [one simple action with explicit nine-stage progression].
Fixed camera, consistent scale and baseline, ample transparent margins.
Complete loop; last pose returns smoothly to first without a jump.
Caption verbatim: [exact Chinese caption].
Caption layout: [approved layout, described explicitly for every cell].
No white sticker outline, no backing paper, no floor shadow.
Real alpha transparency, never draw a checkerboard into the image.
Keep all hands, feet, props and caption wholly inside each cell.
```

配字版式必须按方案填写整个段落。若选 `white_placard`，要求白底黑框加粗黑字顶部牌、九帧位置相同、与角色及配饰间有透明间隙、无支杆。红色方印等其他布局写对应视觉要求，处理配置用 `label_mode: none` 保留，不能偷偷改成白牌；若需要固定红章则须实现并验证独立提取器。角色有白帽、白耳朵时尤其不能强套顶部白牌检测。

白牌安全布局：当前提取器只分析归一化 418px 单格顶部 85px，并在牌框外扩后清除该矩形。提示词可要求牌完全位于顶部 16% 内、最高耳尖在所有动作中低于顶部 27%，两者留透明空隙；这些是生成引导，不能保证工具遵守。歪头、抬耳、举手的极值帧必须另查。牌与耳朵实际重叠或间隙不足时，优先定向重生该张、整体等比例缩小角色增加间隙；不能靠裁掉耳尖使脚本通过。白帽、白色耳尖进入检测区时先检查提取适用性。

不对称角色在英文基底中同时写角色自身与观众视角，例如 cat's left = viewer right；固定花纹左右关系，不固定开心表情。临时包、枕头、爱心只写在该张动作中。明确参考图只约束身份，生气用皱眉闭嘴、委屈用垂耳泪眼等具体变化。

推荐把动作写成「起势→展开→极值→收回」而非九格各做一个动作。首尾姿态接近即可，不必复制完全相同的帧；量化后相同帧可能被 GIF 编码器合并，最终不足九帧需检查，而不能只改报告帧数。

内置工具使用当前实际参数，不编造模型名、原生 GIF 接口、费用或 320×320 限制。按工具要求设置透明背景。查看所有本地参考图片后再传入编辑。每次生成完成即复制源文件到项目，提示词记录使用项目相对路径。

封面：同角色，完整身体或经确认构图，友好动作，无文字、无标牌、透明底。横幅：约15:8宽幅场景，不透明、无文字；主体放在中央安全区域，裁为750×400后再检查。

图面错字、身份漂移、肢体错误应通过内置生图定向修复；拆帧、坐标校正、GIF 编码等确定性处理交给脚本。不要用大量无约束生成掩盖局部问题。
