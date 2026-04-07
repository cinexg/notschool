import os
from google_auth_oauthlib.flow import InstalledAppFlow

# The scope required to create events on the calendar
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def main():
    if not os.path.exists('credentials.json'):
        print("Error: credentials.json not found in this directory.")
        return

    print("Opening browser to authorize Notschool...")
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    
    # This opens your web browser to log in
    creds = flow.run_local_server(port=0)
    
    # Save the credentials for your backend to use
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
        
    print("Success! token.json has been created. Your API Lead is good to go.")

if __name__ == '__main__':
    main()