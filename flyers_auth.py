from fyers_apiv3 import fyersModel
import webbrowser

def generate_fyers_token():
    CLIENT_ID = "7K9AEBKBAJ-200"       # From your Fyers API Dashboard
    SECRET_KEY = "EKPoZAx7Obd3rGL0"   # From your Fyers API Dashboard
    REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html" # Must match your app settings
    
    # 1. Initialize Session Model
    appSession = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )
    
    # 2. Generate the login URL and open it in your browser
    generateTokenUrl = appSession.generate_authcode()
    print(f"🔗 Opening browser for Fyers login...")
    webbrowser.open(generateTokenUrl, new=1)
    
    # 3. Manual Step:
    # After logging in, you will be redirected to your Redirect URL.
    # Look at the browser's address bar and copy the 'auth_code' value from the URL query string.
    # Example URL: https://trade.fyers.in/.../index.html?auth_code=eyJ0eXAi...&state=None
    auth_code = input("🔑 Paste the full redirected URL or just the 'auth_code' here: ").strip()
    
    if "auth_code=" in auth_code:
        # Extract auth_code if user pasted the entire URL
        auth_code = auth_code.split("auth_code=")[1].split("&")[0]
        
    # 4. Generate the Access Token
    appSession.set_token(auth_code)
    response = appSession.generate_token()
    
    if "access_token" in response:
        access_token = response["access_token"]
        print("\n✅ Access Token Generated Successfully!")
        print(access_token)
        
        # Save token to file for your 8BOT backend to read automatically
        with open("fyers_token.txt", "w") as f:
            f.write(access_token)
    else:
        print(f"\n❌ Error generating token: {response}")

if __name__ == "__main__":
    generate_fyers_token()