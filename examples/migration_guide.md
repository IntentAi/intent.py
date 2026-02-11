# Migrating from discord.py to intent.py

## Installation

```bash
# Old
pip install discord.py

# New
pip install intent.py
```

## Imports

```python
# Old
import discord
from discord.ext import commands

# New
import intent
from intent.ext import commands
```

## Basic Bot

Mostly identical:

```python
# discord.py
bot = commands.Bot(command_prefix='!')

# intent.py
bot = commands.Bot(command_prefix='!')
```

## Full migration guide in development
