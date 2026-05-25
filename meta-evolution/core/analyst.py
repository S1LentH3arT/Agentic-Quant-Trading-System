import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import get_path
from datetime import datetime

class MetaAnalyst:
    """
    The cognitive engine that transforms observations into actionable evolution proposals.
    It evaluates 'observation maturity' and drafts structured improvement plans.
    """
    def __init__(self, state_path=None):
        if state_path is None:
            state_path = get_path("meta-evolution", "storage", "state.json")
        self.state_path = state_path
        self.state = self._load_state()
        # Threshold: How many times must a pattern be seen before it's considered a "trend" worth proposing?
        self.MATURITY_THRESHOLD = 5

    def _load_state(self):
        try:
            with open(self.state_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"observations": [], "agenda": [], "last_heartbeat": None}

    def _save_state(self):
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)

    def analyze_observations(self):
        """
        Reviews current observations and promotes mature ones to the Evolution Agenda.
        """
        promoted_count = 0
        for obs in self.state['observations']:
            if obs['status'] == 'observing' and obs['count'] >= self.MATURITY_THRESHOLD:
                self._promote_to_agenda(obs)
                promoted_count += 1

        self._save_state()
        return f"Analysis complete. Promoted {promoted_count} observations to the evolution agenda."

    def _promote_to_agenda(self, observation):
        """
        Transforms a raw observation into a structured proposal.
        """
        proposal_id = f"PROP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Initial drafting of the proposal
        proposal = {
            "id": proposal_id,
            "source_pattern": observation['pattern'],
            "evidence": {
                "occurrences": observation['count'],
                "first_seen": observation['first_seen'],
                "last_seen": observation['last_seen']
            },
            "hypothesis": "TBD - Requires LLM reasoning to determine root cause",
            "proposed_fix": "TBD - Requires LLM reasoning to design solution",
            "expected_gain": "Reduction of systemic noise and improved perception accuracy",
            "risk_level": "TBD",
            "status": "draft", # draft -> pending_approval -> implementing -> verified
            "created_at": datetime.now().isoformat()
        }

        # Update observation status to prevent duplicate promotions
        observation['status'] = 'promoted'

        # Add to the global agenda
        self.state['agenda'].append(proposal)

    def refine_proposal(self, proposal_id, hypothesis, fix, risk):
        """
        Allows the LLM (via Hermes) to fill in the cognitive details of a proposal.
        """
        for prop in self.state['agenda']:
            if prop['id'] == proposal_id:
                prop['hypothesis'] = hypothesis
                prop['proposed_fix'] = fix
                prop['risk_level'] = risk
                prop['status'] = 'pending_approval'
                self._save_state()
                return True
        return False

if __name__ == "__main__":
    analyst = MetaAnalyst()
    print("Analyst initialized. Ready to process observations.")
