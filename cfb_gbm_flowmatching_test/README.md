# CFB-GBM：MRI 起点配对 Flow Matching

独立学生科研原型，只做纵向增强 T1 图像预测。主改进模型 `direct_roi` 从基线 MRI 开始、每次调用持续提供基线条件、weeks 和可用基线 GTV。`noise_roi` 是唯一噪声起点对照。旧 I²SB 工程及 E 盘原始数据保持只读。

GitHub 源码位于 `Fortismind/SRTP_2026` 的 `test-Liu` 分支、`cfb_gbm_flowmatching_test/` 子目录。仓库只包含源码、配置、匿名编号划分和来源许可；下述报告、数据清单、缓存及权重都是本地实验产物，不随源码上传。首次配置与旧工程材料依赖见 `GITHUB_UPLOAD.md`。

先看 `reports/实验报告.md`、`reports/data_audit.json`、`reports/comparison.json`，再看 `results/各方法/summary.json` 和 `per_patient.json`。全部测试患者都有对照图；五个训练模型保存 NIfTI 与覆盖范围。

```powershell
Set-Location 'D:\ai\cfb_gbm_flowmatching_test'
$env:PYTHONUTF8='1'
# 首次运行：已有结果请勿重复覆盖；训练会拒绝同名权重目录。
.\.venv\Scripts\python.exe prepare.py
.\.venv\Scripts\python.exe checks.py
.\.venv\Scripts\python.exe train.py --kind all --config configs/bounded.json
.\.venv\Scripts\python.exe evaluate.py
.\.venv\Scripts\python.exe finalize.py
```

环境位于项目 `.venv`，通过 `.pth` 只读复用本机现有 CUDA PyTorch 与医学影像依赖。来源说明见 THIRD_PARTY.md，确切版本见 requirements.lock.txt / reports/environment.json。从零安装时创建 Python 3.10 venv 后按 lock 文件安装 CUDA 依赖。

主模型定义 `zτ=(1−τ)Y+τB`、`u=B−Y`，训练随机 τ，12.5% 强制为1。从 `z1=B` 用 `z←z−h*v` 向0积分。ROI 辅助估计 `zτ−τv` 只用于训练，不能充当完整生成结果。统一最终 [0,1] 裁剪；无积分中间截断。GTV 是规划区域，不是未来肿瘤真值；按物理5mm膨胀，仅增加区域损失权重，ROI 外仍允许变化。

五个可训练分支为 `direct`（无 GTV/ROI）、`direct_mask`（GTV 条件）、`direct_roi`（加 ROI 损失）、`noise_roi`（只改变起点）、`regression`（同规模残差回归）。均使用相同患者划分、抽样更新预算和完整验证患者集，选取基线确定的最多8层，按脑区 MAE 选权重。`identity` 直接用基线。旧测试集是探索性历史测试集，不能称为从未查看的最终测试集。

独立推理只需要基线与 weeks，可选基线 GTV；没有 target 参数。下面是命令格式，请替换成本机有权使用的输入文件：

```powershell
Set-Location 'D:\ai\cfb_gbm_flowmatching_test'
.\.venv\Scripts\python.exe infer.py --baseline 'D:\your_data\baseline_t1gd.nii.gz' --weeks 12 --mask 'D:\your_data\baseline_gtv.nii.gz' --checkpoint weights/direct_roi/best.pt --out results/manual_prediction --steps 16 --solver euler
# 缺少标注时省略 --mask，走训练中的 missing 分支，不视为无肿瘤。
```

恢复原始 shape、方向、affine 和原始 qform/sform；3D Slicer 同时加载 `prediction_normalized.nii.gz` 与 `coverage.nii.gz`，覆盖外为 NaN。`prediction_baseline_intensity.nii.gz` 仅恢复基线任意强度单位。升采样不能恢复原始分辨率，2D 层间可能不连续。

延长训练必须显式创建配置；下面把总步数加到8000、累计墙钟预算加到1800秒，在原 last.pt 续训（会更新同名结果，已有本轮结果应先归档或用新 --run）：

```powershell
$cfg=Get-Content configs/bounded.json -Raw | ConvertFrom-Json
$cfg.steps=8000
$cfg.max_seconds=1800
$cfg | ConvertTo-Json | Set-Content -Encoding utf8 configs/extended.json
.\.venv\Scripts\python.exe train.py --kind direct_roi --run direct_roi_extended --config configs/extended.json --resume weights/direct_roi/last.pt
```

`last.pt` 含模型、优化器、CPU/CUDA随机状态、患者抽样状态及更新数；同环境可续训。小样本拟合 `weights/overfit_only.pt` 不用于正式训练。训练曲线、步数、耗时、参数、显存、暴露患者和有效 ROI 比例见 logs/*.json。

本项目不做治疗决策或生存预测，不将影像相似度视为临床可靠性。无随访真分割时不提供肿瘤 Dice、未来体积或校准不确定性。
