from unittest import TestCase
from unittest.mock import patch, mock_open
import os

from dakara_player_vlc.text_generator import (
        TextGenerator,
        IDLE_TEXT_NAME,
        TRANSITION_TEXT_NAME,
        )

from dakara_player_vlc.resources_manager import PATH_TEST_FIXTURES


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
        self.text_generator = TextGenerator(
                {
                    'templateDirectory': PATH_TEST_FIXTURES,
                },
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
