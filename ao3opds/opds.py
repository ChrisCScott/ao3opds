""" Provides basic OPDS support for AO3 works. """

from dataclasses import dataclass
import datetime
import mimetypes
import urllib.parse
from typing import Iterable
from jinja2 import Environment, PackageLoader, select_autoescape
import AO3

env = Environment(
    loader=PackageLoader("ao3opds"),
    autoescape=select_autoescape())

FEED_ID_DEFAULT = "christopherscott.ca/apps/ao3opds/{username}"
FEED_TITLE_DEFAULT = "{username}'s AO3 Feed"

AO3_PUBLISHER = "Archive of Our Own"
AO3_TAG_SCHEMA = 'https://archiveofourown.org/faq/tags'
AO3_IMAGE_LINK_REL = 'http://opds-spec.org/image'
AO3_ACQUISITION_LINK_REL = 'http://opds-spec.org/acquisition'
AO3_DOWNLOAD_FILETYPES = ('AZW3', 'EPUB', 'HTML', 'MOBI', 'PDF')
AO3_URL_BASE = 'https://archiveofourown.org/'

@dataclass
class OPDSLink:
    """ An object renderable as an atom:link. """
    href: str # required
    rel: str = None
    type: str = None
    hreflang: str = None
    title: str = None
    length: int = None

@dataclass
class OPDSPerson:
    """ An object renderable as an atom:Person. """
    name: str # required
    uri: str = None
    email: str = None

@dataclass
class OPDSCategory:
    """ An object renderable as an atom:category. """
    term: str
    scheme: str = None
    label: str = None

class AO3OPDS:
    """ An object renderable as a OPDS feed of AO3 works. """

    def __init__(
            self, works: Iterable[AO3.Work], id: str, title: str,
            links: Iterable[OPDSLink]=None, updated:datetime.datetime=None,
            authors: Iterable[OPDSPerson]=None):
        self.id: str = id  # required
        self.title: str = title # required

        self.links: Iterable[OPDSLink] | None = links
        if links is None:
            self.links = []

        self.updated: datetime.datetime = updated
        if updated is None:
            now = datetime.datetime.now(datetime.timezone.utc)
            self.updated = now.isoformat()

        self.authors: Iterable[OPDSPerson] | None = authors

        self.entries: Iterable[AO3WorkOPDS] = []
        for work in works:
            self.entries.append(AO3WorkOPDS(work))

    def render(self):
        """ Renders this object as an OPDS feed. """
        # Pick the correct template (in this case, an OPDS feed):
        template = env.get_template("feed.xml")
        # Render the template for this feed and return the result:
        return template.render(self.__dict__)

