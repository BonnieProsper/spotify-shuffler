# Spotify-Shuffler
A random shuffler for Spotify playlists.


## Security and Deployment Notes

Don’t commit ~/.spotify_shuffler_tokens.json - add it to .gitignore.

In production, prefer a secure token store (OS keychain, encrypted file, or backend service) and use HTTPS for redirects.

If this is ever published as an  app, it must follow Spotify privacy rules and be explicit about scopes and what you store. Spotify docs requires registration of apps and that you list redirect URIs in the dashboard.
