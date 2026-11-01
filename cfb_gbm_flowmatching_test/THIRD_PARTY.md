# 来源与使用范围

本工程为非商业学生科研和评估原型。原始 CFB-GBM 数据不复制分发，使用条件由原数据提供者决定。

源码提交保留 `references/provenance.json` 的文件来源与哈希，以及原工程附带的完整 `references/official/LICENSE`。该许可证用于保留所复用代码来源链的许可信息，不表示本 Flow Matching 是 NVIDIA 官方实现。

`fm/preprocess.py`、`fm/metrics.py` 从本机 `D:/ai/cfb_gbm_i2sb_test/cfb/` 复用；原 `THIRD_PARTY.md` 对该工程审慎限定为非商业研究/评估，本文继续遵守此范围，不另行授予原代码权限。来源文件 SHA256 记录在 `reports/original_artifact_hashes.json`。空间恢复部分改为保留原始 qform/sform，新增 GTV 物理 5 mm 膨胀在本工程 `prepare.py`。不导入或复制旧桥、训练器、模型权重；强度缓存按下述规则验证后只读复用，标注缓存独立重建。

预处理加速：仅在原始 source/target 的 bytes、mtime_ns 和当前 geometry 与旧记录一致，且 baseline 预处理函数源码逐字一致时，只读复用旧 baseline/target/mask 强度缓存；记录每个缓存 SHA256。初始逐例原始重算的新缓存还与旧缓存逐元素比对。任一不一致回退原始重算。所有 GTV/ROI 均重新读取基线标注在新工程生成，旧缓存不修改。

`fm/core.py` 的线性配对 FM、U-Net、损失、Euler/Heun 求解独立实现，无 I²SB 随机桥公式或反向后验。

方法背景：

- Flow Matching for Generative Modeling: https://arxiv.org/abs/2210.02747 （2026-11-01 核对标题和摘要；用于向量场回归的训练思想）。
- Brain-WM: Brain Glioblastoma World Model: https://arxiv.org/abs/2603.07562 （2026-11-01 核对标题和摘要；仅作脑影像及掩膜监督背景，本工程不复现其 MoT、治疗预测、多时点掩膜任务）。不将其作为直接 MRI 起点设计的完整依据，也不转用其临床结论。

PyTorch、NumPy、SciPy、NiBabel、scikit-image、Matplotlib 等依赖遵循各自许可。未下载任何预训练参数或第三方模型代码。
