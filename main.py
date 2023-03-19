import discord
from discord import app_commands
import requests
import json
import uuid
import os
from dataclasses import dataclass
import re
from typing import Literal
from dotenv import load_dotenv
load_dotenv()
VV_HOST = os.getenv("VV_HOST")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@dataclass
class Speaker:
    id: int
    name: str

with open("speakers.json","r") as f:
    #object_hook 第一引数に辞書型で帰ってくるのをいじって返す
    #speaker_dict = json.load(f)#,object_hook=lambda t:Speaker(t["id"],t["name"]))
    speakers = [Speaker(speaker["id"],speaker["name"]) for speaker in json.load(f)]

@dataclass
class ConectedUser:
    user_id: int
    voicevox_id: int

class ConnectedChannel:
    text_channel_id: int
    users: list[ConectedUser]
    select_speaker_index: int
    def __init__(self, text_channel_id):
        self.text_channel_id = text_channel_id
        self.users = []
        self.select_speaker_index = 0
    def say(self, content: str, user_id: int, message: discord.Message):
        if len(list(filter(lambda user : user.user_id == user_id, self.users))) == 0:
            self.users.append(ConectedUser(user_id, speakers[self.select_speaker_index].id))
            self.select_speaker_index += 1
            if len(speakers) == self.select_speaker_index:
                self.select_speaker_index = 0
        target = list(filter(lambda user : user.user_id == user_id, self.users))[0]
        filename = str(uuid.uuid4())+".wav"
        generate_wav(content ,speaker=target.voicevox_id, filename=filename)
        while message.guild.voice_client.is_playing():
            pass
        message.guild.voice_client.play(discord.FFmpegPCMAudio("./audio/"+filename), after=lambda ex: os.remove(f"./audio/{filename}"))


connected_channels: list[ConnectedChannel] = []

host = VV_HOST
port = 50021
def generate_wav(text, speaker=1, filename='audio.wav'):
    params = (
        ('text', text),
        ('speaker', speaker),
    )
    response1 = requests.post(
        f'http://{host}:{port}/audio_query',
        params=params
    )
    headers = {'Content-Type': 'application/json',}
    response2 = requests.post(
        f'http://{host}:{port}/synthesis',
        headers=headers,
        params=params,
        data=json.dumps(response1.json())
    )
    with open("./audio/"+filename, 'wb') as f:
        f.write(response2.content)

def get_speaker_info(speaker_name: str = None,speaker_id: int = None) -> Speaker:
    if speaker_id != None:
        return list(filter(lambda x: x.id == speaker_id, speakers))[0]
    return list(filter(lambda x: x.name == speaker_name, speakers))[0]

def find_url(content: str):
    return re.findall('https?://[A-Za-z0-9_/:%#$&?()~.=+-]+?(?=https?:|[^A-Za-z0-9_/:%#$&?()~.=+-]|$)', content)
def find_stamp(content: str):
    return re.findall('<:.*:[0-9]*>', content)
def find_mention(content: str):
    return re.findall('<@[0-9]*>', content)

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(1032914541195055149))
    print(f'We have logged in as {client.user}')

guild_ids = [discord.Object(1032914541195055149)] # Put your server ID in this array.

