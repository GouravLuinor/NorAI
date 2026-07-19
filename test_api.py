import requests

lecture_id = "default"
url = f"http://127.0.0.1:8000/threads?lecture_id={lecture_id}"
headers = {"Content-Type": "application/json"}
payload = {"thread_id": "my-custom-id-999"}

r = requests.post(url, json=payload, headers=headers)
print(r.status_code)
print(r.json())
