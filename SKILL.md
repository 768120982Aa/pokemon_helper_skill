# Pokémon 综合助手 — 技能文档

你被加载了一个宝可梦对战辅助技能。以下是你拥有的能力和使用方法。

---

## 你能做什么

1. **查数据** — 宝可梦、招式、特性、道具的基础信息
2. **算伤害** — 调用计算引擎，输出伤害范围和击杀判定
3. **查相克** — 属性攻防抗性、双属性组合的弱点免疫
4. **配队伍** — 联防分析、打击面覆盖、速度线对比
5. **查规则** — 当前主流对战规则集（Champions / VGC）

---

## 快速索引

| 你想 | 怎么做 |
|:----|:------|
| 查某只宝可梦的种族值、属性、特性 | [查宝可梦](#1-查宝可梦) |
| 查某个招式的威力、属性、分类标签 | [查招式](#2-查招式) |
| 查某个特性的效果 | [查特性](#3-查特性) |
| 想知道一个招式是否受某个特性加成 | [特性+招式联动](#4-特性与招式联动) |
| 完整计算一次伤害（SQL → 手动修正 → Python） | [完整计算示例](#5-计算伤害) |
| 只算纯数值（所有修正已处理好） | [纯数值计算](#53-纯数值计算) |
| 查某只宝可梦有哪些弱点抗性 | [属性相克](#6-属性相克) |
| 查当前比赛用什么规则 | [规则集](#7-规则集) |
| 查进化链/蛋招式/学习招式 | [进化与学习](#8-进化与学习) |
| 数据库没有这个数据 | [兜底规则](#9-兜底规则) |

---

## 1. 查宝可梦

```sql
-- 基本信息（图鉴编号、名字）
SELECT * FROM pokemon WHERE name_zh = '艾路雷朵';

-- 形态信息（属性、特性列表）
SELECT form_name, type1, type2, ability1, ability2, hidden_ability
FROM pokemon_forms WHERE pokedex_id = '0475';

-- 种族值（指定形态）
SELECT hp, attack, defense, sp_attack, sp_defense, speed
FROM pokemon_stats WHERE pokedex_id = '0475' AND form = '一般';
```

> **图鉴 ID** 是 4 位文本，如 `'0475'`（艾路雷朵）、`'0006'`（喷火龙）。用 `name_zh` 查也可以。
>
> **多形态处理：**
> 1. 先查 `pokemon_forms` 看有哪些形态：
>    ```sql
>    SELECT form_name FROM pokemon_forms WHERE pokedex_id = '0475';
>    -- → ['艾路雷朵', '超级艾路雷朵']
>    ```
> 2. 不同表对形态的叫法不一致，按此规则映射：
>
>    | 宝可梦形态 | `pokemon_forms.form_name` | `pokemon_stats.form` | `pokemon_type_effectiveness.form` |
>    |:----------|:-------------------------|:--------------------|:--------------------------------|
>    | 一般形态 | '艾路雷朵' | `'一般'` | `''`（空字符串） |
>    | Mega 形态 | '超级艾路雷朵' | `'超级进化'` | `''`（多数情况，查不到时用空串） |
>    | 特殊形态（如喷火龙X/Y） | '超级喷火龙Ｘ' | `'超级喷火龙Ｘ'` | `'超级喷火龙Ｘ'` |
>
>    简单规则：**查种族值时 `form='一般'` 是一般形态，`form='超级进化'` 是 Mega 形态。查属性相克时先用 `form=''`（空字符串），没有结果再试具体形态名。**

---

## 2. 查招式

```sql
SELECT name_zh, type, category, power, accuracy, pp
FROM moves WHERE name_zh = '圣剑';
```

`moves` 表额外包含 9 个 **招式分类标签**（值均为 0 或 1），用于判断特性是否生效：

| 字段 | 含义 | 关联的特性 |
|:----|:----|:----------|
| `makes_contact` | 接触类 | 硬爪(×1.3)、毛茸茸(×0.5) |
| `is_slicing` | 剑/切割类 | **锋锐(×1.5)** |
| `is_punch` | 拳类 | **铁拳(×1.2)** |
| `is_bite` | 咬类 | **强壮之颚(×1.5)** |
| `is_sound` | 声音类 | **庞克摇滚(×1.3)**、隔音(免疫) |
| `is_bullet` | 弹/炸弹类 | 防弹(免疫) |
| `is_pulse` | 波动类 | Mega发射器(×1.5) |
| `is_wind` | 风类 | 冲浪之尾(免疫+攻击提升) |
| `has_secondary` | 有追加效果 | **强行(Sheer Force)(×1.3)** |

```sql
-- 查招式分类标签
SELECT name_zh, type, power, makes_contact, is_slicing, is_punch, has_secondary
FROM moves WHERE name_zh = '圣剑';
-- 结果：makes_contact=1, is_slicing=1 → 可触发锋锐
```

> `power` 字段是文本类型，变化类招式值为 `'—'`，取值时需转换。

---

## 3. 查特性

有两个表可用：

### 3.1 效果原文 — `abilities` 表

全部 307 个特性的中文介绍和效果原文：

```sql
SELECT name_zh, name_en, effect FROM abilities WHERE name_zh = '锋锐';
```

### 3.2 结构化数据 — `ability_effects` 表

163 个**影响伤害计算**的特性，按效果类型分类，含具体的倍率和触发条件：

```sql
SELECT * FROM ability_effects WHERE ability_name = '锋锐';
```

**字段说明：**

| 字段 | 含义 | 示例值 |
|:----|:----|:------|
| `effect_type` | 效果类别 | `move_power` / `stat` / `damage_taken` / `type_immune` / `type_change` / `rule` / `crit_immune` / `none` |
| `target` | 作用目标 | `self_attack`（攻击方自身） / `self_defense`（防御方自身） / `opponent`（对方） |
| `param` | 影响的参数 | `move_power` / `attack` / `defense` / `speed` / `other_mod` / `type_eff` / `screens` |
| `modifier` | 数值倍率 | `1.5`（×1.5倍） / `0.5`（减半） / `0.0`（免疫） |
| `flag_field` | 关联的招式标签 | `is_slicing` / `is_punch` / `makes_contact` / NULL |
| `condition` | 触发条件（文字） | 供你直接阅读 |

**effect_type 分类速查：**

| 类别 | 含义 | 数量 | 你的处理方式 |
|:----|:----|:---:|:-----------|
| `move_power` | 改变招式威力 | 25 | 调用 `calc_damage` 前手动调整 `move_power` 参数 |
| `stat` | 改变能力值 | 40 | 调用前手动调整 `stats` 字典的值 |
| `damage_taken` | 减免受到的伤害 | 20 | 调用前手动调整 `other_mod` 或通过 `items` 参数传入 |
| `type_immune` | 属性免疫 | 14 | 通过 `abilities` 参数传入，函数自动处理 |
| `type_change` | 改变招式属性（皮肤系） | 9 | 调用前手动改 `move_type`，并重新计算 STAB |
| `rule` | 特殊规则 | 23 | 见对应规则说明 |
| `crit_immune` | 暴击免疫 | 2 | 告知用户不会暴击 |
| `none` | 不参与伤害计算 | 30 | 仅告知用户存在此特性 |

> 如果特性不在 `ability_effects` 表中，请查 `abilities` 表读 `effect` 原文，自行判断效果。

---

## 4. 特性与招式联动

判断一个特性是否影响某招式：

```sql
-- 步骤 1：查特性的效果
SELECT effect_type, param, modifier, flag_field, condition
FROM ability_effects WHERE ability_name = '锋锐';
-- → effect_type=move_power, modifier=1.5, flag_field=is_slicing

-- 步骤 2：查招式是否有对应的标签
SELECT name_zh, is_slicing FROM moves WHERE name_zh = '圣剑';
-- → is_slicing=1

-- 结论：锋锐的 flag_field=is_slicing，圣剑的 is_slicing=1 → 锋锐生效，威力 ×1.5
```

---

## 5. 计算伤害

`calc_damage.py` 提供 6 个公开接口：

| 函数 | 用途 |
|:----|:-----|
| `calc_champions_stats()` | Champions SP 能力值计算 |
| `calc_gen9_stats()` | 朱紫/Gen9 努力值能力值计算 |
| `calc_damage()` | **完整伤害计算**（核心函数） |
| `calc_damage_raw()` | 纯数值伤害计算（不查数据库） |
| `list_rulesets()` | 列出所有规则集 |
| `get_ruleset()` | 查某个规则集详情 |

**重要原则：** `calc_damage()` 是纯计算引擎，只处理：
- 天气/场地/灼伤/墙壁等场况
- 属性相克（含胆量、飘浮等影响 type_eff 的特性）
- 道具（属性增强×1.2、讲究系列×1.5、命玉×1.3、达人带）

**所有其他特性修正**（锋锐×1.5、大力士攻×2、厚脂肪×0.5 等）必须由你在调用前自行处理，通过调整 `move_power`、`attacker_stats`、`other_mod` 等参数传入。

### 5.1 完整计算流程（标准工作流）

以「极攻锋锐艾路雷朵 圣剑 vs 满HP Mega巨金怪」为例：

```
第 1 步 [SQL] → 查宝可梦数据和种族值
第 2 步 [SQL] → 查招式基础威力和分类标签
第 3 步 [SQL] → 查特性效果（锋锐的倍率和 flag）
第 4 步 [手动] → 推理：标签匹配→修正参数
第 5 步 [Python] → 计算能力值
第 6 步 [Python] → 计算伤害
第 7 步 [手动] → 解读结果
```

**第 1-3 步：SQL 查数据**

```sql
-- 查艾路雷朵
SELECT hp, attack, defense, sp_attack, sp_defense, speed
FROM pokemon_stats WHERE pokedex_id='0475' AND form='一般';
-- → 68/125/65/65/115/80

-- 查圣剑标签
SELECT is_slicing FROM moves WHERE name_zh='圣剑';
-- → 1（剑类，可触发锋锐）

-- 查圣剑基础威力
SELECT power FROM moves WHERE name_zh='圣剑';
-- → 90

-- 查锋锐效果
SELECT effect_type, modifier, flag_field FROM ability_effects WHERE ability_name='锋锐';
-- → move_power, 1.5, is_slicing
```

**第 4 步：手动推理修正**

```
圣剑.is_slicing(1) == 锋锐.flag_field(is_slicing) → 匹配
→ move_power = 90 × 1.5 = 135
```

**第 5-6 步：Python 计算**

```python
from calc_damage import calc_champions_stats, calc_damage

# 攻击方能力值
atk = calc_champions_stats('0475', sps={'attack':32}, nature='固执', form='一般')

# 防御方能力值
def_ = calc_champions_stats('0376', sps={'hp':32}, nature='认真', form='超级进化')

# 计算伤害（已手动修正 move_power=135）
result = calc_damage(
    atk, def_,
    move_power=135,           # 已含锋锐修正
    move_category='物理',
    attacker_types=['超能力','格斗'],
    defender_types=['钢','超能力'],
    move_type='格斗',
)
```

**第 7 步：解读结果**

```python
hp = def_['hp']  # 187
print(result['min'], '~', result['max'])  # 87 ~ 103

if result['min'] >= hp:
    print('确一 (OHKO)')
elif result['max'] >= hp:
    pct = sum(1 for d in result['rolls'] if d >= hp) / 16 * 100
    print(f'乱一 ({pct:.0f}%)')
else:
    hits = (hp + result['max'] - 1) // result['max']
    two_pct = sum(1 for a in result['rolls'] for b in result['rolls']
                  if a + b >= hp) / 256 * 100
    print(f'需要 {hits} 次击杀, 2次率={two_pct:.0f}%')
```

### 5.2 朱紫/Gen9 能力值计算

只在用户明确提到「朱紫」「努力值」「Gen9」时使用。流程与 5.1 相同，只是能力值计算函数换为 `calc_gen9_stats`：

```python
from calc_damage import calc_gen9_stats, calc_damage

atk = calc_gen9_stats('0006', level=50,
    evs={'sp_attack':252, 'speed':252},
    nature='内敛', form='一般')

def_ = calc_gen9_stats('0001', level=50,
    evs={'hp':252, 'sp_defense':252},
    nature='慎重', form='一般')

result = calc_damage(atk, def_, move_power=90, move_category='特殊',
    attacker_types=['火','飞行'], defender_types=['草','毒'],
    move_type='火',
    weather='sun')  # 晴天火系×1.5
```

> **能力值公式（Lv.50, IV=31）：**
> - HP = (种族值×2 + 31 + EV÷4) × 50÷100 + 50 + 10
> - 其他 = ((种族值×2 + 31 + EV÷4) × 50÷100 + 5) × 性格修正（向下取整）

### 5.3 纯数值计算

当所有修正已在外部处理好，只需要算裸伤害时：

```python
from calc_damage import calc_damage_raw

result = calc_damage_raw(
    level=50,
    attack=194,           # 最终攻击值
    defense=170,          # 最终防御值
    move_power=135,       # 最终威力（含特性/道具修正）
    stab=1.5,
    type_effectiveness=1.0,
    other_mod=1.0,        # 含天气/场地/道具/减伤特性等所有修正
    is_critical=False,
)
```

### 5.4 Champions SP 分配参考

| 称呼 | SP 分配 | 性格 |
|:----|:--------|:----|
| 极攻 | Atk/SpA=32 | +攻性格（固执/内敛） |
| 极速 | Spd=32 | +速性格（爽朗/胆小） |
| 满HP | HP=32 | 不限 |
| 极限物耐 | HP=32, Def=32 | +防性格 |
| 极限特耐 | HP=32, SpD=32 | +特防性格 |
| 无速 | 不加速度 | 减速性格 |

> **SP 公式（Lv.50）：** HP = 种族值 + SP_hp + 75；其他 = (种族值 + SP_stat + 20) × 性格修正（向下取整）

### 5.5 特性处理顺序参考

调用 `calc_damage` 前，需自行按此顺序修正参数：

```
第 0 层：规则层（最先判断）
  破格/涡轮火焰/兆级电压 → 防御方特性不生效
  化学变化气体 → 双方特性不生效
  纯朴 → 无视双方能力变化

第 1 层：能力值层（改 stats 字典）
  大力士 → atk_stats['attack'] *= 2
  威吓 → def_stats['attack'] = int(def_stats['attack'] * 0.67)
  灾祸系列 → 全场能力×0.75
  不挠之剑 → atk_stats['attack'] = int(atk_stats['attack'] * 1.5)

第 2 层：招式威力层（改 move_power）
  锋锐 → 查 moves.is_slicing → move_power = int(move_power * 1.5)
  铁拳 → 查 moves.is_punch → move_power = int(move_power * 1.2)
  皮肤系 → 改 move_type + move_power = int(move_power * 1.2)

第 3 层：减伤层（改 other_mod）
  厚脂肪 → other_mod *= 0.5（火/冰）
  多重鳞片 → other_mod *= 0.5（满血时）
  毛皮大衣 → other_mod *= 0.5（物理招式）

第 4 层：type_eff 修正（通过 abilities 参数传入 calc_damage）
  飘浮 → calc_damage(..., abilities={'defender':'飘浮'})
  胆量 → calc_damage(..., abilities={'attacker':'胆量'})
  引火 → calc_damage(..., abilities={'defender':'引火'})
```

---

## 6. 属性相克

`pokemon_type_effectiveness` 表已将双属性合并计算好：

```sql
-- 查 Mega 巨金怪（钢+超能）的弱点/抗性
SELECT defending_type, multiplier
FROM pokemon_type_effectiveness
WHERE pokedex_id = '0376' AND form = '超级进化'
ORDER BY multiplier;
```

| multiplier | 含义 |
|:---------:|:-----|
| 0 | 免疫 |
| 0.25 | 四倍抗 |
| 0.5 | 二倍抗 |
| 1.0 | 普通 |
| 2.0 | 二倍弱 |
| 4.0 | 四倍弱 |

> 注意：特性可能额外修正相克——飘浮(地面免疫)、引火(火免疫)、胆量(可打幽灵)。这些通过 `calc_damage` 的 `abilities` 参数自动处理。

---

## 7. 规则集

```python
from calc_damage import list_rulesets, get_ruleset

print(list_rulesets())      # 列出所有规则集
rs = get_ruleset('champions_reg_m_a')  # 查特定规则集
```

当前主流规则集：

| 规则集 | 游戏 | 时期 | 特点 |
|:------|:----|:----|:-----|
| `champions_reg_m_a` | 宝可梦冠军 | 2026.4-2026.6 | 允许Mega，禁止传说/悖谬 |
| `sv_regulation_g` | 朱紫 | 2025.4- | 允许1只传说 |
| `sv_regulation_h` | 朱紫 | 2024.9-2025.1 | 限制最大 |

> 未指定时默认 Champions。用户提到「朱紫」「VGC」时切到朱紫规则集。

---

## 8. 进化与学习

```sql
-- 进化链
SELECT * FROM pokemon_evolution_chains WHERE pokedex_id = '0475' ORDER BY chain_index;

-- 蛋招式
SELECT move_name, parent_ids FROM pokemon_egg_moves WHERE pokedex_id = '0475';

-- 升级学习
SELECT level, move_name, type, category, power
FROM pokemon_learnable_moves WHERE pokedex_id = '0475' AND form = '一般'
ORDER BY CAST(level AS INTEGER);

-- 招式学习器
SELECT machine, move_name, type, category, power
FROM pokemon_machine_moves WHERE pokedex_id = '0475' AND form = '一般';
```

---

## 9. 兜底规则

| 情况 | 处理方式 |
|:----|:--------|
| 宝可梦名不存在 | 提示未找到，给出相近名称建议 |
| 招式名不存在 | 同上 |
| 形态不存在 | 列出该宝可梦所有已知形态让用户确认 |
| 特性不在 `ability_effects` 表 | 查 `abilities` 表读 `effect` 原文，自行判断 |
| 数据未收录（如新世代） | 提示当前数据库仅收录至 Gen 9 |
| 排位使用率相关 | 告知当前数据库不包含排位数据 |
| **查不到就是查不到** | **绝对不要编造数据** |

---

## 附录：数据库结构

```
pokemon.db（SQLite）

pokemon                     宝可梦 ID、中英文名
pokemon_forms               形态、属性、特性列表、身高体重
pokemon_stats               种族值（六维，区分形态）
pokemon_type_effectiveness  属性相克倍率（已合并双属性）
moves                       招式信息（含9个分类标签字段）
abilities                   特性效果原文（307条）
ability_effects             特性结构化数据（163条，影响伤害计算的）
items                       道具信息
pokemon_evolution_chains    进化链
pokemon_egg_moves           蛋招式
pokemon_learnable_moves     升级学习招式
pokemon_machine_moves       招式学习器
ruleset_pokemon             规则集禁用列表
```

---

## 附录：calc_damage.py 对外接口

```python
from calc_damage import (
    calc_champions_stats,   # Champions SP 能力值
    calc_gen9_stats,        # 朱紫/Gen9 能力值
    calc_damage,            # 完整伤害计算（核心）
    calc_damage_raw,        # 纯数值伤害计算
    list_rulesets,          # 列出规则集
    get_ruleset,            # 查规则集详情
)
```

---

*版本：v2.1 | 最后更新：2026-05-03*
