import yaml
import requests
import os
import argparse
import base64
import json

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
from typing import List, Dict

class YoutubeClient:
    def __init__(self, youtube_client: Resource):
        self.client = youtube_client
        
    def get_youtube_playlists(self) -> Dict:
        request = self.client.playlists().list(part="snippet",mine=True,maxResults=20)
        response = request.execute()
        output = {}
        for p in response['items']:
            output[p['snippet']['title']] = p['id']
        return(output)
    
    def upload_video(self, meeting: PublicMeeting):
        payload={"snippet": {"title": meeting.name,
                             "description": "Copy for personal time-shifted research use"},
                 "status": {"privacyStatus": "private"}}
        
        request = self.client.videos().insert(part="snippet,status", body=payload,
                                      media_body=MediaFileUpload(meeting.filename, resumable=True, chunksize=256*1024))
        
        response = None
        bar = tqdm(total = video['filesize'], desc = "Uploading {}".format(video['filename']),
                   leave = True, unit = "B", unit_scale = True, unit_divisor = 1024)
    
        while response is None:
            status, response = request.next_chunk()
            if status:
                bar.update(256*1024)
        bar.close()
        #TODO, get video id to add to playlist print(response)
    
class PublicMeeting:
    def __init__(self, video_id: str, name: str, body: str, youtube_playlists: Dict):
        self.video_id = video_id
        self.name = name
        self.filename = "{}.mp4".format(name.replace(" ", "_"))
        self.playlist_id = self.match_playlist(body, youtube_playlists)
        self.filesize = 0
        
    def match_playlist(self, body: str, playlists: Dict) -> str:
        if body in playlists.keys():
            return(playlists[body])
        if body == "City Council Committees":
            if "Whole" in video_name: return(playlists['Committee of the Whole'])
            elif "Economic" in video_name: return(playlists['Economic & Community Development Committee'])
            elif "Finance" in video_name: return(playlists['Finance Committee'])
            elif "Licenses" in video_name: return(playlists['Licenses & Franchises Committee'])
            elif "Debt" in video_name: return(playlists['Long Term Debt Committee'])
            elif "Ordinances" in video_name: return(playlists['Ordinances & Rules Committee'])
            elif "Public" in video_name: return(playlists['Public Works & Public Safety Committee'])
            elif "Veterans" in video_name: return(playlists['Veterans Services Committee'])
            else: return(playlists['City Council Committees (Other)'])
        return(None)
    
    def.delete_video(self):
        os.remove(self.filename)

class CSEOMirror:
    def __init__(self, args: argparse.Namespace):
        settings = yaml.safe_load(open('settings.yaml', 'r'))
        self.url = settings['telvue_url']
        self.player_id = settings['player_id']
        self.playlists = settings['playlists']
        self.youtube_creds_file = settings['youtube_creds_file']
        self.MAX_UPLOAD_COUNT = settings['MAX_UPLOAD_COUNT']
        
        if args.production:
            credentials_text = base64.b64decode(args.credentials.encode("ascii")).decode("ascii")
            open(self.youtube_creds_file, "w").write(credentials_text)
    
    def make_youtube_client(self) -> YoutubeClient:
        scopes = json.load(open(self.youtube_creds_file, "r"))['scopes']
        credentials = Credentials.from_authorized_user_file(self.youtube_creds_file, scopes)
        credentials.refresh(Request())
        return(YoutubeClient(googleapiclient.discovery.build("youtube", "v3", credentials=credentials)))
    
    def get_all_public_meetings(self, youtube_playlists: Dict) -> List:
        public_meetings = []
        for k,v in self.playlists.items():
            res = requests.get("{}/{}/playlists/{}".format(self.url,self.player_id,v))
            soup = BeautifulSoup(res.content, features="html.parser")
            
            for meeting in soup.find_all("div", class_="summary"):
                video_id = meeting.find_next("a")['href'].split("/")[-1]
                name = meeting.find_next("p").string
                public_meetings.append(PublicMeeting(video_id, name, k, youtube_playlists))
                
            if len(public_meetings) > self.MAX_UPLOAD_COUNT:
                public_meetings = public_meetings[:6]
                break
        return(public_meetings)
    
    def download_meeting(self, meeting: PublicMeeting):
        res = requests.get("{}/{}/media/{}".format(self.url, self.player_id, PublicMeeting.video_id))
        soup = BeautifulSoup(res.content, features="html.parser")
        download_url = soup.find("meta", property="og:video:url")['content'].replace("connect", "videoplayer")
        download_url = "{}?download_filename={}".format(download_url, PublicMeeting.filename)
        
        res = requests.get(download_url, stream=True)
        if res.status_code != 200:
            return(None)
        
        meeting.filesize = int(res.headers['Content-Length'])
        with open(filename, 'wb') as f, tqdm(total = meeting.filesize, desc = "Downloading {}".format(filename),
                                         unit = "B", unit_scale = True, unit_divisor = 1024, leave = True) as bar:
            for chunk in res.iter_content(1024*32):
            if chunk:
                bar.update(len(chunk))
                f.write(chunk)
                f.flush()
            bar.close()
        
    def cleanup(self):
        os.remove(self.youtube_creds_file)

