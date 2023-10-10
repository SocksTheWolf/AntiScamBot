## How to contribute to AntiScamBot
---

# Did you:

## Find a bug?

* Check to see if the bug has already been submitted under [the issues page](https://github.com/SocksTheWolf/AntiScamBot/issues)
* If it has not been submitted, please open a new one. Make sure to do the following:
    * Have a simple title
    * Clear, detailed description
    * Include any information to reproduce the bug
    * Add appropriate labels. Do not add the `critical` label
    * Do not assign the bug to anyone

## Write a patch that fixes a bug?

**DO NOT** submit security fixes via this method. Instead, please follow the methods outlined in the [security document found here](/SECURITY.md).

* Open a new Github pull request with your patch changes

* Ensure the PR description contains information about what the problem is and the solution. Please link to the issue number using `#NUMBER` if the issue is being tracked.

* Make sure that your code follows the general style of other files in the project, you'll notice some of the qwerks as you read. But in general:
    * Two spaces for indenting
    * if condtionals are always wrapped in paratheses.
    * We use title case for everything
    * Proper error handling
    * Ususally variables are explicitly typed, unless they are a list.

## Fix whitespace, formatting, or make purely cosmetic code changes?

Unless the changes were previously [issue tracked](https://github.com/SocksTheWolf/AntiScamBot/issues), then these changes will be likely not be accepted into the project. [Rails has good rational](https://github.com/rails/rails/pull/13771#issuecomment-32746700) as to why these changes can bog down a project.

## Fix typos, gramatical errors on the website?

Usually these will be taken, but very not often. 

You're welcome to propose changes to the website.

## Intended to add a new feature or upgrade an existing one?

Please suggest your ideas in the `suggestions` forum section of the TAG Server, before writing any code. There may be existing reasoning to why something has not been implemented that may not be immediately clear.

Please also do not open a Github issue unless instructed to do so. The issues page is primarily used for bugs and tasks to move into the full fledged release (we are still early access).

## Have questions about how the bot is used?

Please ask that in the support channel of the TAG discord.