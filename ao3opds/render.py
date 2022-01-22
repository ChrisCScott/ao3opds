""" Generate an OPDS feed from an AO3 user's Marked for Later list. """

import warnings
import AO3
from ao3opds.opds import OPDSPerson, AO3OPDS

# Default values for Feed:
FEED_NAMES = {
    'marked_for_later': "Marked for Later",
    'bookmarks': "Bookmarks",
    'subscriptions': "Subscriptions",
    'history': "History"
}
FEED_ID = "christopherscott.ca/apps/ao3opds/feed/{feed_id}"
FEED_TITLE = "{username}'s AO3 {feed_title} list"
FEED_AUTHOR = OPDSPerson(
    name='Christopher Scott',
    uri='christopherscott.ca',
    email='christopher@christopherscott.ca')
MAX_HISTORY_PAGES_DEFAULT = 3

def _feed_opds(feed_id, works, session, id, title, authors, threaded):
    """ Fetches a feed for `works` """
    # The current version of `ao3_api` does not set the session on works
    # returned from methods such as `session.get_marked_for_later()`,
    # so do that here:
    for work in works:
        work.set_session(session)
    # Default arguments:
    if id is None:
        id=FEED_ID.format(feed_id=feed_id)
    if title is None:
        title=FEED_TITLE.format(
            username=session.username, feed_title=FEED_NAMES[feed_id])
    if authors is None:
        authors=[FEED_AUTHOR]

    # Generate an OPDS feed for the works:
    opds = AO3OPDS(
        works, id=id, title=title, authors=authors, threaded=threaded)
    feed = opds.render()
    return feed

def marked_for_later_opds(
        session: AO3.Session, id:str=None, title:str=None,
        authors:list[OPDSPerson]=None, threaded=False) -> str:
    """ Returns an OPDS feed of Marked for Later works for a user. """
    if session is None:
        return None
    # Get the user's Marked for Later list:
    works: list[AO3.Work] = session.get_marked_for_later()
    feed_id = 'marked_for_later'
    return _feed_opds(feed_id, works, session, id, title, authors, threaded)

def bookmarks_opds(
        session: AO3.Session, id:str=None, title:str=None,
        authors:list[OPDSPerson]=None, threaded=False) -> str:
    """ Returns an OPDS feed of bookmarks works for a user. """
    if session is None:
        return None
    # Get the user's bookmarks and convert them to Works:
    bookmarks:list[tuple] = session.get_bookmarks(use_threading=threaded)
    works: list[AO3.Work] = [AO3.Work(
        work_id, session, load=False) for (work_id, _, _) in bookmarks]
    feed_id = 'bookmarks'
    return _feed_opds(feed_id, works, session, id, title, authors, threaded)

def subscriptions_opds(
        session: AO3.Session, id:str=None, title:str=None,
        authors:list[OPDSPerson]=None, threaded=False) -> str:
    """ Returns an OPDS feed of works in a user's subscriptions list. """
    if session is None:
        return None
    # Get the user's subscriptions (limited to Works):
    works:list[AO3.Work] = session.get_work_subscriptions(
        use_threading=threaded)
    feed_id = 'subscriptions'
    return _feed_opds(feed_id, works, session, id, title, authors, threaded)

def history_opds(
        session: AO3.Session, id:str=None, title:str=None,
        authors:list[OPDSPerson]=None, threaded=False,
        max_pages=MAX_HISTORY_PAGES_DEFAULT) -> str:
    """ Returns an OPDS feed of works in a user's subscriptions list.

    This method performs a first pass of a user's history in a
    non-threaded way. The second pass, where the method loads metadata
    for each work, supports threading.
    """
    if session is None:
        return None
    # Get the user's history (limiting pages to avoid rate-limits):
    history:list[tuple] = session.get_history(max_pages=max_pages)
    works:list[AO3.Work] = [work for (work, _, _) in history]
    feed_id = 'history'
    return _feed_opds(feed_id, works, session, id, title, authors, threaded)
