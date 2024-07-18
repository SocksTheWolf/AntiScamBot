---
title: Privacy Policy
description: The Privacy Policy for the ScamGuard Discord bot
redirect_from: /privacy-policy
previous: /
---

> Last Updated: 7/18/2024

The usage of this service/application ("bot") in your server requires the collection of some specific user data. Usage and interaction of {{ site.bot_name }} ("the bot") is considered an agreement to this policy.

## What is collected?

The usage of the bot requires the following data collected:

* A numeric value that represents a Discord Server ("Server ID")
* A numeric value that represents the Owner ID of the Server ("Owner ID")
* A value that represents if the bot is "activated" in a server with the "Server ID" ("Activated").
* Settings related to {{ site.bot_name }}'s configuration in your server.

For the TAG approver/review team, the following information is stored when they ban an scammer:

* The approver's Discord username
* The approver's Discord user id
* The time the ban was executed

This collection of data may expand or modify in the future, but will usually stay within the scope of minimal collection as per the recommendations of Discord and their Terms of Service.

## Who has access to that data?

Users in the control server that have the "maintenance" role may view the current list of activated servers, and some of the server ids may be visible in the logs/logging notifications that the bot sends periodically.

While external access is protected, this is not guarenteed and the bot owners assume no liability for the unintentional or malicious breach of any data. In the event of unauthorized data access, users in [the control server](/discord) will be alerted.

## Where is the data stored?

It is currently stored in a sqlite database that the bot has access to. There is no external access to the database.

## Do you store information about users?

Outside of the information laid out above, no.

## How do I remove the data the bot has on me/my servers?

Kick/remove the bot from your server. Data will be removed the next time the bot is either online or is processing events.

Data will be fully removed from the active working database and all backups within three calendar weeks.

{% if site.discord_uses_intents == true %}
{% include intents.html %}
{% endif %}

## What about reporting scams from the website?

Data submitted via the [report page](/report) is handled in transit by Zapier and is [subject to their data policy](https://zapier.com/legal/data-privacy). Form data is eventually stored at rest on the TAG support server, and is under the terms set forth by Discord's Privacy Policy itself.

## What about...?

For more information, you can check the [Discord Privacy Policy](https://discord.com/privacy).
