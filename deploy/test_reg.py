import urllib.request, json, sys

for i in range(6):
    email = f'test{i}@test.com'
    data = json.dumps({'email': email, 'name': f'Test{i}', 'password': 'test123', 'country': '中国'}).encode()
    req = urllib.request.Request('http://8.154.26.92:8080/api/register',
        data=data, headers={'Content-Type': 'application/json'})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        body = json.loads(r.read())
        msg = body.get('message') or body.get('error') or str(body)
        print(f'{i+1}: {r.status} - {msg[:60]}')
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
        msg = body.get('detail') or body.get('error') or str(body)
        print(f'{i+1}: {e.code} - {msg[:60]}')
    except Exception as e:
        print(f'{i+1}: ERROR - {e}')
