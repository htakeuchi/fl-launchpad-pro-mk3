import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DEVICE_SCRIPT = REPO_DIR / "hardware" / "NovationLaunchpadProMK3Midi" / "device_LaunchPadProMk3_Midi.py"
FL_MODULES = (
    "patterns",
    "channels",
    "mixer",
    "device",
    "transport",
    "arrangement",
    "general",
    "launchMapPages",
    "playlist",
    "ui",
    "midi",
    "utils",
)


class MidiEvent:
    def __init__(self, midi_id, data1, data2, midi_chan=0):
        self.midiId = midi_id
        self.status = midi_id
        self.data1 = data1
        self.data2 = data2
        self.midiChan = midi_chan
        self.handled = False


class FakePatterns(types.ModuleType):
    def __init__(self, existing_patterns=None, pattern=1, select_clone=True):
        super().__init__("patterns")
        self.length = 16
        self.pattern = pattern
        self.max_pattern = 16
        self.select_clone = select_clone
        self.existing_patterns = set(existing_patterns or [pattern])
        self.find_empty_calls = []
        self.clone_calls = []
        self.jump_calls = []

    def patternNumber(self):
        return self.pattern

    def patternCount(self):
        return len(self.existing_patterns)

    def patternMax(self):
        return self.max_pattern

    def isPatternDefault(self, index):
        return index not in self.existing_patterns

    def jumpToPattern(self, index):
        self.jump_calls.append(index)
        self.pattern = index

    def findFirstNextEmptyPat(self, flags, x=-1, y=-1):
        self.find_empty_calls.append((flags, x, y))
        for index in range(1, self.max_pattern + 1):
            if index not in self.existing_patterns:
                self.pattern = index
                self.existing_patterns.add(index)
                return

    def clonePattern(self, index=None):
        source_index = index if index is not None else self.pattern
        dest_index = max(self.existing_patterns) + 1
        self.clone_calls.append((source_index, dest_index))
        self.existing_patterns.add(dest_index)
        if self.select_clone:
            self.pattern = dest_index

    def getPatternLength(self, index):
        return self.length


class FakeChannels(types.ModuleType):
    def __init__(self, count=1, selected=0):
        super().__init__("channels")
        self.count = count
        self.selected = selected
        self.grid = {(0, 0): 1, (0, 3): 1}
        self.set_grid_calls = []
        self.muted = set()
        self.soloed = set()
        self.mute_calls = []
        self.solo_calls = []

    def channelCount(self):
        return self.count

    def isGridBitAssigned(self, index):
        return 0 <= index < self.count

    def selectedChannel(self, *args):
        return self.selected

    def getChannelColor(self, index):
        return (0x20 << 16) | (0x10 << 8) | (0x08 + index)

    def getGridBit(self, index, step):
        return self.grid.get((index, step), 0)

    def setGridBit(self, index, step, value):
        self.set_grid_calls.append((index, step, value))
        self.grid[(index, step)] = value

    def selectOneChannel(self, index):
        self.selected = index

    def isChannelMuted(self, index, useGlobalIndex=False):
        return index in self.muted

    def muteChannel(self, index, value=-1, useGlobalIndex=False):
        self.mute_calls.append((index, value, useGlobalIndex))
        if value < 0:
            if index in self.muted:
                self.muted.remove(index)
            else:
                self.muted.add(index)
        elif value:
            self.muted.add(index)
        else:
            self.muted.discard(index)

    def isChannelSolo(self, index, useGlobalIndex=False):
        return index in self.soloed

    def soloChannel(self, index, value=-1, useGlobalIndex=False):
        self.solo_calls.append((index, value, useGlobalIndex))
        if value < 0:
            if index in self.soloed:
                self.soloed.remove(index)
            else:
                self.soloed.add(index)
        elif value:
            self.soloed.add(index)
        else:
            self.soloed.discard(index)


class RaisingChannels(FakeChannels):
    def setGridBit(self, index, step, value):
        raise AssertionError("setGridBit should not be called")


class FakeTransport(types.ModuleType):
    def __init__(self, midi_module, playing=False):
        super().__init__("transport")
        self.midi = midi_module
        self.playing = playing
        self.started = 0
        self.stopped = 0

    def isPlaying(self):
        return self.midi.PM_Playing if self.playing else 0

    def start(self):
        self.playing = True
        self.started += 1

    def stop(self):
        self.playing = False
        self.stopped += 1


class FakeMixer(types.ModuleType):
    def __init__(self, song_step_pos=-1):
        super().__init__("mixer")
        self.song_step_pos = song_step_pos

    def getSongStepPos(self):
        return self.song_step_pos

    def getSongTickPos(self, tick_type):
        return 0