class AO3WorkOPDS:
    """ An object renderable as an entry in an OPDS feed of AO3 works. """

    def __init__(self, work:AO3.Work, get_content=False, get_images=False):
        self.work = work
        # Ensure the work's metadata is loaded
        if not work.loaded:
            # Only load the full-text if we need to:
            load_chapters = get_content or get_images
            work.reload(load_chapters=load_chapters)

        # Instantiate!
        self.title = work.title
        self.id = str(work.url).lower() # lowercase recommended for id
        self.updated = work.date_updated.astimezone(
            datetime.timezone.utc).isoformat()
        self.authors = []
        for author in work.authors:
            self.authors.append(AO3UserOPDS(author))
        self.language = work.language
        self.publisher = AO3_PUBLISHER
        self.published = work.date_published.astimezone(
            datetime.timezone.utc).isoformat()
        self.summary = work.summary

        self.categories = self.extract_categories()

        self.content = None
        self.links = []

        # Add an OPDSLink for each acquisition option (EPUB/etc.)
        self.links.extend(self.get_acquisition_links())

        # Add full-text and links to images if we have been asked:
        # (Note: Either of these will cause the full text of the work
        # to be fetched from the web if it hasn't already.)
        if get_content:
            self.content = self.get_content()
        if get_images:
            self.links.extend(self.get_images())

    def extract_categories(self) -> Iterable[OPDSCategory]:
        """ Converts an `AO3.Work`'s tags into `OPDSCategory` objects """
        # AO3 uses the concept of 'tags', which includes fandom,
        # character, relationship, ratings, categories, warnings,
        # and additional tags. We need to add each of these.
        # Apply a separate label for each type for disambiguation.
        categories = []
        for tag in self.work.categories:
            categories.append(OPDSCategory(tag, AO3_TAG_SCHEMA, 'category'))
        for tag in self.work.fandoms:
            categories.append(OPDSCategory(tag, AO3_TAG_SCHEMA, 'fandom'))
        for tag in self.work.characters:
            categories.append(OPDSCategory(tag, AO3_TAG_SCHEMA, 'character'))
        for tag in self.work.relationships:
            categories.append(OPDSCategory(tag, AO3_TAG_SCHEMA, 'relationship'))
        for tag in self.work.warnings:
            categories.append(OPDSCategory(tag, AO3_TAG_SCHEMA, 'warning'))
        for tag in self.work.tags:
            categories.append(OPDSCategory(tag, AO3_TAG_SCHEMA, 'tag'))
        # Each work has exactly one rating:
        if self.work.rating is not None:
            categories.append(
                OPDSCategory(self.work.rating, AO3_TAG_SCHEMA, 'rating'))
        return categories

    def get_content(self) -> str:
        """ Extracts an `AO3.Work`'s full-text content (for all chapters) """
        # Load the full text of the work if not already loaded:
        if not self.work.chapters:
            self.work.load_chapters()
        # Load the full text of the work and store it:
        content = ""
        for chapter in self.work.chapters:
            content += chapter
        return content

    def get_images(self) -> Iterable[OPDSLink]:
        """ Converts an `AO3.Work`'s image links to `OPDSLink` objects. """
        # Load the full text of the work if not already loaded:
        if not self.work.chapters:
            self.work.load_chapters()
        # The method AO3.Work.get_images() returns an awkward data
        # structure: a dict with chapter keys and tuple values, where
        # the tuples' elements are pairs (paragraph_num, image_url). So:
        # `{chapter_num: ((paragraph_num, image_url),...)}`
        # We want to extract just the image URLs:
        image_dict = self.work.get_images()
        images = []
        for image_tuple in image_dict.values():
            for (_, image_url) in image_tuple:
                images.append(image_url)
        # Now convert each image URL to an OPDSLink:
        image_links = []
        for image in images:
            # Infer the MIME-type of the image (None if not inferable):
            (image_mime, _) = mimetypes.guess_type(image)
            image_links.append(
                OPDSLink(image, rel=AO3_IMAGE_LINK_REL, type=image_mime))
        return image_links

    def get_acquisition_links(
            self, filetypes:Iterable[str]=None
        ) -> Iterable[OPDSLink]:
        """ Converts an `AO3.Work`'s acquisition links to `OPDSLink`s. """
        links = []
        link_urls = self._extract_download_urls(filetypes)
        for url in link_urls:
            # Infer the MIME-type of the file (None if not inferable):
            (mime, _) = mimetypes.guess_type(url)
            links.append(
                OPDSLink(url, rel=AO3_ACQUISITION_LINK_REL, type=mime))
        return links

    def _extract_download_urls(self, filetypes: Iterable[str]=None) -> Iterable[str]:
        """ Extracts download urls for an `AO3.Work` """
        # pylint: disable=protected-access
        # This is the only way to access the download links for an
        # AO3.Work without re-fetching the page of the work separately.
        download_list = self.work._soup.find("li", {"class": "download"})
        # pylint: enable=protected-access
        if filetypes is not None:  # convert to lowercase for comparison
            filetypes = map(str.lower, filetypes)
        urls = []
        for download_option in download_list.findAll("li"):
            # Get the link for each download option:
            link = download_option.a
            # Skip non-selected filetypes:
            if filetypes is not None and link.getText().lower() not in filetypes:
                continue
            # The link is relative; resolve to an absolute reference:
            url = urllib.parse.urljoin(AO3_URL_BASE, link.attrs['href'])
            urls.append(url)
        return urls

    def render(self):
        """ Renders this object as an OPDS feed entry.

        NOTE: If you're generating an OPDS feed, you should call
        `AO3OPDS.render`, which will handle rendering of entries too.
        It's not generally necessary to call this method unless you're
        trying to do something clever(/dangerous).
        """
        # Pick the correct template (in this case, an OPDS feed entry):
        template = env.get_template("entry.xml")
        # Render the template for this entry and return the result:
        return template.render(self.__dict__)

