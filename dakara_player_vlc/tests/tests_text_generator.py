from unittest import TestCase
from unittest.mock import patch, mock_open

from path import Path

from dakara_player_vlc.text_generator import (
    TextGenerator,
    IDLE_TEXT_NAME,
    TRANSITION_TEXT_NAME,
    IDLE_TEMPLATE_NAME,
    TRANSITION_TEMPLATE_NAME,
)

from dakara_player_vlc.resources_manager import (
    PATH_TEST_MATERIALS,
    get_test_material,
    get_template,
)


class TextGeneratorPreLoadTestCase(TestCase):
    """Test the text generator class before it is loaded
    """

    def setUp(self):
        # create temporary folder
        self.tempdir = Path("nowhere")

    @patch.object(TextGenerator, "load_templates")
    @patch.object(TextGenerator, "load_icon_map")
    def test_load(self, mocked_load_icon_map, mocked_load_templates):
        """Test the load method
        """
        # create ojbect
        text_generator = TextGenerator({}, self.tempdir)

        # call the method
        text_generator.load()

        # assert the call
        mocked_load_icon_map.assert_called_once_with()
        mocked_load_templates.assert_called_once_with()

    @patch.object(Path, "open", new_callable=mock_open)
    @patch("dakara_player_vlc.text_generator.ICON_MAP_FILE", "icon_map_file")
    @patch("dakara_player_vlc.text_generator.get_file")
    @patch("dakara_player_vlc.text_generator.json.load")
    def test_load_icon_map(self, mocked_load, mocked_get_file, mock_open):
        """Test to load the icon map
        """
        # create the mock
        mocked_load.return_value = {"name": "value"}
        mocked_get_file.return_value = Path("path/to/icon_map_file")

        # create the object
        text_generator = TextGenerator({}, self.tempdir)

        # pre assert there are not icon map
        self.assertDictEqual(text_generator.icon_map, {})

        # call the method
        text_generator.load_icon_map()

        # assert there is an icon map
        self.assertDictEqual(text_generator.icon_map, {"name": "value"})

        # assert the mock
        mocked_load.assert_called_with(mock_open.return_value)
        mocked_get_file.assert_called_with(
            "dakara_player_vlc.resources", "icon_map_file"
        )
        mock_open.assert_called_with()

    def test_load_templates_default(self):
        """Test to load default templates for text

        In that case, the templates come from the fallback directory.
        """
        # create object
        text_generator = TextGenerator({}, self.tempdir)

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
        text_generator = TextGenerator({"directory": PATH_TEST_MATERIALS}, self.tempdir)

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename, get_test_material(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_test_material(TRANSITION_TEMPLATE_NAME),
        )

    def test_load_templates_custom_directory_fail(self):
        """Test to load templates using a directory that does not exist

        In that case, the templates come from the fallback directory.
        """
        # create object
        text_generator = TextGenerator({"directory": "nowhere"}, self.tempdir)

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
                "directory": PATH_TEST_MATERIALS,
                "idle_template_name": "song.ass",
                "transition_template_name": "song.ass",
            },
            self.tempdir,
        )

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename, get_test_material("song.ass")
        )
        self.assertEqual(
            text_generator.transition_template.filename, get_test_material("song.ass")
        )

    def test_load_templates_custom_names_fail(self):
        """Test to load templates using names that do not exist

        In that case, the templates come from the custom directory and have
        the default name.
        """
        # create object
        text_generator = TextGenerator(
            {
                "directory": PATH_TEST_MATERIALS,
                "idle_template_name": "nothing",
                "transition_template_name": "nothing",
            },
            self.tempdir,
        )

        # pre assert there are no templates
        self.assertIsNone(text_generator.idle_template)
        self.assertIsNone(text_generator.transition_template)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertEqual(
            text_generator.idle_template.filename, get_test_material(IDLE_TEMPLATE_NAME)
        )
        self.assertEqual(
            text_generator.transition_template.filename,
            get_test_material(TRANSITION_TEMPLATE_NAME),
        )


class TextGeneratorPostLoadTestCase(TestCase):
    """Test the text generator class after it is loaded
    """

    def setUp(self):
        # create temporary folder
        self.tempdir = Path("nowhere")

        # create idle text file path
        self.idle_text_path = self.tempdir / IDLE_TEXT_NAME

        # creat transition text file path
        self.transition_text_path = self.tempdir / TRANSITION_TEXT_NAME

        # create info dictionary
        self.idle_info = {"vlc_version": "0.0.0"}

        # create playlist entry
        self.playlist_entry = {
            "title": "title",
            "artists": ["someone"],
            "works": ["something"],
            "owner": "me",
        }

        # create idle text content
        self.idle_text_content = self.idle_info["vlc_version"]

        # create transition text content
        self.transition_text_content = "{title}\n{artists}\n{works}\n{owner}".format(
            **self.playlist_entry
        )

        # create text generator object
        # we use a custom template directory to use a simplified template
        self.text_generator = TextGenerator(
            {"directory": PATH_TEST_MATERIALS}, self.tempdir
        )
        self.text_generator.load()

    def test_convert_icon(self):
        """Test the convertion of an available icon name to its code
        """
        self.assertEqual(self.text_generator.convert_icon("music"), "\uf001")
        self.assertEqual(self.text_generator.convert_icon("other"), " ")

    def test_convert_icon_unavailable(self):
        """Test the convertion of an unavailable icon name to a generic code
        """
        self.assertEqual(self.text_generator.convert_icon("unavailable"), " ")

    def test_convert_icon_none(self):
        """Test the convertion of a null icon name is handled
        """
        # test only the music icon
        self.assertEqual(self.text_generator.convert_icon(None), "")

    def test_convert_link_type_name(self):
        """Test the convertion of a link type to its long name
        """
        self.assertEqual(self.text_generator.convert_link_type_name("OP"), "Opening")
        self.assertEqual(self.text_generator.convert_link_type_name("ED"), "Ending")
        self.assertEqual(
            self.text_generator.convert_link_type_name("IN"), "Insert song"
        )
        self.assertEqual(self.text_generator.convert_link_type_name("IS"), "Image song")

    @patch.object(Path, "open", new_callable=mock_open)
    def test_create_idle_text(self, mock_open):
        """Test the generation of an idle text
        """
        # call method
        result = self.text_generator.create_idle_text(self.idle_info)

        # call assertions
        mock_open.assert_called_once_with("w", encoding="utf8")

        mock_open.return_value.write.assert_called_once_with(self.idle_text_content)

        self.assertEqual(result, self.idle_text_path)

    @patch.object(Path, "open", new_callable=mock_open)
    def test_create_transition_text(self, mock_open):
        """Test the generation of a transition text
        """
        # call method
        result = self.text_generator.create_transition_text(self.playlist_entry)

        # call assertions
        mock_open.assert_called_once_with("w", encoding="utf8")

        mock_open.return_value.write.assert_called_once_with(
            self.transition_text_content
        )

        self.assertEqual(result, self.transition_text_path)
