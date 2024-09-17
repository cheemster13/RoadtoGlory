import os
import webbrowser
from flask import Flask, request
from requests_oauthlib import OAuth2Session

# Replace these with your actual credentials
CLIENT_ID = 'dj0yJmk9MUpFRm5MajJ1dE1NJmQ9WVdrOVRHOUtOR2RGVTNJbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PWM4'
CLIENT_SECRET = '93ffbeaad87f050400f5c91911e92bb9d73917ae'
REDIRECT_URI = 'http://localhost:8000/callback'

# OAuth 2.0 endpoints
AUTHORIZATION_BASE_URL = 'https://api.login.yahoo.com/oauth2/request_auth'
TOKEN_URL = 'https://api.login.yahoo.com/oauth2/get_token'

# Scope for Fantasy Sports API (confirm the exact scope from documentation)
SCOPE = ['fspt-w']  # Example scope

# Flask app to handle the callback
app = Flask(__name__)

# Global variable to store tokens
oauth2_session = None
token = None

@app.route('/callback')
def callback():
    global token
    try:
        token = oauth2_session.fetch_token(
            TOKEN_URL,
            client_secret=CLIENT_SECRET,
            authorization_response=request.url
        )
        return f"Access Token: {token['access_token']}"
    except Exception as e:
        return f"Error fetching access token: {e}"

def main():
    global oauth2_session
    # Create an OAuth2 session
    oauth2_session = OAuth2Session(
        CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    )

    # Get the authorization URL
    authorization_url, state = oauth2_session.authorization_url(AUTHORIZATION_BASE_URL)
    print("Opening browser for authorization...")
    webbrowser.open(authorization_url)

    # Start Flask server to handle callback
    print(f"Starting local server at {REDIRECT_URI} to receive the access token...")
    app.run(port=8000)

    if token:
        print("Access Token:", token['access_token'])
        # Save tokens securely
        with open('tokens.txt', 'w') as f:
            f.write(f"ACCESS_TOKEN={token['access_token']}\n")
            f.write(f"REFRESH_TOKEN={token.get('refresh_token', '')}\n")
        print("Tokens saved to tokens.txt")
    else:
        print("Failed to obtain access tokens.")

if __name__ == "__main__":
    main()
