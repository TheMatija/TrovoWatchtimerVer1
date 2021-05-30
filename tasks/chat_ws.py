from discord.ext import commands, tasks
from aiohttp import WSMsgType
import json
from constants import Rank
import random
import sqlite3

lookup_successful = """**Username**: `{}`
**Nickname**: `{}`
**Minecraft username**: `{}`
**Watchtime (u minutama)**: `{}`
**CID**: `{}`"""

session_headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                                 '(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
                   'content-type': 'text/plain'}

'''headers = {'Accept': 'application/json',
           'Client-ID': f'{self.bot.trovo_client_id}',
           'Authorization': f'OAuth {self.bot.access_token}'}'''


class RuntimeCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.active_chat_session_cids = []
        self.bot.active_chat_websockets = []
        self.existing_mana_cids_cache = []
        self.existing_elixir_cids_cache = []
        self.existing_spellpt_cids_cache = []
        self.disconnect_queue = []

    @commands.command(aliases=['dc'])
    @commands.has_any_role(Rank.VLASNIK, Rank.DEVELOPER)
    async def chat_disconnect(self, ctx, username: str):
        cid = username
        if not (username.isnumeric() and len(username) == 9):
            cid, username = await self.bot.convert_username_to_cid(username)

        if cid not in self.disconnect_queue and cid in self.bot.active_chat_session_cids:
            self.disconnect_queue.append(cid)
            await ctx.reply(f'Odspojen od chata {username}')
        else:
            await ctx.reply(f'Nisi spojen sa chatom {username}')

    @commands.command(aliases=['cc'])
    @commands.has_any_role(Rank.VLASNIK, Rank.DEVELOPER)
    async def chat_connect(self, ctx, username: str):
        cid = username
        if not (username.isnumeric() and len(username) == 9):
            cid, username = await self.bot.convert_username_to_cid(username)

        if not cid:
            await ctx.reply(f'Nije moguće pronaći kanal `{username}`')
            return
        if cid == '0':
            await ctx.reply(f'Trovo api je vratio channel id **0** za kanal `{username}`')
            return
        if cid in self.bot.active_chat_session_cids:
            await ctx.reply(f'Već si spojen sa chatom **{username}**, jesi li mislio na `.disconnect|.dc <username>`?')
            return

        await ctx.reply(f'Spajanje sa chatom kanala **{username} ({cid})**')

        # Check if tables exists
        with sqlite3.connect("spellpoints.db") as conn:
            c = conn.cursor()

            c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{cid}'")
            if len(c.fetchall()) == 0:
                print("Table doesnt exists, creating new")
                c.execute(f"CREATE TABLE '{cid}' (message_id text PRIMARY KEY UNIQUE,"      # m['message_id']                          
                                                 "gift_display_name text NOT NULL,"         # m['content_data']['gift_display_name']
                                                 "gift_value integer NOT NULL,"             # m['content']['gift_value']
                                                 "value_type text NOT NULL,"                # m['content']['value_type']
                                                 "gift_id integer NOT NULL,"                # m['content_data']['gift_id']
                                                 "gift_num integer NOT NULL,"               # m['content_data']['gift_num']
                                                 "sender_id integer NOT NULL,"              # m['sender_id']
                                                 "sender_username text NOT NULL,"           # m['user_name']
                                                 "sender_nickname text NOT NULL)")          # m['nick_name']
                conn.commit()
            
            for table_name in (f'{cid}_elixir', f'{cid}_mana', f'{cid}_spellpt'):
                c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                if len(c.fetchall()) == 0:
                    c.execute(f"CREATE TABLE '{table_name}' (channel_id integer PRIMARY KEY UNIQUE, total_casted integer)")

        chat_token = await self.bot.get_chat_token(cid)
        nonce = ''.join(random.sample('1234567890abcdef', k=10))
        auth_json = {"type": "AUTH",
                     "nonce": nonce,
                     "data": {"token": chat_token}}

        ws = await self.bot.chat_ws_session.ws_connect('wss://open-chat.trovo.live/chat', timeout=40)

        await ws.send_str(json.dumps(auth_json))
        msg = json.loads((await ws.receive()).data)
        skipped_first_response = False
        # Check if the connection is successful
        if msg['type'] == 'RESPONSE':
            if msg['nonce'] == nonce:
                self.bot.active_chat_session_cids.append(cid)
                self.bot.active_chat_websockets.append(ws)
                if len(self.bot.active_chat_websockets) == 1:
                    self.ping_chat_service_task.start()
                await ctx.send(f'Spajanje sa {username} ({cid}) uspjesno!')
            else:
                await ctx.reply(f'**Connected to chat service with nonce {nonce} but got {msg["nonce"]} in the response!** Closing the connection.')
        else:
            await ctx.reply(f'**Should have received RESPONSE type message, but received this: {msg}')

        while True:
            msg = await ws.receive()

            if cid in self.disconnect_queue:
                await ws.close()
                self.disconnect_queue.remove(cid)
                self.bot.active_chat_session_cids.remove(cid)
                self.bot.active_chat_websockets.remove(ws)
                print(f'Stopped connection {username}, {cid}')
                break

            if msg.type == WSMsgType.CLOSED:
                await ctx.send('Received a message to close the connection!')
                self.bot.active_chat_session_cids.remove(cid)
                self.bot.active_chat_websockets.remove(ws)
                break
            if msg.data is None:
                await ctx.send(f'**Received message with no data and type {msg.type}**')
                continue

            msg = json.loads(msg.data)

            if msg['type'] == 'CHAT':
                if not skipped_first_response:
                    skipped_first_response = True
                    continue
                for m in msg['data']['chats']:
                    if m['type'] == 0:
                        pass
                        #print(f"Message from {m['nick_name']}")
                        #await ctx.send(f'[`{username}`] Received: **`{message["nick_name"]}:`** `{message["content"]}`')
                    elif m['type'] == 5:
                        # Message_content
                        if 'content_data' not in m.keys():
                            print("Missing content data here")
                            print(m)
                        m_c = json.loads(m['content'])
                        message_id      = m['message_id']
                        gift_name       = m['content_data']['gift_display_name'] if 'content_data' in m.keys() else m_c['gift']
                        gift_value      = m_c['gift_value']
                        value_type      = m_c['value_type']
                        gift_id         = m_c['gift_id']
                        gift_num        = m['content_data']['gift_num'] if 'content_data' in m.keys() else m_c['num']
                        sender_id       = m['sender_id']
                        sender_username = m['user_name']
                        sender_nickname = m['nick_name']
                        with sqlite3.connect("spellpoints.db") as conn:
                            c = conn.cursor()
                            c.execute(f"INSERT INTO '{cid}' (message_id, gift_display_name, gift_value, value_type, gift_id, gift_num, sender_id, sender_username, sender_nickname)"
                                      f"VALUES ('{message_id}', '{gift_name}', {gift_value},"
                                      f"'{value_type}', {gift_id}, {gift_num},"
                                      f"{sender_id}, '{sender_username}', '{sender_nickname}')")
                            conn.commit()

                            if value_type == "Mana":
                                if sender_id in self.existing_mana_cids_cache:
                                    c.execute(f"UPDATE '{cid}_mana' SET total_casted = total_casted + :casted WHERE channel_id=:channelid",
                                              {"casted": gift_value * gift_num, "channelid": sender_id})
                                else:
                                    c.execute(f"SELECT * FROM '{cid}_mana' WHERE channel_id=:channelid",
                                              {"channelid": sender_id})
                                    result = c.fetchone()
                                    if result is None:
                                        # If the user is new, even to the database
                                        c.execute(f"INSERT INTO '{cid}_mana' VALUES (?, ?)",
                                                  (sender_id, gift_value * gift_num))
                                    else:
                                        c.execute(f"UPDATE '{cid}_mana' SET total_casted = total_casted + :casted WHERE channel_id=:channelid",
                                                  {"casted": gift_value * gift_num, "channelid": sender_id})
                                    self.existing_mana_cids_cache.append(sender_id)
                                conn.commit()
                            elif value_type == "Elixir":
                                if sender_id in self.existing_elixir_cids_cache:
                                    c.execute(f"UPDATE '{cid}_elixir' SET total_casted = total_casted + :casted WHERE channel_id=:channelid",
                                              {"casted": gift_value * gift_num, "channelid": sender_id})
                                else:
                                    c.execute(f"SELECT * FROM '{cid}_elixir' WHERE channel_id=:channelid",
                                              {"channelid": sender_id})
                                    result = c.fetchone()
                                    if result is None:
                                        # If the user is new, even to the database
                                        c.execute(f"INSERT INTO '{cid}_elixir' VALUES (?, ?)",
                                                  (sender_id, gift_value * gift_num))
                                    else:
                                        c.execute(f"UPDATE '{cid}_elixir' SET total_casted = total_casted + :casted WHERE channel_id=:channelid",
                                                  {"casted": gift_value * gift_num, "channelid": sender_id})
                                    self.existing_elixir_cids_cache.append(sender_id)
                                conn.commit()

                            # TODO: Too much repeating code
                            if sender_id in self.existing_spellpt_cids_cache:
                                c.execute(
                                    f"UPDATE '{cid}_spellpt' SET total_casted = total_casted + :casted WHERE channel_id=:channelid",
                                    {"casted": gift_value * gift_num * 100 if value_type == "Elixir" else gift_value * gift_num,
                                     "channelid": sender_id})
                            else:
                                c.execute(f"SELECT * FROM '{cid}_spellpt' WHERE channel_id=:channelid",
                                          {"channelid": sender_id})
                                result = c.fetchone()
                                if result is None:
                                    # If the user is new, even to the database
                                    c.execute(f"INSERT INTO '{cid}_spellpt' VALUES (?, ?)",
                                              (sender_id, gift_value * gift_num * 100 if value_type == "Elixir" else gift_value * gift_num))
                                else:
                                    c.execute(
                                        f"UPDATE '{cid}_spellpt' SET total_casted = total_casted + :casted WHERE channel_id=:channelid",
                                        {"casted": gift_value * gift_num * 100 if value_type == "Elixir" else gift_value * gift_num,
                                         "channelid": sender_id})
                                self.existing_elixir_cids_cache.append(sender_id)

        return

    @tasks.loop(seconds=29)
    async def ping_chat_service_task(self):
        for chat_ws in self.bot.active_chat_websockets:
            await chat_ws.send_str(
                json.dumps({
                    'type': 'PING',
                    'nonce': ''.join(random.sample('1234567890abcdef', k=10))
                }))


def setup(bot):
    bot.add_cog(RuntimeCheck(bot))
