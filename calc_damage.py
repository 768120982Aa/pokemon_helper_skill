"""
宝可梦 伤害计算模块
基于神奇宝贝百科公式实现，配合 pokemon.db 使用

对外接口：
  calc_champions_stats()  — Champions SP 能力值
  calc_gen9_stats()       — 朱紫/Gen9 努力值能力值
  calc_damage()           — 完整伤害计算（两系统通用）
  calc_damage_raw()       — 纯数值伤害计算
  list_rulesets()         — 列出规则集
  get_ruleset()           — 查规则集详情

说明：
  特性/道具/皮肤系等修正请由调用方在传入前自行处理。
  calc_damage 仅处理：属性相克（含胆量/飘浮等 type_eff 修正）、天气、场地、灼伤、墙壁。
"""
import sqlite3
import json
import math
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'pokemon.db')
RULESETS_PATH = os.path.join(os.path.dirname(__file__), 'rulesets.json')

# ====================================================================
#  通用工具
# ====================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_nature_mods(nature):
    """性格修正倍率表"""
    table = {
        '勤奋': {}, '坦率': {}, '害羞': {}, '浮躁': {}, '认真': {},
        '怕寂寞': {'attack':1.1, 'defense':0.9},
        '固执':   {'attack':1.1, 'sp_attack':0.9},
        '顽皮':   {'attack':1.1, 'sp_defense':0.9},
        '勇敢':   {'attack':1.1, 'speed':0.9},
        '大胆':   {'defense':1.1, 'attack':0.9},
        '淘气':   {'defense':1.1, 'sp_attack':0.9},
        '乐天':   {'defense':1.1, 'sp_defense':0.9},
        '悠闲':   {'defense':1.1, 'speed':0.9},
        '内敛':   {'sp_attack':1.1, 'attack':0.9},
        '慢吞吞': {'sp_attack':1.1, 'defense':0.9},
        '马虎':   {'sp_attack':1.1, 'sp_defense':0.9},
        '冷静':   {'sp_attack':1.1, 'speed':0.9},
        '温和':   {'sp_defense':1.1, 'attack':0.9},
        '温顺':   {'sp_defense':1.1, 'defense':0.9},
        '慎重':   {'sp_defense':1.1, 'sp_attack':0.9},
        '自大':   {'sp_defense':1.1, 'speed':0.9},
        '胆小':   {'speed':1.1, 'attack':0.9},
        '急躁':   {'speed':1.1, 'defense':0.9},
        '爽朗':   {'speed':1.1, 'sp_attack':0.9},
        '天真':   {'speed':1.1, 'sp_defense':0.9},
    }
    return table.get(nature, {})


def _bankers_round(val):
    """五捨六入"""
    return math.floor(val) if (val - math.floor(val)) < 0.6 else math.ceil(val)


# ====================================================================
#  Champions SP 系统（默认）
# ====================================================================

def calc_champions_stats(pokedex_id, sps=None, nature="认真", form="一般"):
    """
    Champions SP 能力值计算（Lv.50, IV=31）
    
    公式: HP = 种族值 + SP_hp + 75
          其他 = (种族值 + SP_stat + 20) × 性格修正

    Args:
        pokedex_id: 图鉴编号，支持 '0475' 或 475
        sps: SP 分配，如 {'attack':32}，未指定的默认 0
        nature: 性格，如 '固执'
        form: 形态，如 '一般' / '超级进化'
    """
    if sps is None:
        sps = {s:0 for s in ['hp','attack','defense','sp_attack','sp_defense','speed']}
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats "
                "WHERE pokedex_id=? AND form=?", (pokedex_id, form))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats "
                    "WHERE pokedex_id=? LIMIT 1", (pokedex_id,))
        row = cur.fetchone()
        conn.close()
    if not row:
        return None
    
    bases = dict(row)
    nmods = _get_nature_mods(nature)
    
    stats = {}
    for s in ['hp','attack','defense','sp_attack','sp_defense','speed']:
        sp = sps.get(s, 0)
        if s == 'hp':
            stats[s] = bases[s] + sp + 75
        else:
            raw = bases[s] + sp + 20
            stats[s] = int(raw * nmods.get(s, 1.0))
    
    stats['_bases'] = bases
    stats['_pokedex_id'] = pokedex_id
    stats['_level'] = 50
    stats['_sps'] = sps
    return stats


