""" Tests downloader.opds """

from copy import copy
import unittest
import datetime
import xml.etree.ElementTree as xml
import ao3opds.opds
from ao3_work import TEST_WORK

class TestAO3ABC(unittest.TestCase):
    """ ABC for test cases of `ao3opds.opds` classes. """

    def setUp(self) -> None:
        # Get a work without fetching any data over the network:
        self.work = copy(TEST_WORK)  # copy to avoid mutating
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
        opds = ao3opds.opds.AO3OPDS(self.works, id='id!', title='title!')
        feed = opds.render()
        # Check for an OPDS 'id' tag with the correct value:
        self.assertIn(f'<id>{opds.id}</id>', feed)

    def test_render_title(self):
        """ Tests that AO3OPDS feeds generate titles correctly. """
        opds = ao3opds.opds.AO3OPDS(self.works, id='id!', title='title!')
        feed = opds.render()
        # Check for an OPDS 'id' tag with the correct value:
        self.assertIn(f'<title>{opds.title}</title>', feed)

    def test_render_entries(self):
        """ Tests that AO3OPDS feeds generate entries correctly. """
        opds = ao3opds.opds.AO3OPDS(self.works, id='id', title='title')
        feed = opds.render()
        # Confirm that each work in `opds.works` has its id and title
        # in the feed:
        for entry in opds.entries:
            self.assertIn(f'<id>{entry.id}</id>', feed)
            self.assertIn(f'<title>{entry.title}</title>', feed)

    def test_render_XML(self):
        """ Tests that AO3OPDS.render() generates valid XML. """
        opds = ao3opds.opds.AO3OPDS(self.works, id='id', title='title')
        feed = opds.render()
        try:
            _ = xml.fromstring(feed)
        except xml.ParseError as error:
            self.fail('OPDS feed is not valid XML. Parser error: ' + str(error))

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
        # AO3 categories are represented in the `term` and `label`
        # elements of an OPDS category; use `label`, which is 
        # human-readable:
        categories = [category.label for category in opds.categories]
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
