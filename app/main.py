from app.spotify.auth import SpotifyAuth

client_id = "YOUR_CLIENT_ID"  # set via env or config
auth = SpotifyAuth(client_id, redirect_uri="http://127.0.0.1:8888/callback") # set in spotify dashboard
# try to load saved tokens so user doesn't need to re-auth each run
if not auth.load_tokens():
    # starts interactive auth flow (prints URL, open it)
    auth.start_auth_flow()
token = auth.get_access_token()  # safe to call, refreshes if needed
print("access token ready, length:", len(token))
