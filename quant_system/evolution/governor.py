"""
治理审计层 — 元进化系统的安全与审计骨架。
所有参数变更/因子注册/策略调整必须经过审批审计。
"""

import json
import os
from datetime import datetime
from quant_system.config import get_path, ensure_dir


class MetaGovernor:
    """进化系统治理层。审批提案、验证结果、完整审计链。"""

    def __init__(self, state_path=None, audit_path=None):
        if state_path is None:
            state_path = get_path("storage", "state", "governor_state.json")
        if audit_path is None:
            audit_path = get_path("storage", "state", "audit_log.json")
        self.state_path = state_path
        self.audit_path = audit_path
        self.state = self._load_state()

    def _load_state(self):
        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"observations": [], "agenda": [], "last_heartbeat": None}

    def _load_audit_log(self):
        try:
            with open(self.audit_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_audit_log(self, log_entry):
        ensure_dir("storage", "state")
        logs = self._load_audit_log()
        logs.append(log_entry)
        with open(self.audit_path, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

    def approve_proposal(self, proposal_id, approver="User"):
        for prop in self.state['agenda']:
            if prop['id'] == proposal_id and prop['status'] == 'pending_approval':
                prop['status'] = 'implementing'
                prop['approved_by'] = approver
                prop['approved_at'] = datetime.now().isoformat()
                self._save_state()
                self._save_audit_log({
                    "event": "PROPOSAL_APPROVED",
                    "proposal_id": proposal_id,
                    "approver": approver,
                    "timestamp": prop['approved_at']
                })
                return True
        return False

    def verify_evolution(self, proposal_id, result_success, evidence_summary):
        for prop in self.state['agenda']:
            if prop['id'] == proposal_id and prop['status'] == 'implementing':
                prop['status'] = 'verified' if result_success else 'failed'
                prop['verification_date'] = datetime.now().isoformat()
                prop['verification_evidence'] = evidence_summary
                self._save_state()
                self._save_audit_log({
                    "event": "EVOLUTION_VERIFIED",
                    "proposal_id": proposal_id,
                    "success": result_success,
                    "evidence": evidence_summary,
                    "timestamp": prop['verification_date']
                })
                return True
        return False

    def _save_state(self):
        ensure_dir("storage", "state")
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    governor = MetaGovernor()
    print("Governor initialized. System governance is active.")
