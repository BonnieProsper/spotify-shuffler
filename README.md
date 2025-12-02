# Spotify-Shuffler
A random shuffler for Spotify playlists.


## Security and Deployment Notes

Don’t commit ~/.spotify_shuffler_tokens.json - add it to .gitignore.

In production, prefer a secure token store (OS keychain, encrypted file, or backend service) and use HTTPS for redirects.

If this is ever published as an  app, it must follow Spotify privacy rules and be explicit about scopes and what you store. Spotify docs requires registration of apps and that you list redirect URIs in the dashboard.

## Tests and Debugging

Unit tests can mock requests.post to verify that start_auth_flow correctly handles exchange responses. For the redirect handler, a small integration test can simulate a GET to the local server with ?code=abc.

If you get a 400 from token endpoint during exchange, check that you included redirect_uri, client_id, and code_verifier, as these are required in the PKCE token exchange.


