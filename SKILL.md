# Pokémon 综合助手 — Skill 文档

> 版本：v1.1  
> 适用范围：所有宝可梦相关查询、计算、数据维护  
> 默认环境：**Pokémon Champions（SP 系统）**，朱紫/Gen9 为第二优先级  
> 关键词触发：宝可梦、PM、Pokémon、冠军、Champions、对战、VGC、Gen9、朱紫  

---

---

## 📖 快速索引

### 这个 skill 能干什么

| 你想…… | 去这里 |
|--------|--------|
| 查一只宝可梦的属性、特性、种族值 | 第一章 1.1 |
| 算极攻喷火龙打极限特耐快龙能打多少 | 第二章 2.1（Champions）/ 2.2（朱紫） |
| 看某个特性对伤害有没有影响、怎么处理 | **第三章（对伤害计算很重要！）** |
| 算钢+妖精有多少抗性和弱点 | 第四章 4.2 |
| 查一个招式/道具/特性的具体数据 | 第五章 5.1 / 5.2 / 5.3 |
| 问当前对战用什么规则 | 第六章 6.3 |
| 分析队伍的联防和打击面有没有漏洞 | 第七章 7.1 / 7.2 |
| 想知道两个宝可梦谁快 | 第九章 9.1 |
| 查进化链/蛋招式/可学招式 | 第九章 9.2 |
| 告诉我「游戏更新了，更新数据库」 | 第八章 8.2 |
| 数据库里没有这个数据 | 第十章 10.2 兜底规则 |

### 重要提示

- 🥇 **默认 Champions。** 所有计算优先用 SP 系统。只有你明确说「朱紫」「努力值」「Gen9」我才切过去。
- 😠 **特性一定要查第三章。** 不要凭印象处理特性——每个特性的 effect 文本都要读，确定它影响哪个参数（能力值/威力/倍率/相克），再对应调整公式。
- 🤚 **不编造数据。** 数据库没有的就是没有，不会假装知道。

---

## 核心原则

1. **默认 Champions，除非用户明确说朱紫。** 计算能力值用 `calc_champions_stats()`，SP 分配用 SP 表，规则集优先查 `champions_reg_m_a`。
2. **能用脚本调用的，不手算。** `calc_damage.py` 里有的函数优先用。
3. **能用 SQL 查的，不猜。** 数据库里有的数据不要凭记忆回答。
4. **查不到就说查不到。** 不编造种族值、招式威力、特性效果。
5. **多形态优先匹配。** 查询时始终指定 `form`，默认取 `'一般'` 或第一条记录。

---

## 一、能力值相关

### 1.1 查询宝可梦基本信息（两环境通用）

```sql
-- 基本信息（名称、图鉴编号）
SELECT * FROM pokemon WHERE name_zh = '{name}' OR pokedex_id = '{id}';

-- 形态信息（属性、特性列表）
SELECT form_name, type1, type2, ability1, ability2, hidden_ability
FROM pokemon_forms WHERE pokedex_id = '{pid}';

-- 种族值（指定形态）
SELECT hp, attack, defense, sp_attack, sp_defense, speed
FROM pokemon_stats WHERE pokedex_id = '{pid}' AND form = '{form}';
```

**多形态处理：** 先查 `pokemon_forms` 看看有哪些形态，让用户确认用哪个。例如风速狗有普通和洗翠两种形态。

**形态匹配规则：** `pokemon_forms.form_name` 与 `pokemon_stats.form` 对应。一般形态的 form 值为空字符串 `''` 或 `'一般'`。

---

### 1.2 🥇 计算能力值（Champions SP 系统）

**这是默认使用的公式。** 除非用户明确提到「朱紫」「努力值」「Gen9」，否则用这套。

> 📎 详细公式原理（SP 与 EV 的换算关系、性格修正推导）见 `pokemon_formulas_champions.md` 第一章。

调用 `calc_damage.calc_champions_stats()`：

