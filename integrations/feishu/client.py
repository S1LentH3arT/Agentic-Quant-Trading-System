import requests
import json
import os
from datetime import datetime

class FeishuClient:
    """
    A bridge for Hermes Quant Commander to interact with Feishu.
    Implements a PULL-based mechanism to ensure zero public exposure.
    """
    def __init__(self, config_path=None):
        if config_path is None:
            # Use relative path to allow running on physical machine regardless of root folder
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "config.json")

        self.config_path = config_path
        self.load_config()
        self.token = None
        self.token_expires_at = 0

    def load_config(self):
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        self.app_id = self.config['app_id']
        self.app_secret = self.config['app_secret']
        self.api_base = self.config['api_base']

    def get_tenant_access_token(self):
        """Authenticates with Feishu to get a temporary access token."""
        url = f"{self.api_base}/auth/v3/app_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            res_json = response.json()
            self.token = res_json.get("app_access_token")
            # Feishu tokens usually last 2 hours. We'll refresh every 70 minutes to be safe.
            self.token_expires_at = datetime.now().timestamp() + (70 * 60)
            return self.token
        except Exception as e:
            return f"Auth failed: {str(e)}"

    def _ensure_token(self):
        """Ensure token exists and is not expired."""
        if not self.token or datetime.now().timestamp() >= self.token_expires_at:
            self.get_tenant_access_token()
        return self.token

    def send_message(self, receive_id, content):
        """Push a message to Feishu."""
        token = self._ensure_token()
        if "Auth failed" in token: return token

        url = f"{self.api_base}/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        payload = {"receive_id": receive_id, "msg_type": "text", "content": json.dumps({"text": content})}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 401: # Handle unexpected token expiration
                self.get_tenant_access_token()
                return self.send_message(receive_id, content)
            response.raise_for_status()
            return True
        except Exception as e:
            return f"Error: {str(e)}"

    def fetch_unread_messages(self, chat_id):
        """
        Pull messages from a specific chat using the correct search API.
        """
        token = self._ensure_token()
        if "Auth failed" in token: return token

        # Fixed API: Use /im/v1/messages/search/all to find messages in a chat
        url = f"{self.api_base}/im/v1/messages/search/all"
        params = {
            "chat_id": chat_id,
            "page_size": 20,
            "cursor": {"type": "time", "value": int(datetime.now().timestamp() * 1000)} # Example: pull recent
        }
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 401:
                self.get_tenant_access_token()
                return self.fetch_unread_messages(chat_id)
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("items", [])
        except Exception as e:
            return f"Fetch failed: {str(e)}"

if __name__ == "__main__":
    client = FeishuClient()
    print("Feishu Pull-Client initialized.")
