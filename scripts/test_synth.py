import httpx
import json
import os

key = os.getenv("GEMINI_API_KEY", "")
url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}'

payload = {
    'contents': [
        {'role': 'user', 'parts': [{'text': 'What tables exist?'}]},
        {'role': 'model', 'parts': [{'functionCall': {'name': 'list_tables', 'args': {}}}]},
        {'role': 'user', 'parts': [{'functionResponse': {'name': 'list_tables', 'response': {'output': json.dumps({'tables': ['wells', 'inspections']})}}}]}
    ]
}

r = httpx.post(url, json=payload, timeout=15.0)
print('Status:', r.status_code)
if r.status_code == 200:
    cand = r.json()['candidates'][0]['content']['parts']
    for p in cand:
        if 'text' in p:
            print('Text:', p['text'])
else:
    print('Error:', r.text)
