""" Generate an OPDS feed from an AO3 user's Marked for Later list. """

import warnings
import AO3
from ao3opds.opds import OPDSPerson, AO3OPDS

# Default values for Feed:
FEED_ID = "christopherscott.ca/apps/ao3opds/{username}"
FEED_TITLE = "{username}'s AO3 Marked for Later list"
FEED_AUTHOR = OPDSPerson(
    name='Christopher Scott',
    uri='christopherscott.ca',
    email='christopher@christopherscott.ca')

def get_AO3_session(username, password):
    """ Authenticates a user with AO3. """
    try:
        session = AO3.Session(username, password)
    except AO3.utils.LoginError as error:
        warnings.warn(f'Could not log in to AO3 as {username}: ' + str(error))
        return None
    return session

def get_marked_for_later_opds(
        session: AO3.Session | tuple[str, str],
        id:str=None, title:str=None, authors:list[OPDSPerson]=None):
    """ Returns an OPDS feed of Marked for Later lists for a user. """
    # Log in if a (username, password) pair were provided:
    if not isinstance(session, AO3.Session):
        session = get_AO3_session(session[0], session[1])
    if session is None:
        return None
    # Get the user's Marked for Later list:
    marked_for_later = session.get_marked_for_later()
    # The current version of `ao3_api` does not set the session on works
    # returned from `session.get_marked_for_later()`, so do that here:
    for work in marked_for_later:
        work.set_session(session)

    # Default arguments:
    if id is None:
        id=FEED_ID.format(username=session.username)
    if title is None:
        title=FEED_TITLE.format(username=session.username)
    if authors is None:
        authors=[FEED_AUTHOR]

    # Generate an OPDS feed for the works:
    opds = AO3OPDS(marked_for_later, id=id, title=title, authors=authors)
    feed = opds.render()
    return feed
