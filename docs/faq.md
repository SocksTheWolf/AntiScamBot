---
title: FAQ
description: Answers regarding ScamGuard, what it does and other things!
previous: /
---

## The Bot, {{ site.bot_name }}
---

### What is this project in a nutshell?

Think of this as a glorified shared ban list with auditing and public logging. Socks currently hosts an instance for free that you can use, by joining [the project Discord](/discord).

### How do I enable it in my server?

{% include install_info.html %}

### Why does {{ site.bot_name }} need the permissions it has?

Because of how Discord handles permissions it needs the following permissions:

* `Create Commands`: For implementing the various application slash commands.

* `Send Messages`: To send responses to commands that are executed.

* `Ban Members`: To execute the bans

* `Embed Links`: To give you information when you run `/scamguard check`

* `Manage Webhooks`: To allow subscribing to the ban notification feed if you choose during setup.

### I am not able to add the bot, it says the bot needs to be verified?

We have submitted {{ site.bot_name }} for verification but this process has been very slow. While the bot is still being verified, you can add one of the many fallback bots.

Eventually when the main bot is verified, the fallback bots will move their assignments onto the main bot instance. We are aware of how frustrating this is. We hope this is solved sooner, but our hands are tied.

Anything under the "THE BOT" role in the TAG server is allowed to be added.

### When I activate the bot, why is it suddenly banning hundreds of accounts?

{{ site.bot_name }} imports all the bans of scammers that it knows about. This can be several hundreds of accounts, but not to worry, due to the way {{ site.bot_name }} processes bans, these accounts do not have to be in your server. So while it looks like your entire discord community is getting banned, it is not.

### Is {{ site.bot_name }} open source?

Yes! You can see the [project source code here](https://github.com/SocksTheWolf/AntiScamBot).

{% if site.discord_uses_intents == true %}
#{% include intents.html %}
{% endif %}

### What information do you store?

You can [view our privacy policy right here](/privacy)!

### Is there a terms of service for using {{ site.bot_name }}?

Yes, you can [view that page here](/terms)!

## Commission Scammers
---

### What is a commission scammer?

Commission scammers are users/bots on Discord who send unsolicited direct messages demanding that you commission the scammer that you do not know to buy their traced/AI/stolen artwork. In some instances, they charge your payment account (Paypal, Boosty, etc) and never deliver anything.

They will always solicit you first. Do not give these scammers your money.

### Why is the icon of the bot "hey^^"?

When these scammers first ran rampant, they would always open their dms with the message "hey^^". It was really easy to tell if someone was fake because of it.

## The Process
---

### How does {{ site.bot_name }} know who is a commission scammer?

User reports. Vetters go through the user report and then trigger a ban on the user in question if they are a scammer.

### What about abuse?

So currently, this bot requires that someone with a "Trusted" role approves the scammers proposed. If they are approved, the ban will be blasted to all servers that subscribe to {{ site.bot_name }}. 

### How do I know if someone was banned by {{ site.bot_name }}?

The name of the person that initiated this action as well as the user that it happened to will be blasted to a subscribable Discord feed via the announcement channel, of which you can get updates as to the going ons. It is recommended you add the feed as a webhook to your server.

![{{ site.bot_name }} Action Feed Screenshot](/assets/botbanchannel.png){:.centered}

All bans will be logged into your server's audit log. You can revert any ban if you wish and {{ site.bot_name }} will not attempt to re-add it unless you explicitly ask it to reimport bans for your server.

### How do I report a scam?

Join the TAG server! The combat potential abuse, the ability to report is granted on a timer based on how long you are in the server. Users of the bot will be granted access upon successful activation.

Reports are not visible until then.

### Can {{ site.bot_name }} ever ban the server owner or mods?

{{ site.bot_name }} cannot ban anyone who has a role located higher in the roles list than it. The only exception to this rule is if you transfer your server ownership to the bot (don't do this). It is suggested to put the role for {{ site.bot_name }} directly above your general role or underneath your moderator role.

### What about mistakes?

{{ site.bot_name }} can revert any mistakes and unban someone if this needs to happen, approvers have a command to reverse any scam bans that the database knows about (it cannot randomly unban any user, {{ site.bot_name }} can only unban users marked that it banned originally). 

You can also just simply unban the user. 

## The Group
---

### What is "The Antiscam Group"?

It's just a silly little name for the Discord server.

### How do I join the group?

This isn't a formal collective or anything of the sort. It's literally a bunch of people who keep getting commission scams and those that have community servers that use {{ site.bot_name }}.

### I don't have a Discord server, can I join the TAG server?

Yes! If you're getting commission scams, feel free to join and report them. However, realize that the TAG server isn't a social community. Streamer communities are much better suited for that.