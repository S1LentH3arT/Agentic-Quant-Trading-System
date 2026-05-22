import json
import os
from datetime import datetime
from integrations.feishu.client import FeishuClient

class FeishuSyncLoop:
    """
    The automatic synchronization loop that acts as the 'Heartbeat' for Feishu.
    It handles the Pull (Receive) and Push (Send) cycle without public exposure.
    """
    def __init__(self):
        self.client = FeishuClient()
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.inbox_path = os.path.join(current_dir, "inbox.json")
        self.outbox_path = os.path.join(current_dir, "outbox.json")

    def sync(self, target_chat_id=None):
        """
        Executes a full synchronization cycle.
        """
        if target_chat_id is None:
            # Fallback to config.json
            with open(self.client.config_path, 'r') as f:
                config = json.load(f)
                target_chat_id = config.get('target_chat_id')

        if not target_chat_id or "REPLACE_WITH" in target_chat_id:
            print(f"[{datetime.now()}] Error: Valid target_chat_id not provided in config or arguments.")
            return

        print(f"[{datetime.now()}] Starting Feishu Sync Cycle for chat {target_chat_id}...")

        # 1. PULL PHASE (Receive)
        messages = self.client.fetch_unread_messages(target_chat_id)
        if isinstance(messages, list):
            self._update_inbox(messages)
            print(f"Pulled {len(messages)} messages into local inbox.")
        else:
            print(f"Pull failed: {messages}")

        # 2. PUSH PHASE (Check for pending reports)
        self._push_pending_evolutions()

    def _update_inbox(self, messages):
        inbox = []
        if os.path.exists(self.inbox_path):
            with open(self.inbox_path, 'r') as f:
                inbox = json.load(f)

        # Add new messages with timestamps
        for msg in messages:
            if msg not in inbox:
                inbox.append(msg)

        with open(self.inbox_path, 'w') as f:
            json.dump(inbox, f, indent=2)

    def _push_pending_evolutions(self):
        # This links the Feishu sync to the Meta-Evolution framework
        # If there's a 'verified' proposal, broadcast it to the Quant group.
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        state_path = os.path.join(current_dir, "..", "..", "meta-evolution", "storage", "state.json")
        if not os.path.exists(state_path): return

        with open(state_path, 'r') as f:
            state = json.load(f)

        for prop in state['agenda']:
            if prop['status'] == 'verified':
                # Send the verified evolution as a signal
                msg = f"✅ [Evolution Verified] {prop['id']}\nHypothesis: {prop['hypothesis']}\nGain: {prop['expected_gain']}"
                # For demonstration, we use a placeholder chat_id or the target_chat_id
                # self.client.send_message(prop.get('target_chat'), msg)
                pass

if __name__ == "__main__":
    syncer = FeishuSyncLoop()
    syncer.sync()
    print("Sync cycle complete.")
