# Executing the tests
On the root directory, run pytest. SetupDatabase() is called within the test to setup the db file and it uses the config path to remove it inbetween tests to keep them clean

# Current Test Coverage
-  Simple Ban, duplicate ban, Unban functionality
-  Ban with servers in db that are not activated doesn't make ban calls
-  Activating servers only trigger bans on appriopriate servers 