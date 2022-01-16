""" Generate an OPDS feed from an AO3 user's Marked for Later list. """

import sys
import warnings
import argparse
import AO3
from opds import AO3OPDS, OPDSPerson

FEED_ID = "christopherscott.ca/apps/ao3opds/{username}"
FEED_TITLE = "{username}'s AO3 Feed"
FEED_AUTHOR = OPDSPerson(
    name='Christopher Scott',
    uri='christopherscott.ca',
    email='christopher@christopherscott.ca')

# Parse command-line arguments:
parser = argparse.ArgumentParser(
    # Use module docstring as description:
    description=sys.modules[__name__].__doc__)
parser.add_argument(
    '-u', '--username', '--user', default=None, type=str, required=False,
    help='AO3 username', dest='username', metavar='username')
parser.add_argument(
    '-p', '--password', '--pass', default=None, type=str, required=False,
    help='AO3 password', dest='password', metavar='password')
namespace = parser.parse_args()
username = namespace.username
password = namespace.password

# If session args weren't passed, request them from the user:
if username is None:
    username = input('AO3 username: ')
if password is None:
    password = input('AO3 password: ')

# Authenticate with AO3:
try:
    session = AO3.Session(username, password)
except AO3.utils.LoginError:
    warnings.warn(f'Could not log in to AO3 as {username}.')
    quit()

# Get the user's Marked for Later list:
# TODO: Add `sleep` and `timeout_sleep` args to parser?
marked_for_later = session.get_marked_for_later()
# The current version of `ao3_api` does not set the session on works
# returned from `session.get_marked_for_later()`, so do that here:
for work in marked_for_later:
    work.set_session(session)

# Generate an OPDS feed for the works:
feed = AO3OPDS(
    marked_for_later,
    id=FEED_ID.format(username=username),
    title=FEED_TITLE.format(username=username),
    authors=FEED_AUTHOR)

# Print to stdout, leave it to the shell to redirect:
print(feed.render())
