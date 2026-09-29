"""Re-authenticate both accounts after token deletion."""
import sys
sys.path.insert(0, ".")

from auth import get_credentials, _load_config

config = _load_config()

for account_name in config["accounts"]:
    print(f"\nAuthenticating '{account_name}' ({config['accounts'][account_name]['email']})...")
    print("A browser window will open. Please sign in and grant permissions.")
    creds = get_credentials(account_name)
    print(f"  OK! Token saved.")

print("\nDone! Both accounts re-authenticated.")