def make_midi_module():
    module = types.ModuleType("midi")
    module.MIDI_NOTEON = 0x90
    module.MIDI_NOTEOFF = 0x80
    module.MIDI_CONTROLCHANGE = 0xB0
    module.MIDI_CHANAFTERTOUCH = 0xD0
    module.MIDI_KEYAFTERTOUCH = 0xA0
    module.MIDI_BEGINSYSEX = 0xF0
    module.PM_Playing = 1
    module.UF_PR = 0
    module.CR_ScrollToView = 0
    module.FFNEP_FindFirst = 0
    module.FFNEP_DontPromptName = 2
    module.FromMIDI_Max = 65535
    module.CC_Special = 0x1000
    module.ST_Beat = 0
    module.ST_PGB = 1
    return module


def make_utils_module():
    module = types.ModuleType("utils")
    module.Limited = lambda value, low, high: max(low, min(value, high))
    module.InterNoSwap = lambda value, low, high: low <= value <= high
    module.DivModU = lambda value, divisor: divmod(value, divisor)
    module.ColorToRGB = lambda color: ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
    module.RGBToColor = lambda r, g, b: ((int(r) & 0xFF) << 16) | ((int(g) & 0xFF) << 8) | (int(b) & 0xFF)
    module.TClipLauncherLastClip = lambda *args: args
    return module


