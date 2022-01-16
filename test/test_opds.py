""" Tests downloader.opds """

from copy import copy
import unittest
import datetime
import ao3opds.opds
from ao3_work import TEST_WORK, TEST_WORK_ID

class TestAO3ABC(unittest.TestCase):
    """ ABC for test cases of `ao3opds.opds` classes. """

    def setUp(self) -> None:
        # Get a work without fetching any data over the network:
        self.work = copy(TEST_WORK)
        # Change values to something easier to test:
        self.work.id = TEST_WORK_ID
        self.work.title = "Title"
        # Don't overwrite authors, as this is a list[AO3.User]:
        # self.work.authors = ["Author"]
        self.work.categories = ["Category"]
        self.work.characters = ["Character"]
        self.work.fandoms = ["Fandom"]
        self.work.language = "Language"
        self.work.rating = "Rating"
        self.work.relationships = ["Relationship"]
        self.work.summary = "Summary"
        self.work.tags = ["Tag"]
        self.work.url = "URL"
        self.work.date_published = datetime.datetime.now(
            datetime.timezone.utc)
        self.work.date_updated = self.work.date_published
        # We can't actually set `loaded` manually, which is why we
        # import a loaded work and set its variables. (An alternative
        # would be to use `unittest.mock.Mock` - maybe in the future.)
        # self.work.loaded = True
        return super().setUp()

class TestAO3OPDS(TestAO3ABC):
    """ Tests `ao3opds.opds.AO3OPDS` """

    def setUp(self) -> None:
        super().setUp()
        self.works = [self.work]

    def test_entries(self):
        """ Tests that AO3WorksOPDS attrs are processed. """
        opds = ao3opds.opds.AO3OPDS(self.works, id='id', title='title')
        # Confirm that self.works has the correct structure
        self.assertEqual(len(opds.entries), len(self.works))
        for index, entry in enumerate(opds.entries):
            # Check a couple of entry attributes to confirm that
            # each entry matches the corresponding Work:
            self.assertEqual(entry.title, self.works[index].title)
            self.assertEqual(entry.summary, self.works[index].summary)
            # Don't check id, since AO3.Work.id is a five-digit integer
            # that isn't sufficient for an OPDS id (which must be unique
            # across namespaces), so AO3OPDS generates a new id.

    def test_render_id(self):
        """ Tests that AO3OPDS feeds generate ids correctly. """
        tag = 'id'
        val = '123'
        opds = ao3opds.opds.AO3OPDS(self.works, id=val, title='title')
        feed = opds.render()
        # Confirm that each of the represented OPDS tags is in the feed:
        ref_val = '<{tag}>{val}</{tag}>'.format(tag=tag, val=val)
        self.assertIn(ref_val, feed)

    # TODO: Validate the OPDS feed as valid Atom via feedvalidator?
    # See: https://github.com/w3c/feedvalidator

class TestAO3WorkOPDS(TestAO3ABC):
    """ Tests `ao3opds.opds.AO3WorkOPDS`. """

    def test_init_title(self):
        """ Tests that the AO3WorkOPDS.title attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        self.assertEqual(opds.title, self.work.title)

    def test_init_authors(self):
        """ Tests that the AO3WorkOPDS.authors attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        for index, author_name in enumerate(self.work.authors):
            self.assertEqual(opds.authors[index].name, author_name)

    def test_init_categories(self):
        """ Tests that the AO3WorkOPDS.categories attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        # OPDS categories should include all AO3 tags, namely categories,
        # characters, fandoms, relationships, warnings, the rating, and
        # other tags. See https://archiveofourown.org/faq/tags
        tags = (
            self.work.categories + self.work.characters + self.work.fandoms +
            [self.work.rating] + self.work.relationships + self.work.tags +
            self.work.warnings)
        # AO3 categories are represented in the `term` element of an
        # OPDS category (scheme/label elements are optional metadata):
        categories = [category.term for category in opds.categories]
        for tag in tags:
            self.assertIn(tag, categories)

    def test_init_id(self):
        """ Tests that the AO3WorkOPDS.id attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        # AO3.Work.id is a five-digit integer. That isn't sufficient for
        # an OPDS id (which must be unique across namespaces).
        # Require that AO3OPDS generates a new canonical id that's
        # stable across test runs, namely the canonical url of the work.
        self.assertEqual(opds.id, self.work.url.lower())

    def test_init_updated(self):
        """ Tests that the AO3WorkOPDS.updated attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        # OPDS dates must be ISO-formatted (this test has no requirement
        # on the specific datetime value)
        try:
            datetime.datetime.fromisoformat(opds.updated)
        except:
            self.fail('opds.updated is not in ISO-format.')

    def test_init_published(self):
        """ Tests that the AO3WorkOPDS.published attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        # OPDS dates must be ISO-formatted (this test has no requirement
        # on the specific datetime value)
        try:
            datetime.datetime.fromisoformat(opds.published)
        except:
            self.fail('opds.published is not in ISO-format.')

    def test_init_authors(self):
        """ Tests that the AO3WorkOPDS.authors attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        # AO3.Work represents authors as AO3.User objects, which have
        # names and urls. OPDSPerson provides fields for name, email,
        # and uri.
        for index, author in enumerate(self.work.authors):
            self.assertEqual(opds.authors[index].name, author.username)
            self.assertEqual(opds.authors[index].uri, author.url)

    def test_init_language(self):
        """ Tests that the AO3WorkOPDS.language attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        self.assertEqual(opds.language, self.work.language)

    def test_init_summary(self):
        """ Tests that the AO3WorkOPDS.summary attr is set properly. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        self.assertEqual(opds.summary, self.work.summary)

    def test_init_links(self):
        """ Tests that the AO3WorkOPDS.links attr is non-empty. """
        opds = ao3opds.opds.AO3WorkOPDS(self.work)
        # AO3WorkOPDS should populate with one or more acquisition links
        self.assertGreater(len(opds.links), 0)

    def test_init_filetype(self):
        """ Tests passing `acquisition_filetypes` to AO3WorkOPDS. """
        opds = ao3opds.opds.AO3WorkOPDS(
            self.work, acquisition_filetypes=["EPUB"])
        # Verify that there is at least one link and all links are to epubs:
        self.assertGreater(len(opds.links), 0)
        for link in opds.links:
            self.assertTrue('epub' in link.type.lower())

    # TODO: Test get_images and get_content

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
