# pyright: reportShadowedImports=false

# Built-in
import asyncio
import sys
# 3rd-party
import discord
from discord.ext import commands
import requests
# Local
from bot import WhiteRabbit
from cogs.debug import DEBUG_COMMAND_LIST
from data import cards, constants, dirs
from data.gamedata import Context, Data
from data.localization import LOCALIZATION_DATA
import envvars
import utils


# Minimum Python version check
if sys.version_info < (3, 7):
    sys.exit("The White Rabbit does not support Python versions below 3.7. Please install a newer version")

# Clear .pkl files on startup to avoid export bug
utils.delete_files(dirs.FONT_DIR, "pkl")

# Enable Server Members gateway intent to find all users
intents = discord.Intents.all()

bot = WhiteRabbit(command_prefix=commands.when_mentioned_or(constants.COMMAND_PREFIX), intents=intents)
bot.games = {}

# Localization
BOT_CHANNEL = LOCALIZATION_DATA["channels"]["bot-channel"]
SPECTATOR_ROLE = LOCALIZATION_DATA["spectator-role"]


@bot.event
async def on_ready():
    # Set custom status
    await bot.change_presence(
        activity=discord.Game(LOCALIZATION_DATA["title"])
    )


@bot.check
def check_channel(ctx: Context) -> bool:
    """Only allow commands in #bot-channel"""

    return ctx.channel.name == BOT_CHANNEL


@bot.check
def not_spectator(ctx: Context):
    """Don't let spectators run commands"""

    return SPECTATOR_ROLE not in [role.name for role in ctx.author.roles]


@bot.before_invoke
async def before_invoke(ctx: Context):
    """Attaches stuff to ctx for convenience"""

    # that guild's game
    ctx.game: Data = bot.games.setdefault(ctx.guild.id, Data(ctx.guild))

    # access text channels by name
    ctx.text_channels = {
        channel.name: channel
        for channel in ctx.guild.text_channels
    }

    # Character that the author is
    ctx.character = None
    for role in ctx.author.roles:
        if role.name in cards.ROLES_TO_NAMES:
            ctx.character = cards.ROLES_TO_NAMES[role.name]
            break


@bot.event
async def on_command_error(ctx: Context, error):
    """Default error catcher for commands"""

    bot_channel = utils.get_text_channels(ctx.guild)[BOT_CHANNEL]
    ctx.game: Data = bot.games.setdefault(ctx.guild.id, Data(ctx.guild))

    # Failed a check
    if isinstance(error, commands.errors.CheckFailure):
        # Check if user is spectator
        if SPECTATOR_ROLE in [role.name for role in ctx.author.roles]:
            asyncio.create_task(
                ctx.send(
                    LOCALIZATION_DATA["errors"]["SpectatorCommandAttempt"]
                )
            )

            return

        # Commands must be in bot-channel
        if ctx.channel.name != BOT_CHANNEL and utils.is_command(ctx.message.clean_content):
            asyncio.create_task(bot_channel.send(f"{ctx.author.mention} " + LOCALIZATION_DATA["errors"]["CommandInWrongChannel"]))
            return

        # Check if running debug command without being listed as developer
        # TODO: is there a better way to check this than testing against every command/alias?
        if ctx.author.id not in bot.dev_ids:
            message = ctx.message.clean_content
            for command in DEBUG_COMMAND_LIST:
                aliases: list = LOCALIZATION_DATA["commands"]["debug"][command]["aliases"]
                aliases.append(LOCALIZATION_DATA["commands"]["debug"][command]["name"])
                for alias in aliases:
                    if message.startswith(constants.COMMAND_PREFIX + alias):
                        asyncio.create_task(ctx.send(LOCALIZATION_DATA["errors"]["MissingDeveloperPermissions"]))
                        return


        # Automatic/manual check
        if ctx.game.automatic:
            asyncio.create_task(ctx.send(LOCALIZATION_DATA["errors"]["ManualCommandInAuto"]))
            return

        # Couldn't determine a specific error; tell user to check console
        asyncio.create_task(ctx.send(LOCALIZATION_DATA["errors"]["GenericCheckFailure"]))

    # Bad input
    elif isinstance(error, commands.errors.UserInputError):
        asyncio.create_task(ctx.send(LOCALIZATION_DATA["errors"]["UserInputError"]))

    # Can't find command
    elif isinstance(error, commands.errors.CommandNotFound):
        asyncio.create_task(ctx.send(LOCALIZATION_DATA["errors"]["CommandNotFound"]))

    # Everything else
    else:
        asyncio.create_task(ctx.send(LOCALIZATION_DATA["errors"]["UnknownError"]))
        raise error


# Import bot token
try:
    token = envvars.get_env_var("WHITE_RABBIT_TOKEN")
    print("Logging in...")
    bot.run(token)
except FileNotFoundError:
    r = requests.get(constants.BLANK_DOTENV_URL)
    with open(envvars.ENV_FILE, 'x') as env:
        env.write(r.content)
    sys.exit(LOCALIZATION_DATA["errors"]["MissingDotEnv"])
except discord.errors.LoginFailure:
    sys.exit(LOCALIZATION_DATA["errors"]["LoginFailure"])
