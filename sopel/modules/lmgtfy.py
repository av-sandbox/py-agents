from __future__ import annotations

from urllib.parse import urlencode

from sopel import plugin


@plugin.command('lmgtfy', 'lmgify', 'gify', 'gtfy')
@plugin.example('.lmgtfy sopel', 'https://lmgtfy.com/?q=sopel')
@plugin.example('.lmgtfy sopel bot', 'https://lmgtfy.com/?q=sopel+bot', user_help=True)
@plugin.example('.lmgtfy', 'https://www.google.com/', user_help=True)
def googleit(bot, trigger):
    """Let me just… Google that for you."""
    if not trigger.group(2):  # No input
        return bot.say('https://www.google.com/')
    qs = urlencode({
        'q': trigger.group(2),
    })
    bot.say('https://lmgtfy.com/?%s' % qs)