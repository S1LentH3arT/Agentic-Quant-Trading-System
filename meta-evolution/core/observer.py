#!/usr/bin/env python3
"""
元观察者 v2 — 扫描5类数据源，识别重复模式，触发进化
数据源: 扫描记录 / Agent输出 / 交易纪律 / 发现池 / 订单状态
"""
import json
import os
import re
from datetime import datetime, date
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.dirname(BASE)


class MetaObserver:
    def __init__(self, state_path=None):
        if state_path is None:
            state_path = os.path.join(BASE, 'storage', 'state.json')
        self.state_path = state_path
        self.state = self._load_state()

    def _load_state(self):
        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"observations": [], "agenda": [], "last_heartbeat": None}

    def _save_state(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    # ================================================================
    # 通用记录
    # ================================================================
    def _record(self, pattern_type: str, pattern: str, count: int = 1,
                detail: dict = None):
        for obs in self.state['observations']:
            if obs.get('pattern') == pattern:
                obs['count'] += count
                obs['last_seen'] = str(datetime.now())
                if detail:
                    obs['detail'] = detail
                return
        self.state['observations'].append({
            'type': pattern_type,
            'pattern': pattern,
            'count': count,
            'first_seen': str(datetime.now()),
            'last_seen': str(datetime.now()),
            'status': 'observing',
            'detail': detail or {}
        })

    # ================================================================
    # 源1: 扫描记录 — 评分 vs 盈亏偏差
    # ================================================================
    def scan_trade_outcomes(self):
        """扫描 scans/ 目录，检测评分与实际盈亏的偏差"""
        scans_dir = os.path.join(PROJECT, 'tdx-mcp', 'scans')
        if not os.path.exists(scans_dir):
            return

        for fname in sorted(os.listdir(scans_dir)):
            if not fname.endswith('.json') or fname.startswith('week'):
                continue
            try:
                with open(os.path.join(scans_dir, fname), encoding='utf-8') as f:
                    scan = json.load(f)
                # 检查客观指标异常
                metrics = scan.get('objective_metrics', {}).get('metrics', {})
                win_rate = metrics.get('win_rate', 0)
                if win_rate > 0 and win_rate < 0.3:
                    self._record(
                        'score_performance_gap',
                        f'低胜率: {win_rate:.0%}',
                        count=1,
                        detail={'file': fname, 'win_rate': win_rate}
                    )
            except Exception:
                pass

    # ================================================================
    # 源2: Agent输出 — 决策冲突
    # ================================================================
    def scan_agent_conflicts(self):
        """扫描 agents/output/ 检测Agent间决策冲突"""
        output_dir = os.path.join(PROJECT, 'agents', 'output')
        if not os.path.exists(output_dir):
            return

        today = date.today().isoformat()
        tech_file = os.path.join(output_dir, f'technical_{today}.json')
        deploy_file = os.path.join(output_dir, f'deployment_{today}.json')

        if os.path.exists(tech_file) and os.path.exists(deploy_file):
            try:
                with open(tech_file, encoding='utf-8') as f:
                    tech = json.load(f)
                with open(deploy_file, encoding='utf-8') as f:
                    dep = json.load(f)

                tech_qualified = tech.get('qualified_count', 0)
                dep_action = dep.get('deploy', {}).get('action', '')

                # 技术Agent有候选但调度Agent未部署
                if tech_qualified > 0 and dep_action == 'HOLD_CASH':
                    self._record(
                        'agent_conflict',
                        f'技术{tech_qualified}只合格但调度HOLD_CASH',
                        count=1,
                        detail={'tech_qualified': tech_qualified, 'deploy': dep_action}
                    )
            except Exception:
                pass

    # ================================================================
    # 源3: 交易纪律 — 重复违规
    # ================================================================
    def scan_discipline_violations(self):
        """扫描 trading_discipline.md 检测重复违规模式"""
        disc_file = os.path.join(PROJECT, 'memory', 'trading_discipline.md')
        if not os.path.exists(disc_file):
            return

        try:
            with open(disc_file, encoding='utf-8') as f:
                content = f.read()

            # 检查违规记录
            violations = re.findall(r'#[123]\s*\|\s*[\d/]+\s*\|\s*(\d+)\s*\|\s*([\d.]+)', content)
            rule_violations = Counter()
            for code, rule in violations:
                rule_violations[rule] += 1

            for rule, count in rule_violations.items():
                if count >= 2:
                    self._record(
                        'repeated_violation',
                        f'规则 {rule} 重复违规 {count} 次',
                        count=count,
                        detail={'rule': rule, 'violation_count': count}
                    )
        except Exception:
            pass

    # ================================================================
    # 源4: 发现池 — 命中率
    # ================================================================
    def scan_discovery_yield(self):
        """扫描发现池，检测入库→评分合格的转化率"""
        disc_file = os.path.join(PROJECT, 'tdx-mcp', 'discoveries', 'discovery_pool.json')
        if not os.path.exists(disc_file):
            return

        try:
            with open(disc_file, encoding='utf-8') as f:
                pool = json.load(f)

            total = len(pool)
            scored_high = sum(
                1 for v in pool.values()
                if isinstance(v, dict) and v.get('peak_score', 0) >= 6
            )

            # 盲区检测: 是否有主流板块完全缺失
            major_sectors = ['CPO', '光模块', '芯片', '半导体', '新能源', '医药']
            pool_text = json.dumps(pool, ensure_ascii=False)
            missing = [s for s in major_sectors if s not in pool_text]

            if missing:
                self._record(
                    'sector_blind_spot',
                    f'品种池缺失板块: {missing}',
                    count=len(missing),
                    detail={'missing_sectors': missing, 'pool_total': total}
                )

            # 命中率
            if total > 0 and scored_high / total < 0.1:
                self._record(
                    'low_discovery_yield',
                    f'发现池命中率低: {scored_high}/{total} ({scored_high/total:.0%})',
                    count=1,
                    detail={'scored_high': scored_high, 'total': total}
                )
        except Exception:
            pass

    # ================================================================
    # 源5: 订单延迟
    # ================================================================
    def scan_order_delays(self):
        """扫描订单文件，检测下单到成交的延迟"""
        order_file = os.path.join(PROJECT, 'tdx-mcp', 'state', 'pending_order.json')
        if not os.path.exists(order_file):
            return

        try:
            with open(order_file, encoding='utf-8') as f:
                order = json.load(f)

            ts = order.get('timestamp', '')
            action = order.get('action', '')

            if action in ('SELL', 'CLEAR'):
                self._record(
                    'pending_sell_order',
                    f'有待执行卖出订单: {order.get("symbol", "?")}',
                    count=1,
                    detail={'symbol': order.get('symbol'), 'timestamp': ts}
                )
        except Exception:
            pass

    # ================================================================
    # 源6: 日志文件 (保留原有能力)
    # ================================================================
    def scan_logs(self, log_file_path: str):
        """扫描文本日志中的错误/警告模式"""
        if not os.path.exists(log_file_path):
            return f"Log file {log_file_path} not found."

        with open(log_file_path, encoding='utf-8', errors='replace') as f:
            logs = f.readlines()

        error_patterns = []
        for line in logs:
            if any(kw in line.lower() for kw in ['error', 'fail', 'exception', 'warn', 'timeout']):
                normalized = re.sub(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}', '[TS]', line)
                normalized = re.sub(r'0x[a-fA-F0-9]+', '[HEX]', normalized)
                normalized = re.sub(r"'[^']*\.json'", '[FILE]', normalized)
                normalized = normalized.strip()
                error_patterns.append(normalized)

        counts = Counter(error_patterns)
        trends = {k: v for k, v in counts.items() if v > 1}

        for pattern, count in trends.items():
            self._record('log_error', pattern, count)

        self._save_state()
        return f"Scanned {log_file_path}. Found {len(trends)} repeating patterns."

    # ================================================================
    # 全扫描
    # ================================================================
    def scan_all(self) -> dict:
        """扫描所有5类数据源 + 日志"""
        results = {}

        methods = [
            ('trade_outcomes', self.scan_trade_outcomes),
            ('agent_conflicts', self.scan_agent_conflicts),
            ('discipline', self.scan_discipline_violations),
            ('discovery_yield', self.scan_discovery_yield),
            ('order_delays', self.scan_order_delays),
        ]

        for name, method in methods:
            try:
                before = len(self.state['observations'])
                method()
                after = len(self.state['observations'])
                results[name] = f'{after - before} new observations'
            except Exception as e:
                results[name] = f'error: {e}'

        self._save_state()

        # 检查成熟度 → 升级提案
        self._promote_mature()

        return results

    # ================================================================
    # 成熟度 → 提案升级
    # ================================================================
    def _promote_mature(self):
        """count >= 5 的观察升级为提案"""
        for obs in self.state['observations']:
            if obs.get('status') == 'observing' and obs.get('count', 0) >= 5:
                obs['status'] = 'promoted'
                proposal = {
                    'id': f"PROP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'pattern': obs['pattern'],
                    'type': obs['type'],
                    'evidence_count': obs['count'],
                    'first_seen': obs['first_seen'],
                    'last_seen': obs['last_seen'],
                    'status': 'pending_review',
                    'detail': obs.get('detail', {})
                }
                self.state['agenda'].append(proposal)

    def get_proposals(self) -> list[dict]:
        return [a for a in self.state.get('agenda', []) if a.get('status') == 'pending_review']

    def get_observations(self) -> list[dict]:
        return self.state.get('observations', [])


if __name__ == '__main__':
    o = MetaObserver()
    print('=' * 60)
    print('  MetaObserver v2 — 全扫描')
    print('=' * 60)
    results = o.scan_all()
    for src, r in results.items():
        print(f'  {src}: {r}')

    obs = o.get_observations()
    proposals = o.get_proposals()
    print(f'\n  观察: {len(obs)}条 | 提案: {len(proposals)}条')

    if obs:
        print('\n  最近观察:')
        for ob in obs[-5:]:
            t = ob.get('type', '?')
            p = ob.get('pattern', '?')
            c = ob.get('count', 0)
            print(f'    [{t}] {p} (x{c})')
