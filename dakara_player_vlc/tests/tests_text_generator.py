from unittest import TestCase
from unittest.mock import patch, mock_open

from dakara_base.resources_manager import get_file
from path import Path

from dakara_player_vlc.text_generator import (
    TextGenerator,
    IDLE_TEMPLATE_NAME,
    TRANSITION_TEMPLATE_NAME,
)

from dakara_player_vlc.resources_manager import get_template


class TextGeneratorTestCase(TestCase):
    """Test the text generator class unitary
    """

    @patch.object(TextGenerator, "load_templates")
    @patch.object(TextGenerator, "load_icon_map")
    def test_load(self, mocked_load_icon_map, mocked_load_templates):
        """Test the load method
        """
        # create ojbect
        text_generator = TextGenerator({})

        # call the method
        text_generator.load()

        # assert the call
        mocked_load_icon_map.assert_called_once_with()
        mocked_load_templates.assert_called_once_with()

    @patch.object(Path, "open", new_callable=mock_open)
    @patch("dakara_player_vlc.text_generator.ICON_MAP_FILE", "icon_map_file")
    @patch("dakara_player_vlc.text_generator.get_file")
    @patch("dakara_player_vlc.text_generator.json.load")
    def test_load_icon_map(self, mocked_load, mocked_get_file, mocked_open):
        """Test to load the icon map
        """
        # create the mock
        mocked_load.return_value = {"name": "value"}
        mocked_get_file.return_value = Path("path/to/icon_map_file")

        # create the object
        text_generator = TextGenerator({})

        # pre assert there are not icon map
        self.assertDictEqual(text_generator.icon_map, {})

        # call the method
        text_generator.load_icon_map()

        # assert there is an icon map
        self.assertDictEqual(text_generator.icon_map, {"name": "value"})

        # assert the mock
        mocked_load.assert_called_with(mocked_open.return_value)
        mocked_get_file.assert_called_with(
            "dakara_player_vlc.resources", "icon_map_file"
        )
        mocked_open.assert_called_with()

    def test_load_templates_default(self):
        """Test to load default templates for text

        In that case, the templates come from the fallback directory.
        """
        # create object
        text_generator = TextGenerator({})

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename, get_template(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_template(TRANSITION_TEMPLATE_NAME),
        )

    def test_load_templates_custom_directory_success(self):
        """Test to load custom templates using an existing directory

        In that case, the templates come from this directory.
        """
        # create object
        text_generator = TextGenerator(
            {"directory": get_file("dakara_player_vlc.tests.resources", "")}
        )

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename,
            get_file("dakara_player_vlc.tests.resources", IDLE_TEMPLATE_NAME),
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_file("dakara_player_vlc.tests.resources", TRANSITION_TEMPLATE_NAME),
        )

    def test_load_templates_custom_directory_fail(self):
        """Test to load templates using a directory that does not exist

        In that case, the templates come from the fallback directory.
        """
        # create object
        text_generator = TextGenerator({"directory": "nowhere"})

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename, get_template(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_template(TRANSITION_TEMPLATE_NAME),
        )

    def test_load_templates_custom_names_success(self):
        """Test to load templates using existing names

        In that case, the templates come from the custom directory and have the
        correct name.
        """
        # create object
        text_generator = TextGenerator(
            {
                "directory": get_file("dakara_player_vlc.tests.resources", ""),
                "idle_template_name": "song.ass",
                "transition_template_name": "song.ass",
            }
        )

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename,
            get_file("dakara_player_vlc.tests.resources", "song.ass"),
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_file("dakara_player_vlc.tests.resources", "song.ass"),
        )

    def test_load_templates_custom_names_fail(self):
        """Test to load templates using names that do not exist

        In that case, the templates come from the custom directory and have
        the default name.
        """
        # create object
        text_generator = TextGenerator(
            {
                "directory": get_file("dakara_player_vlc.tests.resources", ""),
                "idle_template_name": "nothing",
                "transition_template_name": "nothing",
            }
        )

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename,
            get_file("dakara_player_vlc.tests.resources", IDLE_TEMPLATE_NAME),
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_file("dakara_player_vlc.tests.resources", TRANSITION_TEMPLATE_NAME),
        )

    def test_convert_icon(self):
        """Test the convertion of an available icon name to its code
        """
        # create object
        text_generator = TextGenerator({})
        text_generator.icon_map = {"music": "0xf001"}

        self.assertEqual(text_generator.convert_icon("music"), "\uf001")
        self.assertEqual(text_generator.convert_icon("other"), " ")

    def test_convert_icon_unavailable(self):
        """Test the convertion of an unavailable icon name to a generic code
        """
        # create object
        text_generator = TextGenerator({})

        self.assertEqual(text_generator.convert_icon("unavailable"), " ")

    def test_convert_icon_none(self):
        """Test the convertion of a null icon name is handled
        """
        # create object
        text_generator = TextGenerator({})

        self.assertEqual(text_generator.convert_icon(None), "")

    def test_convert_link_type_name(self):
        """Test the convertion of a link type to its long name
        """
        # create object
        text_generator = TextGenerator({})

        self.assertEqual(text_generator.convert_link_type_name("OP"), "Opening")
        self.assertEqual(text_generator.convert_link_type_name("ED"), "Ending")
        self.assertEqual(text_generator.convert_link_type_name("IN"), "Insert song")
        self.assertEqual(text_generator.convert_link_type_name("IS"), "Image song")


class TextGeneratorIntegrationTestCase(TestCase):
    """Test the text generator class in real conditions
    """

    def setUp(self):
        # create info dictionary
        self.idle_info = {"notes": ["VLC 0.0.0", "Dakara player 0.0.0"]}

        # create playlist entry
        self.playlist_entry = {
            "song": {
                "title": "Song title",
                "artists": [{"name": "Artist name"}],
                "works": [
                    {
                        "work": {
                            "title": "Work title",
                            "subtitle": "Subtitle of the work",
                            "work_type": {
                                "name": "Work type name",
                                "icon_name": "music",
                            },
                        },
                        "link_type": "OP",
                        "link_type_number": 1,
                        "episodes": "1, 2, 3",
                    }
                ],
                "file_path": "path/of/the/file",
            },
            "owner": {"username": "User"},
            "date_created": "1970-01-01T00:00:00.00",
        }

        # create idle text content
        self.idle_text_path = get_file("dakara_player_vlc.tests.resources", "idle.ass")

        # create transition text content
        self.transition_text_path = get_file(
            "dakara_player_vlc.tests.resources", "transition.ass"
        )

        # create text generator object
        self.text_generator = TextGenerator({})
        self.text_generator.load()

    def test_create_idle_text(self):
        """Test the generation of an idle text
        """
        # call method
        result = self.text_generator.create_idle_text(self.idle_info)

        # check file content
        idle_text_content = self.idle_text_path.text(encoding="utf8")
        self.assertEqual(idle_text_content, result)

    def test_create_transition_text(self):
        """Test the generation of a transition text
        """
        # call method
        result = self.text_generator.create_transition_text(self.playlist_entry)

        # check file content
        transition_text_content = self.transition_text_path.text(encoding="utf8")
        self.assertEqual(transition_text_content, result)
