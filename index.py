import discord
import m3u8
from zlib import decompress
import requests
import json

with open("config.json", "r") as f:
    data = json.load(f)
    token = data["token"]
    owners = data["owners"]

client = discord.Client()
tree = discord.app_commands.CommandTree(client)
radio_tasks = []

def get_radios() -> list:
    response = requests.get("https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/radio-stations")
    if not response.ok:
        print("couldn't get radio station list :(")
        exit(0)
    return response.json()["radioStationList"]["stations"]

radios = get_radios()

def get_radioinfo(resourceId: str) -> dict:
    response = requests.get(f"https://fortnite-vod.akamaized.net/{resourceId}/master.blurl")
    data = response.content
    if not (int(data[40:41].hex(), 16) != 1):
        return json.loads(data[8:len(data)].decode("utf-8"))
    else:
        return json.loads(decompress(data[8:len(data)]).decode("utf-8"))

async def play_radio(VoiceChannel: discord.VoiceChannel, TextChannel: discord.TextChannel, language: str):
    index = 0
    voice_client: discord.VoiceClient = await VoiceChannel.connect(reconnect=False)
    msg = await TextChannel.send(embed=discord.Embed(title="Loading"))
    while True:
        radio = radios[index]

        info = get_radioinfo(radio["resourceID"])
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
        master_audio = master_m3u8.media

        embed = discord.Embed(title=radio["title"], description=f"resourceID: "+radio["resourceID"])
        embed.set_image(url=radio["stationImage"])
        await msg.edit(embed=embed)

        voice_client.play(discord.FFmpegPCMAudio(f"{master_uri}/{master_audio[0].uri}"))
        while voice_client.is_playing():
            await __import__('asyncio').sleep(5)

        index=+1
        if index >= len(radios):
            index = 0

async def owners_only(interaction: discord.Interaction) -> bool:
    return interaction.user.id in owners

@tree.command(name="start", description="Start Playing Radio")
@discord.app_commands.check(owners_only)
async def command_start(interaction: discord.Interaction, play_in: discord.VoiceChannel, info: discord.TextChannel, lang: str):
    radio_tasks.append(__import__('asyncio').create_task(play_radio(play_in, info, lang)))
    await interaction.response.send_message("Started playing radio.")

@command_start.error
async def command_start_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("You don't have permission to use the command.")
    else:
        print(str(error))
        await interaction.response.send_message(f"Error\n```\n{str(error)}```")

@client.event
async def on_ready():
    print(f"Ready {client.user} / {client.user.id}")
    #await tree.sync()

client.run(token)