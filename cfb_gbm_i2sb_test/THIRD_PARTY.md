# 方法和来源

本项目是非商业研究/评估原型。原论文的图像恢复实验不等于本项目的纵向 MRI 预测实验。

- Liu 等，**I²SB: Image-to-Image Schrödinger Bridge**，ICML 2023，https://arxiv.org/abs/2302.05872 。本机 `IISB.pdf` 第一页标题一致，共 21 页；已阅读第 4—5 页的 3.1/3.2、公式 11/12 和算法 1/2，第 6 页噪声日程说明。文件哈希见 `references/paper_check.json`。
- 官方实现：https://github.com/NVlabs/I2SB 。核对 `i2sb/diffusion.py` 的桥高斯分布与后验，`i2sb/runner.py` 的标签、x0 重建及 MSE；查阅 README 和完整许可证。本次读取的提交号、网址与文件 SHA256 见 `references/provenance.json`。
- 参考副本在 `references/official/`，保留其原始版权和完整 `LICENSE`。官方代码使用 **NVIDIA Source Code License for I2SB**，限定非商业研究或评估，不能按 MIT 许可传播。
- 本工程的轻量网络、数据管线和训练入口单独编写；`cfb/bridge.py` 根据公式实现，并以官方代码进行核对，没有复制官方训练框架。为审慎处理来源关系，桥实现及本工程衍生使用同样限定为非商业研究/评估；不为第三方代码另行授予权限。
- 官方离散实现采用含两端步长的累计和，本工程使用连续 β 的精确积分，明确定义 B(0)=0、B(1)=S，因此端点是精确 Dirac 分布。它保留 I²SB 的桥分布、归一化残差目标及高斯反向后验，不是逐行复现官方离散化。其他任务改造见 README。
- 依赖 PyTorch、NumPy、SciPy、NiBabel、scikit-image、Matplotlib、pypdf；其许可证仍归各项目。原始 CFB-GBM 数据不打包、不写入，数据使用条件仍由原数据提供方规定。
