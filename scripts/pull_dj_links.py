import csv
import re
import requests
from bs4 import BeautifulSoup
import logging

# Set up logging
logging.basicConfig(filename='get_tracklist_logs.txt', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

#open urls file
url = input("enter a url:")

result_urls = []
track_elements = []
# Send a GET request to the URL and get the HTML response
response = requests.get(url)
logging.debug(f"Request status code: {response.status_code}")
html_content = response.content

# Parse the HTML content using Beautiful Soup
soup = BeautifulSoup(html_content, 'html.parser')

# Find the element with ID "episode-container"
episode_containers = soup.find_all("a", {"class":"nts-grid-v2-item__header nts-app"})

urls = []
for a_tag in episode_containers:
    href = f"https://www.nts.live{a_tag.get('href')}"
    urls.append(href)

# Loop through the track elements and log their text
with open("urls.txt", 'w') as f:
    writer = csv.writer(f)
    for href in urls:
        writer.writerow([href])




