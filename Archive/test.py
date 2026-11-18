from crawler import crawl_x

sukses, pesan = crawl_x(
    x_auth_token="b3b105cc49955b4ed080637f1335a7c768b833fe",
    search_keyword="Prabowo",
    filename="testfile",
    since="2026-05-01",
    until="2026-09-25",
    lang="in",
    limit=5
)    
print("Sukses?", sukses)
print("Pesan:", pesan)