```python
from calc_damage import calc_champions_stats

stats = calc_champions_stats(
    pokedex_id=6,                        # 图鉴编号
    sps={'hp':0, 'attack':32, 'defense':0, 'sp_attack':0, 'sp_defense':0, 'speed':0},
    nature='固执',
    form='一般'
)
# 公式（固定 Lv.50, IV=31）：
#   HP  = 种族值 + SP_hp + 75
#   其他 = (种族值 + SP_stat + 20) × 性格修正（向下取整）
```

**SP 分配速查表（Champions 默认）：**

| 称呼 | SP 分配 | 性格 | 说明 |
|------|---------|------|------|
| 极攻 | Atk/SpA=32 | +攻性格（固执/内敛等） | 标准输出手配置 |
| 满攻 | Atk/SpA=32 | 不减攻性格 | 需要速度/耐久时 |
| 极速 | Spd=32 | +速性格（爽朗/胆小等） | 高速线争夺 |
| 满HP | HP=32 | 不限 | 盾向/空间手 |
| 极限物耐 | HP=32, Def=32 | +防性格 | 物盾 |
| 极限特耐 | HP=32, SpD=32 | +特防性格 | 特盾 |
| 无速 | 不加速度 | 减速性格 | 空间队 |
| 双刀 | Atk=32, SpA=32 | 不减双攻性格 | 双刀用法 |

**性格修正查询：** 见 `calc_damage._get_nature_mods()` 中的完整表格（20种修正性格 + 5种无修正）。

---

### 1.3 🥈 计算能力值（朱紫/Gen9 努力值系统）

只在用户明确提及「朱紫」「努力值」「Gen9」「VGC 朱紫」时使用。

> 📎 完整公式推导、个体值/努力值/性格修正的详细说明见 `pokemon_formulas_gen9.md` 第一章。

调用 `calc_damage.calc_all_stats()`：

```python
from calc_damage import calc_all_stats

stats = calc_all_stats(
    pokedex_id=6,
    level=50,
    evs={'hp':0, 'attack':0, 'defense':0, 'sp_attack':252, 'sp_defense':0, 'speed':252},
    nature='内敛',
    form='一般'
)
# 公式（Lv.50, 默认 IV=31）：
#   HP  = (种族值×2 + IV + EV÷4) × Lv÷100 + Lv + 10
#   其他 = (种族值×2 + IV + EV÷4) × Lv÷100 + 5 × 性格修正
```

**EV 分配速查表（朱紫参考）：**

| 称呼 | EV 分配 | 等效 Champions SP |
|------|---------|------------------|
| 极攻 | 252Atk/SpA | Atk/SpA=32 |
| 极速 | 252Spd | Spd=32 |
| 满HP | 252HP | HP=32 |
| 极限物耐 | 252HP 252Def | HP=32, Def=32 |
| 极攻极速 | 252Atk/SpA 252Spd | Atk=32, Spd=32 |

---

### 1.4 能力变化阶段倍率表（两环境通用）

| 阶段 | +6 | +5 | +4 | +3 | +2 | +1 | 0 | -1 | -2 | -3 | -4 | -5 | -6 |
|------|----|----|----|----|----|----|----|----|----|----|----|----|----|
| 倍率 | 4.0 | 3.5 | 3.0 | 2.5 | 2.0 | 1.5 | 1.0 | 0.67 | 0.5 | 0.4 | 0.33 | 0.29 | 0.25 |

用法：最终能力值 = 基础能力值 × 倍率（向下取整）

---

## 二、伤害计算

**默认使用 Champions 环境的 `quick_calc_champions()`。** 只有用户明确说朱紫才切到 `quick_calc()`。

### 2.1 🥇 Champions 快速计算（默认）

> 📎 完整的逐步计算流程（含具体示例：Mega巨钳螳螂 子弹拳 → 洗翠风速狗）见 `workflow.md`。

