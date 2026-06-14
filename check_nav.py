f = open('/app/nav.js')
c = f.read()
i = c.find('dc-design-inject')
s = c[i:i+2000]
j = s.find('textContent')
part = s[j:]
print(repr(part[:400]))
