# 第二轮训练（2026-10-31）

本轮由 `phase2_run.py` 执行预先固定的有界实验，计划写入 `reports/phase2_2026-10-31/plan.json`。不要删除计划或覆盖旧运行后重跑同名实验。

- 训练/验证/原测试患者划分不变，全部原始数据只读。
- I²SB、回归 U-Net，各使用 20261025 和 20261031 两个种子；前者从原 last.pt 的 600 步延续，后者从头训练，均以总计 5,000 步为上限。
- 每个训练运行最多 8 分钟；检查、验证和导出另计。固定网络、归一化、桥公式、学习率，避免同时改多个因素。
- 选择权重使用全部 24 位验证患者，每位固定 16 张由基线范围决定的均匀切片；每 500 步验证。改用新标准时会重新评价续训起点，旧 4 人验证的最佳分数不再沿用。
- 运行期间禁止读取原测试集的图像缓存及原始 NIfTI。它已用于第一轮报告，本轮只报告验证结果，不能声称取得新的独立测试改善。

检查：`phase2_qc.py` 汇总训练/验证缓存的饱和、掩膜和粗对齐指标；`phase2_raw_qc.py` 只读抽查饱和最高的训练/验证各 3 对原始影像。它们不修改训练变换。`test_phase2.py` 验证空间/指标契约以及更改验证协议时重新计算最佳分数的逻辑。

`phase2_evaluate.py` 对旧模型与所有新种子模型使用同一验证队列、全部基线覆盖切片计算指标；按事先规定的 16 张验证切片 MAE 选择一个种子用于附加诊断。附加诊断包括固定/打乱临床间隔、I²SB 的三个预定采样种子；没有最好样本挑选，也没有临床不确定性校准。

选定模型为验证编号最小的三个患者保存对照图，并为首位验证患者从原始基线独立推理、重建 NIfTI。文件保存在 `results/phase2_2026-10-31/`。NIfTI 的 `coverage=1` 才是模型覆盖范围。

执行入口（已有项目环境；不要重复启动已经在运行或已完成的同名训练）：

```powershell
cd D:\ai\cfb_gbm_i2sb_test
.\.venv\Scripts\python.exe phase2_qc.py
.\.venv\Scripts\python.exe phase2_raw_qc.py
.\.venv\Scripts\python.exe test_phase2.py
.\.venv\Scripts\python.exe phase2_run.py
.\.venv\Scripts\python.exe phase2_evaluate.py
.\.venv\Scripts\python.exe phase2_finalize.py
.\.venv\Scripts\python.exe phase2_verify_delivery.py
```

原有 `weights/*_short`、第一轮日志与报告均保留。新权重在 `weights/*_phase2_s*`，新日志在同名 `logs/` 子目录。新报告为 `reports/phase2_2026-10-31/第二轮训练报告.md`。
