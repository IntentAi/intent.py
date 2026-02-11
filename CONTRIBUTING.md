# Contributing to intent.py

Bot SDK contributions welcome!

## Design Philosophy

**Mirror discord.py patterns** where it makes sense.

Bot developers should find intent.py familiar, not foreign.

## Structure

- `intent/client.py` - Client and Bot classes
- `intent/ext/commands/` - Command decorator framework
- `intent/gateway.py` - WebSocket + MessagePack
- `intent/models/` - Message, Server, Channel, etc.

## Requirements

- Python 3.8+
- Full type hints
- discord.py naming compatibility
- Comprehensive tests
- Async/await throughout

## License

MIT License
