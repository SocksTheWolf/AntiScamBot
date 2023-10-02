---
title: Privacy Policy
description: The Privacy Policy for the Discord bot
previous: /
---

# Privacy Policy

The usage of this service/application ("bot") in your server requires the collection of some specific user data. Usage and interaction of the bot is considered an agreement to this policy. 

## What is collected?

The usage of the bot requires the following data collected:

* A numeric value that represents a Discord Server ("Server ID")
* A numeric value The Discord Owner ID of the Server ("Owner ID")
* A value that represents if the bot is "activated" in a server with the "Server ID" ("Activated").

If you are a trusted approver, the following information is stored when you ban an user in the TAG server:

* Your global discord username
* Your discord user id
* The time the ban was executed

This collection of data may expand or modify in the future, but will usually stay within the scope of minimal collection as per the recommendations of Discord and their Terms of Service.

## Who has access to that data?

Users in the control server that have the "maintenance" role may view the current list of activated servers, and some of the server ids may be visible in the logs/logging notifications that the bot sends periodically.

While external access is protected, this is not guarenteed and the bot owners assume no liability for the unintentional or malicious breach of any data. In the event of unauthorized data access, users in [the control server](/discord) will be alerted.

## Where is the data stored?

It is currently stored in a sqlite database that the bot has access to.

## How do I remove the data the bot has on me/my servers?

Kick/remove the bot from your server. Data will be removed the next time the bot is either online or is processing events.

## Everything else

For more information, you can check the [Discord Terms Of Service](https://discord.com/terms).