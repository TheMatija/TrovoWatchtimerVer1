import yaml
import os

from discord.activity import Activity
from discord.enums import ActivityType, Status
from discord.ext import commands
from discord.ext import tasks

from aiohttp import ClientSession

from constants import default_config
from trovo.TrovoUtilities import TrovoUtilities


if os.path.exists('config.yaml'):
    with open('config.yaml', 'r') as f:
        conf = yaml.safe_load(f.read())
else:
    with open('config.yaml', 'w') as f:
        conf = default_config
        yaml.safe_dump(default_config, f)


class Bot(commands.Bot, TrovoUtilities):
    def __init__(self, **kwargs):
        super().__init__(case_insensitive=True, **kwargs)

        self.conf = conf
        self.access_token = conf['access-token']

        self.default_headers = {
            'Accept': 'application/json',
            'Client-ID': conf['client-id']
        }
        self.auth_headers = {
            'Accept': 'application/json',
            'Client-ID': 'XvvMwd88D8Mu7GNRQkDw3U7f9VTvkGXF',
            'Authorization': f'OAuth {conf["access-token"]}'
        }

    async def on_ready(self):
        print(f'Uspješno prijavljen kao: {self.user}')
        self.session = ClientSession()
        self.chat_ws_session = ClientSession()
        self.load_extension('tasks.chat_ws')

        if not await self.validate_access_token():
            pass
            # TODO: await self.request_access_token()

    @tasks.loop(count=1)
    async def main_task(self):
        await self.wait_until_ready()
        self.spellpoint_channel = self.get_channel(conf['spell-point'])

        # Set the custom status "watching Psihic"
        # https://discordpy.readthedocs.io/en/latest/faq.html?highlight=subcommand#how-do-i-set-the-playing-status
        activity = Activity(type=ActivityType.watching, name="Psihic")
        await bot.change_presence(status=Status.online, activity=activity)


bot = Bot(command_prefix=conf['command-prefix'], help_command=None)  # intents=Intents.all()

bot.run(bot.conf['token'])