```python
from calc_damage import quick_calc_champions

print(quick_calc_champions(
    '海豚侠', '喷射拳', '喷火龙',
    atk_sp=32,              # 攻击 SP（默认极攻）
    spd_sp=0,               # 速度 SP
    def_sp=0,               # 防御 SP
    hp_sp=0,                # HP SP
    sdef_sp=0,              # 特防 SP
    nature='固执',
    def_nature='认真',       # 防御方性格
    item='神秘水滴',         # 道具（可选）
    weather=None,           # 天气
    terrain=None,           # 场地
    is_critical=False,
    screens=0,
))
```

### 2.2 🥈 朱紫快速计算

> 📎 朱紫专属的伤害公式细节、随机数规则、特性/道具在公式中的具体位置见 `pokemon_formulas_gen9.md` 第二章。

```python
from calc_damage import quick_calc

print(quick_calc(
    '喷火龙', '喷射火焰', '妙蛙种子',
    level=50,
    atk_ev=252, def_ev=0,   # 努力值
    nature='内敛',
    weather=None, terrain=None,
    is_critical=False,
    screens=0,
))
```

### 2.3 完整参数版（两环境通用）

当快速计算接口的参数不够用时，手动准备数据后调 `calc_damage()`：

```python
from calc_damage import calc_damage, calc_champions_stats, get_pokemon_info, get_move_info

# 以 Champions 为例
atk_info = get_pokemon_info('海豚侠')
def_info = get_pokemon_info('喷火龙')
move_info = get_move_info('喷射拳')

atk_stats = calc_champions_stats(963, sps={'attack':32}, nature='固执')
def_stats = calc_champions_stats(6, sps={'hp':32}, nature='认真')

result = calc_damage(
    atk_stats, def_stats,
    move_power=int(move_info['power']),
    move_category=move_info['category'],
    attacker_types=['水'],
    defender_types=['火','飞行'],
    move_type='水',
    weather='rain',          # 雨天
    terrain=None,
    is_burned=False,
    screens=0,
    help_active=False,
    multi_target=False,
    items={'attacker': '神秘水滴'},
    abilities=None,          # 特性影响请在调用前处理好，见第三章
)
```

### 2.4 纯数值接口

不查数据库，所有参数手动传入。适合调用方已准备好所有数值的场景：

```python
from calc_damage import calc_damage_raw

result = calc_damage_raw(
    level=50,
    attack=202,             # 最终攻击值（含性格、能力变化、道具修正）
    defense=100,            # 最终防御值
    move_power=60,          # 最终威力（含技术高手等修正）
    stab=1.5,
    type_effectiveness=2.0,
    other_mod=1.0,
    is_critical=False,
)
```

### 2.5 伤害判定规则

```python
hp = def_stats['hp']
if result['min'] >= hp:
    判定 = "确一 (OHKO)"
elif result['max'] >= hp:
    kill_count = sum(1 for d in result['rolls'] if d >= hp)
    概率 = kill_count / len(result['rolls']) * 100
    判定 = f"乱一 ({概率:.0f}%)"
else:
    hits = (hp + result['max'] - 1) // result['max']
    判定 = f"需要 {hits} 次击杀"
```

---

## 三、 特性判定

**这是整个 skill 最关键的判断环节。** 特性会影响能力值、招式威力、伤害倍率、属性相克等多个参数，**不能在各个章节零散处理**，必须在计算伤害前汇总判断。

### 3.1 特性判定流程（必读）

```
步骤 1：查攻击方和防御方拥有的特性
─────────────────────────────
  SELECT ability1, ability2, hidden_ability
  FROM pokemon_forms WHERE pokedex_id = '{pid}' AND form_name LIKE '%{form}%'

步骤 2：拿到特性名后，查效果文本
─────────────────────────────
  SELECT name_zh, effect, introduction
  FROM abilities WHERE name_zh = '{ability_name}'

步骤 3：读 effect 文本，判断影响哪个参数
─────────────────────────────
  ⚠️ 不能只看特性名就下结论。必须读 effect 原文，判断：
     - 改能力值（攻击/防御/速度等）→ 最终在调用 calc_damage 前调整 stats
     - 改招式威力（含「威力提高」等表述）→ 调整 move_power
     - 改伤害倍率 → 加入 other_mod
     - 改属性相克（含「免疫」「減半」等）→ 调整 type_effectiveness
     - 其他效果（回血、追加效果、场地等）→ 根据具体效果单独处理

步骤 4：分类处理后，将结果代入 calc_damage
─────────────────────────────
```

