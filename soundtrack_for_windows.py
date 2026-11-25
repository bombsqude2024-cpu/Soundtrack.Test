# ba_meta require api 9

### Soundtrack for Windows

# Bored hearing the same old music while your Android and
# Mac friends play custom soundtracks in their game?
# Fear Not for I am here to give you access to that
# unobtainable treasure of custom soundtracks, NOW IN WINDOWS!

# Made by: Me, Myself, and I (DarkSigil)
# SUPPORTED EXTENSIONS: .wav (This is the only one highly supported by windows in all devices)
# If you have mp3 files, you can convert your mp3 files to wav here:
# <https://www.freeconvert.com/mp3-to-wav>
# But mostly, there are ways to download wav files directly, so it won't be much trouble.

## Installation
# Just paste the file into your mods folder, turn it on in plugins window, and restart the game!

## Usage
# Go to Settings > Audio.
# You will find the new soundtrack option where you can customize
# your music by selecting .wav audio files from your device.

## Uninstallation
# I recommend you to delete your soundtracks or switching to the default
# soundtrack before turning off/deleting the plugin as it can cause problems
# because the game cannot play the files without this plugin.

from typing import override, Callable, Any

import os
import ctypes

import babase
import bauiv1 as bui
from baclassic._music import *
import bauiv1lib.soundtrack.entrytypeselect as ets
from bauiv1lib.soundtrack.entrytypeselect import SoundtrackEntryTypeSelectWindow


class NewMusicSubsystem(MusicSubsystem):
    def __init__(self) -> None:
        super().__init__()
        if self.supports_soundtrack_entry_type('wavFile'):
            self._music_player_type = WindowsMusicPlayer

    def supports_soundtrack_entry_type(self, entry_type: str) -> bool:
        env = babase.env()
        platform = env.get('platform')
        assert isinstance(platform, str)
        if entry_type == 'wavFile':
            return platform == 'windows'
        return super().supports_soundtrack_entry_type(entry_type)


