"""Quick script to list available models on your Anthropic account."""
import os
import anthropic

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not set")
    exit(1)

client = anthropic.Anthropic(api_key=api_key)
try:
    models = client.models.list()
    print("Available models on your account:")
    for m in models.data:
        print(f"  - {m.id}  (display: {m.display_name})")
except Exception as e:
    print(f"Error: {e}")
