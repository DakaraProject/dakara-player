from unittest import TestCase
from unittest.mock import patch, mock_open
import os

from dakara_player_vlc.text_generator import (
        TextGenerator,
        IDLE_TEXT_NAME,
        TRANSITION_TEXT_NAME,
        IDLE_TEMPLATE_NAME,
        TRANSITION_TEMPLATE_NAME,
        )

from dakara_player_vlc.resources_manager import (
    PATH_TEST_FIXTURES,
    get_test_fixture,
    get_template,
)


class TextGeneratorTestCase(TestCase):
    """Test the text generator class
    """
    def setUp(self):
        # create temporary folder
        self.temdir = "nowhere"

        # create idle text file path
        self.idle_text_path = os.path.join(self.temdir, IDLE_TEXT_NAME)

        # creat transition text file path
        self.transition_text_path = os.path.join(self.temdir,
                                                 TRANSITION_TEXT_NAME)

        # create info dictionary
        self.idle_info = {
                'vlc_version': "0.0.0",
                }

        # create playlist entry
        self.playlist_entry = {
                'title': 'title',
                'artists':  ['someone'],
                'works': ['something'],
                'owner': 'me',
                }

        # create idle text content
        self.idle_text_content = self.idle_info['vlc_version']

        # create transition text content
        self.transition_text_content = \
            "{title}\n{artists}\n{works}\n{owner}".format(
                    **self.playlist_entry
                    )

        # create text generator object
        # we use a custom template directory to use a simplified template
        self.text_generator = TextGenerator(
                {'templateDirectory': PATH_TEST_FIXTURES},
                self.temdir
                )

    @patch('dakara_player_vlc.text_generator.open', new_callable=mock_open)
    def test_create_idle_text(self, mock_open):
        """Test the generation of an idle text
        """
        # call method
        result = self.text_generator.create_idle_text(self.idle_info)

        # call assertions
        mock_open.assert_called_once_with(
                self.idle_text_path,
                'w',
                encoding='utf8'
                )

        mock_open.return_value.write.assert_called_once_with(
                self.idle_text_content
                )

        self.assertEqual(result, self.idle_text_path)

    @patch('dakara_player_vlc.text_generator.open', new_callable=mock_open)
    def test_create_transition_text(self, mock_open):
        """Test the generation of a transition text
        """
        # call method
        result = self.text_generator.create_transition_text(
                self.playlist_entry
                )

        # call assertions
        mock_open.assert_called_once_with(
                self.transition_text_path,
                'w',
                encoding='utf8'
                )

        mock_open.return_value.write.assert_called_once_with(
                self.transition_text_content
                )

        self.assertEqual(result, self.transition_text_path)


class TextGeneratorCustomTestCase(TestCase):
    """Test the text generator class with custom resources
    """
    def setUp(self):
        # create temporary folder
        self.tempdir = "nowhere"

    def test_default(self):
        """Test to instanciate with default parameters

        In that case, the templates come from the fallback directory.
        """
        # create object
        text_generator = TextGenerator(
            {},
            self.tempdir
        )

        # assert object
        self.assertEqual(
            text_generator.idle_template.filename,
            get_template(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_template(TRANSITION_TEMPLATE_NAME)
        )

    def test_custom_template_directory_sucess(self):
        """Test to instanciate with an existing template directory

        In that case, the templates come from this directory.
        """
        # create object
        text_generator = TextGenerator(
            {'templateDirectory': PATH_TEST_FIXTURES},
            self.tempdir
        )

        # assert object
        self.assertEqual(
            text_generator.idle_template.filename,
            get_test_fixture(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_test_fixture(TRANSITION_TEMPLATE_NAME)
        )

    def test_custom_template_directory_fail(self):
        """Test to instanciate with a template directory thad does not exist

        In that case, the templates come from the fallback directory.
        """
        # create object
        text_generator = TextGenerator(
            {'templateDirectory': "nowhere"},
            self.tempdir
        )

        # assert object
        self.assertEqual(
            text_generator.idle_template.filename,
            get_template(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_template(TRANSITION_TEMPLATE_NAME)
        )

    def test_custom_template_names_success(self):
        """Test to instanciate with existing template names

        In that case, the templates come from the custom directory and have the
        correct name.
        """
        # create object
        text_generator = TextGenerator(
            {
                'templateDirectory': PATH_TEST_FIXTURES,
                'idleTemplateName': "song.ass",
                'transitionTemplateName': "song.ass"
            },
            self.tempdir
        )

        # assert object
        self.assertEqual(
            text_generator.idle_template.filename,
            get_test_fixture("song.ass")
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_test_fixture("song.ass")
        )

    def test_custom_template_names_fail(self):
        """Test to instanciate with template names that do not exist

        In that case, the templates come from the custom directory and have
        the default name.
        """
        # create object
        text_generator = TextGenerator(
            {
                'templateDirectory': PATH_TEST_FIXTURES,
                'idleTemplateName': "nothing",
                'transitionTemplateName': "nothing"
            },
            self.tempdir
        )

        # assert object
        self.assertEqual(
            text_generator.idle_template.filename,
            get_test_fixture(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_test_fixture(TRANSITION_TEMPLATE_NAME)
        )
