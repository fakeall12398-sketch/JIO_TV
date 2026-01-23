import requests

url = "https://jiotvapi.cdn.jio.com/apis/v1.3/getepg/get"
params = {"channel_id": "101", "offset": 0}

r = requests.get(url, params=params, headers={
    "User-Agent": "Mozilla/5.0 (Linux; Android 13)",
    "Referer": "https://www.jiotv.com/",
    "Origin": "https://www.jiotv.com",
})

print(r.status_code)
print(r.text[:200])
