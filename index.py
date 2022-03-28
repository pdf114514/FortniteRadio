import discord
import m3u8
from zlib import decompress
import requests
import json
import asyncio

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

async def owners_only(interaction: discord.Interaction) -> bool:
    return interaction.user.id in owners

class RadioButtons(discord.ui.View):
    def __init__(self, voice_client: discord.VoiceClient):
        super().__init__()
        self.voice_client: discord.VoiceClient = voice_client
        self.nextreq: bool = False
        self.playing: bool = True
        self.stopped: bool = False
    
    @discord.ui.button(label="⏭", style=discord.ButtonStyle.green)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await owners_only(interaction):
            await interaction.response.send_message("You don't have permission to use the command.", ephemeral=True)
        else:
            self.nextreq = True
            self.voice_client.stop()
            await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="⏸", style=discord.ButtonStyle.grey)
    async def play_or_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await owners_only(interaction):
            await interaction.response.send_message("You don't have permission to use the command.", ephemeral=True)
        else:
            self.playing = not self.playing
            button.label = ("⏸" if self.playing else "▶")
            self.voice_client.resume() if self.playing else self.voice_client.pause()
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await owners_only(interaction):
            await interaction.response.send_message("You don't have permission to use the command.", ephemeral=True)
        else:
            self.playing = False
            self.stopped = True
            self.voice_client.stop()
            await self.voice_client.disconnect()
            await interaction.response.edit_message(content="Bye!", embed=None, view=None)

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

        buttons = RadioButtons(voice_client)
        embed = discord.Embed(title=radio["title"], description=f"resourceID: "+radio["resourceID"])
        embed.set_image(url=radio["stationImage"])
        await msg.edit(embed=embed, view=buttons)

        voice_client.play(discord.FFmpegPCMAudio(f"{master_uri}/{master_audio[0].uri}", before_options="-reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 8", options="-vn"))
        while voice_client.is_playing() or not buttons.playing:
            await asyncio.sleep(.5)
            if buttons.nextreq:
                buttons.nextreq = False
                break
        if buttons.stopped:
            return

        index+=1
        if index >= len(radios):
            index = 0

@tree.command(name="start", description="Start Playing Radio")
@discord.app_commands.check(owners_only)
async def command_start(interaction: discord.Interaction, play_in: discord.VoiceChannel, info: discord.TextChannel, lang: str):
    radio_tasks.append(asyncio.create_task(play_radio(play_in, info, lang)))
    await interaction.response.send_message("Started playing radio.", ephemeral=True)

@command_start.error
async def command_start_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("You don't have permission to use the command.", ephemeral=True)
    else:
        print(str(error))
        await interaction.response.send_message(f"Error\n```\n{str(error)}```")

@client.event
async def on_ready():
    print(f"Ready {client.user} / {client.user.id}")
    #await tree.sync()

client.run(token)