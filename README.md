![turtlebott banner](https://github.com/turtledevv/turtlebott/blob/main/assets/banner.png?raw=true)
# Turtlebott
My ultimate experiments bot, with easy-to-make modules that you can slide in (with just **3 steps**)!

## Installation
1. Clone, download, whatever. Just get a local copy of the repo.
2. Install the dependencies using `pip install -r requirements.txt`, or `pip install .` if you like going through pip hell.
> [!WARNING]
> I've had problems with doing `pip install -e .`, so if you plan on modifying the code once installing, I would recommend using requirements.txt.

## Config
### Environment Variables
Create an .env file in the project root with your discord token.
> [!TIP]
> You can copy the example.env, and rename it to .env, then fill it out!
(You can get the token from the [Discord developers app page](https://discord.com/developers/applications).)

### Module Configuration
Configure all modules (and if they're enabled) in config.yml.
> [!NOTE]
> Just the same as .env, you can copy the example file and rename!
Just set the enabled flag to true/false. Some modules have additional configuration that you can change!

## Running the Bot
Start the bot with `python3 -m turtlebott`. *(you can also do `python`, `py`, etc.. Whatever you want.)*

## How to create a module
Creating a module is super easy!
### 1. Create the file
  In the turtlebott/modules folder, create your python file! Name it whatever you want, but write down that name for later.
### 2. Writing the code
  Then, you can look at other modules and the example module for good examples on how to make your module.
### 3. Enabling the module
  Once you're all ready to test your module out, go in the config.yml and add a new entry for your module. (Make sure to add the enabled flag, and set it to true!)
  After that, restart the bot, and it'll automatically load! Make sure the entry name in config.yml is the same as the name of your module file.

## License
Turtlebott
Copyright (C) 2026 Turtledevv

This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it under certain conditions.

See LICENSE for more details.
