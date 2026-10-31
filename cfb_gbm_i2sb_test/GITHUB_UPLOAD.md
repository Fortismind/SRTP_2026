# 上传源码并创建分支

当前项目默认只上传源码、配置、固定患者划分 `data/splits.json` 和来源记录/许可证。MRI、缓存、权重、日志、患者清单和本地报告不纳入 Git。这些忽略规则不会删除本地文件。

GitHub 上的源码仓库不等于整个本地实验归档。README 和运行脚本提到的缓存、权重、报告需要在取得原始数据后本地生成；本地环境通过 `.pth` 复用现有 PyTorch，其他计算机需要按 requirements 或 README 重新配置，不能复制本机 `.venv`。固定划分只有匿名患者编号，不含影像路径或治疗字段；若不准备共享编号，可进一步排除该文件，但会影响精确复现实验划分。

保留 `THIRD_PARTY.md`、`references/provenance.json` 和 `references/official/LICENSE`。原始数据是否能另行分享，应遵循数据提供方条件；导出脚本不包含原始数据和病例图。

以下 URL、目录和分支名都是示例，请替换为实际值。执行前应已安装 Git，并能登录自己的 GitHub 账号；不要把 token 写入脚本或 remote URL。

## 情况一：已有仓库，包括已经有 README 的仓库

先克隆，创建分支，再把本项目源码放进一个新子目录，避免与仓库根目录已有文件冲突。以下命令从远端默认分支开始：

```powershell
cd D:\ai
git clone https://github.com/YOUR_NAME/YOUR_REPO.git cfb_gbm_repo
cd D:\ai\cfb_gbm_repo
git switch -c feature/cfb-gbm-i2sb

& 'D:\ai\cfb_gbm_i2sb_test\.venv\Scripts\python.exe' `
  'D:\ai\cfb_gbm_i2sb_test\export_source.py' `
  --output 'D:\ai\cfb_gbm_repo\cfb_gbm_i2sb_test'

git add cfb_gbm_i2sb_test
git diff --cached --stat
git status --short
# 核对暂存内容，确认没有数据、权重和本地记录，再提交与推送
git commit -m "Add CFB-GBM I2SB research prototype"
git push -u origin feature/cfb-gbm-i2sb
```

`export_source.py` 只允许导出到不存在的新目录，不覆盖已有代码，不执行 Git 提交或网络操作。先加 `--dry-run` 可以只列清单。

若仓库已克隆，先进入那个本地仓库再建分支，不要重复克隆覆盖同名目录。若要从团队指定的非默认分支开始，先切换到该分支，再运行 `git switch -c`。分支若已存在，用 `git switch 分支名` 继续，不用 `-c` 重建。目标目录如果已经包含同名项目，需按实际情况更新，不能再直接使用仅支持新目录的导出脚本。

## 情况二：新建的完全空仓库

在 GitHub 创建空仓库时，不预先添加 README、gitignore 或许可证。然后可以直接在当前项目初始化：

```powershell
cd D:\ai\cfb_gbm_i2sb_test
git init -b main
git add .
git diff --cached --stat
git status --short
git commit -m "Initial CFB-GBM I2SB prototype"

git remote add origin https://github.com/YOUR_NAME/YOUR_REPO.git
git push -u origin main

git switch -c feature/cfb-gbm-i2sb
git push -u origin feature/cfb-gbm-i2sb
```

这会建立 main 基线，再创建并上传一个起初内容相同的新分支。之后的修改在新分支提交。如果仓库根本没有 main，只想上传一个初始分支，也可 `git init -b feature/cfb-gbm-i2sb`，提交后直接推送该分支；但这不会同时建立 main。

远端已有提交时应使用情况一，不使用强制推送或拼接不相关历史来覆盖远端。

## 日常提交

```powershell
git status
git add 具体修改的文件
git diff --cached
git commit -m "Describe the change"
git push
```

分支名可自己选择，`feature/cfb-gbm-i2sb` 只是示例；`-u` 设置本地分支对应的远端分支，后续可以直接 `git push`。GitHub 上推送分支不会自动把它合并进 main；如需团队审阅，再创建 Pull Request。

如果 Git 提示缺少提交者信息，在当前仓库设置 `git config user.name "你的名字"` 与 `git config user.email "你的邮箱或 GitHub noreply 邮箱"`，不必改变其他项目的全局配置。

`.gitignore` 只阻止尚未跟踪的文件加入 Git；已提交过的数据不会因增加忽略规则自动从历史消失。当前项目在本次检查时尚未初始化 Git，因此现在补好规则再首次提交即可。
