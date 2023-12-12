import csv
import requests
from bs4 import BeautifulSoup
import logging

# Set up logging
logging.basicConfig(filename='get_tracklist_logs.txt', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
url = input("enter a url: ")
# url = "https://www.nts.live/shows/jazmin-garcia/episodes/como-la-flor-w-jazmin-17th-february-2020"
csv_title = input("enter a title: ")
csv_title = csv_title + ".csv"
logging.debug(f"csv title is {csv_title}")

# Send a GET request to the URL and get the HTML response
response = requests.get(url)
logging.debug(f"Request status code: {response.status_code}")
html_content = response.content

# Parse the HTML content using Beautiful Soup
soup = BeautifulSoup(html_content, 'html.parser')

# Find the element with ID "episode-container"
episode_container = soup.find(id="episode-container")

# Find all the elements with class "track" inside the heading element
track_elements = episode_container.find_all(class_="track")

# Loop through the track elements and log their text
with open(f"../unread_csvs/{csv_title}", 'w') as f:
    writer = csv.writer(f)
    writer.writerow(["TITLE", "ARTIST"])
    for track_element in track_elements:
        artist = track_element.find(class_="track__artist").text.strip()
        logging.debug(f"artist: {artist}")
        title = track_element.find(class_="track__title").text.strip()
        logging.debug(f"title: {title}")
        writer.writerow([title, artist])

