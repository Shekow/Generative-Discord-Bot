import discord
import os
from discord import Message, app_commands, Interaction
from discord.ext import commands, tasks
from mario import ChatRoom
from datetime import datetime, timedelta
from dotenv import load_dotenv
from emails import EmailSender
from tts import TTSVoiceQueue

# global variables

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)
bot.channels = {}
bot.queues = {}

emailSender = EmailSender(os.getenv("EMAIL"), os.getenv("PASS"))

# utility functions

def log_command(interaction: Interaction, name: str, **kwargs):
    print(f"[{datetime.now()}][{interaction.channel}] {interaction.user} used \"/{name}\" with {kwargs}")

def log_message(message: Message):
    print(f"[{datetime.now()}][{message.channel}] {message.author} said \"{message.content}\"")

async def respond_to_message(guild: discord.Guild, user: discord.Member, prompt: str, respond):
    if len(prompt) == 0:
        return
    try:
        chat_room: ChatRoom = ChatRoom.get_chat_room(user)
        response: ChatRoom.GeneratedResponse = chat_room.get_response(prompt)

        await respond(content=response.content)

        # if response.is_harmful:
        #     duration = timedelta(seconds=5*chat_room.strikes)
        #     await user.timeout(duration, reason=response.content)
        if guild.voice_client:
            if response.is_harmful:
                await guild.voice_client.disconnect()
            else:
                guild_id = guild.id
                bot.queues[guild_id].enqueue(response.content)
        return response.get_emoji_for_response()
    except ChatRoom.IDontLikeYou:
        await respond("I don't like you")
    except Exception as e:
        print(e)

# events

@bot.event
async def on_ready():
    print(f"{bot.user} says \"MamaMia!\"")
    print("Syncing command(s)...")
    try:
        synced = await bot.tree.sync()
        bot.synced_commands = synced
        print(f"Synced {len(synced)} command(s) successfully")
        print(f"{bot.user.display_name} is listening...")
        await bot.change_presence(status=discord.Status.do_not_disturb, activity=discord.Activity(type=discord.ActivityType.watching, name="my life crumble before my eyes"))
    except Exception as e:
        print(e)

@bot.event
async def on_message(message: Message):
    if message.author == bot.user or message.content[0] == bot.command_prefix:
        return
    if not bot.channels.get(message.channel):
        return
    log_message(message)
    emoji = await respond_to_message(message.guild, message.author, message.content, message.reply)
    if emoji:
        await message.add_reaction(emoji)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if before.channel is not None and after.channel is None and member == bot.user:
        bot.queues[before.channel.guild.id].clear()
        del bot.queues[before.channel.guild.id]

@bot.event
async def on_command_error(interaction: Interaction, error: commands.CommandError):
    error_message = "Something went wrong"
    try:
        await interaction.response.send_message(error_message)
    except Exception:
        await interaction.edit_original_response(error_message)

# commands

@bot.tree.command(name="chat", description="Lets you chat with mario!")
@app_commands.describe(prompt="Your prompt")
async def chat(interaction: Interaction, prompt: str):
    log_command(interaction, "chat", prompt=prompt)
    await interaction.response.send_message("Mario is thinking...")
    await respond_to_message(interaction.guild, interaction.user, prompt, interaction.edit_original_response)

@bot.tree.command(name="mario", description="Lets mario talk normally (without /chat)!")
@app_commands.describe(option="free/caged")
async def mario(interaction: Interaction, option: str):
    log_command(interaction, "mario", option=option)
    option = option.strip().lower()
    try:
        if (option == "free") == (bot.channels.get(interaction.channel)):
            await interaction.response.send_message("The dumb kind, I see")
        elif option == "free":
            bot.channels[interaction.channel] = True
            await interaction.response.send_message("Mario is free!")
        elif option == "caged":
            bot.channels[interaction.channel] = False
            await interaction.response.send_message("Mario is no longer free! :(")
        else:
            await interaction.response.send_message("Mario is confused (Unknown option)")
    except Exception as e:
        print(e)

