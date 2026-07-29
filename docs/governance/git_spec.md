---
author: e3mydu1f
version:
date modified: July 28th 2026, 1:43 pm
date created: July 28th 2026, 12:59 pm
---
## Git 协作开发流模式
本项目采取 <span style="color:#000; background:#fff59d; font-weight:bold;">主干开发</span>的模式
>主干开发（Trunk-Based Development，简称 TBD）：
>是一种 Git 协作工作流，其核心思想是：所有开发人员围绕唯一的「**主干分支**」（通常命名为 main / trunk）进行协作，所有功能、修复都通过短生命周期的临时分支开发，完成后立即合并回主干，保证主干始终处于可发布、可稳定运行的状态。

在项目中`main`分支作为稳定版本分支，每个功能开发/重构临时建立分支。
## commit 前格式化检查办法
在commit前需要先对整个项目进行**代码格式化检查**，尽可能避免格式不规范的代码被提交到仓库。
使用命令 `uv run ruff check <相对路径>`即可检查代码格式是否符合规范。（相对路径写 . 表示当前整个项目目录）
修复建议采用AI方案，由于ruff目前还不能接入AI,所以采用的方案是 `提示词模板+可视化变动和允许回退的IDE 进行修复`。

## commit message 规范
本项目采用<span style="color:#000; background:#fff59d; font-weight:bold;">Conventional Commits</span>
>Conventional Commits（约定式提交）是一套轻量级的 Git 提交信息规范，它为提交消息定义了统一的结构化格式，让提交历史具备**可读性、可追溯性、可自动化处理**的特性。该规范脱胎于 Angular 团队的提交准则，现已成为业界广泛采用的通用标准，官方定义站点为 [conventionalcommits.org](https://www.conventionalcommits.org)
本地提交严格遵循Conventional Commits规范。
如果在**uv环境终端执行**，提交时会自动检查commit message格式是否符合规范。
P.S.这里是因为配置了 `git/hooks/commit-msg` 钩子。

## Squash Merge 规范
分支合并到主干时采用压缩合并Squash Merge的方式，合并的信息采取 `pull request title and commit detail`规范。
示例：
Chore/init alembic migration (#2)
* chore: initialize alembic migration framework

* chore: add sqlalchemy base model and session

* fix: repair the import name storeage to storage in alembic/env.py

* docs: add alembic migration workflow guidelines

P.S.合并信息主流网站可以**自动生成**，无需手动编写。
但信息格式需要**特殊配置**，例如在 GitHub 需要在仓库的settings的Pull Request的Allow squash merging中
修改Default commit message为 **Pull request title and commit details**


## Git 开发全流程规范
> 所有操作均需要在uv环境终端执行。类似终端显示
>`(ipo-know) PS C:\Users\#425c37e5\Desktop\ipo-know>`

1. 新功能开发/重构/其他工作临时建立分支。
分支命名需要按照 conventional commits 规范。类似 `feat/新功能` 或 `fix/修复xx` 等。(最好用全英文)
分支内可以有多个提交，每个提交都需要符合 conventional commits 规范。

2. 开发完成后，对分支的所有提交进行格式化检查，有问题作为一个提交进行修复。具体方法参照 `## commit 前格式化检查办法` 。

2. 开发+格式化检查修复提交完成后，将分支推送到云端仓库。发起Pull Request(PR)。
合并时使用压缩合并的方式，合并的信息采取上面 `## Squash Merge规范` 。
P.S.如果多人合作开发，可以早些推送到云端仓库，但开发最后完成前必须对代码进行格式化检查和修复。

3. 在云端仓库网站(如 GitHub、GitLab 等)上操作，合并分支到主干。
- 如果你不是管理员，可以联系管理员进行合并。
- 或者开发组交接情况下，可以联系之前的管理员给当前开发组的管理员添加合并权限。

4. 清理本地临时分支。建议使用安全模式删除，避免误删。使用命令 `git branch -d <分支名>`。
P.S. git branch -D <分支名> 会强制删除分支，不提示确认。

流程具体命令演示：
在uv环境终端：
1. 有新业务需求，新建分支。
`git switch -c feat/<new-feature-name>`
2. 然后期间，开发人员在分支上进行开发。
`git add <relative-path>`
`git commit -m "feat: new feature"`
3. 开发完成后，对分支的所有提交进行格式化检查，有格式问题作为一个提交进行修复。具体方法参照 `## commit 前格式化检查办法` 。
`uv run ruff check .`
4. 开发+格式化检查修复提交完成后，将分支推送到云端仓库。发起Pull Request(PR)。
`git push -u origin feat/<new-feature-name>`
P.S.这里名字和分支名最好一致，方便后续操作。
5. 在云端仓库网站(如 GitHub、GitLab 等)上发起合并分支的Pull Request(PR)。
管理员审核通过后，合并分支到主干。PR关闭。
6. 清理本地临时分支。切换到主干分支，拉取最新代码。
`git switch main`
`git pull`
7. 删除本地临时分支。
使用命令 `git branch -d feat/<new-feature-name>`。
