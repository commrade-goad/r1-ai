from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import os

FOLDER_ID = '1gN6-qfJCKUC-OeADS3gN6R_Iua3fEp_o'
SERVICE_ACCOUNT_FILE = 'service-acc.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/drive']
)
service = build('drive', 'v3', credentials=credentials)

# List all image files in the folder
query = f"'{FOLDER_ID}' in parents and mimeType contains 'image/'"
results = service.files().list(q=query, fields="files(id, name)").execute()
files = results.get('files', [])

for file in files:
    file_id = file['id']
    file_name = file['name']
    imgUrl = f"https://drive.google.com/uc?export=view&id={file_id}";
    print(imgUrl)

    # print(f"Downloading: {file_name}")
    #
    # request = service.files().get_media(fileId=file_id)
    # fh = io.FileIO(file_name, 'wb')
    # downloader = MediaIoBaseDownload(fh, request)
    #
    # done = False
    # while not done:
    #     status, done = downloader.next_chunk()

