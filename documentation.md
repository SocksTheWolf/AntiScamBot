#  ScamGuard Command Documentation

The commands for the bot can be accessed by running them via `/scamguard command`.

Certain commands have access restrictions consisting of any, or all of the following: cooldown, execution location, role, permission; these are detailed inside each command.

Commands listed here are grouped by access via execution location.

## Administrative
> These commands are only available only on the primary command and control server

### `info`
|     |     |
| --- | --- | 
| Description | Prints an embed with details about ScamGuard |
| Cooldown | once every 3 seconds |
| Restricted to | MaintainerRole |

### `backup`
|     |     |
| --- | --- | 
| Description | Causes ScamGuard to backup and archive its internal database outside of its normal scheduled time |
| Restricted to | MaintainerRole |

### `forceleave server`
|     |     |
| --- | --- | 
| Description | Forces ScamGuard to leave |
| Cooldown | once every 3 seconds |
| Restricted to | MaintainerRole |

| Arguments | Type |
| --- | --- |
| server |  discord id of a server |

### `forceactivate server`
|     |     |
| --- | --- | 
| Description | Forces ScamGuard activate on a server |
| Restricted to | MaintainerRole |

| Arguments | Type |
| --- | --- |
| server | discord id of a server |

### `retryactions server count`
|     |     |
| --- | --- | 
| Description | Forces ScamGuard to retry a set of actions on a server |
| Restricted to | MaintainerRole |

| Arguments | Type |
| --- | --- |
| server |  discord id of a server |
| count | count of last actions to retry |

### `retryinstance instance count`
|     |     |
| --- | --- | 
| Description | Forces ScamGuard to retry a set of actions for a instance of ScamGuard |
| Restricted to | MaintainerRole |

| Arguments | Type |
| --- | --- |
| instance | id of a ScamGuard instance |
| count | count of last actions to retry |

### `ping instance`
|     |     |
| --- | --- | 
| Description | Pings an instance of ScamGuard |
| Restricted to | MaintainerRole |

| Arguments | Type |
| --- | --- |
| instance | id of a ScamGuard instance |

### `print`
|     |     |
| --- | --- | 
| Description | Prints stats and information about all connected ScamGuard instances |
| Restricted to | MaintainerRole |

### `scamban userid`
|     |     |
| --- | --- | 
| Description | Bans a user id |
| Restricted to | MaintainerRole |

| Arguments | Type |
| --- | --- |
| userid | discord userid to ban |

### `scamunban userid`
|     |     |
| --- | --- | 
| Description | Unbans a user id |
| Restricted to | MaintainerRole |

| Arguments | Type |
| --- | --- |
| userid | discord userid to unban |

### `activate`
|     |     |
| --- | --- | 
| Description | Activates all servers and brings in previous bans if caller owns any known servers |

### `deactivate`
|     |     |
| --- | --- | 
| Description | Deactivates all servers and prevents any future ban information from being shared if the caller owns any known servers |

### `scamcheck userid`
|     |     |
| --- | --- | 
| Description | Checks to see if a userid is banned |
| Cooldown | once every 3 seconds |

| Arguments | Type |
| --- | --- |
| userid | discord userid to check |


## Global
> These commands can be run on any server where ScamGuard is joined

### `check userid`
|     |     |
| --- | --- | 
| Description | Checks to see if a userid is banned |
| Permissions | can ban members |

| Arguments | Type |
| --- | --- |
| userid | discord userid to check |

### `setup`
|     |     |
| --- | --- | 
| Description | Run ScamGuard setup |
| Cooldown | once every 5 seconds |
| Permissions | can ban members |

### `config`
|     |     |
| --- | --- | 
| Description | Configure ScamGuard settings |
| Permissions | can ban members |

### `info`
|     |     |
| --- | --- | 
| Description | Prints info and stats about ScamGuard |
| Cooldown | once every 5 seconds |
