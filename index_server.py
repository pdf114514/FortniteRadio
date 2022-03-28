import sanic
import sanic.response
import m3u8
from zlib import decompress
import requests
import json

app = sanic.Sanic("Server")
host = "127.0.0.1"
port = 8000
resourceId = input("ResourceID?: ") or "hgsuJcchvKuaEzzijr" # https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/radio-stations
language = input("Language?: ") or "en"

def getinfo(resourceId: str) -> dict:
    response = requests.get(f"https://fortnite-vod.akamaized.net/{resourceId}/master.blurl")
    data = response.content
    if not (int(data[40:41].hex(), 16) != 1):
        return json.loads(data[8:len(data)].decode("utf-8"))
    else:
        return json.loads(decompress(data[8:len(data)]).decode("utf-8"))

@app.route("/favicon.ico")
async def favicon(req):
    return sanic.response.empty()

@app.after_server_start
async def after_server_start(_app, _loop):
    __import__("os").system(f"start http://{host}:{port}")

@app.route("/")
async def root(req):
    #return sanic.response.text(fortnite.getinfo(resourceId)["data"], content_type="text/plain")
    info = getinfo(resourceId)
    playlists = info["playlists"]
    for playlist in playlists:
        if playlist.get("language") == language:
            master_m3u8 = m3u8.loads(playlist["data"])
            master_uri = "/".join(playlist["url"].split("/")[:-1])
            break
    else:
        for playlist in playlists:
            if playlist.get("language") == "en":
                master_m3u8 = m3u8.loads(playlist["data"])
                master_uri = "/".join(playlist["url"].split("/")[:-1])
                break
    
    # videos
    #master_most = max([playlist for playlist in master_m3u8.playlists], key=lambda x: max(x.stream_info.resolution or [0]))
    #uri = "/".join(master_most.uri.split("/")[:-1])
    #data_m3u8 = m3u8.loads(requests.get(f"{master_uri}/{master_most.uri}").content.decode("utf-8"))
    
    master_audio = master_m3u8.media
    uri = "/".join(master_audio.uri[0].split("/")[:-1])
    data_m3u8 = m3u8.loads(requests.get(f"{master_uri}/{master_audio[0].uri}").content.decode("utf-8"))
    
    async def streaming_fn(response):
        await response.write(requests.get(f"{master_uri}/{uri}/{data_m3u8.segments[0].init_section.uri}").content)
        for segment in data_m3u8.segments:
            await response.write(requests.get(f"{master_uri}/{uri}/{segment.uri}").content)

    return sanic.response.stream(streaming_fn, content_type="audio/mp3")

app.run(host, port)