class NewSoundtrackEntryTypeSelectWindow(SoundtrackEntryTypeSelectWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert bui.app.classic is not None
        music = bui.app.classic.music
        spacing = 80
        do_windows_wav = music.supports_soundtrack_entry_type('wavFile')

        if do_windows_wav:
            self._height += spacing
        v, i = self._height - 155, 0

        bui.containerwidget(
            edit=self._root_widget,
            size=(self._width, self._height)
        )

        values = [
            (35, self._height - 65),
            (self._width * 0.5, self._height - 32),
            (self._width * 0.5, self._height - 56),
            (50, v), (50, v - spacing),
            (50, v - (spacing * 2)), (50, v - (spacing * 3))
        ]

        if do_windows_wav:
            for i, child in enumerate(self._root_widget.get_children()):
                if i in (1, 2):
                    bui.textwidget(edit=child, position=values[i])
                else:
                    bui.buttonwidget(edit=child, position=values[i])

            btn = bui.buttonwidget(
                parent=self._root_widget,
                size=(self._width - 100, 60),
                position=(50, v - (spacing * (i - 2))),
                label=bui.Lstr(value='.wav File (Windows)'),
                on_activate_call=self._on_wav_file_press,
            )

            if music.get_soundtrack_entry_type(self._current_entry) == 'wavFile':
                bui.containerwidget(edit=self._root_widget, selected_child=btn)

    def _on_wav_file_press(self) -> None:
        from bauiv1lib.fileselector import FileSelectorWindow

        base_path = 'C:/Users'
        assert bui.app.classic is not None

        self.main_window_replace(
            lambda: FileSelectorWindow(
                base_path,
                callback=self._wav_file_selector_cb,
                show_base_path=True,
                valid_file_extensions=(
                    WindowsMusicPlayer.get_valid_music_file_extensions()
                ),
                allow_folders=False,
            ),
        )

    def _wav_file_selector_cb(self, result: str | None) -> None:
        if result is None:
            self._callback(self._current_entry)
        else:
            self._callback({'type': 'wavFile', 'name': result})


class WindowsMusicPlayer(MusicPlayer):
    SUPPORTED = ['wav']

    @classmethod
    def get_valid_music_file_extensions(cls) -> list[str]:
        """Return file extensions for types playable on this device."""
        return ['wav']

    def __init__(self):
        super().__init__()
        self._winmm = ctypes.windll.winmm
        self._alias = 'bgmusic'
        self._current_file = None

        self._looping = False
        self._loop_thread = None

        self._paused_position = 0
        self._length = 0  # total length in ms
        self._last_played_entry = None

    @override
    def on_select_entry(
        self,
        callback: Callable[[Any], None],
        current_entry: Any,
        selection_target_name: str,
    ) -> bui.MainWindow:
        # pylint: disable=cyclic-import
        from bauiv1lib.soundtrack.entrytypeselect import (
            SoundtrackEntryTypeSelectWindow,
        )

        return SoundtrackEntryTypeSelectWindow(
            callback, current_entry, selection_target_name
        )

    def _mci(self, command):
        buf = ctypes.create_unicode_buffer(512)
        ret = self._winmm.mciSendStringW(
            ctypes.c_wchar_p(command), buf, 511, 0
        )
        return ret, buf.value

    def _mci_error(self, err_code):
        buf = ctypes.create_unicode_buffer(512)
        self._winmm.mciGetErrorStringW(err_code, buf, 511)
        return buf.value

    def _get_length(self):
        ret, length = self._mci(f'status {self._alias} length')
        if ret != 0:
            return 0
        try:
            return int(length)
        except Exception:
            return 0

    @override
    def on_play(self, entry: Any, loop=True) -> None:
        assert babase.app.classic is not None
        music = babase.app.classic.music

        entry_type = music.get_soundtrack_entry_type(entry)
        if entry_type != 'wavFile':
            print(
                'WindowsMusicPlayer passed unrecognized entry type:',
                entry_type,
            )
            return

        filepath = music.get_soundtrack_entry_name(entry)
        filepath = os.path.abspath(filepath)

        if not os.path.exists(filepath):
            babase.screenmessage('Music File not Found!', color=(1, 0, 0))
            raise FileNotFoundError(f"File not found: {filepath}")

        ext = filepath.rsplit('.', 1)[-1].lower()
        if ext not in self.SUPPORTED:
            babase.screenmessage('Unsupported Music File Format!', color=(1, 0, 0))
            raise ValueError(f"Unsupported format '{ext}'")

        if (
            self._actually_playing
            and self._current_file == filepath
            and self._last_played_entry == entry
        ):
            return

        self.on_stop()

        ret, _ = self._mci(f'open "{filepath}" type waveaudio alias {self._alias}')
        if ret != 0:
            raise RuntimeError(f"MCI open failed: {self._mci_error(ret)}")

        self._mci(f'set {self._alias} time format milliseconds')
        self._length = self._get_length()

        ret, _ = self._mci(f'play {self._alias} from 0')
        if ret != 0:
            raise RuntimeError(f"MCI play failed: {self._mci_error(ret)}")

        self._current_file = filepath
        self._looping = loop
        self._actually_playing = True
        self._entry_to_play = entry
        self._last_played_entry = entry
        self._paused_position = 0

        if loop and self._length > 0:
            self._loop_thread = babase.AppTimer(
                self._length / 1000.0,
                babase.CallStrict(self._restart_loop),
                repeat=True,
            )
        elif loop:
            print(
                'WindowsMusicPlayer: could not determine track length; '
                'looping disabled for this track.'
            )
            self._loop_thread = None

    def _restart_loop(self) -> None:
        if self._actually_playing and self._looping:
            self._mci(f'play {self._alias} from 0')

    @override
    def on_stop(self):
        self._looping = False
        self._loop_thread = None

        self._mci(f'stop {self._alias}')
        self._mci(f'close {self._alias}')
        self._actually_playing = False

        self._current_file = None
        self._paused_position = 0
        self._length = 0

    def pause(self):
        ret, _ = self._mci(f'pause {self._alias}')
        if ret == 0:
            return

        ret, pos = self._mci(f'status {self._alias} position')
        if ret == 0:
            try:
                self._paused_position = int(pos)
            except Exception:
                self._paused_position = 0

        self._mci(f'stop {self._alias}')

    def resume(self):
        ret, _ = self._mci(f'resume {self._alias}')
        if ret == 0:
            return

        ret, _ = self._mci(f'play {self._alias} from {self._paused_position}')
        if ret != 0:
            raise RuntimeError(f"MCI resume failed: {self._mci_error(ret)}")

    @override
    def on_set_volume(self, volume: float) -> None:
        self._volume = volume
        vol = int(max(0.0, min(1.0, volume)) * 0xFFFF)
        dword_vol = (vol << 16) | vol
        self._winmm.waveOutSetVolume(None, dword_vol)

    def get_volume(self):
        vol = ctypes.c_ulong(0)
        self._winmm.waveOutGetVolume(None, ctypes.byref(vol))
        left = vol.value & 0xFFFF
        return int(left / 0xFFFF * 100)

    def is_playing(self):
        ret, result = self._mci(f'status {self._alias} mode')
        if ret != 0:
            return False
        return result.strip().lower() == 'playing'

    @override
    def on_app_shutdown(self) -> None:
        self.on_stop()

    @override
    def _update_play_state(self) -> None:
        should_play = self._entry_to_play is not None and self._volume > 0.0

        if should_play and not self._actually_playing:
            can_resume = (
                self._paused_position
                and self._current_file is not None
                and self._entry_to_play == self._last_played_entry
            )
            self.resume() if can_resume else self.on_play(self._entry_to_play)
            self._actually_playing = True
        elif not should_play and self._actually_playing:
            self.on_stop() if self._entry_to_play is None else self.pause()
            self._actually_playing = False

    @property
    def current_file(self):
        return self._current_file


# ba_meta export babase.Plugin
class Activate(babase.Plugin):

    @override
    def __init__(self) -> None:
        assert babase.app.classic is not None
        babase.app.classic.music = NewMusicSubsystem()
        ets.SoundtrackEntryTypeSelectWindow = NewSoundtrackEntryTypeSelectWindow

    @override
    def on_app_running(self) -> None:
        babase.screenmessage('Initializing Windows Music Player!', color=(0, 1, 0))