### 3.2 按影响参数分类的完整特性列表

以下列表按影响参数分类。**这是一个参考列表，不是穷尽列表。** 实际判断始终以步骤 2 的 `effect` 原文为准。

#### 3.2.1 影响能力值（在调用 calc_damage 前调整 stats）

| 特性 | 效果 | 判断依据（看 effect 中是否含以下关键词） |
|------|------|------------------------------------------|
| 大力士 / 瑜伽之力 | 攻击×2.0 | 「攻击变为2倍」 |
| 毅力 | 烧伤时攻击×1.5，无视烧伤物攻减半 | 「攻击提升」「无视烧伤」 |
| 强行 | 有追加效果时威力×1.3，追加效果不触发 | 「招式威力提升」+「追加效果不再发动」——注意：这是 move_power 类，不是能力值类 |
| 慢启动 | 5回合内攻击速度减半 | 「攻击」「速度减半」 |
| 太阳之力 | 晴天特攻×1.5，每回合损失HP | 「特攻提升」 |
| 叶绿素 / 悠游自如 / 拨沙 / 拨雪 | 对应天气下速度×2 | 「速度提升」|
| 轻装 | 失去道具时速度×2 | 「速度提升」+「道具」 |
| 万能变身（变幻自如 / 自由者） | 使用招式时变为该属性 | 改的是属性，不是能力值——见 3.2.4 |

**处理方式：**
```python
# 例：大力士 → 攻击翻倍
if attacker_ability == '大力士':
    atk_stats['attack'] = atk_stats['attack'] * 2
# 例：烧伤 + 毅力 → 攻击×1.5 且不触发烧伤减半
if is_burned and attacker_ability == '毅力':
    atk_stats['attack'] = int(atk_stats['attack'] * 1.5)
    is_burned = False  # 标记为已处理，后续 other_mod 不再乘 0.5
```

#### 3.2.2 影响招式威力（调整 move_power）

| 特性 | 效果 | 判断关键词 |
|------|------|-----------|
| 技术高手 | 威力≤60的招式×1.5 | 「威力≤60的招式」「威力提高」 |
| 铁拳 | 拳类招式×1.2 | 「拳类招式」「威力提高」 |
| 强壮之颚 | 咬类招式×1.5 | 「咬类招式」「威力提高」 |
| 锐利目光 | 命中率不会降低（不影响伤害） | 不处理 |
| 狙击手 | 击中要害时伤害×2.25（代替1.5） | 「击中要害」「提升」 |
| 异兽提升 | 打倒对手后最高能力×1.1 | 战后能力变化，当前回合不处理 |
| 庞克摇滚 | 声音类招式×1.3 | 「声音类招式」「威力提高」 |
| 冲浪之尾 / 钢铁意志 | 特定条件（入水/铁壁形态）威力提升 | 看 effect 具体条件 |
| 大力士（复） | 已在 3.2.1 中处理，此处不重复 | |

**注意强行（Sheer Force）：** 它的 effect 通常描述为「招式威力提升」和「追加效果不再触发」。如果招式有追加效果（如喷射火焰10%烧伤），则 move_power ×1.3，同时无视道具（生命宝珠不扣血、追加效果不触发）。如果招式本身没有追加效果，强行不生效。

**处理方式：**
```python
if attacker_ability == '技术高手' and move_power <= 60:
    move_power = int(move_power * 1.5)
```

#### 3.2.3 影响伤害倍率（调整 other_mod）

