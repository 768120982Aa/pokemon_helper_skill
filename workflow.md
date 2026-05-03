# 宝可梦伤害计算工作流 v2.1

> 适用：Pokémon Champions  
> 核心原则：**先查再判断，不从文档死记**

---

## 调用入口

```python
from calc_damage import calc_damage_raw, calc_champions_stats

result = calc_damage_raw(
    level=50,                    # 固定 Lv.50
    attack=actual_atk,           # 最终攻击/特攻（含性格、能力变化、道具/特性对能力的修正）
    defense=actual_def,          # 最终防御/特防
    move_power=final_power,      # 招式威力（含技术高手、属性增强道具等对威力的修正）
    stab=1.5,                    # STAB
    type_effectiveness=2.0,      # 属性相克（查表）
    other_mod=1.0,               # 剩余倍率乘积
    is_critical=False,           # 击中要害
)
```

---

## 步骤 1：获取双方信息

```sql
-- 先查有哪些形态
SELECT pf.form_name, pf.type1, pf.type2, 
       pf.ability1, pf.ability2, pf.hidden_ability,
       ps.form, ps.hp, ps.attack, ps.defense, 
       ps.sp_attack, ps.sp_defense, ps.speed
FROM pokemon_forms pf
JOIN pokemon_stats ps ON pf.pokedex_id = ps.pokedex_id
WHERE pf.pokedex_id = '{pid}'

-- 然后选正确的 (form_name, ps.form) 配对
-- ps.form 已归一化：'一般' / '洗翠' / '阿罗拉' / '超级进化' / '超级喷火龙Ｙ' …
```

---

## 步骤 2：计算能力值

```
HP     = 种族値 + SP_hp   + 75
其他    = (种族値 + SP_stat + 20) × 性格修正（向下取整）
```

| SP 名 | 分配 | 等效朱紫 |
|--------|------|---------|
| 极攻 | Atk=32 + 攻击性格(1.1) | 252Atk + 固执 |
| 满攻 | Atk=32 + 不减攻击性格 | 252Atk |
| 极速 | Spd=32 + 速度性格(1.1) | 252Spd + 爽朗 |
| 无速 | Spd=0 | 0Spd |
| 满HP | HP=32 | 252HP |

---

## 步骤 3：获取招式

```sql
SELECT name_zh, type, category, power FROM moves WHERE name_zh = '{move}'
```

---

## 步骤 4：查双方特性 → 判断对伤害的影响

```sql
-- 攻击方特性
SELECT ability1, ability2, hidden_ability FROM pokemon_forms
WHERE pokedex_id = '{atk_pid}' AND form_name LIKE '%目标形态%'

-- 防守方特性（同理）
```

拿到特性名后，查效果文本：
```sql
SELECT introduction, effect FROM abilities WHERE name_zh = '{ability}'
```

### 常见特性分类（帮助判断，非穷尽）

**直接改招式威力（乘在 move_power）：**
技术高手（≤60威力 ×1.5）、铁拳（拳类 ×1.2）、强行（有追加效果 ×1.3）、狙击手（会心伤害再 ×1.5）

**改能力值（乘在实际 atk/def 上）：**
大力士/瑜伽之力（攻击 ×2.0）、毅力（烧伤时攻击 ×1.5 且无视烧伤减半）

**改倍率（乘在 other_mod）：**
厚脂肪（受火/冰 ×0.5）、坚硬岩石/过滤（效果绝佳 ×0.75）、多重鳞片/幻影防守（满血 ×0.5）、冰鳞粉（特殊 ×0.5）、友情防守（队友在场 ×0.75）、毛茸茸（近身 ×0.5 但火 ×2）

**改变属性相克（乘在 type_effectiveness 或在查表时特殊处理）：**
飘浮（地面 ×0）、干燥皮肤（水×0 回血/火×1.25）、蓄电/避雷针/电气引擎（电 ×0）、引火（火 ×0 提升威力）、胆量（一般/格斗可打幽灵）

> 原则：先查宝可梦有哪些特性，再用上面分类判断是否需要调整数值。如果效果文本是「受到 XX 属性伤害减半」→ other_mod，「攻击变为 2 倍」→ 能力值，「威力提高」→ move_power。

---

## 步骤 5：确认道具 → 分类处理

道具分两类：改威力 vs 改倍率。

### 判断方法

```sql
SELECT name_zh, description FROM items WHERE name_zh = '{item}'
```

看 description 文本判断：
- "XX属性招式威力提高" → **move_power ×1.2**
- "携带后招式威力变为 X 倍" → **move_power ×X**
- "攻击/特攻变为 X 倍" → **能力值 ×X**
- 其余情况（生命宝珠/达人带等）→ **other_mod ×X**

