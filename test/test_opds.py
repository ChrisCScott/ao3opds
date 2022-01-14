""" Tests downloader.opds """

import enum
import unittest
import datetime
import pickle
import AO3
import downloader.opds
from ao3_work import TEST_WORK, TEST_WORK_ID

class TestAO3OPDS(unittest.TestCase):
    """ Tests `downloader.opds.AO3OPDS` """

    def setUp(self) -> None:
        # Create a work but don't fetch any data over the network:
        self.work = AO3.Work(TEST_WORK_ID, load=False, load_chapters=False)
        # Instantiate manually:
        self.work.title = "Title"
        self.work.authors = ["Author"]
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
            datetime.timezone.utc).isoformat()
        self.work.date_updated = self.work.date_published
        # Prevent the work from getting loaded by `AO3OPDS`:
        self.work.loaded = True
        self.works = [self.work]
        return super().setUp()

    def test_entries(self):
        """ Tests that AO3WorksOPDS attrs are processed. """
        opds = downloader.opds.AO3OPDS(self.works, id='id', title='title')
        # Confirm that self.works has the correct structure
        self.assertEqual(len(opds.entries), len(self.works))
        for index, entry in enumerate(opds.entries):
            # Check a couple of entry attributes to confirm that
            # each entry matches the corresponding Work:
            self.assertEqual(entry.title, self.works[index].title)
            self.assertEqual(entry.id, self.works[index].id)

    def test_render(self):
        """ Tests that AO3OPDS feeds are generated correctly. """
        opds = downloader.opds.AO3WorkOPDS(self.works, id='id', title='title')
        feed = opds.render()
        # Confirm that each of the represented OPDS tags is in the feed:
        self.assertIn()

class TestAO3WorkOPDS(unittest.TestCase):
    """ Tests `downloader.opds.AO3WorkOPDS`. """

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_authors(self):
        """ Tests that the AO3OPDS.authors attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.authors[0].name, self.work.authors[0])

    def test_init_categories(self):
        """ Tests that the AO3OPDS.categories attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)

    def test_init_title(self):
        """ Tests that the AO3OPDS.title attr is set properly. """
        opds = downloader.opds.AO3OPDS(self.works)
        self.assertEqual(opds.title, self.work.title)
