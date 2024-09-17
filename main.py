import os
import webbrowser
from flask import Flask, request
from requests_oauthlib import OAuth1Session

# Replace these with your actual credentials
CLIENT_KEY = 'dj0yJmk9MUpFRm5MajJ1dE1NJmQ9WVdrOVRHOUtOR2RGVTNJbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PWM4'       # Consumer Key
CLIENT_SECRET = '93ffbeaad87f050400f5c91911e92bb9d73917ae'  # Consumer Secret

# Yahoo OAuth endpoints
REQUEST_TOKEN_URL = 'https://api.login.yahoo.com/oauth/v2/get_request_token'
AUTHORIZE_URL = 'https://api.login.yahoo.com/oauth/v2/request_auth'
ACCESS_TOKEN_URL = 'https://api.login.yahoo.com/oauth/v2/get_token'

# Flask app to handle the callback
app = Flask(__name__)

# Global variables to store tokens
oauth_session = None
access_token = None
access_token_secret = None

@app.route('/callback')
def callback():
    global oauth_session, access_token, access_token_secret
    oauth_verifier = request.args.get('oauth_verifier')
    if oauth_verifier:
        # Fetch the access token
        oauth_tokens = oauth_session.fetch_access_token(ACCESS_TOKEN_URL, verifier=oauth_verifier)
        access_token = oauth_tokens.get('oauth_token')
        access_token_secret = oauth_tokens.get('oauth_token_secret')
        return f"Access Token: {access_token}<br>Access Token Secret: {access_token_secret}"
    return "Authorization failed."

def get_oauth_session():
    global oauth_session
    oauth_session = OAuth1Session(
        CLIENT_KEY,
        client_secret=CLIENT_SECRET,
        callback_uri='http://localhost:8000/callback'
    )
    return oauth_session

def main():
    global oauth_session
    # Step 1: Obtain a request token
    oauth = get_oauth_session()
    try:
        fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    except ValueError:
        print("Failed to fetch request token.")
        return

    resource_owner_key = fetch_response.get('oauth_token')
    resource_owner_secret = fetch_response.get('oauth_token_secret')

    # Step 2: Redirect the user to Yahoo for authorization
    authorization_url = oauth.authorization_url(AUTHORIZE_URL)
    print("Opening browser for authorization...")
    webbrowser.open(authorization_url)

    # Step 3: Start Flask server to handle callback
    print("Starting local server at http://localhost:8000/callback to receive the access token...")
    app.run(port=8000)

    # After Flask server completes, tokens will be printed
    if access_token and access_token_secret:
        print("Access Token:", access_token)
        print("Access Token Secret:", access_token_secret)
        # Optionally, save these tokens securely for future use
        with open('tokens.txt', 'w') as f:
            f.write(f"ACCESS_TOKEN={access_token}\n")
            f.write(f"ACCESS_SECRET={access_token_secret}\n")
        print("Tokens saved to tokens.txt")
    else:
        print("Failed to obtain access tokens.")

if __name__ == "__main__":
    main()
