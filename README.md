# PRISM · SRTP 科研展示网站

面向“基于多模态的脑肿瘤纵向生成与预后预测”项目的静态展示网站，服务于前期答辩和成果展示。

## 本地预览

直接打开 `index.html`，或在目录中启动任意静态文件服务器：

```powershell
python -m http.server 8080
```

然后访问 `http://localhost:8080`。

## 页面内容

- 研究问题与“静态快照 → 纵向轨迹”的范式转换
- 基于真实原型 PSNR 记录的滚动数据叙事
- MRI 点阵平滑重组为四模态指标，支持滚动前进与回退
- 可交互的 Build Spec 实验构型器与实时 JSON 编译预览
- `Ctrl/⌘ + K` Research Command Center
- 多模态生成、纵向条件建模与预后耦合技术路线
- “LLM 作为待验证条件编码器”的四组消融实验
- 当前 Med-DDPM 原型及真实调试图片
- 影像质量与预后效用双轨评价体系
- 2026.10—2027.06 项目进程

## 动效规划

- `motion/motionsites-notes.md`：MotionSites 免费案例筛选与取舍。
- `motion/scenes.md`：90 秒解释片的逐镜头规划、叙事节奏与 ManimCE 技术备注。

当前网站直接使用 Canvas 2D 实现点阵 morph，不依赖 Manim 运行时。完整 90 秒视频可在后续按 `scenes.md` 用 ManimCE 单独渲染。

## GitHub Pages 部署

站点没有构建步骤，可以将仓库根目录直接作为 GitHub Pages 的发布源。

```powershell
git init
git add .
git commit -m "Build SRTP project showcase"
git branch -M main
git remote add origin https://github.com/<USERNAME>/<REPOSITORY>.git
git push -u origin main
```

推送后进入仓库的 **Settings → Pages**：

1. Source 选择 **Deploy from a branch**。
2. Branch 选择 **main**，目录选择 **/(root)**。
3. 保存后，网站将发布到 `https://<USERNAME>.github.io/<REPOSITORY>/`。

如果仓库名使用 `<USERNAME>.github.io`，则发布地址为 `https://<USERNAME>.github.io/`。

## 素材与边界

- 当前原型截图来自项目现有的 Med-DDPM 调试结果。
- 页面中的未来轨迹视觉为研究框架示意，不代表真实预测结果。
- 本项目仅用于科研验证，不作为临床诊断或治疗决策系统。
