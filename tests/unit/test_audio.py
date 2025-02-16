from importlib.resources import as_file, files
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from dakara_player.audio import get_audio_files, is_audio_file


class IsAudioFileTestCase(TestCase):
    def test_mp3(self):
        """Test to detect a MP3 file."""
        with as_file(files("tests.resources").joinpath("song2.mp3")) as file:
            self.assertTrue(is_audio_file(file))

    def test_ass(self):
        """Test to not detect an ASS file."""
        with as_file(files("tests.resources").joinpath("song2.ass")) as file:
            self.assertFalse(is_audio_file(file))

    def test_mkv(self):
        """Test to not detect a MKV file."""
        with as_file(files("tests.resources").joinpath("song2.mkv")) as file:
            self.assertFalse(is_audio_file(file))


@patch("dakara_player.audio.is_audio_file", autospec=True)
@patch.object(Path, "glob", autospec=True)
class GetAudioFileTestCase(TestCase):
    def test_no_audio(self, mocked_glob, mocked_is_audio_file):
        """Test no audio file found."""
        file_video = Path("aa") / "file.mp4"
        mocked_glob.return_value = [file_video]

        self.assertEqual(len(get_audio_files(file_video)), 0)
        mocked_glob.assert_called_with(Path("aa"), "file.*")

    def test_one_audio(self, mocked_glob, mocked_is_audio_file):
        """Test one audio file found."""
        file_video = Path("aa") / "file.mp4"
        file_audio = Path("aa") / "file.mp3"
        mocked_glob.return_value = [file_video, file_audio]
        mocked_is_audio_file.return_value = True

        files_audio = get_audio_files(file_video)
        self.assertEqual(len(files_audio), 1)
        self.assertListEqual(files_audio, [file_audio])
        mocked_glob.assert_called_with(Path("aa"), "file.*")

    def test_two_audio(self, mocked_glob, mocked_is_audio_file):
        """Test one audio file found."""
        file_video = Path("aa") / "file.mp4"
        file_audio1 = Path("aa") / "file.mp3"
        file_audio2 = Path("aa") / "file.ogg"
        mocked_glob.return_value = [file_video, file_audio1, file_audio2]
        mocked_is_audio_file.return_value = True

        files_audio = get_audio_files(file_video)
        self.assertEqual(len(files_audio), 2)
        self.assertListEqual(files_audio, [file_audio1, file_audio2])
        mocked_glob.assert_called_with(Path("aa"), "file.*")
