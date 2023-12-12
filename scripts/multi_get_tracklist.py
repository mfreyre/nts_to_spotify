from unidecode import unidecode
import csv
import re
import requests
from bs4 import BeautifulSoup
import logging

def clean_string(s):
    # Remove any parentheses and their contents
    s = unidecode(s)
    s = s.lower()
    # s = re.sub(r'\([^)]*\)', '', s)
    # s = re.sub(r'[^a-zA-Z0-9\s]', '', s)
    # Remove any extra spaces
    # s = re.sub(r'\s+', ' ', s).strip()
    # Remove "ft" and anything that comes after it
    s = re.sub(r'\sft.*', '', s, flags=re.IGNORECASE)
    index = s.find("feat")
    if index != -1:
        s = s[:index]
    return s

# Set up logging
logging.basicConfig(filename='get_tracklist_logs.txt', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

#open urls file
url_file_string = input("enter file:")
url_file = open(url_file_string, "r")
# url_file = open("urls.txt", "r")  # Open the file for reading
urls = []  # Create an empty list to store the URLs

for line in url_file:
    urls.append(line.strip())  # Remove any whitespace from the line and add it to the list

url_file.close()  # Close the file

# url = "https://www.nts.live/shows/jazmin-garcia/episodes/como-la-flor-w-jazmin-17th-february-2020"
csv_title = input("enter a title: ")
csv_title = csv_title + ".csv"
logging.debug(f"csv title is {csv_title}")
track_elements = []

for url in urls:
    # Send a GET request to the URL and get the HTML response
    print(f"working on url {url}\n")
    response = requests.get(url)
    logging.debug(f"Request status code: {response.status_code}")
    html_content = response.content

    # Parse the HTML content using Beautiful Soup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the element with ID "episode-container"
    episode_container = soup.find(id="episode-container")

    # Find all the elements with class "track" inside the heading element
    for elem in episode_container.find_all(class_="track"):
        track_elements.append(elem)


# Loop through the track elements and log their text
with open(f"../unread_csvs/{csv_title}", 'w') as f:
    writer = csv.writer(f)
    writer.writerow(["TITLE", "ARTIST"])
    for track_element in track_elements:
        artist = track_element.find(class_="track__artist").text.strip()
        artist = clean_string(artist)
        logging.debug(f"artist: {artist}")
        title = track_element.find(class_="track__title").text.strip()
        title = clean_string(title)
        logging.debug(f"title: {title}")
        writer.writerow([title, artist])