@bot.tree.command(name="mode", description="Sets the level of harmful language mario can tolerate")
@app_commands.describe(mode="super polite, polite, almost naughty, or naughty")
async def mode(interaction, mode: str):
    mode = mode.strip().lower()
    new_mode = None
    response = ""
    
    try:
        chat_room = ChatRoom.get_chat_room(interaction.user)
    except ChatRoom.IDontLikeYou:
        await interaction.response.send_message("I don't like you")
        return

    match mode:
        case "super polite":
            new_mode = ChatRoom.SUPER_POLITE
            response = "That's no fun!"
        case "polite":
            new_mode = ChatRoom.POLITE
            response = "BORING"
        case "almost naughty":
            new_mode = ChatRoom.ALMOST_NAUGHTY
            response = "I guess that's fair"
        case "naughty":
            new_mode = ChatRoom.NAUGHTY
            response = "Like it spicy huh?"
        case _:
            new_mode = chat_room.mode
            response = "Mario is confused (Unknown mode)"
    try:
        chat_room.change_mode(new_mode)
        await interaction.response.send_message(response)
    except Exception as e:
        print(e)

@bot.tree.command(name="voice", description="Lets mario join/leave your voice channel")
@app_commands.describe(option="join/leave")
async def voice(interaction: Interaction, option: str):
    if not interaction.guild:
        await interaction.response.send_message("You can't use this command in a dm channel :(")
        return
    
    log_command(interaction, "voice", option=option)
    option = option.strip().lower()
    match option:
        case "join":
            if interaction.user.voice:
                await interaction.response.send_message("Sure thing!")
                if interaction.guild.voice_client:
                    await interaction.guild.voice_client.disconnect()
                await interaction.user.voice.channel.connect()
                guild_id = interaction.guild.id
                bot.queues[guild_id] = TTSVoiceQueue(interaction.guild.voice_client)
                bot.queues[guild_id].start()
            else:
                await interaction.response.send_message("Mario doesn't know where to join")
        case "leave":
            if interaction.guild.voice_client:
                await interaction.response.send_message("Mario respects privacy!")
                await interaction.guild.voice_client.disconnect()
            else:
                await interaction.response.send_message("Mario isn't in any voice channel")
        case _:
            await interaction.response.send_message("Mario is confused (Unknown option)")

@bot.tree.command(name="reset", description="Resets your chat with mario")
async def reset(interaction: Interaction):
    log_command(interaction, "reset")
    ChatRoom.reset_chat_room(interaction.user)
    guild_id = interaction.guild.id
    if bot.queues.get(guild_id):
        bot.queues[guild_id].clear()
    await interaction.response.send_message("Your convo is now brand new!")

@bot.tree.command(name="echo", description="Sends a message to all members with the specified role in the guild ('@': mention, '#': name)")
@app_commands.describe(msg="Message to be sent", role="Target role")
async def echo(interaction: Interaction, msg: str, role: discord.Role):
    log_command(interaction, "echo", msg=msg, role=role.name)
    if not interaction.guild:
        await interaction.response.send_message("You can't use this command in a dm channel :(")
        return
    msg = msg.strip().lower()

    if len(msg) == 0:
        msg = "MAMA MIA!"
    
    await interaction.response.send_message("MAMA MIA!!!")
    for member in interaction.guild.members:
        try:
            if role in member.roles:
                await member.send(msg.replace("@", member.mention).replace("#", member.global_name))
        except Exception as e:
            pass

@bot.tree.command(name="help", description="Shows a list of commands along with their description")
async def help(interaction: Interaction):
    response = "# Available Commands:\n"
    for command in bot.synced_commands:
        response += f"`{bot.command_prefix}{command.name}`"
        for option in command.options:
            response += f" `{option.name}`"
        response += f"\n\t\t**{command.description}**\n"

    embed = discord.Embed(description=response, color=0xff0000, )
    embed.set_author(name="Mario", icon_url=bot.user.avatar.url)
    if bot.user.banner is not None:
        embed.set_thumbnail(url=bot.user.banner.url)
    await interaction.response.send_message(content="", embed=embed)

def main():
    bot.run(token=DISCORD_TOKEN)

if __name__ == "__main__":
    main()

