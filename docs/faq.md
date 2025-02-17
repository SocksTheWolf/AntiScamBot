---
title: FAQ
description: Answers regarding ScamGuard, what it does and other things!
previous: /
---

## {{ site.bot_name }} Info

---

### How do I enable {{ site.bot_name}} in my server?

{% include install_info.html %}

### Why does {{ site.bot_name }} need the permissions it has?

Because of how Discord handles permissions it needs the following permissions:

* `Create Commands`: For implementing the various application slash commands.

* `Send Messages`: To send responses to commands that are executed.

* `Ban Members`: To execute the bans on scammers.

* `Embed Links`: To give you information when you run `/scamguard check` and other commands.

* `Manage Webhooks`: To allow for subscribing to the ban notification feed if you so choose during setup.

* `View Channels`: To handle sending messages on initial setup.

### When I activate the bot, why is it suddenly banning hundreds of accounts?

{{ site.bot_name }} imports all the bans of scammers that it knows about. This can be several hundreds of accounts, but not to worry, due to the way {{ site.bot_name }} processes bans, these accounts do not have to be in your server. So while it looks like your entire discord community is getting banned, it is not.

### Someone messaged me saying they're unable to get into my server, is that ScamGuard's doing?

This is an _extremely rare_ occurance.

You can run a `/scamguard check` against their user id to see if they're registered as a scammer in {{ site.bot_name }}. If it comes back as false, then the user was likely marked as a suspicious IP by Discord.
This can happen if a scammer previously had their IP address (as IP addresses often recycle to various people) and made several accounts, or violated their TOS.

Sometimes, when a scam account is banned, Discord will also flag the IP the account when you get the ban imported by the bot. This is considered a feature by Discord.

Legitimate users can get around this Discord behavior by joining the server on mobile instead.

### Is {{ site.bot_name }} open source?

Yes! You can see the [project source code here](https://github.com/SocksTheWolf/AntiScamBot).

{% if site.discord_uses_intents == true %}
#{% include intents.html %}
{% endif %}

### What information do you store?

You can [view our privacy policy right here](/privacy)!

### Is there a terms of service for using {{ site.bot_name }}?

Yes, you can [view that page here](/terms)!

### Why is the icon of the bot "hey^^"?

When these scammers first ran rampant, they would always open their dms with the message "hey^^". It was really easy to tell if someone was fake because of it.

## How to use

---

This section assumes that you are either in a server that has or you have installed the bot and went through the setup steps.

### How do I report a scam?

Currently we support three different ways of reporting a scam!

* Via the `/scamguard report` command the bot has
* Via the [Discord Server](/discord)
* Via the [web report system](/report)

Reports are not immediately visible to newly joined servers of the server to combat potential abuse.

When you report an user, you'll be asked to provide some image evidence, this is important when determining appropriate action.

<span class="install-note">**SUGGESTION**: When you go to ban an user from Discord from your server, use the bot's report function beforehand, that way you can make the ban more impactful, and help protect others too!</span>

### How do I know if someone is already banned?

A couple of different ways!

* Via the server feed (see below) that you can install when setting up the bot
* Via [the API](/api)
* Running the command `/scamguard check` with an user id or a discord handle

![{{ site.bot_name }} Action Feed Screenshot](/assets/botbanchannel.png){:.centered}

All bans will be logged into your server's audit log. You can revert any ban if you wish and {{ site.bot_name }} will not attempt to re-add it unless you explicitly ask it to reimport bans for your server.

## Scammers

---

### What is a scammer?

Scammers are users/bots on Discord who send unsolicited direct messages demanding that you commission the scammer that you do not know to buy their traced/AI/stolen artwork. In some instances, they charge your payment account (Paypal, Boosty, etc) and never deliver anything.

This is not a complete list, but these are also scams as well:

* Ask you to playtest their game out of the blue (this is usally from someone getting their account compromised)
* Ask you what you'd do with sudden influxes of cash (the "sugar momma" scam)
* Direct solicitation of commissions
* Stolen/traced/obvious AI artwork
* Fake steam game offers, phishing links
* Impersonating other users
* Management/Methods to boost your channel

They will always solicit you first. Do not give these scammers your money.

## The Process

---

### How does {{ site.bot_name }} know who is a scammer?

User reports via the bot or the website! {{ site.bot_name }} has a Trust and Safety team that reviews each user report and takes appropriate action.

### What about abuse?

So currently, this bot requires that someone with a "Trusted" role approves the scammers proposed. If they are approved, the ban will be blasted to all servers that subscribe to {{ site.bot_name }}.

### Can {{ site.bot_name }} ever ban the server owner or mods?

{{ site.bot_name }} cannot ban anyone who has a role located higher in the roles list than it. The only exception to this rule is if you transfer your server ownership to the bot (don't do this). It is suggested to put the role for {{ site.bot_name }} directly above your general role or underneath your moderator role.

### What about mistakes?

{{ site.bot_name }} can revert any mistakes and unban someone if this needs to happen, approvers have a command to reverse any scam bans that the database knows about (it cannot randomly unban any user, {{ site.bot_name }} can only unban users that it banned originally).

You can also just simply unban the user.

## The Group

---

### What is "The Antiscam Group"?

It's just a silly little name for the Discord server.

### How do I join the group?

This isn't a formal collective or anything of the sort. It's literally a bunch of people who keep getting commission scams and those that have community servers that use {{ site.bot_name }}.

### I don't have a Discord server, can I join the TAG server?

Yes! If you're getting commission scams, feel free to join and report them. However, realize that the TAG server isn't a social community. Streamer communities are much better suited for that.
