""" CLI script to generate an OPDS feed from a Marked for Later list. """

import sys
import os
import warnings
import argparse
import AO3
from ao3opds.render import marked_for_later_opds
from opds import AO3OPDS, OPDSPerson

# Parse command-line arguments:
parser = argparse.ArgumentParser(
    # Use module docstring as description:
    description=sys.modules[__name__].__doc__)
# Provide args for username and password (also passable via environment
# variable):
parser.add_argument(
    '-u', '--username', '--user', type=str, required=False,
    help='AO3 username', dest='username', metavar='username',
    default=os.environ.get('AO3USERNAME'))
parser.add_argument(
    '-p', '--password', '--pass', type=str, required=False,
    help='AO3 password', dest='password', metavar='password',
    default=os.environ.get('AO3PASSWORD'))
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
except AO3.utils.LoginError as error:
    warnings.warn(f'Could not log in to AO3 as {username}: ' + str(error))
    quit()

feed = marked_for_later_opds(session, threaded=True)

# Print to stdout, leave it to the shell to redirect:
print(feed)
