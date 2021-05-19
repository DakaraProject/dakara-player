from unittest import TestCase
from unittest.mock import patch, MagicMock

from path import Path, TempDir
from pathlib import Path as Path_pathlib

try:
    from importlib.resources import path

except ImportError:
    from importlib_resources import path

from dakara_player.text_generator import (
    separate_package_last_directory,
    TemplateNotFoundError,
    TextGenerator,
)


class TextGeneratorTestCase(TestCase):
    """Test the text generator class unitary
    """

    @patch.object(TextGenerator, "load_templates")
    @patch.object(TextGenerator, "load_icon_map")
    def test_load(self, mocked_load_icon_map, mocked_load_templates):
        """Test the load method
        """
        # create ojbect
        text_generator = TextGenerator("package")

        # call the method
        text_generator.load()

        # assert the call
        mocked_load_icon_map.assert_called_once_with()
        mocked_load_templates.assert_called_once_with()

    @patch.object(Path_pathlib, "read_text", autospec=True)
    @patch("dakara_player.text_generator.json.loads", autospec=True)
    def test_load_icon_map(self, mocked_loads, mocked_read_text):
        """Test to load the icon map
        """
        # create the mock
        mocked_loads.return_value = {"name": "value"}
        mocked_read_text.return_value = '{"name": "value"}'

        # create the object
        text_generator = TextGenerator("package")

        # pre assert there are not icon map
        self.assertDictEqual(text_generator.icon_map, {})

        # call the method
        text_generator.load_icon_map()

        # assert there is an icon map
        self.assertDictEqual(text_generator.icon_map, {"name": "value"})

        # assert the mock
        mocked_loads.assert_called_with(mocked_read_text.return_value)

    @patch.object(TextGenerator, "check_template", autospec=True)
    @patch("dakara_player.text_generator.ChoiceLoader", autospec=True)
    @patch("dakara_player.text_generator.PackageLoader", autospec=True)
    @patch("dakara_player.text_generator.FileSystemLoader", autospec=True)
    @patch("dakara_player.text_generator.Environment", autospec=True)
    def test_load_templates(
        self,
        mocked_environment_class,
        mocked_file_system_loader_class,
        mocked_package_loader_class,
        mocked_choice_loader_class,
        mocked_check_template,
    ):
        """Test to load templates for text
        """
        mocked_environment_class.return_value.filters = {}
        # create object
        text_generator = TextGenerator(
            "package.templates", Path("directory"), filenames={"text": "text.ass"}
        )

        # pre assert there are no templates
        self.assertIsNone(text_generator.environment)

        # call the method
        text_generator.load_templates()

        # assert there are templates defined
        self.assertIsNotNone(text_generator.environment)

        mocked_file_system_loader_class.assert_called_with(Path("directory"))
        mocked_package_loader_class.assert_called_with("package", "templates")
        mocked_choice_loader_class.assert_called_with(
            [
                mocked_file_system_loader_class.return_value,
                mocked_package_loader_class.return_value,
            ]
        )
        mocked_environment_class.assert_called_with(
            loader=mocked_choice_loader_class.return_value
        )
        mocked_check_template.assert_called_once_with(
            text_generator, "text", "text.ass"
        )

    def test_convert_icon(self):
        """Test the convertion of an available icon name to its code
        """
        # create object
        text_generator = TextGenerator("package")
        text_generator.icon_map = {"music": "0xf001"}

        self.assertEqual(text_generator.convert_icon("music"), "\uf001")
        self.assertEqual(text_generator.convert_icon("other"), " ")

    def test_convert_icon_unavailable(self):
        """Test the convertion of an unavailable icon name to a generic code
        """
        # create object
        text_generator = TextGenerator("package")

        self.assertEqual(text_generator.convert_icon("unavailable"), " ")

    def test_convert_icon_none(self):
        """Test the convertion of a null icon name is handled
        """
        # create object
        text_generator = TextGenerator("package")

        self.assertEqual(text_generator.convert_icon(None), "")

    def test_convert_link_type_name(self):
        """Test the convertion of a link type to its long name
        """
        # create object
        text_generator = TextGenerator("package")

        self.assertEqual(text_generator.convert_link_type_name("OP"), "Opening")
        self.assertEqual(text_generator.convert_link_type_name("ED"), "Ending")
        self.assertEqual(text_generator.convert_link_type_name("IN"), "Insert song")
        self.assertEqual(text_generator.convert_link_type_name("IS"), "Image song")

    @patch.object(TextGenerator, "get_environment_loaders", autospec=True)
    def test_check_template_custom(self, mocked_get_environment_loaders):
        """Test to find a custom template
        """
        mocked_loader_custom = MagicMock()
        mocked_loader_custom.list_templates.return_value = ["idle.ass"]
        mocked_loader_default = MagicMock()
        mocked_loader_default.list_templates.return_value = ["idle.ass"]

        mocked_get_environment_loaders.return_value = [
            mocked_loader_custom,
            mocked_loader_default,
        ]

        with self.assertLogs("dakara_player.text_generator", "DEBUG") as logger:
            text_generator = TextGenerator("package", filenames={"idle": "idle.ass"})
            text_generator.check_template("idle", "idle.ass")

        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.text_generator:Loading custom idle text "
                "template file 'idle.ass'"
            ],
        )

    @patch.object(TextGenerator, "get_environment_loaders", autospec=True)
    def test_check_template_default(self, mocked_get_environment_loaders):
        """Test to find a default template
        """
        mocked_loader_custom = MagicMock()
        mocked_loader_custom.list_templates.return_value = []
        mocked_loader_default = MagicMock()
        mocked_loader_default.list_templates.return_value = ["idle.ass"]

        mocked_get_environment_loaders.return_value = [
            mocked_loader_custom,
            mocked_loader_default,
        ]

        with self.assertLogs("dakara_player.text_generator", "DEBUG") as logger:
            text_generator = TextGenerator("package", filenames={"idle": "idle.ass"})
            text_generator.check_template("idle", "idle.ass")

        self.assertListEqual(
            logger.output,
            [
                "DEBUG:dakara_player.text_generator:Loading default idle "
                "text template file 'idle.ass'"
            ],
        )

    @patch.object(TextGenerator, "get_environment_loaders", autospec=True)
    def test_check_template_not_found(self, mocked_get_environment_loaders):
        """Test to find an unaccessible template
        """
        mocked_loader_custom = MagicMock()
        mocked_loader_custom.list_templates.return_value = []
        mocked_loader_default = MagicMock()
        mocked_loader_default.list_templates.return_value = []

        mocked_get_environment_loaders.return_value = [
            mocked_loader_custom,
            mocked_loader_default,
        ]

        with self.assertRaisesRegex(
            TemplateNotFoundError, "No idle text template file found for 'idle.ass'"
        ):
            text_generator = TextGenerator("package", filenames={"idle": "idle.ass"})
            text_generator.check_template("idle", "idle.ass")


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
            "use_instrumental": True,
            "date_created": "1970-01-01T00:00:00.00",
        }

        # create text generator object
        self.text_generator = TextGenerator(
            package="dakara_player.resources.templates",
            filenames={"idle": "idle.ass", "transition": "transition.ass"},
        )
        self.text_generator.load()

    def test_load_templates_default(self):
        """Test to load default templates using an existing directory

        Integration test.
        """
        with TempDir() as temp:
            # create object
            text_generator = TextGenerator(
                package="dakara_player.resources.templates",
                directory=temp,
                filenames={"idle": "idle.ass", "transition": "transition.ass"},
            )

            # call the method
            text_generator.load_templates()

            # assert there are templates defined
            loader_custom, loader_default = text_generator.environment.loader.loaders
            self.assertNotIn("idle.ass", loader_custom.list_templates())
            self.assertNotIn("transition.ass", loader_custom.list_templates())
            self.assertIn("idle.ass", loader_default.list_templates())
            self.assertIn("transition.ass", loader_default.list_templates())

    def test_load_templates_custom(self):
        """Test to load custom templates using an existing directory
        """
        with TempDir() as temp:
            # prepare directory
            with path("dakara_player.resources.templates", "idle.ass") as file:
                Path(file).copy(temp)

            with path("dakara_player.resources.templates", "transition.ass") as file:
                Path(file).copy(temp)

            # create object
            text_generator = TextGenerator(
                package="dakara_player.resources.templates",
                directory=temp,
                filenames={"idle": "idle.ass", "transition": "transition.ass"},
            )

            # call the method
            text_generator.load_templates()

            # assert there are templates defined
            loader_custom, loader_default = text_generator.environment.loader.loaders
            self.assertIn("idle.ass", loader_custom.list_templates())
            self.assertIn("transition.ass", loader_custom.list_templates())

    def test_get_idle_text(self):
        """Test the generation of an idle text
        """
        # call method
        result = self.text_generator.get_text("idle", self.idle_info)

        # check file content
        with path("tests.resources", "idle.ass") as file:
            idle_text_content = file.read_text(encoding="utf8")
            self.assertEqual(idle_text_content, result)

    def test_get_transition_text(self):
        """Test the generation of a transition text
        """
        # call method
        result = self.text_generator.get_text(
            "transition", {"playlist_entry": self.playlist_entry, "fade_in": True}
        )

        # check file content
        with path("tests.resources", "transition.ass") as file:
            transition_text_content = file.read_text(encoding="utf8")
            self.assertEqual(transition_text_content, result)


class SeparatePackageLastDirectoryTestCase(TestCase):
    """Test the separate_package_last_directory function
    """

    def test_three(self):
        """Test separate package with three elements
        """
        package, directory = separate_package_last_directory("a.b.c")
        self.assertEqual(package, "a.b")
        self.assertEqual(directory, "c")

    def test_two(self):
        """Test separate package with two elements
        """
        package, directory = separate_package_last_directory("a.b")
        self.assertEqual(package, "a")
        self.assertEqual(directory, "b")

    def test_one(self):
        """Test separate package with one element
        """
        package, directory = separate_package_last_directory("a")
        self.assertEqual(package, "")
        self.assertEqual(directory, "a")
