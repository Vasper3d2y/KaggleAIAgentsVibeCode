import os
import argparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# If modifying these scopes, delete the file token.json.
# 'https://www.googleapis.com/auth/drive.file' allows creating and editing
# files that this specific app has uploaded/created.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_credentials():
    """Gets valid user credentials from storage or initiates OAuth2 flow."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Access token expired. Refreshing token...")
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "Missing 'credentials.json'. Please download your OAuth 2.0 Client credentials "
                    "from the Google Cloud Console (APIs & Services > Credentials) and save it "
                    "as 'credentials.json' in this folder."
                )
            
            print("Initiating authorization flow. Please authenticate in your browser...")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("Credentials saved to 'token.json'.")
            
    return creds

def upload_file(file_path, folder_id=None, drive_service=None):
    """Uploads a local file to Google Drive.

    Args:
        file_path (str): Path to the local file to upload.
        folder_id (str, optional): Target Google Drive Folder ID.
        drive_service: Pre-authenticated Google Drive API client.

    Returns:
        str: Uploaded file ID or None on failure.
    """
    if not os.path.exists(file_path):
        print(f"Error: Local file '{file_path}' does not exist.")
        return None

    if not drive_service:
        try:
            creds = get_credentials()
            drive_service = build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"Authentication failed: {e}")
            return None

    filename = os.path.basename(file_path)
    
    # Metadata for the new file on Google Drive
    file_metadata = {'name': filename}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    # Dynamically detect basic mimetype or default to octet-stream
    import mimetypes
    mimetype, _ = mimetypes.guess_type(file_path)
    if not mimetype:
        mimetype = 'application/octet-stream'

    print(f"Uploading '{filename}' ({mimetype})...")

    try:
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()

        print("\n🎉 Upload Successful!")
        print(f"File Name: {file.get('name')}")
        print(f"File ID:   {file.get('id')}")
        print(f"Web Link:  {file.get('webViewLink')}")
        return file.get('id')

    except HttpError as error:
        print(f"An API error occurred: {error}")
        return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Upload files to Google Drive using Drive API v3.")
    parser.add_argument("file_path", help="Path to the local file you want to upload.")
    parser.add_argument("--folder", help="Optional Google Drive Folder ID to upload into.")
    
    args = parser.parse_args()
    upload_file(args.file_path, args.folder)
