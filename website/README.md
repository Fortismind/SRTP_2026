# SRTP 医学科研展示网站

面向“基于多模态的脑肿瘤纵向生成与预后预测”项目的静态展示网站，主要用于科研汇报、前期答辩和阶段成果介绍。

## 项目内容

- 研究问题与“静态影像快照 → 纵向演化轨迹”的范式转换
- 基于真实原型 PSNR 记录的滚动数据叙事
- MRI 点阵连续重组为四模态评价指标
- 可交互的实验构型器与 JSON 参数预览
- 多模态生成、纵向条件建模和预后信号耦合路线
- 语言条件编码的对照实验设计
- 当前 Med-DDPM 原型及真实调试图片
- 影像质量与预后效用双轨评价体系
- 2026.10—2027.06 项目进程

## 目录说明

如果网页位于 `website/` 子目录，主要结构如下：

```text
website/
├── index.html
├── styles.css
├── script.js
├── favicon.svg
├── .nojekyll
├── assets/
└── README.md
```

## 本地预览

进入网页所在目录后启动静态文件服务器：

```powershell
cd website
python -m http.server 8080
```

浏览器访问：

```text
http://localhost:8080
```

如果网页文件直接位于仓库根目录，则直接在根目录启动同一命令。

## GitHub Pages 部署

站点不需要构建步骤。若网页位于 `website/` 目录，可在仓库的 **Settings → Pages** 中设置：

1. Source 选择 **Deploy from a branch**。
2. Branch 选择包含网页的分支，例如 `main` 或 `website`。
3. Folder 选择 `/website`。
4. 保存后等待 GitHub Pages 自动构建。

若网页直接位于仓库根目录，则 Folder 选择 `/(root)`。

## 科研说明

- 当前原型截图来自 Med-DDPM 调试输出。
- 页面中的未来轨迹为研究框架示意，不代表真实预测结果。
- 单例指标不能替代患者级验证，也不代表模型总体性能。
- 本项目仅用于科研展示，不作为临床诊断或治疗决策系统。