def get_all_video_metadata_old(youtube_playlists: Dict, mirror: CSEOMirror) -> List:
    video_metadata = []
    
    youtube_playlists = get_youtube_playlists(youtube)
    for k,v in mirror.playlists.items():
        res = requests.get("{}/{}/playlists/{}".format(mirror.url,mirror.id,v))
        soup = BeautifulSoup(res.content, features="html.parser")
        
        for video in soup.find_all("div", class_="summary"):
            video_id = video.find_next("a")['href'].split("/")[-1]
            video_name = video.find_next("p").string
            filename = "{}.mp4".format(video_name.replace(" ", "_"))
            playlist_id = match_playlist(youtube_playlists, k, video_name)
            video_metadata.append({"id": video_id,
                                   "name": video_name,
                                   "filename": filename,
                                   "playlist": playlist_id
                                   })
    return(video_metadata)
def match_playlist_old(playlists: Dict, body_name: str, video_name: str) -> str:
    if body_name in playlists.keys():
        return(playlists[body_name])
    if body_name == "City Council Committees":
        if "Whole" in video_name: return(playlists['Committee of the Whole'])
        elif "Economic" in video_name: return(playlists['Economic & Community Development Committee'])
        elif "Finance" in video_name: return(playlists['Finance Committee'])
        elif "Licenses" in video_name: return(playlists['Licenses & Franchises Committee'])
        elif "Debt" in video_name: return(playlists['Long Term Debt Committee'])
        elif "Ordinances" in video_name: return(playlists['Ordinances & Rules Committee'])
        elif "Public" in video_name: return(playlists['Public Works & Public Safety Committee'])
        elif "Veterans" in video_name: return(playlists['Veterans Services Committee'])
        else: return(playlists['City Council Committees (Other)'])
    return(None)
def already_downloaded_old(video: Dict, youtube: Resource) -> bool:
    request = youtube.playlistItems().list(
        part="snippet",
        playlistId=video['playlist'],
        maxResults=50
    )
    response = request.execute()
    #TODO
    #When this is in prod, I will be able to test more accurately
    return(False)
def download_video_old(mirror: CSEOMirror, video: Dict) -> Dict:
    res = requests.get("{}/{}/media/{}".format(mirror.url,mirror.id,video['id']))
    soup = BeautifulSoup(res.content, features="html.parser")
    download_url = soup.find("meta", property="og:video:url")['content'].replace("connect","videoplayer")
    
    download_url = "{}?download_filename={}".format(download_url,video['filename'])
    
    res = requests.get(download_url, stream=True)
    if res.status_code != 200:
        return(None)
    
    size_bytes = int(res.headers['Content-Length'])
    with open(filename, 'wb') as f, tqdm(total = size_bytes, desc = "Downloading {}".format(filename),
                                         unit = "B", unit_scale = True, unit_divisor = 1024, leave = True) as bar:
        for chunk in res.iter_content(1024*32):
            if chunk:
                bar.update(len(chunk))
                f.write(chunk)
                f.flush()
        bar.close()
    
    video['filename'] = filename
    video['filesize'] = size_bytes
    return(video)
def upload_video_old(youtube: Resource, video: Dict) -> None:
    payload={"snippet": {"title": video['name'],
                         "description": video['name']},
             "status": {"privacyStatus": "private"}}
    
    request = youtube.videos().insert(part="snippet,status", body=payload,
                                      media_body=MediaFileUpload(video['filename'], resumable=True, chunksize=256*1024))
    
    response = None
    bar = tqdm(total = video['filesize'], desc = "Uploading {}".format(video['filename']), leave = True,
               unit = "B", unit_scale = True, unit_divisor = 1024)
    
    while response is None:
        status, response = request.next_chunk()
        if status:
            bar.update(256*1024)
    bar.close()
    print(response)


parser = argparse.ArgumentParser()
parser.add_argument('--credentials', nargs=1)
parser.add_argument('--production', action="store_true")
args = parser.parse_args()

mirror = CSEOMirror(args)
youtube = mirror.make_youtube_client()
youtube_playlists = youtube.get_youtube_playlists()
meeting_metadata = mirror.get_all_public_meetings(youtube_playlists)

print("Uploading {} meeting(s)\n{}".format(len(meeting_metadata),[m.name for m in meeting_metadata]))

if not args.production:
    exit(0)

for meeting in meeting_metadata:
    mirror.download_meeting(meeting)
    youtube.upload_video(meeting)
    meeting.delete_video()
        
mirror.cleanup()
        
#TODOs
#Check to see if video has been backedup already
#https://medium.com/@nathan_149/making-a-fully-automated-youtube-channel-20f2fa57e469
#Convert creds file to base64 and then store it as a GitHub Actions Secret https://svrooij.io/2021/08/17/github-actions-secret-file/