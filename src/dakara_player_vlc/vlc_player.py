import json
import logging

from dakara_base.exceptions import DakaraError
from pkg_resources import parse_version

try:
    import vlc

except ImportError:
    vlc = None

from dakara_player_vlc.media_player import MediaPlayer
from dakara_player_vlc.mrl import path_to_mrl, mrl_to_path


try:
    METADATA_KEY = vlc.Meta.Setting

except AttributeError:
    METADATA_KEY = None

logger = logging.getLogger(__name__)


class VlcTooOldError(DakaraError):
    pass


class MediaPlayerVlc(MediaPlayer):
    player_name = "VLC"

    @staticmethod
    def is_available():
        return vlc is not None and vlc.Instance() is not None

    def init_player(self, config, tempdir):
        # parameters
        config_vlc = config.get("vlc") or {}
        self.media_parameters = config_vlc.get("media_parameters") or []

        # VLC objects
        self.instance = vlc.Instance(config_vlc.get("instance_parameters") or [])
        self.player = self.instance.media_player_new()
        self.event_manager = self.player.event_manager()

        # vlc callbacks
        self.vlc_callbacks = {}

        # playlist entry objects
        self.playlist_entry_data = {}
        self.clear_playlist_entry_player()

    def load_player(self):
        # check VLC version
        self.check_version()

        # set VLC callbacks
        self.set_vlc_default_callbacks()

        # set VLC fullscreen
        self.player.set_fullscreen(self.fullscreen)

        # print VLC version
        logger.info("VLC %s", self.get_version())

        # force VLC to use the explicitally added files only
        self.media_parameters.append("no-sub-autodetect-file")

    def get_timing(self):
        """Player timing getter

        Returns:
            int: current song timing in seconds if a song is playing or 0 when
                idle or during transition screen.
        """
        if self.is_playing("idle") or self.is_playing("transition"):
            return 0

        timing = self.player.get_time()

        # correct the way VLC handles when it hasn't started to play yet
        if timing == -1:
            timing = 0

        return timing // 1000

    @staticmethod
    def get_version():
        """Print the VLC version and perform some parameter adjustements

        VLC version given by the lib is on the form "x.y.z CodeName" in bytes.
        """
        return vlc.libvlc_get_version().decode()

    def check_version(self):
        version_str, _ = self.get_version().split()
        version = parse(version_str)

        if version.major < 3:
            raise VlcTooOldError("VLC is too old (version 3 and higher supported)")

    def set_vlc_default_callbacks(self):
        """Set VLC player default callbacks
        """
        self.set_vlc_callback(
            vlc.EventType.MediaPlayerEndReached, self.handle_end_reached
        )
        self.set_vlc_callback(
            vlc.EventType.MediaPlayerEncounteredError, self.handle_encountered_error
        )
        self.set_vlc_callback(vlc.EventType.MediaPlayerPlaying, self.handle_playing)
        self.set_vlc_callback(vlc.EventType.MediaPlayerPaused, self.handle_paused)

    def set_vlc_callback(self, event, callback):
        """Assing an arbitrary callback to a VLC event

        Callback is attached to the VLC event manager and added to the
        `vlc_callbacks` dictionary.

        Args:
            event (vlc.EventType): VLC event to attach the callback to, name of
                the callback in the `vlc_callbacks` attribute.
            callback (function): function to assign.
        """
        self.vlc_callbacks[event] = callback
        self.event_manager.event_attach(event, callback)

    def is_playing(self, what=None):
        if what:
            return get_metadata(self.player.get_media())["type"] == what

        return self.player.get_state() == vlc.State.Playing

    def is_paused(self):
        return self.player.get_state() == vlc.State.Paused

    def play(self, what):
        if what == "idle":
            # create idle screen media
            media = self.instance.media_new_path(
                self.background_loader.backgrounds["idle"]
            )

            media.add_options(
                *self.media_parameters,
                "image-duration={}".format(self.durations["idle"]),
                "sub-file={}".format(self.text_paths["idle"]),
            )

            set_metadata(media, {"type": "idle"})

            self.generate_text("idle")

        elif what == "transition":
            media = self.playlist_entry_data["transition"].media

        elif what == "song":
            media = self.playlist_entry_data["song"].media

        else:
            raise ValueError("Unexpected action to play: {}".format(what))

        self.player.set_media(media)
        self.player.play()

    def pause(self, paused):
        if self.is_playing("idle"):
            return

        if paused:
            if self.is_paused():
                logger.debug("Player already in pause")
                return

            logger.info("Setting pause")
            self.player.pause()
            return

        if not self.is_paused():
            logger.debug("Player already playing")
            return

        logger.info("Resuming play")
        self.player.play()

    def skip(self):
        """Skip the current song
        """
        if self.is_playing("transition") or self.is_playing("song"):
            self.callbacks["finished"](self.playlist_entry["id"])
            logger.info("Skipping '%s'", self.playlist_entry["song"]["title"])
            self.clear_playlist_entry()

    def stop(self):
        logger.info("Stopping player")
        self.player.stop()
        logger.debug("Stopped player")

    def set_playlist_entry_player(self, playlist_entry, file_path, autoplay):
        # create transition screen media
        media_transition = self.instance.media_new_path(
            self.background_loader.backgrounds["transition"]
        )

        media_transition.add_options(
            *self.media_parameters,
            "image-duration={}".format(self.durations["transition"]),
            "sub-file={}".format(self.text_paths["transition"]),
        )

        set_metadata(
            media_transition,
            {"type": "transition", "playlist_entry": self.playlist_entry},
        )

        self.generate_text("transition")

        self.playlist_entry_data["transition"].media = media_transition

        # start playing transition right away if requested
        if autoplay:
            self.play("transition")

        # create song media
        media_song = self.instance.media_new_path(file_path)
        media_song.add_options(*self.media_parameters)
        set_metadata(
            media_song, {"type": "song", "playlist_entry": self.playlist_entry}
        )

        self.playlist_entry_data["song"].media = media_song

        # manage instrumental
        if playlist_entry["use_instrumental"]:
            self.manage_instrumental(playlist_entry, file_path)

    def manage_instrumental(self, playlist_entry, file_path):
        """Manage the requested instrumental track

        Instrumental track is searched first in audio files having the same as
        the video file, then in extra audio tracks of the video file.

        Args:
            playlist_entry (dict): Playlist entry data. Must contain the key
                `use_instrumental`.
            file_path (path.Path): Path of the song file.
        """
        # get instrumental file if possible
        audio_path = self.get_instrumental_file(file_path)

        # if audio file is present, request to add the file to the media
        # as a slave and register to play this extra track (which will be
        # the last audio track of the media)
        if audio_path:
            number_tracks = self.get_number_tracks(
                self.playlist_entry_data["song"].media
            )
            logger.info(
                "Requesting to play instrumental file '%s' for '%s'",
                audio_path,
                file_path,
            )
            try:
                # try to add the instrumental file
                self.playlist_entry_data["song"].media.slaves_add(
                    vlc.MediaSlaveType.audio, 4, path_to_mrl(audio_path).encode()
                )

            except NameError:
                # otherwise fallback to default
                logger.error(
                    "This version of VLC does not support slaves, cannot add "
                    "instrumental file"
                )
                return

            self.playlist_entry_data["song"].audio_track_id = number_tracks
            return

        # get audio tracks
        audio_tracks_id = self.get_audio_tracks_id(
            self.playlist_entry_data["song"].media
        )

        # if more than 1 audio track is present, register to play the 2nd one
        if len(audio_tracks_id) > 1:
            logger.info("Requesting to play instrumental track of '%s'", file_path)
            self.playlist_entry_data["song"].audio_track_id = audio_tracks_id[1]
            return

        # otherwise, fallback to register to play the first track and log it
        logger.warning(
            "Cannot find instrumental file or track for file '%s'", file_path
        )

    def clear_playlist_entry_player(self):
        self.playlist_entry_data = {
            "transition": Media(),
            "song": MediaSong(),
        }

    @staticmethod
    def get_number_tracks(media):
        """Get number of all tracks of the media

        Args:
            media (vlc.Media): Media to investigate.

        Returns:
            int: Number of tracks in the media.
        """
        # parse media to extract tracks
        media.parse()

        return len(list(media.tracks_get()))

    @staticmethod
    def get_audio_tracks_id(media):
        """Get ID of audio tracks of the media

        Args:
            media (vlc.Media): Media to investigate.

        Returns:
            list of int: ID of audio tracks in the media.
        """
        # parse media to extract tracks
        media.parse()
        audio = [
            item.id for item in media.tracks_get() if item.type == vlc.TrackType.audio
        ]

        return audio

    def handle_end_reached(self, event):
        """Callback called when a media ends

        This happens when:
            - A transition screen ends, leading to playing the actual song;
            - A song ends, leading to calling the callback
                `callbacks["finished"]`;
            - An idle screen ends, leading to reloop it.

        A new thread is created in any case.

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Song end callback called")

        # the transition screen has finished, request to play the song itself
        if self.is_playing("transition"):
            logger.debug(
                "Will play '{}'".format(
                    mrl_to_path(self.playlist_entry_data["song"].media.get_mrl())
                )
            )
            thread = self.create_thread(target=self.play, args=("song",))
            thread.start()

            return

        # the media has finished, so call the according callback and clean memory
        if self.is_playing("song"):
            self.callbacks["finished"](self.playlist_entry["id"])
            self.clear_playlist_entry()

            return

        # the idle screen has finished, simply restart it
        if self.is_playing("idle"):
            thread = self.create_thread(target=self.play, args=("idle",))
            thread.start()

            return

        # if no state can be determined, raise an error
        raise InvalidStateError("End reached on an undeterminated state")

    def handle_encountered_error(self, event):
        """Callback called when error occurs

        There is no way to capture error message, so only a generic error
        message is provided. Call the callbacks `callbackss["finished"]` and
        `callbacks["error"]`

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Error callback called")

        # the current song media has an error, skip the song, log the error and
        # call error callback
        if self.is_playing("song"):
            logger.error(
                "Unable to play '%s'", mrl_to_path(self.player.get_media().get_mrl())
            )
            self.callbacks["error"](
                self.playlist_entry["id"], "Unable to play current song"
            )
            self.skip()

            return

        # do not assess other errors

    def handle_playing(self, event):
        """Callback called when playing has started

        This happens when:
            - The player resumes from pause;
            - A transition screen starts;
            - A song starts, leading to set the requested audio track to play;
            - An idle screen starts.

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Playing callback called")

        # the media or the transition is resuming from pause
        # it is pretty hard to detect this case, as we do not have a previous
        # state in memory
        # we rely on a specific flag stored in `playlist_entry_data` Media
        # objects which is set to True when the corresponding media starts
        if (
            self.is_playing("transition")
            and self.playlist_entry_data["transition"].started
            or self.is_playing("song")
            and self.playlist_entry_data["song"].started
        ):
            self.callbacks["resumed"](self.playlist_entry["id"], self.get_timing())
            logger.debug("Resumed play")

            return

        # the transition screen starts to play
        if self.is_playing("transition"):
            self.callbacks["started_transition"](self.playlist_entry["id"])
            self.playlist_entry_data["transition"].started = True
            logger.info(
                "Playing transition for '%s'", self.playlist_entry["song"]["title"]
            )

            return

        # the song starts to play
        if self.is_playing("song"):
            self.callbacks["started_song"](self.playlist_entry["id"])

            # set instrumental track if necessary
            audio_track_id = self.playlist_entry_data["song"].audio_track_id
            if audio_track_id is not None:
                logger.debug("Requesting to play audio track %i", audio_track_id)
                self.player.audio_set_track(audio_track_id)

            self.playlist_entry_data["song"].started = True
            logger.info(
                "Now playing '%s' ('%s')",
                self.playlist_entry["song"]["title"],
                mrl_to_path(self.player.get_media().get_mrl()),
            )

            return

        # the idle screen starts to play
        if self.is_playing("idle"):
            logger.debug("Playing idle screen")

            return

        raise InvalidStateError("Playing on an undeterminated state")

    def handle_paused(self, event):
        """Callback called when pause is set

        Args:
            event (vlc.EventType): VLC event object.
        """
        logger.debug("Paused callback called")

        # call paused callback
        self.callbacks["paused"](self.playlist_entry["id"], self.get_timing())

        logger.debug("Set pause")


def set_metadata(media, metadata):
    media.set_meta(METADATA_KEY, json.dumps(metadata))


def get_metadata(media):
    return json.loads(media.get_meta(METADATA_KEY))


class Media:
    def __init__(self, media=None):
        self.media = media
        self.started = False


class MediaSong(Media):
    def __init__(self, *args, audio_track_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.audio_track_id = audio_track_id


class InvalidStateError(RuntimeError):
    pass
