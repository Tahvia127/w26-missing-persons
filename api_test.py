import requests

API_KEY = "your_api_key_here"
name = "Jane Doe missing"

url = f"https://newsapi.org/v2/everything?q={name}&apiKey={API_KEY}"
response = requests.get(url)
data = response.json()

print(f"Found {data['totalResults']} articles")
for article in data['articles'][:5]:
    print(f"- {article['title']}")
