import requests
import json
import base64
import webbrowser

# Your Spotify API credentials
client_id = 'YOUR_CLIENT_ID'
client_secret = 'YOUR_CLIENT_SECRET'
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
webbrowser.open_new(auth_response.url)
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

# Step 4: Use the access token to create a new playlist
playlist_name = 'My Playlist'
playlist_description = 'A playlist of my favorite songs'
user_response = requests.get('https://api.spotify.com/v1/me', headers={
    'Authorization': f'Bearer {access_token}',
})
user_data = user_response.json()
user_id = user_data['id']
playlist_response = requests.post(f'https://api.spotify.com/v1/users/{user_id}/playlists', headers={
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json',
}, json={
    'name': playlist_name,
    'description': playlist_description,
})

# Get the playlist ID from the playlist response
playlist_data = playlist_response.json()
playlist_id = playlist_data['id']

# List of songs and artist names
song_list = [
    {
        'title': 'Song Title 1',
        'artist': 'Artist Name 1',
    },
    {
        'title': 'Song Title 2',
        'artist': 'Artist Name 2',
    },
    {
        'title': 'Song Title 3',
        'artist': 'Artist Name 3',
    },
    # Add more songs and artist names as needed
]

print(song_list);
