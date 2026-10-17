import json
import httpx

def run():
    payload = {
        "messages": [
            {"role": "user", "content": "Which well produced the most oil in 2026?"}
        ],
        "stream": True,
        "use_tools": True
    }
    with httpx.Client(timeout=60.0) as client:
        with client.stream("POST", "http://127.0.0.1:8000/chat", json=payload) as response:
            print("Status:", response.status_code, flush=True)
            for line in response.iter_lines():
                if line:
                    print(line, flush=True)

if __name__ == "__main__":
    run()
