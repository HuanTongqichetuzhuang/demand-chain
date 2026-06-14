import re
f = open("/app/nav.js")
content = f.read()
# Find the dc-design-inject textContent
idx = content.find("dc-design-inject")
if idx >= 0:
    section = content[idx:idx+1500]
    # Find the textContent assignment
    m = re.search(r"textContent\s*=\s*'([^']+)'", section)
    if m:
        css = m.group(1)
        print("CSS length:", len(css))
        bi = css.find("brand img")
        if bi >= 0:
            print("Found brand img at position", bi)
            print("Context:", repr(css[bi-5:bi+60]))
        else:
            print("brand img NOT FOUND in CSS!")
            # Check if brand{ exists
            bi2 = css.find("brand{")
            if bi2 >= 0:
                print("brand{ found. Next 100 chars:", repr(css[bi2:bi2+100]))
            else:
                print("brand{ NOT FOUND either!")
    else:
        print("textContent not found")
