from unittest import TestCase
from unittest.mock import patch, mock_open
import logging
import os

from dakara_player_vlc.text_generator import (
        TextGenerator,
        IDLE_TEXT_NAME,
        TRANSITION_TEMPLATE_NAME,
        SHARE_DIR_ABSOLUTE,
        )


# shut down text_generator logging
logging.getLogger("text_generator").setLevel(logging.DEBUG)


class TextGeneratorTestCase(TestCase):
    """Test the text generator class
    """
    def setUp(self):
        # set idle text template
        self.idle_text_template_name = "tests_idle.txt"
        self.idle_text_template = os.path.join(
                SHARE_DIR_ABSOLUTE,
                self.idle_text_template_name
                )

        # set transition text template
        self.transition_text_template_name = "tests_transition.txt"
        self.transition_text_template = os.path.join(
                SHARE_DIR_ABSOLUTE,
                self.transition_text_template_name
                )

        # create temporary folder
        self.temdir = "nowhere"

        # create idle text file path
        self.idle_text_path = os.path.join(self.temdir, IDLE_TEXT_NAME)

        # creat transition text file path
        self.transition_text_path = os.path.join(self.temdir,
                                                 TRANSITION_TEMPLATE_NAME)

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
                    'idleTemplateName': self.idle_text_template_name,
                    'transitionTemplateName':
                        self.transition_text_template_name,
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

    def test_convert_icon(self):
        """Test the convertion of an icon name to its code
        """
        # test only the music icon
        self.assertEqual(self.text_generator.convert_icon('music'), '\uf001')

    def test_convert_link_type_name(self):
        """Test the convertion of a link type to its long name
        """
        self.assertEqual(self.text_generator.convert_link_type_name('OP'),
                         'Opening')
        self.assertEqual(self.text_generator.convert_link_type_name('ED'),
                         'Ending')
        self.assertEqual(self.text_generator.convert_link_type_name('IN'),
                         'Insert song')
        self.assertEqual(self.text_generator.convert_link_type_name('IS'),
                         'Image song')
