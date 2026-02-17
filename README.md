# intent.py

Python bot SDK for [Intent](https://github.com/IntentAi/intent). Mirrors discord.py patterns for easy bot migration.

> Phase 1 development — gateway and REST client implemented, models and state cache in progress.

## Why

Communities won't migrate without their bots. intent.py makes porting straightforward:

```python
# discord.py
import discord
client = discord.Client()

# intent.py
import intent
client = intent.Client()
```

Same class structure, same decorators, same async patterns.

## Quick Start

```python
import intent

client = intent.Client()

@client.event
async def on_ready():
    print(f'Logged in as {client.user.name}')

@client.event
async def on_message(message):
    if message.content == '!ping':
        await message.channel.send('Pong!')

client.run('your-bot-token')
```

## Install

```bash
pip install intent.py  # coming soon
```

For development:
```bash
git clone https://github.com/IntentAi/intent.py
cd intent.py
pip install -e ".[dev]"
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT
