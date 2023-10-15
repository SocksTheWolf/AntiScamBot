---
title: FAQ
description: Answers regarding ScamGuard, what it does and other things!
previous: /
---

## The Bot, ScamGuard
---

### What is this project in a nutshell?

Think of this as a glorified shared ban list with auditing and public logging. Socks currently hosts an instance for free that you can use, by joining [the project Discord](/discord).

### How do I enable it in my server?

{% include install_info.html %}

### Why does the bot need the permissions it has?

Because of how Discord handles permissions it needs the following permissions:

* `Create Commands`: For implementing the various application slash commands.

* `Send Messages`: To send responses to commands that are executed.

* `Ban Members`: To execute the bans

* `Embed Links`: To give you information when you run `/scamcheck`

### Is the bot open source?

Yes! You can see the [project source code here](https://github.com/SocksTheWolf/AntiScamBot).

### What information do you store?

You can [view our privacy policy right here](/privacy-policy)!

## Commission Scammers
---

### What is a commission scammer?

Commission scammers are users/bots on Discord who send unsolicited direct messages demanding that you commission the scammer that you do not know to buy their traced/AI/stolen artwork. In some instances, they charge your payment account (Paypal, Boosty, etc) and never deliver anything.

They will always solicit you first. Do not give these scammers your money.

### Why is the icon of the bot "hey^^"?

When these scammers first ran rampant, they would always open their dms with the message "hey^^". It was really easy to tell if someone was fake because of it.

## The Process
---

### How does the bot know who is a commission scammer?

User reports. Vetters go through the user report and then trigger a ban on the user in question if they are a scammer.

### What about abuse?

So currently, this bot requires that someone with a "Trusted" role approves the scammers proposed. If they are approved, the ban will be blasted to all servers that subscribe to the bot. 

### How do I know if someone was banned by the bot?

The name of the person that initiated this action as well as the user that it happened to will be blasted to a subscribable Discord feed via the announcement channel, of which you can get updates as to the going ons. It is recommended you add the feed as a webhook to your server.

![Bot Action Feed Screenshot](/assets/botbanchannel.png){:.centered}

All bans will be logged into your server's audit log. You can revert any ban if you wish and the bot will not attempt to re-add it unless you explicitly ask the bot to reimport bans for your server.

### Can the bot ever ban the server owner or mods?

The bot cannot ban anyone who has a role located higher in the roles list than it. The only exception to this rule is if you transfer your server ownership to the bot (don't do this). It is suggested to put the role for the bot directly above your general role or underneath your moderator role.

### What about mistakes?

The bot can revert any mistakes and unban someone if this needs to happen, approvers have a command to reverse any scam bans that the database knows about (it cannot randomly unban any user, the bot can only unban users marked that it banned originally). 

You can also just simply unban the user. 

## The Group
---

### What is "The Antiscam Group"?

It's just a silly little name for the Discord server.

### How do I join the group?

This isn't a formal collective or anything of the sort. It's literally a bunch of people who keep getting commission scams and those that have community servers that use the bot.

### I don't have a Discord server, can I join the bot server?

Yes! If you're getting commission scams, feel free to join and report them. However, realize that the TAG server isn't a social community. Streamer communities are much better suited for that.