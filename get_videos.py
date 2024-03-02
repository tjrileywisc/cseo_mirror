import yaml
import requests
import os
import argparse
import base64

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

class CSEOMirror:
    def __init__(self, settings):
        self.url = settings['telvue_url']
        self.id = settings['player_id']
        self.playlists = settings['playlists']
        self.MAX_UPLOAD_COUNT = settings['MAX_UPLOAD_COUNT']
def get_all_video_metadata(youtube: Resource, mirror: CSEOMirror) -> List:
    video_metadata = []
    
    youtube_playlists = get_youtube_playlists(youtube)
    pprint(youtube_playlists)
    exit(1)
    for k,v in mirror.playlists.items():
        res = requests.get("{}/{}/playlists/{}".format(mirror.url,mirror.id,v))
        soup = BeautifulSoup(res.content, features="html.parser")
        
        for video in soup.find_all("div", class_="summary"):
            video_id = video.find_next("a")['href'].split("/")[-1]
            video_name = video.find_next("p").string
            filename = "{}.mp4".format(name.replace(" ", "_"))
            playlist_id = match_playlist(youtube_playlists, k, video_name)
            video_metadata.append({"id": video_id,
                                   "name": video_name,
                                   "filename": filename,
                                   "playlist": playlist_id
                                   })
    return(video_metadata)

def get_youtube_playlists(youtube: Resource) -> Dict:
    request = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=20
    )
    response = request.execute()
    pprint(response)
    output = {}
    for p in response['items']:
        output[p['snippet']['title']] = p['id']
    return(output)
def match_playlist(playlists: Dict, body_name: str, video_name: str) -> str:
    if body_name in playlists.keys():
        return(playlists[body_name])
    if body_name is "City Council Committees":
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
def already_downloaded(video: Dict, youtube: Resource) -> bool:
    request = youtube.playlistItems().list(
        part="snippet",
        playlistId=video['playlist'],
        maxResults=50,
        type="video"
    )
    pprint(request.to_json())
    exit(1)
    response = request.execute()
    print(response)
    return(False)
def download_video(mirror: CSEOMirror, video: Dict) -> Dict:
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
def upload_video(youtube: Resource, video: Dict) -> None:
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

def make_youtube_client(encoded_credentials: str) -> Resource:
    creds_text = base64.b64decode(encoded_credentials.encode("ascii")).decode("ascii")
    open("reconstructed_creds.json", "w").write(creds_text)
    scopes = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube.force-ssl"]
    credentials = Credentials.from_authorized_user_file("reconstructed_creds.json", scopes)
    os.remove("reconstructed_creds.json")
    credentials.refresh(Request())
    return(googleapiclient.discovery.build("youtube", "v3", credentials=credentials))

parser = argparse.ArgumentParser()
parser.add_argument('--credentials', required=True)
args = parser.parse_args()

mirror = CSEOMirror(yaml.safe_load(open('settings.yaml', 'r')))      
CURRENT_UPLOAD_COUNT = 0

youtube = make_youtube_client(args.credentials)
video_metadata = get_all_video_metadata(youtube, mirror)

for video in video_metadata:
    if already_downloaded(video, youtube):
        continue
    #video = download_video(mirror,video)
    a = is_video_backedup(video, youtube)
    exit(1)
    #upload_video(video)
    os.remove(video['filename'])
    
    CURRENT_UPLOAD_COUNT+=1
    if CURRENT_UPLOAD_COUNT >= mirror.MAX_UPLOAD_COUNT:
        break
        
#TODOs
#Check to see if video has been backedup already
#Automate Google Auth https://github.com/googleapis/google-api-python-client/blob/main/docs/oauth.md
#https://medium.com/@nathan_149/making-a-fully-automated-youtube-channel-20f2fa57e469
#Convert creds file to base64 and then store it as a GitHub Actions Secret https://svrooij.io/2021/08/17/github-actions-secret-file/
#Switch to politics youtube channel
#Add playlists in Youtube
#Define playlist in upload body based on committee