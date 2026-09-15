# 小霖学徒 · xiaolin-apprentice

命理师小霖带 AI 徒弟看盘的工作流(Codex / Claude Code skill)。

- 第一阶段(本版):出生时间 + 性别 → 确定性排盘 → 强弱喜忌 v1.0 → 命盘卡片(HTML + PNG)。
- 第二阶段:小霖说「继续」后按他定的维度出判断(七维度、断语纪律见 `SKILL.md` 与 `references/dimensions.md`)。
- 第三阶段:原样收小霖口语反馈 → 逐条对齐(对 / 错 / 漏 + 五类错因)→ 出定版 → 提理法候选问小霖 → 归档。

## 自进化机制

看一个盘,沉淀一次;下一次做题前把沉淀翻一遍。每次定版后从小霖的纠正里提炼理法候选,当面问他「对不对、边界是不是这样」,**他确认过的**才用 `scripts/notebook.py` 追加进 `references/lifa-notebook.md`(追加式、只增不删,要改就写「修订」条目);第二阶段推断前把这本笔记整本读入,优先级低于卡片事实、高于模型自己的取象,用到哪条就在推导末尾标「(笔记 L003)」。
不打分、不出命中率、不做规则升降级或回放门禁 —— 机制就是一本笔记本。归档由 `scripts/archive.py` 做(校验五件套、分配案例代号、更新 `cases/index.md`、commit + push)。

安装:`git clone https://github.com/RussGuo/xiaolin-apprentice ~/.agents/skills/xiaolin-apprentice`(完整克隆,不要 sparse),`pip3 install "lunar_python>=1.4,<2"`。目录里若缺 `scripts/`,执行 `git sparse-checkout disable && git checkout -- .`。

排盘脚本 `scripts/paipan.py` 来自 [guosanguan](https://github.com/RussGuo/guosanguan)(MIT);喜忌脚本 `scripts/xiji.py` 实现 FateTell《喜忌判定 · 伪代码 v1.0》,`scripts/test_xiji.py` 为其 13 条回归。
