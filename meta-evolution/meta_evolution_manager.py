import json
from datetime import datetime
from core.observer import MetaObserver
from core.analyst import MetaAnalyst
from core.governor import MetaGovernor

class MetaEvolutionManager:
    """
    The Orchestrator that connects the observer, analyst, and governor.
    This is the primary interface for the Hermes Agent to interact with its evolution system.
    """
    def __init__(self):
        self.observer = MetaObserver()
        self.analyst = MetaAnalyst()
        self.governor = MetaGovernor()

    def run_heartbeat_cycle(self, target_log_path=None):
        """
        Executes a full 'Observe -> Analyze' cycle.
        Returns a summary of findings for the Agent to review.
        """
        # 1. Observation Phase
        obs_result = "No logs provided for scanning."
        if target_log_path:
            obs_result = self.observer.scan_logs(target_log_path)

        # 2. Analysis Phase
        analysis_result = self.analyst.analyze_observations()

        # 3. Check for new proposals that need LLM reasoning
        pending_drafts = [p for p in self.analyst.state['agenda'] if p['status'] == 'draft']

        summary = {
            "heartbeat_time": datetime.now().isoformat(),
            "observation_phase": obs_result,
            "analysis_phase": analysis_result,
            "new_draft_proposals": [p['id'] for p in pending_drafts],
            "total_agenda_size": len(self.analyst.state['agenda'])
        }

        return summary

    def get_proposal_details(self, proposal_id):
        """Retrieves a specific proposal for the Agent to refine."""
        for prop in self.analyst.state['agenda']:
            if prop['id'] == proposal_id:
                return prop
        return None

    def refine_and_submit(self, proposal_id, hypothesis, fix, risk):
        """The Agent uses this to apply intelligence to a draft and submit for approval."""
        success = self.analyst.refine_proposal(proposal_id, hypothesis, fix, risk)
        return "Proposal refined and submitted for approval." if success else "Proposal not found."

    def execute_approval(self, proposal_id, approver="User"):
        """The Agent calls this after the User provides approval."""
        success = self.governor.approve_proposal(proposal_id, approver)
        return "Proposal approved and moved to implementation." if success else "Approval failed."

    def finalize_evolution(self, proposal_id, success, evidence):
        """The Agent calls this after verifying the fix in the environment."""
        success_bool = str(success).lower() == 'true'
        res = self.governor.verify_evolution(proposal_id, success_bool, evidence)
        return "Evolution verified and closed." if res else "Verification failed."

if __name__ == "__main__":
    manager = MetaEvolutionManager()
    print("Hermes Meta-Evolution Manager is online.")