def make_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class DeviceScriptTestCase(unittest.TestCase):
    def load_device_script(
        self,
        patterns_module=None,
        channels_module=None,
        mixer_module=None,
        transport_module=None,
        device_module=None,
    ):
        patterns_module = patterns_module or FakePatterns()
        channels_module = channels_module or FakeChannels()
        midi_module = make_midi_module()
        mixer_module = mixer_module or FakeMixer()
        transport_module = transport_module or FakeTransport(midi_module)
        device_module = device_module or make_module(
            "device",
            isAssigned=lambda: False,
            createRefreshThread=lambda: None,
            destroyRefreshThread=lambda: None,
            fullRefresh=lambda: None,
            midiOutSysex=lambda data: None,
            stopRepeatMidiEvent=lambda: None,
        )

        fakes = {
            "patterns": patterns_module,
            "channels": channels_module,
            "mixer": mixer_module,
            "device": device_module,
            "transport": transport_module,
            "arrangement": make_module("arrangement"),
            "general": make_module("general", saveUndo=lambda *args: None, getVersion=lambda: 40),
            "launchMapPages": make_module("launchMapPages"),
            "playlist": make_module(
                "playlist",
                trackCount=lambda: 8,
                liveDisplayZone=lambda *args: None,
                lockDisplayZone=lambda *args: None,
            ),
            "ui": make_module("ui", getVersion=lambda: 40, crDisplayRect=lambda *args: None),
            "midi": midi_module,
            "utils": make_utils_module(),
        }

        original_modules = {name: sys.modules.get(name) for name in FL_MODULES}
        self.addCleanup(self.restore_modules, original_modules)
        sys.modules.update(fakes)

        module_name = f"launchpad_device_under_test_{id(self)}_{len(self._cleanups)}"
        spec = importlib.util.spec_from_file_location(module_name, DEVICE_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.addCleanup(sys.modules.pop, module_name, None)
        return module, patterns_module, channels_module

    @staticmethod
    def restore_modules(original_modules):
        for name, module in original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class StepPatternActionTests(DeviceScriptTestCase):
    def test_clear_button_creates_first_empty_pattern_without_prompt(self):
        patterns_module = FakePatterns(existing_patterns={1}, pattern=1)
        module, _, _ = self.load_device_script(patterns_module=patterns_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer
        launchpad.StepOfs = 16

        event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.ClearButton, 127)
        launchpad.OnMidiMsg(event)

        self.assertTrue(event.handled)
        self.assertEqual(patterns_module.find_empty_calls, [(module.midi.FFNEP_DontPromptName, -1, -1)])
        self.assertEqual(patterns_module.patternNumber(), 2)
        self.assertEqual(launchpad.StepOfs, 0)

    def test_duplicate_button_clones_current_pattern_and_selects_clone(self):
        patterns_module = FakePatterns(existing_patterns={1, 2}, pattern=2)
        module, _, _ = self.load_device_script(patterns_module=patterns_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.DuplicateButton, 127)
        launchpad.OnMidiMsg(event)

        self.assertTrue(event.handled)
        self.assertEqual(patterns_module.clone_calls, [(2, 3)])
        self.assertEqual(patterns_module.patternNumber(), 3)

    def test_duplicate_button_moves_to_new_clone_if_clone_api_keeps_source_active(self):
        patterns_module = FakePatterns(existing_patterns={1, 3}, pattern=1, select_clone=False)
        module, _, _ = self.load_device_script(patterns_module=patterns_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.DuplicateButton, 127)
        launchpad.OnMidiMsg(event)

        self.assertTrue(event.handled)
        self.assertEqual(patterns_module.clone_calls, [(1, 4)])
        self.assertEqual(patterns_module.jump_calls, [4])
        self.assertEqual(patterns_module.patternNumber(), 4)

    def test_patterns_button_cycles_only_non_default_patterns(self):
        patterns_module = FakePatterns(existing_patterns={1, 3}, pattern=1)
        module, _, _ = self.load_device_script(patterns_module=patterns_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        first_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.PatternsButton, 127)
        launchpad.OnMidiMsg(first_event)
        second_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.PatternsButton, 127)
        launchpad.OnMidiMsg(second_event)

        self.assertTrue(first_event.handled)
        self.assertTrue(second_event.handled)
        self.assertEqual(patterns_module.jump_calls, [3, 1])
        self.assertEqual(patterns_module.patternNumber(), 1)

    def test_shift_patterns_button_does_not_cycle_patterns(self):
        patterns_module = FakePatterns(existing_patterns={1, 2}, pattern=1)
        module, _, _ = self.load_device_script(patterns_module=patterns_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer
        launchpad.Shift = True

        event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.PatternsButton, 127)
        launchpad.OnMidiMsg(event)

        self.assertTrue(event.handled)
        self.assertEqual(patterns_module.jump_calls, [])
        self.assertEqual(patterns_module.patternNumber(), 1)

    def test_step_pattern_buttons_are_handled_before_nonzero_midi_channel_guard(self):
        patterns_module = FakePatterns(existing_patterns={1, 3}, pattern=1)
        module, _, _ = self.load_device_script(patterns_module=patterns_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        clear_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.ClearButton, 127, midi_chan=1)
        duplicate_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.DuplicateButton, 127, midi_chan=1)
        patterns_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.PatternsButton, 127, midi_chan=1)
        launchpad.OnMidiMsg(clear_event)
        launchpad.OnMidiMsg(duplicate_event)
        launchpad.OnMidiMsg(patterns_event)

        self.assertTrue(clear_event.handled)
        self.assertTrue(duplicate_event.handled)
        self.assertTrue(patterns_event.handled)
        self.assertEqual(patterns_module.find_empty_calls, [(module.midi.FFNEP_DontPromptName, -1, -1)])
        self.assertEqual(patterns_module.clone_calls, [(2, 4)])
        self.assertEqual(patterns_module.jump_calls, [1])

    def test_mk3_cc_channel_sequence_enters_step_mode_before_pattern_buttons(self):
        patterns_module = FakePatterns(existing_patterns={1, 3}, pattern=1)
        module, _, _ = self.load_device_script(patterns_module=patterns_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True

        note_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.NoteButton, 127, midi_chan=1)
        clear_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.ClearButton, 127, midi_chan=1)
        duplicate_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.DuplicateButton, 127, midi_chan=1)
        patterns_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.PatternsButton, 127, midi_chan=1)
        launchpad.OnMidiMsg(note_event)
        launchpad.OnMidiMsg(clear_event)
        launchpad.OnMidiMsg(duplicate_event)
        launchpad.OnMidiMsg(patterns_event)

        self.assertTrue(note_event.handled)
        self.assertTrue(launchpad.IsStepSequencerMode())
        self.assertTrue(clear_event.handled)
        self.assertTrue(duplicate_event.handled)
        self.assertTrue(patterns_event.handled)
        self.assertEqual(patterns_module.find_empty_calls, [(module.midi.FFNEP_DontPromptName, -1, -1)])
        self.assertEqual(patterns_module.clone_calls, [(2, 4)])
        self.assertEqual(patterns_module.jump_calls, [1])

    def test_step_edit_skips_steps_outside_current_pattern_length(self):
        module, _, channels_module = self.load_device_script(channels_module=RaisingChannels())
        launchpad = module.LaunchPadPro
        launchpad.StepOfs = 16
        launchpad.UpdateStepSequencerView = lambda force=False: None
        launchpad.FocusStepSequencerRect = lambda: None

        launchpad.ToggleStepSequencerPad(0, 0)

        self.assertEqual(launchpad.StepOfs, 16)
        self.assertEqual(channels_module.set_grid_calls, [])


if __name__ == "__main__":
    unittest.main()