# ====================================================================
#  朱紫 / Gen9 努力值系统
# ====================================================================

def _calc_gen9_stat(base, iv=31, ev=0, level=50, nature_mult=1.0, is_hp=False):
    """单项能力值（朱紫公式，向下取整）"""
    if is_hp:
        return ((base * 2 + iv + ev // 4) * level // 100) + level + 10
    else:
        return int(((base * 2 + iv + ev // 4) * level // 100 + 5) * nature_mult)


def calc_gen9_stats(pokedex_id, level=50, ivs=None, evs=None, nature="认真", form="一般"):
    """
    朱紫/Gen9 能力值计算

    Args:
        pokedex_id: 图鉴编号
        level: 等级
        ivs: 个体值，如 {'hp':31, 'attack':31, ...}
        evs: 努力值，如 {'hp':252, 'sp_attack':252, ...}
        nature: 性格
        form: 形态
    """
    if ivs is None:
        ivs = {s:31 for s in ['hp','attack','defense','sp_attack','sp_defense','speed']}
    if evs is None:
        evs = {s:0 for s in ['hp','attack','defense','sp_attack','sp_defense','speed']}
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats "
                "WHERE pokedex_id=? AND form=?", (pokedex_id, form))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats "
                    "WHERE pokedex_id=? LIMIT 1", (pokedex_id,))
        row = cur.fetchone()
        conn.close()
    if not row:
        return None
    
    bases = dict(row)
    nature_mods = _get_nature_mods(nature)
    
    stats = {}
    stat_names = ['hp','attack','defense','sp_attack','sp_defense','speed']
    for s in stat_names:
        is_hp = (s == 'hp')
        stats[s] = _calc_gen9_stat(bases[s], ivs.get(s,31), evs.get(s,0), level, 
                                   nature_mods.get(s, 1.0), is_hp)
    
    stats['_bases'] = bases
    stats['_level'] = level
    stats['_pokedex_id'] = pokedex_id
    return stats


# ====================================================================
#  核心伤害计算
# ====================================================================

def calc_damage(attacker_stats, defender_stats, move_power, move_category,
                attacker_types=None, defender_types=None,
                move_type=None, is_critical=False,
                weather=None, terrain=None, is_burned=False,
                screens=0, help_active=False, charge_active=False,
                multi_target=False, items=None, abilities=None,
                tera_type=None, random_roll=None):
    """
    完整伤害计算（Champions / Gen9 通用）

    此函数为纯计算引擎。特性/道具等修正请在调用前自行处理：
      - 改 move_power: 锋锐/铁拳/强行等
      - 改 stats: 大力士/威吓/灾祸等
      - 改 other_mod: 厚脂肪/多重鳞片等（通过 items 或直接改 stats）

    函数内置处理：
      - 道具（属性增强 ×1.2、讲究系列 ×1.5、命玉 ×1.3、达人带 ×1.2）
      - 天气（晴/雨对火/水 ±×1.5）
      - 场地（电/草/超能 ×1.3）
      - 灼伤（物理 ×0.5）
      - 墙壁（单打 ×0.5、双打 ×2/3）
      - 帮助 ×1.5、充电 ×2、多目标 ×0.75
      - 属性相克（含特性修正：胆量/飘浮/引火等，通过 abilities 参数）
      - 击中要害 ×1.5
      - STAB ×1.5
      - 太晶化 STAB

    Args:
        attacker_stats: calc_champions_stats 或 calc_gen9_stats 返回
        defender_stats: 同上
        move_power: 招式威力，特性/道具修正后传入
        move_category: '物理' / '特殊'
        attacker_types: 攻击方属性列表，如 ['超能力','格斗']
        defender_types: 防御方属性列表，如 ['钢','超能力']
        move_type: 招式属性
        is_critical: 是否暴击
        weather: 天气，None / 'sun' / 'rain' / 'sand' / 'snow'
        terrain: 场地，None / 'electric' / 'psychic' / 'grassy' / 'misty'
        is_burned: 攻击方是否灼伤
        screens: 0=无 / 1=单打 / 2=双打
        help_active: 帮助状态
        charge_active: 充电状态
        multi_target: 是否攻击多个目标
        items: 道具，如 {'attacker':'讲究头带'}
        abilities: 特性影响 type_eff，如 {'defender':'飘浮'}
        tera_type: 太晶属性
        random_roll: 随机数 0.85~1.00，不传则自动全部生成

    Returns:
        dict: min, max, rolls, base_damage, type_mult, stab, other_mod
    """
    level = attacker_stats.get('_level', 50)
    
    # 攻击/防御能力值
    if move_category == '物理':
        atk = attacker_stats['attack']
        dfs = defender_stats['defense']
    else:
        atk = attacker_stats['sp_attack']
        dfs = defender_stats['sp_defense']
    
    # --- 基础伤害 ---
    step1 = (2 * level // 5 + 2)
    step2 = step1 * move_power * atk // dfs
    base_dmg = step2 // 50 + 2
    
    # --- 其他加成 ---
    other_mod = 1.0
    
    _items = items or {}
    a_item = _items.get('attacker')
    
    # 道具
    TYPE_ITEMS = ['木炭','奇迹种子','神秘水滴','不融冰','磁铁','锐利鸟嘴',
                   '银粉','软沙','硬石头','诅咒之符','龙之牙','黑色眼镜',
                   '金属膜','毒针','丝绸围巾']
    if a_item in TYPE_ITEMS:
        other_mod *= 1.2
    elif a_item in ('讲究头带', '讲究眼镜', '讲究围巾'):
        other_mod *= 1.5
    elif a_item == '生命宝珠':
        other_mod *= 1.3
    elif a_item == '达人带':
        pass  # 在后面根据 type_mult 判断
    
    # 天气
    if weather == 'sun':
        if move_type == '火':
            other_mod *= 1.5
        elif move_type == '水':
            other_mod *= 0.5
    elif weather == 'rain':
        if move_type == '水':
            other_mod *= 1.5
        elif move_type == '火':
            other_mod *= 0.5
    
    # 场地
    if terrain == 'electric' and move_type == '电':
        other_mod *= 1.3
    elif terrain == 'grassy' and move_type == '草':
        other_mod *= 1.3
    elif terrain == 'psychic' and move_type == '超能力':
        other_mod *= 1.3
    
    # 灼伤（毅力请在调用前自行处理，通过 is_burned=False + attacker_stats 调整）
    if is_burned and move_category == '物理':
        other_mod *= 0.5
    
    # 墙壁
    if screens == 1:
        other_mod *= 0.5
    elif screens == 2:
        other_mod *= 2 / 3
    
    # 帮助、充电、多目标
    if help_active:
        other_mod *= 1.5
    if charge_active and move_type == '电':
        other_mod *= 2.0
    if multi_target:
        other_mod *= 0.75
    
    # 暴击
    crit_mod = 1.5 if is_critical else 1.0
    
    step_a = _bankers_round(other_mod * crit_mod)
    
    # --- 属性相克 ---
    type_mult = 1.0
    if attacker_types and defender_types and move_type:
        def_pokedex_id = defender_stats.get('_pokedex_id')
        type_mult = _get_type_effectiveness(move_type, defender_types, def_pokedex_id)
    
    # 达人带
    if a_item == '达人带' and type_mult > 1.0:
        step_a = _bankers_round(step_a * 1.2)
    
    # 特性修正 type_eff（胆量解除免疫、飘浮等增加免疫）
    type_mult = _apply_ability_type_effects(
        type_mult, abilities or {}, move_type, defender_types,
        attacker_types, defender_stats.get('_pokedex_id')
    )
    
    # STAB
    stab = 1.5 if (move_type and attacker_types and move_type in attacker_types) else 1.0
    if tera_type:
        if move_type == tera_type:
            if move_type in (attacker_types or []):
                stab = 2.0
            else:
                stab = 1.5
    
    # --- 计算伤害范围 ---
    def calc_dmg_with_roll(roll_val):
        step_b = base_dmg * step_a * roll_val // 1
        step_c = _bankers_round(step_b * stab)
        if type_mult == 0:
            return 0
        final = int(step_c * type_mult)
        return max(1, final)
    
    all_rolls = []
    min_dmg = float('inf')
    max_dmg = 0
    for r in range(85, 101):
        roll = r / 100.0
        d = calc_dmg_with_roll(roll)
        all_rolls.append(d)
        min_dmg = min(min_dmg, d)
        max_dmg = max(max_dmg, d)
    
    return {
        'min': min_dmg,
        'max': max_dmg,
        'rolls': all_rolls,
        'base_damage': base_dmg,
        'type_mult': type_mult,
        'stab': stab,
        'other_mod': step_a,
    }


def calc_damage_raw(level, attack, defense, move_power,
                    stab=1.5, type_effectiveness=1.0,
                    other_mod=1.0, is_critical=False):
    """
    纯数值伤害计算——所有参数由调用方准备，不查数据库。
    
    适合特性/道具已在外部处理完毕的场景。
    
    Returns:
        dict: {'min': int, 'max': int, 'rolls': [16种], 'base_damage': int}
    """
    step1 = (2 * level // 5 + 2)
    step2 = step1 * move_power * attack // defense
    base_dmg = step2 // 50 + 2
    
    crit_mod = 1.5 if is_critical else 1.0
    
    def full_calc(r):
        a = _bankers_round(other_mod * crit_mod)
        b = int(base_dmg * a * r)
        c = _bankers_round(b * stab)
        d = int(c * type_effectiveness)
        return max(1, d)
    
    all_rolls = [full_calc(pct / 100.0) for pct in range(85, 101)]
    
    return {
        'min': min(all_rolls),
        'max': max(all_rolls),
        'rolls': all_rolls,
        'base_damage': base_dmg,
    }


# ====================================================================
#  属性相克
# ====================================================================

def _get_type_effectiveness(move_type, defender_types, defender_pokedex_id=None):
    """
    从数据库获取属性相克倍率。
    pokemon_type_effectiveness 表已合并双属性。
    """
    if not defender_pokedex_id:
        conn = get_db()
        cur = conn.cursor()
        mult = 1.0
        for dtype in defender_types:
            cur.execute("""
                SELECT multiplier FROM pokemon_type_effectiveness 
                WHERE defending_type=? AND multiplier IS NOT NULL
                AND pokedex_id IN (SELECT pokedex_id FROM pokemon_forms WHERE type1=? OR type2=?)
                LIMIT 1
            """, (move_type, dtype, dtype))
            row = cur.fetchone()
            if row:
                m = row['multiplier']
                if m == 0:
                    mult = 0
                    break
                mult *= m
        conn.close()
        return mult
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT multiplier FROM pokemon_type_effectiveness 
        WHERE pokedex_id=? AND defending_type=? AND multiplier IS NOT NULL
        ORDER BY CASE WHEN form='' THEN 0 ELSE 1 END, form
        LIMIT 1
    """, (defender_pokedex_id, move_type))
    row = cur.fetchone()
    conn.close()
    return row['multiplier'] if row else 1.0


def _apply_ability_type_effects(type_mult, abilities, move_type, defender_types,
                                 attacker_types, defender_pokedex_id):
    """
    根据特性修正属性相克倍率。

    1. 攻击方解除免疫：胆量（格斗/一般→幽灵）
    2. 防御方增加免疫：飘浮(地)、引火(火)、蓄电/避雷针/电气引擎(电)、
                        引水/储水/干燥皮肤(水)、食草(草)、食土(地)
    """
    a_ability = abilities.get('attacker')
    d_ability = abilities.get('defender')

    if a_ability == '胆量' and move_type in ('一般', '格斗') and '幽灵' in (defender_types or []):
        if type_mult == 0:
            non_ghost = [t for t in defender_types if t != '幽灵']
            if non_ghost:
                type_mult = _get_type_effectiveness(move_type, non_ghost, None)
            else:
                type_mult = 1.0

    if d_ability in ('飘浮', '食土') and move_type == '地面':
        type_mult = 0.0
    if d_ability == '引火' and move_type == '火':
        type_mult = 0.0
    if d_ability in ('蓄电', '避雷针', '电气引擎') and move_type == '电':
        type_mult = 0.0
    if d_ability in ('引水', '储水', '干燥皮肤') and move_type == '水':
        type_mult = 0.0
    if d_ability == '食草' and move_type == '草':
        type_mult = 0.0

    return type_mult


# ====================================================================
#  规则集
# ====================================================================

def list_rulesets():
    """列出所有可用的规则集"""
    with open(RULESETS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    lines = []
    lines.append(f"{'='*55}")
    lines.append(f"  可用规则集 ({data['_meta']['last_updated']})")
    lines.append(f"{'='*55}")
    for rid, rs in data['rulesets'].items():
        lines.append(f"  [{rid}]")
        lines.append(f"    游戏: {rs['game']}")
        lines.append(f"    名称: {rs['name']}")
        lines.append(f"    赛季: {rs['period']}")
        lines.append(f"    格式: {rs['format']}")
        lines.append(f"    说明: {rs.get('description','')}")
        lines.append(f"    Mega进化: {'Y' if rs['rules'].get('mega_evolution') else 'N'}")
        lines.append(f"    太晶化: {'Y' if rs['rules'].get('tera_crystal') else 'N'}")
        lines.append(f"    传说禁用: {'Y' if rs['rules'].get('legendary_banned') else 'N'}")
        lines.append(f"    限制级: {rs['rules'].get('restricted_limit','0')} 只")
        if rs['rules'].get('special_notes'):
            lines.append(f"    备注: {rs['rules']['special_notes']}")
        lines.append('')
    return '\n'.join(lines)


def get_ruleset(ruleset_id):
    """获取某个规则集的详细信息"""
    with open(RULESETS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['rulesets'].get(ruleset_id)


# ====================================================================
#  测试 / 演示
# ====================================================================

if __name__ == '__main__':
    print("=" * 55)
    print("  请使用以下方式调用：")
    print("=" * 55)
    print()
    print("  from calc_damage import calc_champions_stats, calc_damage")
    print()
    print("  # 攻击方：艾路雷朵 极攻")
    print("  atk = calc_champions_stats('0475', sps={'attack':32}, nature='固执', form='一般')")
    print()
    print("  # 防御方：Mega巨金怪 满HP")
    print("  def_ = calc_champions_stats('0376', sps={'hp':32}, nature='认真', form='超级进化')")
    print()
    print("  # 锋锐修正威力：90 × 1.5 = 135")
    print("  r = calc_damage(atk, def_, move_power=135, move_category='物理',")
    print("      attacker_types=['超能力','格斗'], defender_types=['钢','超能力'],")
    print("      move_type='格斗')")
    print("  print(r['min'], '~', r['max'])")
    print()
    print("  # 规则集")
    print("  from calc_damage import list_rulesets")
    print("  print(list_rulesets())")
