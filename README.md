# Turtlebott

A multi-purpose Discord bot for random experiments and automation.

## Features

- Modular architecture with configurable experiments
- Example module for basic functionality
- AI-generated surprise commands
- Battle panel control system
- Comprehensive logging

## Requirements

- Python 3.10 or higher
- Discord.py
- python-dotenv
- pydirectinput

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   Or with the project's pyproject.toml:
   ```bash
   pip install .
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root with your Discord bot token:

```env
DISCORD_TOKEN=your_discord_bot_token_here
```

### Experiments

Configure which modules are enabled in `config.yml`:

```yaml
experiments_config:
  example:
    enabled: true
  ai_suprise:
    enabled: true
  battle_panel:
    enabled: false
    userWhitelistEnabled: false
    userWhitelist:
      - YOUR_USER_ID
```

## Running

Start the bot with:

```bash
python -m turtlebott
```

## Project Structure

- `turtlebott/` - Main package
  - `bot.py` - Bot initialization and module loading
  - `config.py` - Configuration settings
  - `modules/` - Experiment modules
  - `utils/` - Utility functions and logging

## License

None! 🏴‍☠️ :3
