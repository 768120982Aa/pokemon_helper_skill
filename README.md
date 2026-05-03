# Pokémon 综合助手

一个零外部依赖的宝可梦对战辅助技能包，专为大模型（LLM）设计。

只需 Python 3 标准库，无需安装任何第三方包。

## 文件结构

```
pokemon_helper_skill/
│
├── SKILL.md                ← 技能文档（LLM 读这个）
├── calc_damage.py          ← 伤害计算引擎（6个函数）
├── pokemon.db              ← 数据库（SQLite）
├── rulesets.json           ← 对战规则集数据
│
├── pokemon_formulas_champions.md  公式说明（参考）
└── pokemon_formulas_gen9.md       公式说明（参考）
```

## 能力概述

本技能可以帮 LLM 完成：

- **查数据** — 宝可梦种族值、属性、特性、招式分类标签
- **算伤害** — Champions SP / 朱紫 Gen9 两种环境
- **查相克** — 双属性弱点抗性、特性修正
- **配队伍** — 联防分析、打击面、速度线
- **查规则** — 当前主流对战规则集

## 对外接口

```python
from calc_damage import (
    calc_champions_stats,   # Champions SP 能力值
    calc_gen9_stats,        # 朱紫/Gen9 能力值
    calc_damage,            # 完整伤害计算（核心）
    calc_damage_raw,        # 纯数值计算
    list_rulesets,          # 列出规则集
    get_ruleset,            # 查规则集详情
)
```

## 依赖

**零。** `calc_damage.py` 只用了 Python 3 标准库：

- `sqlite3` — 数据库查询
- `json` — 规则集读取
- `math` — 数学运算
- `os` — 路径处理

数据库使用 SQLite 格式，无需安装 MySQL 或其他数据库服务。

## 数据来源

- 宝可梦数据基于 [42arch/pokemon-dataset-zh](https://github.com/42arch/pokemon-dataset-zh)
- 招式分类标签（锋锐/铁拳/强行判定）抽取自 [smogon/damage-calc](https://github.com/smogon/damage-calc)
- 对战规则集参考 Pokémon Champions 和 VGC 官方规则
- 招式/道具/特性数据覆盖至 **Gen 9**

## 使用方式

本技能面向 **大模型使用**，详细用法请 LLM 阅读 `SKILL.md`。

基本工作流：

```
SQL 查数据 → 手动推理特性修正 → Python 调用 calc_damage → 解读结果
```

LLM 通过 SQL 查询数据库获取种族值、招式标签、特性效果，自行计算特性/道具修正后，调用 `calc_damage()` 得出伤害范围和击杀判定。

## 常见问题

**Q: 需要安装 MySQL 吗？**
A: 不需要。数据库是 SQLite 格式，Python 内置支持。

**Q: 需要安装第三方 Python 包吗？**
A: 不需要。所有依赖都在 Python 3 标准库中。

**Q: 数据库有多新？**
A: 覆盖至第九世代（朱紫），包含全部 1025 只宝可梦、935 个招式、307 个特性。

**Q: 特性数据全吗？**
A: `ability_effects` 表收录了 163 个影响伤害计算的特性，含倍率、触发条件和关联招式标签。不在表中的特性请查阅 `abilities` 表的效果原文自行判断。

---

*版本：v2.1*
