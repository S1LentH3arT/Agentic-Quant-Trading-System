#!/usr/bin/env python3
"""
举一反三引擎 — 从单一经验推导多条泛化规则
泛化: 特定→通用 | 类比: 历史相似场景 | 组合: 多规则叠加
"""
import json
import os
from datetime import datetime, date
from typing import Optional

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE, 'storage')
KNOWLEDGE = os.path.join(os.path.dirname(BASE), 'knowledge')
RULES_FILE = os.path.join(KNOWLEDGE, 'rules', 'rules.json')


def load_rules() -> dict:
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {"rules": []}


def save_rules(data: dict):
    data['updated'] = str(datetime.now())
    with open(RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Deriver:
    """从输入经验推导新规则"""

    def __init__(self):
        self.derivations = []

    # ================================================================
    # 模式1: 泛化 — 特定板块规则 → 通用规则
    # ================================================================
    def generalize(self, rule_id: str, rule_text: str,
                   source_sector: str, target_sectors: list[str] = None) -> list[dict]:
        """
        从特定板块规则推导通用规则
        例: "芯片退潮反弹不追" → 检查CPO/机器人是否有同样规律
        """
        if target_sectors is None:
            target_sectors = ['CPO光模块', '机器人', '智能驾驶',
                              '玻璃基板', '绿电', 'AI通信', '电能', '算力', '液冷']

        derived = []
        for sector in target_sectors:
            if sector != source_sector:
                d = {
                    'id': f'{rule_id}_gen_{len(derived)+1}',
                    'text': f'[{sector}] {rule_text.replace(source_sector, sector)}',
                    'source': 'generalization',
                    'parent': rule_id,
                    'source_sector': source_sector,
                    'target_sector': sector,
                    'status': 'pending_validation',
                    'validation_count': 0,
                    'created': str(date.today())
                }
                derived.append(d)

        return derived

    # ================================================================
    # 模式2: 类比 — 搜索历史相似场景
    # ================================================================
    def analogize(self, current_state: dict, lookback_days: int = 180) -> list[dict]:
        """
        当前市场状态 → 搜索历史最相似的N天 → 输出后续走势
        current_state: {change_pct, volume, up_count, down_count, leading_sector}
        """
        scans_dir = os.path.join(os.path.dirname(BASE), 'tdx-mcp', 'scans')
        if not os.path.exists(scans_dir):
            return []

        analogs = []
        try:
            for fname in sorted(os.listdir(scans_dir)):
                if not fname.endswith('.json') or fname.startswith('week'):
                    continue
                with open(os.path.join(scans_dir, fname), encoding='utf-8') as f:
                    scan = json.load(f)

                metrics = scan.get('objective_metrics', {}).get('metrics', {})
                if not metrics:
                    continue

                # 相似度评分
                score = 0
                if 'change_pct' in current_state:
                    hist_chg = metrics.get('avg_change_pct', 0)
                    if abs(hist_chg - current_state['change_pct']) < 2:
                        score += 3
                if 'leading_sector' in current_state:
                    sector_data = scan.get('sector_data', {})
                    if current_state['leading_sector'] in str(sector_data):
                        score += 2

                if score >= 3:
                    analogs.append({
                        'date': fname.replace('.json', ''),
                        'similarity_score': score,
                        'metrics': metrics,
                        'scan_summary': scan.get('summary', '')
                    })

            analogs.sort(key=lambda x: x['similarity_score'], reverse=True)
        except Exception:
            pass

        return analogs[:3]

    # ================================================================
    # 模式3: 组合 — 多条规则同时触发时推导新规则
    # ================================================================
    def combine(self, triggered_rules: list[dict]) -> Optional[dict]:
        """
        两个独立规则同时触发 → 推导组合规则
        例: "退潮" + "红盘>3500" → 虚假繁荣，强烈不参与
        """
        if len(triggered_rules) < 2:
            return None

        r1, r2 = triggered_rules[0], triggered_rules[1]

        combined = {
            'id': f'{r1["id"]}_{r2["id"]}_combo',
            'text': f'组合信号: [{r1["text"]}] + [{r2["text"]}] → 叠加效应，需综合判断',
            'source': 'combination',
            'parents': [r1['id'], r2['id']],
            'trigger_condition': f'当 {r1["id"]} 和 {r2["id"]} 同时触发时',
            'status': 'pending_validation',
            'validation_count': 0,
            'created': str(date.today())
        }
        return combined

    # ================================================================
    # 主推导流程
    # ================================================================
    def derive_all(self, new_experience: dict = None) -> dict:
        """
        对所有活跃规则运行举一反三
        new_experience: 用户刚输入的新经验（可选）
        """
        rules_data = load_rules()
        all_rules = rules_data.get('rules', [])

        results = {
            'generalizations': [],
            'analogs': [],
            'combinations': [],
            'new_rules_added': 0
        }

        # 1. 对新经验立即泛化
        if new_experience:
            sector = new_experience.get('sector', '一般')
            text = new_experience.get('text', '')
            rule_id = new_experience.get('id', f'R{len(all_rules)+1:03d}')

            gens = self.generalize(rule_id, text, sector)
            for g in gens:
                all_rules.append(g)
                results['new_rules_added'] += 1
            results['generalizations'] = [g['text'] for g in gens]

        # 2. 对现有的活跃规则两两组合
        active = [r for r in all_rules if r.get('status') == 'active']
        for i in range(len(active)):
            for j in range(i+1, len(active)):
                combo = self.combine([active[i], active[j]])
                if combo and combo['id'] not in [r.get('id', '') for r in all_rules]:
                    all_rules.append(combo)
                    results['new_rules_added'] += 1
                    results['combinations'].append(combo['text'])

        rules_data['rules'] = all_rules
        rules_data['total_active'] = sum(1 for r in all_rules if r.get('status') == 'active')
        rules_data['total_pending'] = sum(1 for r in all_rules if r.get('status') == 'pending_validation')
        save_rules(rules_data)

        self.derivations.append({
            'timestamp': str(datetime.now()),
            'input': new_experience,
            'results': results
        })

        return results


if __name__ == '__main__':
    d = Deriver()

    # 测试: 模拟输入新经验
    test_exp = {
        'id': 'R009',
        'text': 'CPO光模块连续3日净流入后第4日大概率回调',
        'sector': 'CPO光模块'
    }

    print('=== 举一反三引擎 测试 ===')
    results = d.derive_all(test_exp)
    print(f"泛化: {results['generalizations']}")
    print(f"组合: {results['combinations'][:3]}")
    print(f"新增规则: {results['new_rules_added']}条")

    rules = load_rules()
    print(f"\n规则库: {rules['total_active']}活跃 + {rules['total_pending']}待验证")
