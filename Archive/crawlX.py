# Import
import subprocess

# Auth token
x_auth_token = "xxx"

# Input user
keyword = input("Input keyword: ")
filename = input("Input filename: ")
since = input("Since (format YYYY-MM-DD): ")
until = input("Until (format YYYY-MM-DD): ")
lang = input("Language (in/en): ")
limit = input("Limit of tweet: ")

search_keyword = f'"{keyword}" since:{since} until:{until} lang:{lang}'

# Crawling with Tweet Harvest
command = [
    "npx", "-y", "tweet-harvest@latest",
    "-o", filename,
    "-s", search_keyword,
    "--tab", "LATEST",
    "-l", str(limit),
    "--token", x_auth_token
]

# Running
result = subprocess.run(command, capture_output=True, text=True)

if result.returncode == 0:
    print("Berhasil")
    print(result.stdout)
else:
    print("Gagal")
    print(result.stderr)