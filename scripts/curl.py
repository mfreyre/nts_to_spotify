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



episode_slug = f"https://www.nts.live/shows/{show_name}/episodes/"
# Initialize an empty dictionary
d = {}

# Iterate over each string in the list
for s in episodes:
    # Extract the last 4 digits using string slicing
    year = s[-4:]

    # Add the string to the dictionary for this year
    if year in d:
        d[year].append(f"{episode_slug}{s}")
    else:
        d[year] = [f"{episode_slug}{s}"]


# Write each group of lines to a new file
for year, lines in d.items():
    print(f"python cli_get_tracks.py by_year/{year}.txt {show_name}_{year}")
    # Construct the output file name based on the year
    output_file_name = f"by_year/{year}.txt"

    # Write the lines to the output file
    with open(output_file_name, "w") as output_file:
        for line in lines:
            output_file.write(line+"\n")

# with open("episodes.txt", "a") as file:
#     for episode in episodes:
#         file.write(episode_slug + episode + "\n")
