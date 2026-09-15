# 小霖学徒 · xiaolin-apprentice

命理师小霖带 AI 徒弟看盘的工作流(Codex / Claude Code skill)。

- 第一阶段(本版):出生时间 + 性别 → 确定性排盘 → 强弱喜忌 v1.0 → 命盘卡片(HTML + PNG)。
- 第二阶段:小霖说「继续」后按他定的维度出判断(待建)。
- 第三阶段:收小霖口语反馈,出定版,归档(待建)。

安装:`git clone https://github.com/RussGuo/xiaolin-apprentice ~/.agents/skills/xiaolin-apprentice`(完整克隆,不要 sparse),`pip3 install "lunar_python>=1.4,<2"`。目录里若缺 `scripts/`,执行 `git sparse-checkout disable && git checkout -- .`。

排盘脚本 `scripts/paipan.py` 来自 [guosanguan](https://github.com/RussGuo/guosanguan)(MIT);喜忌脚本 `scripts/xiji.py` 实现 FateTell《喜忌判定 · 伪代码 v1.0》,`scripts/test_xiji.py` 为其 13 条回归。
