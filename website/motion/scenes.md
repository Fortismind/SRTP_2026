# SRTP：从影像快照到未来轨迹

## Overview

- **Topic**: 多模态脑肿瘤影像生成与生存预后预测
- **Hook**: 一张 MRI 只是时间中的一个快照，模型怎样推断“下一步”？
- **Target Audience**: 具备基础深度学习与医学影像概念的高校评审、老师和同学
- **Estimated Length**: 90 seconds
- **Key Insight**: 生成轨迹不是装饰性中间产物，而应该成为连接影像变化、动态特征与生存风险的中间表征。

## Narrative Arc

从一张静态 MRI 出发，先让多模态与随访条件进入同一个视觉系统，再观察图像被重排成可评价的数据；最后把动态轨迹连向生存风险，同时明确当前单例结果不能代替患者级验证。

---

## Scene 1: 一张影像只是一个时间点

**Duration**: 0:00–0:12
**Purpose**: 建立问题与情绪钩子。

### Visual Elements

- 深色背景，中央显示真实 MRI 切片的点阵化轮廓。
- 时间轴只有一枚 `T0` 光点。
- 右侧以低透明度显示“SURVIVAL?”。
- 点阵轻微呼吸，但不做随机闪烁。

### Content

点阵从中心向外显现，形成一张脑部 MRI 轮廓。画面短暂停留后，`T0` 点向右方延伸成一条尚未画完的线。旁侧只出现一句：`如果把生存预测建立在单一时间点上，我们会遗漏什么？`

### Narration Notes

语气克制、提出问题，不急于展示模型。停顿约 1.2 秒，让观众看清单时间点的局限。

### Technical Notes

- 中文使用 `Text`；Markdown 不适合 LaTeX 中文。
- 点阵通过 `VGroup(Dot(...))` 或自定义 `VMobject` 生成。
- 使用 `LaggedStart(..., lag_ratio=0.03)` 形成连续显现。
- 不使用纸笔、涂鸦或随机散点装饰。

---

## Scene 2: 让四种模态同时进入画面

**Duration**: 0:12–0:30
**Purpose**: 解释 T1、T1CE、T2、FLAIR 的互补关系。

### Visual Elements

- 中央保留点阵 MRI。
- 四个模态标签从四个方向进入，薄荷绿、浅青、珊瑚橙、紫色分别编码。
- 四条细线从标签汇聚到同一个条件节点 `C_t`。
- 下方出现 `T1 + T1CE + T2 + FLAIR`。

### Content

四种模态依次靠近，不替换原图，而是以细线接入共同的条件表示。画面强调：模型学习的不是四张孤立图片，而是跨模态的解剖与病理对应。

### Narration Notes

语速稍快，四个模态名称要清楚，最后停在“互补信息”。

### Technical Notes

- `VGroup` 管理四个标签与连线。
- 使用 `Create` 与 `LaggedStart`，不连续使用多次孤立 `FadeIn`。
- 条件节点用 `ValueTracker` 控制脉冲幅度。
- 保留颜色到概念的固定映射。

---

## Scene 3: 时间和治疗改变下一帧

**Duration**: 0:30–0:50
**Purpose**: 展示 MAISI-v2、纵向 ControlNet 与随访/治疗条件建模的核心。

### Visual Elements

- 条件节点展开为 `X_t + M_t + T + Δt`。
- `Δt` 作为从 `T0` 到 `T+1` 的尺度变化，观测时间 `T` 与事件指示 `δ` 在预后阶段进入。
- 未来影像先以轮廓和不确定性光晕出现，而不是直接展示虚假的患者影像。
- 治疗与时间标签通过连线进入生成器。

### Content

`X_t`、`M_t`、治疗信息与 `Δt` 汇入基于 MAISI-v2 的条件生成器，由自行实现的纵向 ControlNet 与 Rectified Flow 输出 `X_{t+1}`、`M_{t+1}` 与不确定性 `U`。画面避免使用装饰笔触，强调条件、预测目标和不确定性的关系。

### Narration Notes

在 `Δt` 出现处放慢。说明治疗信息与随访间隔不是附加说明，而是决定分布转移的条件。

### Technical Notes

- 公式使用 `MathTex`：

  `G_\theta(X_t, M_t, T, \Delta t) \rightarrow (X_{t+1}, M_{t+1}, U)`

- 中文说明使用 `Text`，MAISI-v2、ControlNet 与 Rectified Flow 使用独立标签与连线。
- 使用 `TransformMatchingTex` 连接前后状态。
- 不确定性用半透明同心轮廓，不使用伪造数值。
- 相机仅做轻量推进，避免眩晕。

---

## Scene 4: 从轨迹中提取删失感知预后信号

**Duration**: 0:50–0:72
**Purpose**: 把“生成结果”与“临床评价”连接起来。

### Visual Elements

- 未来影像序列折叠成三个动态特征卡片：体积变化率、水肿梯度、增强轨迹。
- 三条特征流汇入 Cox + DeepHit 主路径，并旁接自行实现的 SDPM 创新路径。
- Censored Flow Matching（CFM）以虚线和“探索”标签旁列，不上升为独立主流程。
- 右侧出现风险曲线和患者级验证图标。
- 影像指标与预后指标分列两栏。

### Content

纵向输出不再停留在视觉展示，而是被压缩成时间序列特征。画面先说明观测时间 `T`、事件指示 `δ` 与右删失，再将特征送入 Cox + DeepHit；SDPM 是主要生成式创新。Censored Flow Matching（CFM）作为次级探索与三者并列在同一预后阶段，但不承担核心验收指标，也不是结题前置条件。预后评价使用 C-index、时间依赖 AUC、Integrated Brier Score 与校准曲线；Dice、SSIM 与体积误差保留在影像评价一侧。

