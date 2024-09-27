import os
import json
import argparse
import csv
import sqlite3
import time
from ssl import SSLEOFError
from googleapiclient.errors import HttpError, ResumableUploadError
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
secret_file = r"C:\\secret\\file\\path\\downloaded-from-google-developer.json"
token_file = "token.json"

class QuotaExceededError(Exception):
    pass

def get_authenticated_service():
    creds = None

    # Check if the token file exists, and load it
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If credentials are not valid, refresh or generate new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Use the correct secret file for the OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials to the token file for future use
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    # Return the authenticated YouTube API service
    return build('youtube', 'v3', credentials=creds)

class DataStorage:
    def __init__(self, storage_type, filename):
        self.storage_type = storage_type
        self.filename = filename
        if storage_type == 'sqlite':
            self.conn = sqlite3.connect(filename)
            self.cursor = self.conn.cursor()
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS videos
                                (id TEXT PRIMARY KEY, title TEXT, playlist_id TEXT, file_path TEXT)''')
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS playlists
                                (id TEXT PRIMARY KEY, name TEXT)''')
            self.conn.commit()
        elif storage_type == 'csv':
            if not os.path.exists(filename):
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'title', 'playlist_id', 'file_path'])
    
    def get_video(self, file_path):
        if self.storage_type == 'sqlite':
            self.cursor.execute("SELECT * FROM videos WHERE file_path = ?", (file_path,))
            return self.cursor.fetchone()
        elif self.storage_type == 'csv':
            with open(self.filename, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 3:
                        if row[3] == file_path:
                            return row
        return None
    
    def add_video(self, video_id, title, playlist_id, file_path):
        if self.storage_type == 'sqlite':
            self.cursor.execute("INSERT OR REPLACE INTO videos VALUES (?, ?, ?, ?)",
                                (video_id, title, playlist_id, file_path))
            self.conn.commit()
        elif self.storage_type == 'csv':
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([video_id, title, playlist_id, file_path])
    
    def add_dry_run_video(self, title, playlist_id, file_path):
        if self.storage_type == 'csv':
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['DRY_RUN', title, playlist_id, file_path])

    def get_playlist(self, name):
        if self.storage_type == 'sqlite':
            self.cursor.execute("SELECT * FROM playlists WHERE name = ?", (name,))
            return self.cursor.fetchone()
        elif self.storage_type == 'csv':
            with open(self.filename, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 1:
                        if row[1] == name:
                            return row
        return None
    
    def add_playlist(self, playlist_id, name):
        if self.storage_type == 'sqlite':
            self.cursor.execute("INSERT OR REPLACE INTO playlists VALUES (?, ?)", (playlist_id, name))
            self.conn.commit()
        elif self.storage_type == 'csv':
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([playlist_id, name])

def create_or_get_playlist(youtube, playlist_name, storage):
    stored_playlist = storage.get_playlist(playlist_name)
    if stored_playlist:
        return stored_playlist[0]

    if youtube is None:  # Dry run mode
        playlist_id = f"dry_run_playlist_{playlist_name}"
        storage.add_playlist(playlist_id, playlist_name)
        return playlist_id

    request = youtube.playlists().list(
        part="snippet",
        mine=True
    )
    response = request.execute()

    for item in response['items']:
        if item['snippet']['title'] == playlist_name:
            storage.add_playlist(item['id'], playlist_name)
            return item['id']

    request = youtube.playlists().insert(
        part="snippet,status",
        body={
          "snippet": {
            "title": playlist_name
          },
          "status": {
            "privacyStatus": "private"
          }
        }
    )
    response = request.execute()
    storage.add_playlist(response['id'], playlist_name)
    return response['id']

def upload_video(youtube, file_path, playlist_id, storage, update_file_progress):
    max_retries = 5
    retry_delay = 5  # seconds

    try:
        stored_video = storage.get_video(file_path)
    except:
        stored_video = None
    
    if stored_video:
        print(f"Video {os.path.basename(file_path)} already uploaded. Skipping.")
        return stored_video[0], stored_video[1], stored_video[2]
    
    video_title = os.path.splitext(os.path.basename(file_path))[0]
    
    if youtube is None:  # Dry run mode
        video_id = f"dry_run_video_{video_title}"
        storage.add_video(video_id, video_title, playlist_id, file_path)
        return video_id, video_title, playlist_id

    for attempt in range(max_retries):
        try:
            media = MediaFileUpload(file_path, resumable=True)
            request = youtube.videos().insert(
                part="snippet,status",
                body={
                    'snippet': {
                        'title': video_title,
                        'description': 'Uploaded using bulk uploader script',
                        "tags": ["bulk", "uploader", "youtube"],
                        "categoryId": "22",
                    },
                    'status': {
                        'privacyStatus': 'unlisted',
                    }
                },
                media_body=media
            )
            response = None
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        progress = int(status.progress() * 100)  # Progress in percentage
                        remaining_time = (status.total_size - status.resumable_progress) / 1024  # Estimated time in KB
                        update_file_progress.emit(playlist_id, file_path, progress, remaining_time)
                except HttpError as e:
                    if e.resp.status == 403 and 'quotaExceeded' in [i["reason"] for i in e.error_details]:
                        raise QuotaExceededError("YouTube API quota has been exceeded. Please try again later.")
                    else:
                        raise e  # Re-raise other exceptions
            video_id = response['id']
            video_title = response.get("snippet")["title"]

            playlist_request = youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id
                        }
                    }
                }
            )
            playlist_request.execute()

            storage.add_video(video_id, video_title, playlist_id, file_path)
            return video_id, video_title, playlist_id

        except (SSLEOFError, HttpError, ResumableUploadError) as e:
            if isinstance(e, (HttpError, ResumableUploadError)):
                if e.resp.status == 403 and 'quotaExceeded' in e._get_reason():
                    raise QuotaExceededError("YouTube API quota has been exceeded. Please try again later.")
                
                else:
                    raise Exception(f"An error occurred: {e}")
                if getattr(e, 'resp', {}).get('status') not in [500, 502, 503, 504]:
                    print("Client error. Upload failed.")
                    raise
            elif isinstance(e, SSLEOFError):
                print(f"SSLEOFError occurred: {e}")

            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds... (Attempt {attempt + 1} of {max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("Max retries reached. Upload failed.")
                raise

    return None, None, None  # If all retries fail

def process_directory(youtube, root_dir, storage, dry_run=False):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        rel_path = os.path.relpath(dirpath, root_dir)
        if rel_path == '.':
            continue

        playlist_name = '_'.join(rel_path.split(os.path.sep))
        video_files = [f for f in filenames if f.endswith(('.mp4', '.avi', '.mov', '.mkv', '.m4v'))]

        if video_files:
            print(f"Playlist: {playlist_name}")
            for video in video_files:
                print(f"  - {video}")
            print()
            
            if dry_run:
                playlist_id = f"DRY_RUN_PLAYLIST_{playlist_name}"
                for video in video_files:
                    video_path = os.path.join(dirpath, video)
                    video_title = os.path.splitext(video)[0]
                    storage.add_dry_run_video(video_title, playlist_id, video_path)
                    print(f"Dry run: Processed {video} in playlist {playlist_name}")
            else:
                playlist_id = create_or_get_playlist(youtube, playlist_name, storage)
                for video in video_files:
                    video_path = os.path.join(dirpath, video)
                    upload_video(youtube, video_path, playlist_id, storage)
                    print(f"Processed {video} in playlist {playlist_name}")

def main():
    parser = argparse.ArgumentParser(description='Bulk YouTube Video Uploader')
    parser.add_argument('directory', help='Root directory containing videos')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without uploading')
    parser.add_argument('--storage', choices=['sqlite', 'csv'], default='sqlite', help='Storage type for metadata')
    args = parser.parse_args()

    storage_filename = 'youtube_uploader_data.sqlite' if args.storage == 'sqlite' else 'youtube_uploader_data.csv'
    storage = DataStorage(args.storage, storage_filename)

    if args.dry_run:
        print("Performing dry run...")
        process_directory(None, args.directory, storage, dry_run=True)
    else:
        youtube = get_authenticated_service()
        process_directory(youtube, args.directory, storage)

if __name__ == '__main__':
    main()