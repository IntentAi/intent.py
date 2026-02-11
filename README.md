# intent.py

Python bot SDK for Intent.

**Designed to mirror discord.py patterns** for easy bot migration.

## Status

 **Phase 1 Development** - SDK being built.

## Why intent.py?

Communities won't migrate without their bots. intent.py makes bot porting trivial:

```python
# Change this:
import discord

# To this:
import intent

# Most of your code just works
```

Same class structure, same decorators, same event patterns as discord.py where possible.

## Installation

```bash
pip install intent.py
```

(Coming soon)

## Quick Start

```python
import intent
from intent.ext import commands

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
  print(f'Logged in as {bot.user.name}')

@bot.command()
async def ping(ctx):
  await ctx.send('Pong!')

bot.run('your-bot-token')
```

## Features

- discord.py-compatible API
- MessagePack binary protocol
- Async/await support
- Decorator-based commands
- Full type hints

## Migration from discord.py

See [examples/migration_guide.md](examples/migration_guide.md)

## Documentation

In development: Full API documentation

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License - See [LICENSE](LICENSE)