| 特性 | 效果 | 判断关键词 |
|------|------|-----------|
| 厚脂肪 | 受到火/冰招式伤害×0.5 | 「火」「冰」「减半」 |
| 坚硬岩石 | 受到效果绝佳招式伤害×0.75 | 「效果绝佳」「减伤」 |
| 过滤 | 受到效果绝佳招式伤害×0.75 | 「效果绝佳」「减伤」同坚硬岩石 |
| 多重鳞片 | HP全满时受到伤害×0.5 | 「HP全满」「减半」 |
| 幻影防守 | HP全满时受到伤害×0.5 | 同上（效果同多重鳞片） |
| 冰鳞粉 | 受到特殊招式伤害×0.5 | 「特殊招式」「减半」 |
| 友情防守 | 队友在场时受到伤害×0.75 | 「队友」「减伤」 |
| 毛茸茸 | 接触类招式伤害×0.5，但火招式×2 | 「接触」「减半」「火→2倍」 |
| 干燥皮肤 | 水招式无效+回HP，火招式×1.25 | 「水」「回复」「火」「提升」——注意这是属性相克类 |
| 重金属 / 轻金属 | 仅影响重量，不影响伤害 | 除非涉及打草结等重量相关招式 |
| 神奇守护（欠揍） | 只有效果绝佳招式能命中 | 效果绝佳以外的招式 multiplier 设为 0 |
| 凸凸头盔 / 附着针 / 污泥浆等 | 反伤类，不参与伤害计算 | 告知用户存在此特性即可 |
| 诅咒之躯 / 孢子 / 静电等 | 接触后追加效果类 | 不参与伤害计算，告知用户 |

**处理方式：**
```python
# 厚脂肪：火/冰 ×0.5
if defender_ability == '厚脂肪' and move_type in ('火', '冰'):
    other_mod *= 0.5
```

#### 3.2.4 影响属性相克（调整 type_effectiveness）

| 特性 | 效果 | 处理方式 |
|------|------|---------|
| 飘浮 | 地面招式免疫→×0 | type_effectiveness = 0 |
| 引火 | 火招式免疫，且特攻提升一级 | type_eff=0，额外告知触发提升效果 |
| 蓄电 / 避雷针 / 电气引擎 | 电招式免疫 | type_eff=0，电气引擎提升速度 |
| 引水 / 储水 | 水招式免疫 | type_eff=0，引水提升特攻、储水回复HP |
| 干燥皮肤 | 水招式回复HP | 水招式 type_eff 设为负值（回血标记） |
| 胆量 | 一般/格斗可命中幽灵 | 原本 type_eff=0 的幽灵对一般/格斗改为 1.0 |
| 透光 / 察觉 | 不改变相克 | 不处理 |

**处理方式：** 在查完 `pokemon_type_effectiveness` 表的倍率之后，再根据特性做二次修正。

#### 3.2.5 影响等级或特殊计算

| 特性 | 效果 | 处理 |
|------|------|------|
| 穿透 | 无视光墙/反射壁/替身 | screens 参数设为 0 |
| 破格 / 涡轮火焰 / 兆级电压 | 无视对方特性 | 对方特性不生效 |
| 化学变化气体 | 全场特性失效（除自己） | 双方特性均不生效 |
| 同步 | 传递给对方异常状态 | 不参与伤害计算 |
| 复制 | 复制对方特性 | 查对方特性作为自己的特性 |
| 变身者 | 变身成对方样子 | 复制对方全部能力 |

**破格处理示例：**
```python
if attacker_ability in ('破格', '涡轮火焰', '兆级电压'):
    # 防御方特性失效
    defender_ability = None  # 不应用任何防御方特性效果
```

### 3.3 综合判断示例

假设计算「大力士玛力露丽 水流尾 → 厚脂肪卡比兽」：

```
1. 查特性：攻击方=大力士，防御方=厚脂肪
2. 读效果：
   - 大力士：「攻击×2」→ 能力值类，stats['attack'] ×= 2
   - 厚脂肪：「受到火/冰招式减半」→ 水流尾是水，不触发
3. 调用 calc_damage：
   - attack = 已 ×2 后的值
   - other_mod 不因厚脂肪改变（水不触发）
4. 判定结果
```

假设计算「大晴天+叶绿素妙蛙花 亿万吸取 → 引水海兔兽」：

```
1. 查特性：攻击方=叶绿素，防御方=引水
2. 读效果：
   - 叶绿素：「晴天速度×2」→ 影响速度，不影响当前伤害
   - 引水：「水招式免疫并提升特攻」→ 亿万吸取是草，不触发
3. 防御方另一个特性可能是「储水」→ 也不是草，不触发
4. 正常计算
```

---

## 四、属性与抗性

### 4.1 单属性相克查询

```sql
SELECT defending_type, multiplier
FROM pokemon_type_effectiveness
WHERE pokedex_id = '{defender_pid}' AND form = '{form}'
ORDER BY multiplier ASC;
```

### 4.2 双属性组合抗性

**路径 A（推荐）：** 直接用宝可梦查。`pokemon_type_effectiveness` 已经将双属性合并计算好。

```sql
SELECT defending_type, multiplier
FROM pokemon_type_effectiveness
WHERE pokedex_id = '{pid}' AND form = '{form}'
ORDER BY multiplier;

-- multiplier 含义：
-- 0     = 免疫
-- 0.25  = 四倍抗
-- 0.5   = 二倍抗
-- 1.0   = 普通
-- 2.0   = 二倍弱
-- 4.0   = 四倍弱
```

**路径 B（理论查询）：** 用户问「某属性+某属性有多少抗性」时，找一个具有该属性组合的宝可梦，用路径 A 查。

**注意：** 查完属性倍率后，还需要结合第三章「特性判定」中的 3.2.4 节修正——例如飘浮让地面免疫、引火让火免疫等。

### 4.3 属性组合→弱点/抗性列表生成（给用户看）

输出格式建议：

```
钢+妖精 属性组合：
─────────────────────────
🛡 免疫：毒（×0）、龙（×0）
👍 四倍抗：虫（×¼）
👍 二倍抗：一般、草、冰、飞行、超能、岩石、恶、妖精（×½）
⚠️ 普通：水、电、格斗、幽灵
💀 二倍弱：火、地面（×2）
💀 四倍弱：无
```

---

## 五、招式与道具

### 5.1 招式查询

```sql
SELECT name_zh, type, category, power, accuracy, pp, description, effect
FROM moves
WHERE name_zh = '{move_name}';
```

**注意：** `power` 字段是 TEXT 类型，可能包含 `'—'`（变化招式）、`'不定'`等，使用时需转换。

**招式分类（辅助特性判断）：**

| 分类 | 相关特性 | 判断方式 |
|------|---------|---------|
| 拳类 | 铁拳 ×1.2 | 招式的 description 含「拳」，或中文名含「拳」「巴掌」 |
| 咬类 | 强壮之颚 ×1.5 | 中文名含「咬」「啃」「噬」 |
| 声音类 | 隔音免疫、庞克摇滚 ×1.3 | 中文名含「声」「音」「歌」「吼」「叫」「鸣」 |
| 波动类 | 波动无防备（Mega拉鲁拉丝） | 中文名含「波动」「波」 |
| 弹/炸弹类 | 防弹免疫 | 中文名含「弹」「球」或英文为Ball/Bomb |

### 5.2 道具查询

```sql
SELECT name_zh, description, category_path
FROM items
WHERE name_zh = '{item_name}';
```

**道具效果分类（伤害计算时判断参数放哪里）：**

| 类别 | 效果 | 影响参数 | 示例 |
|------|------|---------|------|
| 属性增强 | XX属性招式威力×1.2 | move_power | 木炭、神秘水滴、奇迹种子、磁铁…… |
| 能力增强 | 攻击/特攻×1.5 | 能力值（atk_stats） | 讲究头带、讲究眼镜 |
| 泛用增伤 | 伤害×1.3 或 效果绝佳时×1.2 | other_mod | 生命宝珠、达人带 |
| 抗性果 | 受到效果绝佳的XX属性×0.5（一次性） | other_mod | 抗火果、抗冰果…… |
| 半减果 | HP≤1/4时 ×0.5（一次性） | other_mod | 勿花果、枝荔果…… |

### 5.3 特性查询（获取效果文本）

