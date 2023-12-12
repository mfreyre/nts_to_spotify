import requests
import json

# url = input("enter url:")
offset = "0"
limit = "12"
show_name = input("show name:")
url = f"https://www.nts.live/api/v2/shows/{show_name}/episodes?limit={limit}&offset={offset}"

def getResults(url):
    response = requests.get(url, headers=headers)
    decoded_content = response.content.decode('utf-8')  # decode byte string into a string using utf-8 encoding
    json_data = json.loads(decoded_content)  # parse JSON string into a Python object
    return json_data["results"]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

episodes = []
results = getResults(url)
while (len(results) > 0):
    for result in results:
        episodes.append(result["episode_alias"])
    offset = str(int(offset) + 12)
    url = f"https://www.nts.live/api/v2/shows/{show_name}/episodes?limit={limit}&offset={offset}"
    results = getResults(url)
    print(url)

print(episodes)
# Append the episodes to a file
episode_slug = f"https://www.nts.live/shows/{show_name}/episodes/"
with open("episodes.txt", "a") as file:
    for episode in episodes:
        file.write(episode_slug + episode + "\n")
