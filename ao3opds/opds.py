""" Provides basic OPDS support for AO3 works. """

from dataclasses import dataclass
import datetime
import mimetypes
import urllib.parse
from typing import Iterable
import warnings
from jinja2 import Environment, PackageLoader, select_autoescape
import AO3

env = Environment(
    loader=PackageLoader("ao3opds"),
    autoescape=select_autoescape(),
    trim_blocks=True)

AO3_PUBLISHER = "Archive of Our Own"
AO3_TAG_SCHEMA = 'https://archiveofourown.org/faq/tags'
AO3_IMAGE_LINK_REL = 'http://opds-spec.org/image'
AO3_IMAGE_LINK_REL_THUMB = 'http://opds-spec.org/image/thumbnail'
AO3_ACQUISITION_LINK_REL = 'http://opds-spec.org/acquisition'
AO3_DOWNLOAD_FILETYPES = ('AZW3', 'EPUB', 'HTML', 'MOBI', 'PDF')
AO3_URL_BASE = 'https://archiveofourown.org/'

# AO3 provides support for 'AZW3', 'EPUB', 'HTML', 'MOBI', and 'PDF'
AO3_DOWNLOAD_MIME_TYPES = {
    '.azw3': 'application/x-mobi8-ebook',
    '.epub': 'application/epub+zip',
    '.html': 'text/html',
    '.mobi': 'application/x-mobipocket-ebook',
    '.pdf': 'application/pdf'}
# Ensure mimetypes supports each of these:
for ext, type_ in AO3_DOWNLOAD_MIME_TYPES.items():
    mimetypes.add_type(type_, ext)

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
        if self.authors is None:
            self.authors = []

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

    def __init__(self,
            work:AO3.Work,
            acquisition_filetypes: str | Iterable[str]=None,
            get_content:bool=False, get_images:bool=False):
        self.work = work
        # Ensure the work's metadata is loaded
        if not work.loaded:
            # Only load the full-text if we need to:
            load_chapters = get_content or get_images
            try:
                work.reload(load_chapters=load_chapters)
            except AO3.utils.InvalidIdError as error:
                warnings.warn(f'Could not load work #{work.id}')
        # pylint: disable=private-access
        # `AO3` does not provide a way to access certain attributes of
        # a work's metadata, so we sometimes need to parse the HTML
        # ourselves. We can access it as a pre-loaded BeautifulSoup
        # object via `AO3.Work._soup`.
        self._soup = work._soup
        # pylint: enable=private-access

        # Instantiate!
        self.title = work.title
        self.id = str(work.url).lower() # lowercase recommended for id
        # It's not clear how AO3 differentiates between edits and
        # updates, but for OPDS purposes we want to use whichever one
        # is later. (AO3.Work guarantees these are non-None; they fall
        # back to AO3.Work.date_published if never updated/edited:)
        if work.date_edited > work.date_updated:
            updated = work.date_edited
        else:
            updated = work.date_updated
        self.updated = updated.astimezone(datetime.timezone.utc).isoformat()
        # Ensure `authors` is non-None. We iterate over it in `render()`
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
        self.links.extend(self.get_acquisition_links(
            filetypes=acquisition_filetypes))

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
        tags = (
            self.work.categories + self.work.fandoms + self.work.characters +
            self.work.relationships + self.work.warnings + self.work.tags)
        if self.work.rating is not None:  # `rating` is an item, not a list
            tags.append(self.work.rating)
        # The `term` element of an OPDS category would ideally point to
        # the URL for each tag (e.g. for the "Explicit" tag, this would
        # be https://archiveofourown.org/tags/Explicit).
        # The element "label" is the human-readable term for that
        # specific tag. The "scheme" element is the same for all tags.
        categories = [
            OPDSCategory(self._tag_to_url(tag), AO3_TAG_SCHEMA, tag)
            for tag in tags]
        return categories

    def _tag_to_url(self, tag):
        """ Gets the url for an AO3 tag. """
        # Find the link that points to `tag` and return its url:
        link = self._soup.find('a', string=tag)
        if link is not None:
            url = link.attrs['href']
            # Trim trailing `/works` portion of URL, if present:
            url = url.removesuffix('/works')
            return url
        # Every tag on AO3 maps to a url of the form
        # `https://archiveofourown.org/tags/{tag-stub}`.
        # AO3 uses an idiosyncratic url-encoding for tag-stubs; e.g.
        # they encode '&' as '*a*' instead of '%26', they don't encode
        # single-quotes ("'"), they do encode dots ('.'->'*d*'), and
        # so on. Plus, some tags and stubs use different text; e.g.
        # 'Creator Chose Not To Use Archive Warnings' has the stub
        # 'Choose Not To Use Archive Warnings' (after url-unquoting).
        # If we wanted to manually create urls for tags, we'd need:
        #   (a) a list of characters that are (or aren't) url-quoted
        #   (b) a mapping of characters that are specially-quoted to
        #       their quote pattern (e.g. '.'->'*d*').
        #   (c) a mapping of tags with special tag-url mappings to urls
        #       (e.g. 'Creator Chose Not To Use Archive Warnings' ->
        #       'Choose Not To Use Archive Warnings')
        # We don't have those things, and in testing the above seems to
        # work fine, so rather than try to guess urls we'll just return
        # the tag itself on failure (which is permitted; `term` does
        # not have to be a URI or otherwise be machine-readable.)
        return tag

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
            # `mimetypes` seems to have better luck if URLs are stripped
            # of any non-path elements (i.e. query/fragment suffixes):
            url_parts = urllib.parse.urlsplit(url)
            guess_url = urllib.parse.urlunsplit((*url_parts[0:3], None, None))
            # Infer the MIME-type of the file (None if not inferable)
            (mime, _) = mimetypes.guess_type(guess_url)
            links.append(
                OPDSLink(
                    url, rel=AO3_ACQUISITION_LINK_REL, type=mime,
                    hreflang=self.work.language,
                    title=self._get_acquisition_link_title(mime)))
        return links

    def _get_acquisition_link_title(self, mime_type:str | None):
        """ Gets a link title for an acquisition link based on mime-type """
        # If we don't know the mime-type, return a generic title:
        if mime_type is None:
            return f'Download link for {self.work.title}'
        # Otherwise, try to infer the extension for this type of file:
        ext = mimetypes.guess_extension(mime_type)
        # If we can't, use the generic title above:
        if ext is None:
            return self._get_acquisition_link_title(None)
        # If we can infer the filetype, use a more informative title:
        # First, convert mime-type extensions (e.g. '.pdf') to something
        # friendlier (e.g. 'PDF)
        filetype = ext.upper()
        if filetype[0] == '.':
            filetype = filetype[1:]
        return f'{filetype} download link for {self.work.title}'

    def _extract_download_urls(
            self, filetypes: str | Iterable[str]=None) -> Iterable[str]:
        """ Extracts download urls for an `AO3.Work` """
        download_list = self._soup.find("li", {"class": "download"})
        # For convenience, allow users to pass a single filetype as str:
        if isinstance(filetypes, str):
            filetypes = [filetypes]
        # Convert filetypes to lowercase for easy comparison:
        if filetypes is not None:
            filetypes = list(map(str.lower, filetypes))
        # Collect a list of download links:
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
