import requests
import json

# Your Spotify API credentials
client_id = 'addhere'
client_secret = 'addhere'

redirect_uri = 'http://localhost:8000/callback/'

# Step 1: Authorization Request
auth_url = 'https://accounts.spotify.com/authorize'
auth_params = {
    'client_id': client_id,
    'response_type': 'code',
    'redirect_uri': redirect_uri,
    'scope': 'playlist-modify-public',
}
auth_response = requests.get(auth_url, params=auth_params)

# Step 2: User Authorization
print('Please authorize this app to access your Spotify account.')
print('Opening browser...')
auth_code = input('Enter the authorization code from the URL: ')

# Step 3: Access Token Request
token_url = 'https://accounts.spotify.com/api/token'
auth_header = base64.b64encode(f'{client_id}:{client_secret}'.encode('ascii')).decode('ascii')
token_params = {
    'grant_type': 'authorization_code',
    'code': auth_code,
    'redirect_uri': redirect_uri,
}
token_response = requests.post(token_url, headers={'Authorization': f'Basic {auth_header}'}, data=token_params)

# Get the access token and refresh token from the token response
token_data = token_response.json()
access_token = token_data['access_token']
refresh_token = token_data['refresh_token']

# Authenticate with the Spotify API
auth_response = requests.post('https://accounts.spotify.com/api/token', data={
    'grant_type': 'client_credentials',
    'client_id': client_id,
    'client_secret': client_secret,
})

# Get the access token from the auth response
auth_response_data = auth_response.json()
access_token = auth_response_data['access_token']

# Create a new playlist
playlist_name = 'NTS Playlist Test'
playlist_description = 'A playlist of my favorite songs'
user_id = '1229504606'
playlist_response = requests.post(f'https://api.spotify.com/v1/users/{user_id}/playlists', headers={
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json',
}, json={
    'name': playlist_name,
    'description': playlist_description,
})

# Get the playlist ID from the playlist response
playlist_data = playlist_response.json()
print("playlist data")
print(playlist_data)
playlist_id = playlist_data['id']

# List of songs and artist names
song_list = [
    {
        'title': 'Toxic',
        'artist': 'Britney Spears',
    },
    # Add more songs and artist names as needed
]

# Search for tracks based on the song titles and artist names
tracks = []
for song in song_list:
    query = f"track:{song['title']} artist:{song['artist']}"
    search_response = requests.get('https://api.spotify.com/v1/search', headers={
        'Authorization': f'Bearer {access_token}',
    }, params={
        'q': query,
        'type': 'track',
    })
    search_results = search_response.json()
    if 'items' in search_results:
        tracks.append(search_results['items'][0]['uri'])

# Add the tracks to the playlist
add_tracks_response = requests.post(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers={
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json',
}, json={
    'uris': tracks,
})

print(f"{len(tracks)} tracks added to the playlist.")

