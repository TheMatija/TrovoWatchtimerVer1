from dataclasses import dataclass

"""
UNUSED
This is a test-only file!
Used to catch errors from invalid config yaml
"""


@dataclass
class BotConfiguration:

    def __init__(self, data):
        self.raw = data

        self.token = self.get_from_config('token')

    def get_from_config(self, key, block=None):
        if block is None:

            if key in self.raw.keys():
                return self.raw[key]
            else:
                return None