@tree.command(name="connect",description="実行したユーザーが接続中のボイスチャンネルに接続します。",guilds=guild_ids)
async def connect_vc(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("実行者がボイスチャンネルに入っていないため接続できませんでした。")
        return
    await interaction.user.voice.channel.connect()
    await interaction.response.send_message("接続しました。")
    connected_channels.append(ConnectedChannel(interaction.channel.id))
    print(connected_channels)

@tree.command(name="disconnect",description="ボイスチャンネルから切断します。",guilds=guild_ids)
async def disconnect_vc(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("botがボイスチャンネルに接続されていないため切断できませんでした。")
        return

    await interaction.guild.voice_client.disconnect()
    connected_channels.remove(list(filter(lambda channel : channel.text_channel_id == interaction.channel.id ,connected_channels))[0])
    print(connected_channels)
    await interaction.response.send_message("切断しました。")

@tree.command(name="speakerinfo",description="各ユーザーごとに割り当てられているキャラクター一覧を表示します。",guild=discord.Object(1032914541195055149))
async def speakerinfo(interaction: discord.Interaction):
    await interaction.response.defer()
    channels = list(filter(lambda channel : channel.text_channel_id == interaction.channel.id, connected_channels))
    if len(channels) > 0:
        users = list(filter(lambda user : user.user_id == interaction.user.id ,channels[0].users))
        if len(users) > 0:
            speaker_name = get_speaker_info(speaker_id = users[0].voicevox_id).name
            await interaction.followup.send(interaction.user.display_name + ":" + speaker_name)
            return
    await interaction.followup.send("設定されているユーザーはいません。")

@tree.command(name="setspeaker",description="使用するキャラクターを設定します。",guilds=guild_ids)
async def set_speaker(interaction: discord.Interaction, name: Literal[tuple([str(speaker.name) for speaker in speakers])]):
    await interaction.response.defer()
    if name not in [str(speaker.name) for speaker in speakers]:
        await interaction.followup.send("正しくない形式です")
        return
    channels = list(filter(lambda channel : channel.text_channel_id == interaction.channel.id, connected_channels))
    if len(channels) > 0:
        users = list(filter(lambda user : user.user_id == interaction.user.id ,channels[0].users))
        if len(users) < 0:
            await interaction.followup.send("喋るユーザーとして登録されていません。なにか喋ってからもう一度試してください。")
        elif len(users) > 0:
            users[0].voicevox_id = get_speaker_info(name).id
            await interaction.followup.send(f"{interaction.user.display_name}さんの声を「{name}」にしました")
        return
    await interaction.followup.send("ボイスチャンネルに入っていないためコマンドを実行できませんでした。")

@tree.command(name="speakerlist",description="使用できるキャラクター一覧を表示します。",guilds=guild_ids)
async def speaker_list(interaction: discord.Interaction):
    await interaction.response.send_message("\n".join([str(speaker.name) for speaker in speakers]))

@tree.command(name="listdic",description="追加済みのユーザー辞書の単語一覧を表示します。",guilds=guild_ids)
async def speaker_list(interaction: discord.Interaction):
    res = requests.get(f'http://{host}:{port}/user_dict')
    dic_json = res.json()
    await interaction.response.send_message("ID:表記:発音(カタカナ):音が下がる場所\n" + "\n".join([f"{key}:{dic_json[key]['surface']}:{dic_json[key]['pronunciation']}:{dic_json[key]['accent_type']}" for key in dic_json]))

@tree.command(name="adddic",description="ユーザー辞書に単語を追加します。",guilds=guild_ids)
async def add_dic(interaction: discord.Interaction,surface:str,pronunciation:str,accent:int):
    params = (
        ('surface', surface),
        ('pronunciation', pronunciation),
        ('accent_type', accent)
    )
    res = requests.post(f'http://{host}:{port}/user_dict_word', params=params)
    if res.ok:
        await interaction.response.send_message(":white_check_mark:追加に成功しました")
    else:
        await interaction.response.send_message(":dizzy_face:追加に失敗しました")
        print(res.text)

@tree.command(name="deldic",description="追加済みのユーザー辞書の単語一覧を表示します。",guilds=guild_ids)
async def del_dic(interaction: discord.Interaction,id:str):
    res = requests.delete(f'http://{host}:{port}/user_dict_word/{id}')
    if res.ok:
        await interaction.response.send_message(":wastebasket:削除に成功しました")
    else:
        await interaction.response.send_message(":dizzy_face:削除に失敗しました")
        print(res.text)

@client.event
async def on_message(message: discord.Message):
    # メッセージの送信者がbotだった場合は無視する
    if message.author.bot:
        return
    else:
        channels = list(filter(lambda channel : channel.text_channel_id == message.channel.id ,connected_channels))
        if len(channels) > 0:
            urls = find_url(message.content)
            stamps = find_stamp(message.content)
            mentions = find_mention(message.content)
            content = message.content
            print(content)
            print(urls)
            for url in urls:
                content = content.replace(url,"URL")
            for stamp in stamps:
                content = content.replace(stamp,"")
            for mention in mentions:
                content = content.replace(mention,"")
            if len(content) == 0:
                return
            channels[0].say(content, message.author.id, message)

# Botのトークンを指定（デベロッパーサイトで確認可能）
client.run(os.getenv("DISCORD_BOT_TOKEN"))