### Narration Notes

这是全片的核心转折：“生成”必须接受影像与预后两类检验。语气要明确 CFM 是可选探索，不能让观众误以为项目成败依赖 CFM。

### Technical Notes

- 使用 `Axes` 绘制风险曲线，范围仅作结构示意时必须明确标注。
- 用显式分支标签区分 Cox、DeepHit、SDPM 与 CFM；CFM 使用虚线边框和“OPTIONAL / EXPLORATION”标签。
- CFM 只在 SDPM 主线稳定后进入小规模对照，画面不展示虚构结果。
- 指标卡使用 `RoundedRectangle` 与 `Text`。
- 采用 `AnimationGroup` 控制特征流向，并保留 0.7 秒的阅读停顿。

---

## Scene 5: 留下未知的下一格

**Duration**: 0:72–0:90
**Purpose**: 收束到可验证结论与项目边界。

### Visual Elements

- 画面回到四个真实 PSNR 点：`14.69`、`14.75`、`15.76`、`11.23 dB`。
- 画出单例均值 `14.11 dB`，但旁边保留虚线 `NEXT?`。
- 最后出现 `PATIENT-LEVEL → LONGITUDINAL → PROGNOSTIC GAIN?`
- 结尾文字：`没有一个样本，能独自代表未来。`

### Content

四个真实指标重新出现，表明当前原型已经跑通可视化与评价流程，但单一病例不能证明总体性能。虚线槽位代表下一阶段仍需完成的患者级与纵向验证。

### Narration Notes

放慢语速。先读四个数值，再读均值，最后停在未完成的问题上。

### Technical Notes

- 不把四个指标做成夸张柱状图；使用同尺度点阵与均值线。
- 虚线框使用 `DashedVMobject`。
- 结尾停 2 秒再淡出，避免仓促。

---

## Transitions & Flow

### Scene Connections

- Scene 1 → 2：单张 MRI 点阵不消失，四模态标签向它汇聚。
- Scene 2 → 3：条件节点 `C_t` 直接展开成四个输入。
- Scene 3 → 4：未来输出的点阵沿路径折叠成动态特征，再分叉到稳定路径、创新路径与探索路径。
- Scene 4 → 5：风险曲线收缩为四个真实 PSNR 点，形成“回到证据”的闭环。

### Recurring Visual Motifs

- 点阵：表示真实的影像结构，并在后半段重组为数据点。
- 一条持续向右的轨迹线：表示时间和条件推进。
- 虚线空槽：表示尚未验证的结论。
- 薄荷绿表示输入与稳定性，珊瑚橙表示关键输出与风险，紫色用于 ControlNet、SDPM 和 CFM 研究分支。

---

## Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Background | 墨黑 | `#080B0D` | 全局背景 |
| Primary | 薄荷绿 | `#9CF5C7` | 输入、结构、稳定信号 |
| Accent | 珊瑚橙 | `#FF896C` | 关键结果、风险、未知 |
| Secondary | 紫色 | `#B7A3FF` | ControlNet、SDPM 与 CFM 研究分支 |
| Text | 暖白 | `#EEF4F0` | 主要文字 |
| Muted | 灰绿 | `#95A29D` | 辅助说明 |

---

## Mathematical Content

### Equations to Render

1. `G_\theta(X_t, M_t, C_t, \Delta t) \rightarrow (X_{t+1}, M_{t+1}, U)`
2. `h_{t} = \phi(X_t, M_t)`
3. `\Delta h_t = h_{t+1} - h_t`
4. `\hat{R} = S(\Delta h_{t_1}, \ldots, \Delta h_{t_n}, c)`

### Graphs/Plots

1. MRI 点阵轮廓：只取真实影像亮度，不做诊断性形状增强。
2. 四模态 PSNR 点阵柱群：范围 `0–18 dB`，使用真实记录。
3. 风险曲线：结构性示意，明确标注“示意，不代表实验结果”。

### Geometric Objects

1. 点阵 MRI：真实 MRI 切片的亮度采样。
2. 条件节点：中心圆与四条输入路径。
3. 动态特征：三条从左向右流动的线。
4. 未知槽位：虚线矩形。

---

## Implementation Order

1. **Scene 1**：定义点阵、背景和全局颜色。
2. **Scene 2**：复用点阵，加入四模态标签。
3. **Scene 3**：建立条件节点与公式变换。
4. **Scene 4**：复用时间线，加入特征和评价节点。
5. **Scene 5**：回到真实指标并完成收束。

### Shared Components

- `MRI_DOT_FIELD`：真实切片采样生成的点阵。
- `TIME_AXIS`：贯穿全片的向右轨迹。
- `CONDITION_NODE`：多模态和纵向条件汇聚节点。
- `UNKNOWN_CELL`：虚线未来槽位。

---

## Web Adaptation

本次网站改动优先实现 Scene 1 与 Scene 5 的连续视觉转译：

- 用真实 MRI 切片采样生成 Canvas 点阵。
- 滚动进度驱动点阵逐点重组为四模态 PSNR 点阵柱群。
- 以低通平滑代替分段跳变，并支持反向滚动。
- 不再使用纸张、红蓝铅笔或手写涂鸦。
- 保留现有深色、薄荷绿和珊瑚橙配色。

## Rendering Note

90 秒完整解释片如需输出，使用 ManimCE：

```bash
manim -r 1920,1080 --fps 30 scene.py SRTPExplainer
```

当前网站改造不依赖 Manim 运行时；`scenes.md` 作为统一叙事与动效规范。
