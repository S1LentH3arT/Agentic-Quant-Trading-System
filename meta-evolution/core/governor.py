import json
import os
from datetime import datetime

class MetaGovernor:
    """
    The legal and safety layer of the evolution system.
    Ensures that no 'evolution' happens without approval, and all changes are audited.
    """
    def __init__(self, state_path="F:/working-project/meta-evolution/storage/state.json", audit_path="F:/working-project/meta-evolution/storage/audit_log.json"):
        self.state_path = state_path
        self.audit_path = audit_path
        self.state = self._load_state()

    def _load_state(self):
        try:
            with open(self.state_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"observations": [], "agenda": [], "last_heartbeat": None}

    def _load_audit_log(self):
        try:
            with open(self.audit_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_audit_log(self, log_entry):
        logs = self._load_audit_log()
        logs.append(log_entry)
        with open(self.audit_path, 'w') as f:
            json.dump(logs, f, indent=2)

    def approve_proposal(self, proposal_id, approver="User"):
        """
        Moves a proposal from 'pending_approval' to 'implementing'.
        """
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
        """
        Finalizes the evolution process by verifying the fix and closing the loop.
        """
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
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)

if __name__ == "__main__":
    governor = MetaGovernor()
    print("Governor initialized. System governance is active.")
