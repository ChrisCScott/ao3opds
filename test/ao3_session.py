""" Provides an AO3.Session for testing. """

import AO3
# Get username and password for testing:
try:
    from credentials import USERNAME, PASSWORD
except:
    USERNAME = input("AO3 username: ")
    PASSWORD = input("Password for {username}: ".format(username=USERNAME))

# This raises an AO3.utils.LoginError if unsuccessful.
# If this module is being used, login failure likely _should_ be fatal,
# so don't handle it here:
TEST_SESSION = AO3.Session(USERNAME, PASSWORD)

# We don't pickle the session, as they expire.
