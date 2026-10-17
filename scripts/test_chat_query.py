import json
import urllib.request

def test_query(prompt: str):
    print(f"\n--- Testing Query: {prompt} ---")
    req_body = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "use_tools": True,
        "temperature": 0.2
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/chat",
        data=json.dumps(req_body).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("Response Status:", resp.status)
            print("Content:\n", data.get("content"))
    except Exception as e:
        print("Error:", e)
        if hasattr(e, 'read'):
            print("Details:", e.read().decode("utf-8"))

if __name__ == "__main__":
    test_query("Which wells in Northeast Block 7 need a root-cause analysis on their pump jack?")
