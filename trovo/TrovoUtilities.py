"""
commands.Bot inherits from this class,
so "Unsolved reference" errors can
be safely ignored
"""


class TrovoUtilities:
    async def convert_username_to_cid(self, username):
        r = await self.session.post('https://open-api.trovo.live/openplatform/getusers',
                                    json={"user": [username]},
                                    headers=self.default_headers)
        json = await r.json()
        print(json)
        if 'error' not in json.keys():
            return json['users'][0]['channel_id'], json['users'][0]['username']
        return False, False

    async def get_chat_token(self, cid):
        """THIS SHOULD ONLY BE CALLED IF CID IS CHECKED TO EXIST!"""
        r = await self.session.get(f'https://open-api.trovo.live/openplatform/chat/channel-token/{cid}',
                                   headers=self.auth_headers)
        json = await r.json()
        return json['token']

    async def validate_access_token(self):
        r = await self.session.get('https://open-api.trovo.live/openplatform/validate',
                                   headers=self.auth_headers)
        json = await r.json()
        print(json)
        if 'error' not in json.keys():
            return True
        return False
