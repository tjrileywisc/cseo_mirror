import yaml
import requests
import os
import argparse
import base64
import json
from captioning import CaptionExtractor

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

from bs4 import BeautifulSoup
from tqdm import tqdm

from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import Resource

from pprint import pprint
from typing import Dict, List

class PublicMeeting:
    def __init__(self, video_id: str, name: str, playlist_id: str):
        self.video_id = video_id
        self.name = name
        self.filename = "{}.mp4".format(name.replace(" ", "_"))
        self.playlist_id = playlist_id
        self.filesize = 0
    
    def delete_video(self):
        os.remove(self.filename)
class YoutubeClient:
    def __init__(self, youtube_client: Resource):
        self.client = youtube_client
        
    def get_youtube_playlists(self) -> Dict:
        request = self.client.playlists().list(part="snippet",mine=True,maxResults=20)
        response = request.execute()
        output = {"recent_videos":[]}
        for p in response['items']:
            output[p['snippet']['title']] = p['id']
            
            latest_item_request = self.client.playlistItems().list(part="snippet",playlistId=p['id'],maxResults=1)
            latest_item_response = latest_item_request.execute()
            if latest_item_response['items']:
                output['recent_videos'].append(latest_item_response['items'][0]['snippet']['title'])
        
        return(output)
    
    def upload_video(self, meeting: PublicMeeting):
        payload={"snippet": {"title": meeting.name,
                             "description": "Copy for personal time-shifted research use"},
                 "status": {"privacyStatus": "private"}}
        
        request = self.client.videos().insert(part="snippet,status", body=payload,
                                      media_body=MediaFileUpload(meeting.filename, resumable=True, chunksize=256*1024))
        
        response = None
        bar = tqdm(total = meeting.filesize, desc = "Uploading {}".format(meeting.filename),
                   leave = True, unit = "B", unit_scale = True, unit_divisor = 1024)

        i = 0
        while response is None:
            status, response = request.next_chunk()
            i += 1
            if status and not i % 64:
                bar.update(1024*256*64)
        bar.close()
        
        payload={"snippet": {"playlistId": meeting.playlist_id,
                             "resourceId": {"kind":"youtube#video","videoId":response['id']}}}
        request = self.client.playlistItems().insert(part="snippet", body=payload)
        response = request.execute()

class CSEOMirror:
    def __init__(self, args: argparse.Namespace):
        settings = yaml.safe_load(open('settings.yaml', 'r'))
        self.url = settings['telvue_url']
        self.player_id = settings['player_id']
        self.playlists = settings['playlists']
        self.youtube_token_file = settings['youtube_token_file']
        self.client_secrets_file = settings['client_secrets_file']
        self.MAX_UPLOAD_COUNT = settings['MAX_UPLOAD_COUNT']
        
        if args.production:
            token_text = base64.b64decode(args.token[0].encode("ascii")).decode("ascii")
            open(self.youtube_token_file, "w").write(token_text)
    
    def make_youtube_client(self) -> YoutubeClient:
        scopes = json.load(open(self.youtube_token_file, "r"))['scopes']
        credentials = Credentials.from_authorized_user_file(self.youtube_token_file, scopes)
        credentials.refresh(Request())
        return(YoutubeClient(googleapiclient.discovery.build("youtube", "v3", credentials=credentials)))
    
    def refresh_youtube_token(self) -> None:
        scopes = json.load(open(self.youtube_token_file, "r"))['scopes']
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(self.client_secrets_file, scopes)
        credentials = flow.run_local_server()
        open(self.youtube_token_file, "w").write(credentials.to_json())
        print("New token file created, upload the following to GHA Secrets:\n{}"
              .format(base64.b64encode(credentials.to_json().encode("ascii")).decode("ascii")))
    
    def get_new_public_meetings(self, youtube_playlists: Dict) -> List:
        public_meetings = []
        for k,v in self.playlists.items():
            res = requests.get("{}/{}/playlists/{}".format(self.url,self.player_id,v))
            soup = BeautifulSoup(res.content, features="html.parser")
            
            n = len(public_meetings)
            for meeting in reversed(soup.find_all("div", class_="summary")):
                video_id = meeting.find_next("a")['href'].split("/")[-1]
                name = meeting.find_next("p").string
                if name in youtube_playlists['recent_videos']:
                  break
                public_meetings.insert(n, PublicMeeting(video_id, name, youtube_playlists[k]))
            
            if len(public_meetings) > self.MAX_UPLOAD_COUNT:
                public_meetings = public_meetings[:self.MAX_UPLOAD_COUNT]
                break
        return(public_meetings)
    
    def download_meeting(self, meeting: PublicMeeting):
        res = requests.get("{}/{}/media/{}".format(self.url, self.player_id, meeting.video_id))
        soup = BeautifulSoup(res.content, features="html.parser")
        download_url = soup.find("meta", property="og:video:url")['content'].replace("connect", "videoplayer")
        download_url = "{}?download_filename={}".format(download_url, meeting.filename)
        
        res = requests.get(download_url, stream=True)
        if res.status_code != 200:
            return(None)
        
        meeting.filesize = int(res.headers['Content-Length'])
        with open(meeting.filename, 'wb') as f, tqdm(total = meeting.filesize, desc = "Downloading {}".format(meeting.filename),
                                                     unit = "B", unit_scale = True, unit_divisor = 1024, leave = True) as bar:
            i = 0
            for chunk in res.iter_content(1024*256):
                if chunk:
                    i += 1
                    if not i % 64:
                        bar.update(1024*256*64)
                    f.write(chunk)
                    f.flush()
            bar.close()
        
    def cleanup(self):
        os.remove(self.youtube_token_file)


parser = argparse.ArgumentParser()
parser.add_argument('--token', nargs=1)
parser.add_argument('--production', action="store_true")
parser.add_argument('--refresh', action="store_true")
parser.add_argument('--transcribe', help="transcribe audio to srt format subtitles", action="store_true")

args = parser.parse_args()

mirror = CSEOMirror(args)

if args.refresh:
  mirror.refresh_youtube_token()
  exit(0)

youtube = mirror.make_youtube_client()
youtube_playlists = youtube.get_youtube_playlists()
meeting_metadata = mirror.get_new_public_meetings(youtube_playlists)

print("Uploading {} meeting(s)\n{}".format(len(meeting_metadata),[m.name for m in meeting_metadata]))
if not args.production:
    exit(0)
    
for meeting in meeting_metadata:
    mirror.download_meeting(meeting)
    youtube.upload_video(meeting)
    CaptionExtractor(meeting.filename)
    meeting.delete_video()
        
mirror.cleanup()
        
#TODOs
#Check to see if video has been backedup already