---
title: Bot FAQ
description: Answers regarding the bot, what it does and other questions
previous: /
---

### What is this in a nutshell?

Think of this as a glorified shared ban list with auditing and public logging. Socks currently hosts an instance for free that you can use, by joining [the project discord](/discord).


### How do I enable it in my server?

1. Join the [TAG server here](/discord) 
2. Invite the bot account to a server you own
3. Activate the bot

### What is a commission scammer?

A commission scammer is someone who plays a confidence game in order to sell you on either AI art, traced/stolen artwork or just takes your money and runs.

They will always solicit you first. Do not give them money.

### Why is the icon of the bot "hey^^"?

When these scammers first ran rampant, they would always open their dms with the message "hey^^". It was really easy to tell if someone was fake because of it.

### How does it know who is a commission scammer?

User reports. Vetters go through the user report and then trigger a ban on the user in question if they are a scammer.

### Why does the bot need the permissions it has?

Because of how Discord handles permissions it needs the following permissions

* `Read Messages`: To handle commands. The bot will only look for messages that start with "?". If a message does not start with that character, the bot stops processing the message. Eventually I'd like to move to a system where this is not required, but it's was not easy to set up for early access.

* `Send Messages`: To send responses to commands that are executed.

* `Ban Members`: To execute the commands

* `Add Reactions`: Right now this permission is unused by the bot, but this is to add reactions to command messages in the future.

### What about abuse?

So currently, this bot requires that someone with a "Trusted" role approves the scammers proposed. If they are approved, the ban will be blasted to all servers that subscribe to the bot. 

### How do I know if someone was banned by the bot?

The name of the person that initiated this action as well as the user that it happened to will be blasted to a subscribable Discord feed via the announcement channel, of which you can get updates as to the going ons. It is recommended you add the feed as a webhook to your server.

![Bot Action Feed Screenshot](/assets/botbanchannel.png){:.centered}

All bans will be logged into your server's audit log. You can revert any ban if you wish and the bot will not attempt to re-add it unless you manually ask the bot to reimport bans.

### What about mistakes?

The bot can revert any mistakes and unban someone if this needs to happen, approvers have a command to reverse any scam bans that the database knows about (it cannot randomly unban any user, the bot can only unban users marked that it banned originally). You can also just simply unban the user. 

### Is the bot open source?

Yes! You can see the [project source code here](https://github.com/SocksTheWolf/AntiScamBot).