### 注意陷阱

- 木炭只加**火**属性招式威力，对非火招式无效
- 神秘水滴只加**水**属性，其他属性增强道具同理
- 属性宝石（一次性）→ ×1.3，也是威力类
- 讲究头带/眼镜 → ×1.5 作用在**攻击/特攻值**，不是招式威力也不是 other_mod

---

## 步骤 6：能力变化

直接乘实际能力值，不参与 other_mod：

| 阶段 | +6 | +4 | +2 | +1 | 0 | -1 | -2 | -4 | -6 |
|------|----|----|----|----|---|----|----|----|----|
| 倍率 | 4.0 | 3.0 | 2.0 | 1.5 | 1.0 | 0.67 | 0.5 | 0.33 | 0.25 |

```python
atk_final = int(atk_base * boost_mult)
```

---

## 步骤 7：属性相克

```sql
-- 先看 type_effectiveness 表里该形态有哪些 form 名
SELECT DISTINCT form FROM pokemon_type_effectiveness 
WHERE pokedex_id = '{defender_pid}'

-- 用匹配的 form 查倍率
SELECT multiplier FROM pokemon_type_effectiveness 
WHERE pokedex_id = '{defender_pid}' 
  AND form = '{form}'          -- 必须指定形态
  AND defending_type = '{move_type}'
```

> 表单已归一化，不再有"的样子"后缀。部分形态带能力后缀如"洗翠(引火)"，匹配时注意。

---

## 步骤 8：STAB

| 条件 | 倍率 |
|------|------|
| 招式属性 ∈ 攻击方属性 | ×1.5 |
| 否则 | ×1.0 |

---

## 步骤 9：汇总 other_mod

从以下来源逐项检查并连乘：

| 来源 | 条件 | 倍率 |
|------|------|------|
| 大晴天 | 火招式 | ×1.5 |
| 大晴天 | 水招式 | ×0.5 |
| 下雨 | 水招式 | ×1.5 |
| 下雨 | 火招式 | ×0.5 |
| 电气场地 | 地面上的 PM 用电招式 | ×1.3 |
| 青草场地 | 地面上的 PM 用草招式 | ×1.3 |
| 精神场地 | 地面上的 PM 用超能招式 | ×1.3 |
| 薄雾场地 | 龙招式 | ×0.5 |
| 攻击方灼伤 | 物理招式（非毅力特性）| ×0.5 |
| 反射壁/光墙/极光幕 | 单打 | ×0.5 |
| 反射壁/光墙/极光幕 | 双打 | ×2⁄3 |
| 帮助 | — | ×1.5 |
| 多目标 | 攻击目标 ≥2 | ×0.75 |
| 生命宝珠 | 携带 | ×1.3 |
| 达人带 | 属性效果绝佳 | ×1.2 |
| 特性影响 | 从步骤 4 的倍率类特性汇总 | — |

```python
other_mod = 1.0
for factor in [weather, terrain, burn, screens, help, multi_target, 
               item_other, ability_other1, ability_other2]:
    if factor:
        other_mod *= factor
```

---

## 步骤 10：调用 + 判定

```python
result = calc_damage_raw(level=50, attack=atk, defense=df,
    move_power=pwr, stab=stab, type_effectiveness=type_eff, other_mod=other)

if result['min'] >= target_hp:
    print("确一 ✓")
elif result['max'] >= target_hp:
    print(f"乱一 ({sum(d>=target_hp for d in result['rolls'])/16*100:.0f}%)")
else:
    print(f"需 {(target_hp+result['max']-1)//result['max']} 次")
```

---

## 完整示例

### Mega巨钳螳螂 满攻 子弹拳 → 洗翠风速狗（无HP）

```
步骤1: 巨钳螳螂 forms='巨钳螳螂', ps.form='超级进化' → Atk=150
      风速狗 ps.form='洗翠' → HP=95, Def=80

步骤2: 满攻 202, HP=170, Def=100

步骤3: 子弹拳 钢/物理 威力40

步骤4: 查询特性 → 巨钳螳螂 ability1='技术高手' → 查效果: "威力≤60的招式×1.5"
      → move_power=40→60（威力类）

步骤5: 无道具

步骤6: 无能力变化

步骤7: type_eff 查表: form='洗翠' 钢 → ×1.0

步骤8: STAB: 虫+钢 → 钢=×1.5

步骤9: other_mod=1.0

步骤10: calc_damage_raw(50,202,100,60,1.5,1.0,1.0) → 69~82, 3次击杀
```