class AO3UserOPDS:
    """ Renders an AO3.User as an atom:Person."""

    def __init__(self, user: AO3.User | str):
        if isinstance(user, str):
            self.name = user
            self.uri = None
        else:
            self.name = user.username
            self.uri = user.url
        self.email = None  # Not provided for AO3 authors

def get_acquisition_links(work:AO3.Work) -> list[str]:
    """ """
    # TODO: Will probably need to parse work._soup
    return []

# TODO: Write wrappers that turn AO3.Work into dicts of OPDS attributes,
# with helper functions that construct authors/contributors, links,
# and categories appropriately. (Consider using `mimetypes` module for
# generating mimetypes for images/etc; may need to hard-code mimetypes
# for links to OPDS resources, if any.)

# Attributes of AO3.Work that should be represented in an OPDS catalog:
#   1. title
#   2. EPUB url (and alternative links?)
#   3. authors
#   4. complete/WIP status
#   5. number of chapters
#   6. hits
#   7. kudos
#   8. comments (count)
#   9. restricted status
#   10. work count
#   11. language
#   12. bookmarks (count)
#   13. date published
#   14. date updated
#   15. tags
#   16. characters
#   17. relationships
#   18. fandoms
#   19. categories (c.f. https://archiveofourown.org/faq/tutorial-posting-a-work-on-ao3?language_id=en#pwtcategory)
#   20. warnings
#   21. rating
#   22. summary
#   23. AO3 canonical url
# Other attributes:
#   1. URN
#      (generate distinct UUID for each user by hashing username and
#       passing to uuid4()? Or create one UUID for the dynamic catalog?)
#      (c.f. https://docs.python.org/3/library/uuid.html)
#   2. Feed title
#      ("{username}'s Marked For Later list"?)
#   3. Related links?
#      (Only if providing OPDS catalogs for, e.g., bookmarks. Not in v1)
#   4. Updated
#      (Provide current time? Only if there are changes since last call?
#       Avoid repeated calls if within a short period of time?)
#   5. Author name
#      (me!)
#   6. Author URI
#      (my website!)
#
# OPDS 1.2 Entry Metadata tags:
# See https://datatracker.ietf.org/doc/html/rfc4287#page-17
#   1. author: atom:Person construct
#   2. category: term[, scheme, label]
#   3. contributor: atom:Person construct
#   4. generator: string[, uri, version]
#   5. icon: URL
#   6. id: uuid (may be canonical link to work)
#   7. link: href (URL), rel (URL), type (MIME), hreflang (language),
#      title (string), length (int)
#   8. logo: URL (2x1 aspect ratio)
#   9. published: atom:Date
#   10. rights: string
#   11. source: copy of metadata from source Atom feed
#   12. subtitle: string
#   13. summary: string
#   14. title: string
#   15. updated: atom:Date

# Support request with Bluehost to be added to Compilers group: 37925740
# Installing Python 3.10.1
# Login via SSH: ssh -p 2222 hristrf2@162.241.219.11
# To set up Python, follow instructions at:
# https://www.bluehost.com/help/article/python-installation
# To set up a WSGI application, try this:
# https://docs.cpanel.net/knowledge-base/web-services/how-to-install-a-python-wsgi-application/
# (Look into using Flask to serve CGI pages; perhaps a templating
# library to allow for generation of OPDS catalogs from a template)
