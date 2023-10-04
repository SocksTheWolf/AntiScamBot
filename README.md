# AntiScamBot

This is a Discord bot that bans scammers who offer unsolicited commissions to users of a discord server.

These scammers are a scourge on our Discord communities. Unfortunately, unless they are banned in all relative servers, they’ll hop onto the next server and then attempt to scam people from there next.

To stop this from happening, this bot shares a ban list of known scammers to any servers it is activated in such that the scammers are unable to contact anyone.

This bot is powered via community reporting, trusted verification, and complete transparency in all actions.

You can read more on [the website here](https://theantiscamgroup.com)!

## Configurations to Run

### Environment Vars

To start the bot locally, create a .env file in the directory with the following: 

```
DISCORD_TOKEN="your discord token"  
DATABASE_FILE="a path to your sql file"  
CONFIG_FILE="a path to your config file"  
BACKUP_LOCATION="a path to your sql backup file"  
DEVELOPMENT_MODE="TRUE or FALSE"  
```

here is an example of a .env file

```
DISCORD_TOKEN="OTk1MTU1NzcyMzFYxMTQ2NFM.489fy9.WSF8YHE87F98efye79wsLSKDF0s"  
DATABASE_FILE="database.db"  
CONFIG_FILE="config.json"  
BACKUP_LOCATION="backup/"  
DEVELOPMENT_MODE="TRUE"  
```

You can also have these environment variables set directly

### Config.json

With the provided config.json as a base, you will need to update the IDs with your server/roles/channels. Here's how you get those IDs  
- Server ID: Right click your server icon and click on Copy Server ID
- Role ID: Go to your Server Settings -> Roles -> "..." button for the role -> Copy Role ID
- Channel ID: Right click the channel and click on Copy Channel ID