```sql
-- 从数据库查
SELECT name_zh, name_en, introduction, effect
FROM abilities
WHERE name_zh = '{ability_name}';
```

或从 JSON 数据集读取：

```python
import json, os
ability_dir = r'D:\astrbot\databasepoke\pokemon-dataset-zh-main\data\abilities'
filepath = os.path.join(ability_dir, f'{ability_name}.json')
if os.path.exists(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
```

拿到效果文本后，按第三章的流程处理。

---

## 六、规则集查询

### 6.1 列出所有规则集

```python
from calc_damage import list_rulesets
print(list_rulesets())
```

### 6.2 查询特定规则集

```python
from calc_damage import get_ruleset
rs = get_ruleset('champions_reg_m_a')
```

### 6.3 当前主流规则集

| 规则集 | 游戏 | 时期 | 特点 |
|--------|------|------|------|
| `champions_reg_m_a` | Champions | 2026.4-2026.6 | 🥇允许Mega，禁止传说/悖谬 |
| `sv_regulation_g` | 朱紫 | 2025.4- | 允许1只传说 |
| `sv_regulation_h` | 朱紫 | 2024.9-2025.1 | 限制最大 |

### 6.4 规则适用判断

收到查询时，默认使用 `champions_reg_m_a`。如果用户提到「朱紫」「VGC」，切到朱紫规则集。

---

## 七、队伍构建辅助（静态数据分析）

**本模块只分析静态数据，不涉及环境热门宝可梦。** 环境数据不在当前数据库中。

### 7.1 防御联防分析

给定一支队伍，计算整体防御弱点覆盖情况：

```python
def analyze_defensive_synergy(team):
    """
    输入: [('振翼发', '一般'), ('厄诡椪', '碧草面具'), ('快龙', '一般'), ...]
    输出: 
      - cover_rate: 各属性被队伍中至少一只宝可梦抗/免疫的比例
      - weak_spots: 队伍中≥2只宝可梦共同弱点的属性
      - four_times_weak: 队伍中四倍弱点的宝可梦列表
    """
    # 实现：遍历每只宝可梦，查 pokemon_type_effectiveness
    # 统计各属性的抗性覆盖情况
    pass
```

**输出格式示例：**

```
队伍联防分析：
─────────────────────────
✅ 良好覆盖：火、水、草、电、格斗（≥2只抗性）
⚠️ 轻微漏洞：地面（仅1只抗性）
💀 严重漏洞：冰（无人抗性）
⚠️ 共同弱点：岩石（3只弱岩）
💀 四倍弱点：暴鲤龙弱电×4
```

### 7.2 本系打击面分析

```python
def analyze_stab_coverage(team):
    """
    输入: [('振翼发', '一般'), ('厄诡椪', '碧草面具'), ...]
    输出: 队伍的 STAB 打击面覆盖了哪些属性，遗漏了哪些属性
    """
    # 实现：每个成员的属性就是其 STAB 属性
    # 查每个 STAB 属性打击面（type_effectiveness）
    # 汇总为整体 STAB 覆盖
    pass
```

**输出格式示例：**

```
本系打击面分析：
─────────────────────────
💪 有效打击（≥1个STAB能打出×2以上）：
  水（暴鲤龙）、草（厄诡椪）、幽灵+妖精（振翼发）
❌ 打击盲点（无STAB能打出×2以上）：
  钢、毒、火、地面
```

### 7.3 速度线参考

如果需要对比队伍内外的速度线，使用章节 9.1 的速度比较方法。

---

## 八、数据库维护

### 8.1 数据库结构概览

```
pokemon                    → 宝可梦基本信息
pokemon_forms              → 形态信息（属性、特性、身高体重）
pokemon_stats              → 种族值（六维，区分形态）
pokemon_type_effectiveness → 属性相克倍率（已合并双属性，区分形态）
moves                      → 招式信息
abilities                  → 特性效果
items                      → 道具信息
pokemon_learnable_moves    → 升级学习招式
pokemon_machine_moves      → 机器学习招式
pokemon_egg_moves          → 蛋招式
pokemon_evolution_chains   → 进化链
ruleset_pokemon            → 规则集禁用列表
```

