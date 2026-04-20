import asyncio
import httpx
import os
import sys

# Add src to path
sys.path.append(os.getcwd())
from src.config import HF_API_KEY

async def test_model(model_id):
    print(f"Testing {model_id}...")
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": "Salut"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(api_url, headers=headers, json=payload)
            if resp.status_code == 200:
                print(f"✅ SUCCESS: {model_id} is active!")
                return True
            elif resp.status_code == 503:
                print(f"⏳ LOADING: {model_id} is available but loading.")
                return True
            else:
                print(f"❌ FAILED {resp.status_code}: {resp.text[:100]}")
                return False
    except Exception as e:
        print(f"⚠️ ERROR: {e}")
        return False

async def main():
    models = [
        "google/gemma-2-2b-it",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "HuggingFaceH4/zephyr-7b-beta",
        "microsoft/Phi-3-mini-4k-instruct",
        "google/gemma-1.1-2b-it"
    ]
    for m in models:
        if await test_model(m):
            print(f"\nWe should use: {m}")
            break

if __name__ == "__main__":
    asyncio.run(main())
