# GitHub 源码提交范围

远端仓库：https://github.com/Fortismind/SRTP_2026.git

目标分支：`test-Liu`。本项目放在仓库的 `cfb_gbm_flowmatching_test/` 子目录，保留已有 I²SB 工程和 website。

上传源码、训练配置、中文文档、匿名患者编号划分 `data/splits.json` 和来源/许可记录。这个源码副本不包含原始 MRI、GTV 文件、患者影像路径清单、临床表、缓存、权重、日志、本地报告、病例图或逐患者预测结果。本地实验文件不会因忽略规则被删除。

`.gitignore` 覆盖 Python 环境/缓存、实验输出目录、`logs_*.txt`、患者清单和常见医学影像/数组/权重后缀；`.pth` 也排除，避免提交本机依赖复用路径。`export_source.py` 使用白名单导出，只写入不存在的新目录。

## 复现前提

1. 自行取得有权使用的 CFB-GBM 原始数据；本仓库不分发数据或已训练参数。
2. 在旧 I²SB 项目先生成本地 `data/manifest.json`、`data/splits.json`、`reports/data_audit.json`、`reports/header_forms_and_source_signatures.json` 和相应缓存；这些文件没有纳入源码提交。`prepare.py` 会读取这些材料核验来源。按本机位置调整 `fm/common.py` 中的 `OLD`。
3. 在新项目创建 Python 3.10 环境并安装 `requirements.lock.txt`。本机已有 `.venv` 不上传。
4. 运行 README 中的数据准备、检查、训练及推理命令，产物保存在本地。已有结果使用新的 `--run`，避免覆盖。
5. `finalize.py` 是本轮本地报告汇总器，还需要本地人工/目录审计记录 `reports/file_inventory.json`、`reports/label_inventory.json`、`reports/visual_review.json` 等，以及检查、评价和 CLI 验证结果；源码副本不携带这些材料，不能把完整本地归档等同于可直接运行的报告附件。

来源见 `THIRD_PARTY.md` 和 `references/provenance.json`。保留 `references/official/LICENSE`，延续原工程的非商业研究/评估范围。

## 之后更新源码

在 `test-Liu` 检出目录中更新对应源文件，检查暂存列表后提交：

```powershell
git status --short --branch
git add cfb_gbm_flowmatching_test
git diff --cached --stat
git diff --cached --name-only
git commit -m "Update CFB-GBM Flow Matching source"
git push origin test-Liu
```

`.gitignore` 不会自动取消已被 Git 跟踪的文件，也不会清理远端历史；更新时仍需检查暂存内容。不要强制推送覆盖团队分支。