### 8.2 更新流程：检测上游数据源更新

当收到「游戏更新了」时：

```
步骤 1：检查上游是否有更新
─────────────────────────────
   上游：https://github.com/42arch/pokemon-dataset-zh
   方法 A（推荐）：
     cd D:\astrbot\databasepoke\pokemon-dataset-zh-main
     git fetch origin main
     git log HEAD..origin/main --oneline
   方法 B（git 连不上时）：
     访问上游 GitHub 页面，看 Latest commit 日期
     判断是否有新提交

步骤 2→5：同 v1.0，见文档末尾备注
```

### 8.3 单条数据修改

```sql
-- 更新种族值
UPDATE pokemon_stats SET attack=110 WHERE pokedex_id='006' AND form='一般';
-- 添加新形态
INSERT INTO pokemon_forms (...) VALUES (...);
```

---

## 九、其他常见查询

### 9.1 速度比较

默认用 Champions SP 系统计算：

```python
from calc_damage import calc_champions_stats

a = calc_champions_stats(6, sps={'speed':32}, nature='爽朗')   # 喷火龙极速
b = calc_champions_stats(9, sps={'speed':32}, nature='爽朗')   # 水箭龟极速
```

需要考虑的因素：
- 特性速度提升：轻装（道具用完×2）、叶绿素（晴×2）、悠游自如（雨×2）、拨沙（沙×2）、拨雪（雪×2）
- 道具：讲究围巾（×1.5）
- 顺风：速度×2
- 能力变化阶段

### 9.2 进化链 / 蛋招式 / 可学习招式

```sql
-- 进化链
SELECT * FROM pokemon_evolution_chains WHERE pokedex_id = '{pid}' ORDER BY chain_index;

-- 蛋招式
SELECT move_name, parent_ids FROM pokemon_egg_moves WHERE pokedex_id = '{pid}';

-- 升级学习
SELECT level, move_name, move_type, category, power
FROM pokemon_learnable_moves WHERE pokedex_id = '{pid}' AND form = '{form}'
ORDER BY CAST(level AS INTEGER);

-- TM学习
SELECT machine, move_name, move_type, category, power
FROM pokemon_machine_moves WHERE pokedex_id = '{pid}' AND form = '{form}';
```

---

## 十、调用优先级与兜底

### 10.1 查询优先级

```
1. SQLite 数据库（pokemon.db）      → 最快、最准确
2. JSON 数据集                      → 补充数据（特性详细效果）
3. calc_damage.py 函数              → 计算类任务
4. 神奇宝贝百科/官方信息来源          → 数据库没有时，建议用户自行查阅
5. 绝对禁止：编造数据
```

### 10.2 查不到时的处理

| 情况 | 处理方式 |
|------|---------|
| 宝可梦名不存在 | 提示「未找到」，给出相似名称建议 |
| 招式名不存在 | 同上 |
| 形态不存在 | 列出该宝可梦所有已知形态让用户确认 |
| 数据未收录（如新世代） | 提示「当前数据库仅收录至 Gen 9，建议更新」 |
| 特性效果文本不明确 | 读原文后用自己的理解描述效果，不自作主张加数值 |
| 排位使用率相关 | 告知「当前数据库不包含排位数据」 |

---

## 十一、更新日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-03 | v1.1 | 重写结构：Champions 设为默认环境；新增独立特性判定模块（第三章）；简化队伍分析为静态数据 |
| 2026-05-03 | v1.0 | 初始版本 |

---

> **附录：常用快捷调用**
>
> ```python
> # Champions 确一判断（默认）
> from calc_damage import quick_calc_champions
> print(quick_calc_champions('振翼发', '月亮之力', '快龙', atk_sp=32, nature='内敛'))
>
> # 朱紫确一判断
> from calc_damage import quick_calc
> print(quick_calc('振翼发', '月亮之力', '快龙', atk_ev=252, nature='内敛'))
>
> # 规则集速查
> from calc_damage import list_rulesets
> print(list_rulesets())
> ```
