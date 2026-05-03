"""
宝可梦 Gen 9 伤害计算模块
基于神奇宝贝百科公式实现，配合 pokemon.db 使用
"""
import sqlite3
import json
import math
import random

DB_PATH = r'D:\astrbot\databasepoke\pokemon.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== 能力值计算 ====================

def calc_stat(base, iv=31, ev=0, level=50, nature_mult=1.0, is_hp=False):
    """计算单项能力值"""
    if is_hp:
        return ((base * 2 + iv + ev // 4) * level // 100) + level + 10
    else:
        return ((base * 2 + iv + ev // 4) * level // 100 + 5) * nature_mult

def calc_all_stats(pokedex_id, level=50, ivs=None, evs=None, nature="认真", form="一般"):
    """
    计算宝可梦全部六项能力值（朱紫规则）

    Args:
        pokedex_id: 图鉴编号
        level: 等级
        ivs: dict, 如 {'hp':31, 'attack':31, ...}
        evs: dict, 如 {'hp':252, 'attack':252, ...}
        nature: 性格名称
        form: 形态名称
    """
    if ivs is None:
        ivs = {s:31 for s in ['hp','attack','defense','sp_attack','sp_defense','speed']}
    if evs is None:
        evs = {s:0 for s in ['hp','attack','defense','sp_attack','sp_defense','speed']}
    
    conn = get_db()
    cur = conn.cursor()
    
    # 获取种族值
    cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats WHERE pokedex_id=? AND form=?", (pokedex_id, form))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        # 尝试不限制形态
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats WHERE pokedex_id=? LIMIT 1", (pokedex_id,))
        row = cur.fetchone()
        conn.close()
    
    if not row:
        return None
    
    bases = dict(row)
    
    # 性格修正
    nature_mods = _get_nature_mods(nature)
    
    stats = {}
    stat_names = ['hp','attack','defense','sp_attack','sp_defense','speed']
    for s in stat_names:
        is_hp = (s == 'hp')
        stats[s] = calc_stat(bases[s], ivs.get(s,31), evs.get(s,0), level, 
                             nature_mods.get(s, 1.0), is_hp)
    
    # 也返回原始种族值供参考
    stats['_bases'] = bases
    stats['_level'] = level
    stats['_pokedex_id'] = pokedex_id
    return stats

def _get_nature_mods(nature):
    """返回性格修正倍率 dict"""
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

# ==================== 伤害计算 ====================

def calc_damage(attacker_stats, defender_stats, move_power, move_category,
                attacker_types=None, defender_types=None,
                move_type=None, is_critical=False,
                weather=None, terrain=None, is_burned=False,
                screens=0, help_active=False, charge_active=False,
                multi_target=False, items=None, abilities=None,
                tera_type=None, random_roll=None):
    """
    完整伤害计算
    
    Args:
        attacker_stats: calc_all_stats 返回的攻击方能力值 dict
        defender_stats: calc_all_stats 返回的防御方能力值 dict
        move_power: 招式威力
        move_category: '物理' 或 '特殊'
        attacker_types: 攻击方属性列表 e.g. ['草','毒']
        defender_types: 防御方属性列表 e.g. ['草','毒']
        move_type: 招式属性
        is_critical: 是否击中要害
        weather: None / 'sun' / 'rain' / 'sand' / 'snow'
        terrain: None / 'electric' / 'psychic' / 'grassy' / 'misty'
        is_burned: 攻击方是否灼伤
        screens: 0=none, 1=单打, 2=双打
        help_active: 是否处于帮助状态
        charge_active: 是否处于充电状态（仅电招式）
        multi_target: 是否攻击多个目标
        items: 道具影响 dict e.g. {'attacker': '讲究头带', 'defender': '抗火果'}
        abilities: 特性影响 dict e.g. {'attacker': '大力士', 'defender': '厚脂肪'}
        tera_type: 太晶属性（如有）
        random_roll: 随机数，不传则自动生成 0.85~1.00
    
    Returns:
        dict: {'min': min_damage, 'max': max_damage, 'rolls': [damage_list]}
    """
    level = attacker_stats.get('_level', 50)
    
    # 确定攻击/防御能力值
    if move_category == '物理':
        atk = attacker_stats['attack']
        dfs = defender_stats['defense']
    else:  # 特殊
        atk = attacker_stats['sp_attack']
        dfs = defender_stats['sp_defense']
    
    # 特殊情况：欺诈（用防御方的攻击）
    # 调用者自行处理，这里不实现
    
    # --- 基础伤害 ---
    step1 = (2 * level // 5 + 2)  # 向下取整
    step2 = step1 * move_power * atk // dfs  # 向下取整
    base_dmg = step2 // 50 + 2  # 向下取整
    
    # --- 其他加成计算 ---
    other_mod = 1.0
    
    # 道具
    _items = items or {}
    a_item = _items.get('attacker')
    d_item = _items.get('defender')
    
    if a_item in ['木炭','奇迹种子','神秘水滴','不融冰','磁铁','锐利鸟嘴',
                   '银粉','软沙','硬石头','诅咒之符','龙之牙','黑色眼镜',
                   '金属膜','毒针','丝绸围巾']:
        other_mod *= 1.2
    elif a_item in ['讲究头带','讲究眼镜','讲究围巾']:
        other_mod *= 1.5  # 对应能力变化，实际上更复杂，简化处理
    elif a_item == '生命宝珠':
        other_mod *= 1.3
    elif a_item == '达人带':
        # 需要属性相克 > 1 才生效，后面判断
        pass
    
    # 特性 - 简化处理常见特性
    _abilities = abilities or {}
    
    if _abilities.get('attacker') == '大力士':
        other_mod *= 2.0
    
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
    
    # 灼伤
    if is_burned and move_category == '物理' and _abilities.get('attacker') != '毅力':
        other_mod *= 0.5
    
    # 墙壁
    if screens == 1:  # 单打
        other_mod *= 0.5
    elif screens == 2:  # 双打
        other_mod *= 2/3
    
    # 帮助
    if help_active:
        other_mod *= 1.5
    
    # 充电
    if charge_active and move_type == '电':
        other_mod *= 2.0
    
    # 多目标
    if multi_target:
        other_mod *= 0.75
    
    # 击中要害
    crit_mod = 1.5 if is_critical else 1.0
    if is_critical and _abilities.get('attacker') == '狙击手':
        crit_mod = 2.25
    
    # --- 第一步：其他加成 × 击中要害倍率，五捨六入 ---
    step_a = _bankers_round(other_mod * crit_mod)
    
    # 属性相克
    type_mult = 1.0
    if attacker_types and defender_types and move_type:
        # 从数据库获取属性相克倍率（用防御方 pokedex_id 最准确）
        def_pokedex_id = defender_stats.get('_pokedex_id')
        type_mult = _get_type_effectiveness(move_type, defender_types, def_pokedex_id)
    
    # 达人带：属性效果绝佳时生效
    if a_item == '达人带' and type_mult > 1.0:
        step_a = _bankers_round(step_a * 1.2)
    
    # 厚脂肪
    if _abilities.get('defender') == '厚脂肪' and move_type in ('火','冰'):
        step_a = _bankers_round(step_a * 0.5)
    
    # 坚硬岩石
    if _abilities.get('defender') == '坚硬岩石' and type_mult > 1.0:
        step_a = _bankers_round(step_a * 0.75)
    
    # 多重鳞片 / 幻影防守
    if _abilities.get('defender') in ('多重鳞片', '幻影防守'):
        step_a = _bankers_round(step_a * 0.5)
    
    # STAB
    stab = 1.5 if (move_type and attacker_types and move_type in attacker_types) else 1.0
    
    # 太晶化 STAB
    if tera_type:
        if move_type == tera_type:
            if move_type in (attacker_types or []):
                stab = 2.0  # 太晶属性与原有属性相同
            else:
                stab = 1.5  # 太晶属性与原有属性不同
    
    # --- 计算伤害范围 ---
    def calc_dmg_with_roll(roll_val):
        # 第二步：随机数 向下取整
        step_b = base_dmg * step_a * roll_val // 1
        # 第三步：STAB 五捨六入
        step_c = _bankers_round(step_b * stab)
        # 第四步：属性相克 向下取整
        if type_mult == 0:
            return 0
        final = int(step_c * type_mult)
        return max(1, final)
    
    # 生成所有可能的伤害值（随机数 85~100 共16种）
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

def _bankers_round(val):
    """五捨六入（宝可梦特殊取整规则）"""
    # 小数部分 >= 0.6 则进位，否则舍去
    return math.floor(val) if (val - math.floor(val)) < 0.6 else math.ceil(val)

def _get_type_effectiveness(move_type, defender_types, defender_pokedex_id=None):
    """从数据库获取属性相克倍率
    
    用 pokemon_type_effectiveness 表中存储的每个宝可梦的完整倍率
    （该表已经将双属性合并计算好了）
    """
    if not defender_pokedex_id:
        # 如果没有pokedex_id，回退到类型查询
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
    
    # 直接用 pokedex_id 查（最准确，已合并双属性）
    conn = get_db()
    cur = conn.cursor()
    # 优先查基础形态(form='')，否则取第一条
    cur.execute("""
        SELECT multiplier FROM pokemon_type_effectiveness 
        WHERE pokedex_id=? AND defending_type=? AND multiplier IS NOT NULL
        ORDER BY CASE WHEN form='' THEN 0 ELSE 1 END, form
        LIMIT 1
    """, (defender_pokedex_id, move_type))
    row = cur.fetchone()
    conn.close()
    return row['multiplier'] if row else 1.0

# ==================== 便捷查询 ====================

def get_pokemon_info(name_or_id):
    """获取宝可梦基本信息"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT p.*, pf.type1, pf.type2, pf.ability1, pf.ability2, pf.hidden_ability
        FROM pokemon p
        JOIN pokemon_forms pf ON p.pokedex_id = pf.pokedex_id
        WHERE p.name_zh = ? OR p.pokedex_id = ?
        LIMIT 1
    """, (name_or_id, name_or_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_move_info(move_name):
    """获取招式信息"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM moves WHERE name_zh=?", (move_name,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def quick_calc(attacker_name, move_name, defender_name, level=50,
               atk_iv=31, atk_ev=252, def_iv=31, def_ev=252,
               nature='固执', weather=None, terrain=None,
               is_critical=False, screens=0):
    """
    快速伤害计算（一键调用）
    
    示例：
        quick_calc('喷火龙', '喷射火焰', '妙蛙种子')
    """
    # 获取攻击方信息
    atk_info = get_pokemon_info(attacker_name)
    if not atk_info:
        return f"找不到宝可梦: {attacker_name}"
    
    def_info = get_pokemon_info(defender_name)
    if not def_info:
        return f"找不到宝可梦: {defender_name}"
    
    move_info = get_move_info(move_name)
    if not move_info:
        return f"找不到招式: {move_name}"
    
    # 计算能力值
    atk_stats = calc_all_stats(atk_info['pokedex_id'], level,
                               evs={'hp':0,'attack':atk_ev,'defense':0,'sp_attack':0,'sp_defense':0,'speed':0},
                               nature=nature)
    def_stats = calc_all_stats(def_info['pokedex_id'], level,
                               evs={'hp':0,'attack':0,'defense':def_ev,'sp_attack':0,'sp_defense':def_ev,'speed':0},
                               nature='认真')
    
    if not atk_stats or not def_stats:
        return "计算能力值失败"
    
    # 伤害计算
    result = calc_damage(
        atk_stats, def_stats,
        move_power=int(move_info.get('power', 0) or 0),
        move_category=move_info.get('category', '特殊'),
        attacker_types=[t for t in [atk_info.get('type1'), atk_info.get('type2')] if t],
        defender_types=[t for t in [def_info.get('type1'), def_info.get('type2')] if t],
        move_type=move_info.get('type'),
        is_critical=is_critical,
        weather=weather,
        terrain=terrain,
        screens=screens,
    )
    
    if not result:
        return "计算伤害失败"
    
    # 格式化输出
    lines = []
    lines.append(f"{'='*50}")
    lines.append(f"  {atk_info['name_zh']} Lv.{level} → {def_info['name_zh']} Lv.{level}")
    lines.append(f"  招式: {move_name} ({move_info.get('type','?')}/{move_info.get('category','?')} 威力{move_info.get('power','?')})")
    lines.append(f"{'='*50}")
    lines.append(f"  攻击方 {atk_info['name_zh']}:")
    for s in ['hp','attack','defense','sp_attack','sp_defense','speed']:
        lines.append(f"    {s}: {atk_stats[s]}")
    lines.append(f"  防御方 {def_info['name_zh']}:")
    for s in ['hp','attack','defense','sp_attack','sp_defense','speed']:
        lines.append(f"    {s}: {def_stats[s]}")
    lines.append(f"{'='*50}")
    lines.append(f"  STAB: x{result['stab']}")
    lines.append(f"  属性相克: x{result['type_mult']}")
    lines.append(f"  其他加成: x{result['other_mod']}")
    lines.append(f"  基础伤害: {result['base_damage']}")
    lines.append(f"{'='*50}")
    lines.append(f"  伤害范围: {result['min']} ~ {result['max']}")
    lines.append(f"  16种可能: {result['rolls']}")
    
    # 判断击杀
    target_hp = def_stats['hp']
    lines.append(f"  防御方HP: {target_hp}")
    if result['min'] >= target_hp:
        lines.append(f"  >> 确一 (OHKO)")
    elif result['max'] >= target_hp:
        lines.append(f"  >> 乱一 (乱数击杀)")
    else:
        hits_needed = (target_hp + result['max'] - 1) // result['max']
        lines.append(f"  >> 需要 {hits_needed} 次击杀")
    
    lines.append(f"{'='*50}")
    return '\n'.join(lines)


# ==================== 测试 ====================

# ==================== Champions 能力值计算 ====================

def calc_champions_stats(pokedex_id, sps=None, nature="认真", form="一般"):
    """
    Champions SP系统能力值计算（固定 Lv.50, IV=31）
    
    公式: (种族值 + SP + 20) × 性格修正  (非HP)
          (种族值 + SP + 75)              (HP)
    
    Args:
        pokedex_id: 图鉴编号
        sps: dict, 如 {'hp':32, 'attack':32, ...}  默认全为0
        nature: 性格名称
    """
    if sps is None:
        sps = {s:0 for s in ['hp','attack','defense','sp_attack','sp_defense','speed']}
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats WHERE pokedex_id=? AND form=?", (pokedex_id, form))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT hp, attack, defense, sp_attack, sp_defense, speed FROM pokemon_stats WHERE pokedex_id=? LIMIT 1", (pokedex_id,))
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


# ==================== Champions 快速计算 ====================

def quick_calc_champions(attacker_name, move_name, defender_name,
                         atk_sp=32, spd_sp=32, def_sp=0, hp_sp=0, sdef_sp=0,
                         nature='固执', def_nature='认真',
                         item=None, weather=None, terrain=None,
                         is_critical=False, screens=0):
    """
    Champions SP系统 一键伤害计算
    
    示例:
        quick_calc_champions('海豚侠', '喷射拳', '喷火龙', atk_sp=32, item='神秘水滴')
    """
    atk_info = get_pokemon_info(attacker_name)
    def_info = get_pokemon_info(defender_name)
    move_info = get_move_info(move_name)
    
    if not atk_info: return f"找不到: {attacker_name}"
    if not def_info: return f"找不到: {defender_name}"
    if not move_info: return f"找不到招式: {move_name}"
    
    # 道具提升招式威力
    move_power = int(move_info.get('power', 0) or 0)
    TYPE_ITEMS = ['木炭','奇迹种子','神秘水滴','不融冰','磁铁','锐利鸟嘴',
                  '银粉','软沙','硬石头','诅咒之符','龙之牙','黑色眼镜',
                  '金属膜','毒针','丝绸围巾']
    if item in TYPE_ITEMS:
        move_power = int(move_power * 1.2)
    elif item == '生命宝珠':
        pass  # 命玉在伤害公式里作为 other_mod
    
    atk_stats = calc_champions_stats(atk_info['pokedex_id'],
        sps={'hp':0,'attack':atk_sp,'defense':0,'sp_attack':0,'sp_defense':0,'speed':spd_sp},
        nature=nature)
    def_stats = calc_champions_stats(def_info['pokedex_id'],
        sps={'hp':hp_sp,'attack':0,'defense':def_sp,'sp_attack':0,'sp_defense':sdef_sp,'speed':0},
        nature=def_nature)
    
    result = calc_damage(atk_stats, def_stats,
        move_power=move_power,
        move_category=move_info.get('category','物理'),
        attacker_types=[t for t in [atk_info.get('type1'),atk_info.get('type2')] if t],
        defender_types=[t for t in [def_info.get('type1'),def_info.get('type2')] if t],
        move_type=move_info.get('type'),
        is_critical=is_critical, weather=weather, terrain=terrain, screens=screens)
    
    hp = def_stats['hp']
    lines = [
        f"{'='*50}",
        f"  {atk_info['name_zh']} → {def_info['name_zh']}  [Champions]",
        f"  招式: {move_name} ({move_info.get('type','?')}/{move_info.get('category','?')} 威力{move_power})",
        f"  攻: Atk{atk_stats['attack']} SpA{atk_stats['sp_attack']}",
        f"  防: HP{hp} Def{def_stats['defense']} SpD{def_stats['sp_defense']}",
        f"  STAB×{result['stab']} 相克×{result['type_mult']}",
        f"  范围: {result['min']}~{result['max']}  {result['rolls']}",
    ]
    if result['min'] >= hp:
        lines.append(f"  >> 确一 (OHKO)")
    elif result['max'] >= hp:
        pct = sum(1 for d in result['rolls'] if d>=hp)/len(result['rolls'])*100
        lines.append(f"  >> 乱一 ({pct:.0f}%)")
    else:
        lines.append(f"  >> 需要 {(hp+result['max']-1)//result['max']} 次")
    lines.append(f"{'='*50}")
    return chr(10).join(lines)


# ==================== 纯数值伤害计算接口 ====================

def calc_damage_raw(level, attack, defense, move_power,
                    stab=1.5, type_effectiveness=1.0,
                    other_mod=1.0, is_critical=False):
    """
    纯数值伤害计算——所有参数由调用方（大模型+SQL）准备。
    
    Args:
        level:              攻击方等级 (Champions固定50, 朱紫任意)
        attack:             攻击方实际攻击/特攻能力值
        defense:            防御方实际防御/特防能力值
        move_power:         招式威力（已计入道具加成如神秘水滴×1.2）
        stab:               属性一致加成 (默认1.5)
        type_effectiveness: 属性相克倍率 (0, 0.25, 0.5, 1.0, 2.0, 4.0)
        other_mod:          其他加成乘积 (天气/场地/墙壁/特性等)
        is_critical:        是否击中要害
    
    Returns:
        dict: {'min': int, 'max': int, 'rolls': [16种可能], 'base_damage': int}
    
    使用流程见 workflow_calc_damage.md
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


# ==================== 能力值计算（朱紫） ====================

RULESETS_PATH = 'D:/astrbot/databasepoke/rulesets.json'

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
        lines.append(f"    Mega进化: {'✅' if rs['rules'].get('mega_evolution') else '❌'}")
        lines.append(f"    太晶化: {'✅' if rs['rules'].get('tera_crystal') else '❌'}")
        lines.append(f"    传说禁用: {'✅' if rs['rules'].get('legendary_banned') else '❌'}")
        lines.append(f"    限制级: {rs['rules'].get('restricted_limit','0')} 只")
        if rs['rules'].get('special_notes'):
            lines.append(f"    备注: {rs['rules']['special_notes']}")
        lines.append('')
    return chr(10).join(lines)

def get_ruleset(ruleset_id):
    """获取某个规则集的详细信息"""
    with open(RULESETS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['rulesets'].get(ruleset_id)


if __name__ == '__main__':
    # 测试：喷火龙 喷射火焰 打 妙蛙种子
    print(quick_calc('喷火龙', '喷射火焰', '妙蛙种子', level=50, nature='内敛'))
    print()
    # 测试：物攻向
    print(quick_calc('纸御剑', '叶刃', '妙蛙花', level=50, nature='固执'))
    print()
    # 测试：规则集列表
    print(list_rulesets())
