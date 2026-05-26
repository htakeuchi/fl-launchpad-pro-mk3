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
    def __init__(self, midi_id, data1, data2):
        self.midiId = midi_id
        self.status = midi_id
        self.data1 = data1
        self.data2 = data2
        self.midiChan = 0
        self.handled = False


class FakePatterns(types.ModuleType):
    def __init__(self, expose_length_api=False):
        super().__init__("patterns")
        self.length = 16
        self.pattern = 1
        self.max_pattern = 512
        if expose_length_api:
            self.setPatternLength = self._set_pattern_length

    def patternNumber(self):
        return self.pattern

    def patternMax(self):
        return self.max_pattern

    def getPatternLength(self, index):
        return self.length

    def _set_pattern_length(self, index, length):
        self.length = length


class FakeChannels(types.ModuleType):
    def __init__(self, count=1, selected=0):
        super().__init__("channels")
        self.count = count
        self.selected = selected
        self.grid = {(0, 0): 1, (0, 3): 1}
        self.step_params = {}
        self.set_grid_calls = []
        self.muted = set()
        self.soloed = set()
        self.mute_calls = []
        self.solo_calls = []

    def channelCount(self):
        return self.count

    def isGridBitAssigned(self, index):
        return 0 <= index < self.count

    def getChannelIndex(self, index):
        return index

    def selectedChannel(self, *args):
        return self.selected

    def getChannelColor(self, index):
        return (0x20 << 16) | (0x10 << 8) | (0x08 + index)

    def getGridBit(self, index, step):
        return self.grid.get((index, step), 0)

    def setGridBit(self, index, step, value):
        self.set_grid_calls.append((index, step, value))
        self.grid[(index, step)] = value

    def getCurrentStepParam(self, index, step, parameter):
        return 100 + parameter

    def setStepParameterByIndex(self, channel_index, pattern_index, step, parameter, value, flags):
        self.step_params[(channel_index, pattern_index, step, parameter)] = value

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


class StepDoubleTests(DeviceScriptTestCase):
    def test_shift_duplicate_does_not_call_double_when_feature_flag_is_disabled(self):
        module, _, _ = self.load_device_script()
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer
        launchpad.Shift = True

        def fail_double():
            raise AssertionError("DoubleCurrentStepPatternPage should not be called")

        launchpad.DoubleCurrentStepPatternPage = fail_double
        event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.DuplicateButton, 127)

        launchpad.OnMidiMsg(event)

        self.assertTrue(event.handled)

    def test_double_does_not_copy_without_pattern_length_api(self):
        module, _, channels_module = self.load_device_script(channels_module=RaisingChannels())
        launchpad = module.LaunchPadPro
        launchpad.UpdateStepSequencerView = lambda force=False: None
        launchpad.FocusStepSequencerRect = lambda: None

        launchpad.DoubleCurrentStepPatternPage()

        self.assertEqual(launchpad.StepOfs, 0)
        self.assertEqual(channels_module.set_grid_calls, [])

    def test_double_copies_after_pattern_length_api_extends_length(self):
        patterns_module = FakePatterns(expose_length_api=True)
        channels_module = FakeChannels()
        module, _, _ = self.load_device_script(patterns_module=patterns_module, channels_module=channels_module)
        launchpad = module.LaunchPadPro
        launchpad.UpdateStepSequencerView = lambda force=False: None
        launchpad.FocusStepSequencerRect = lambda: None

        launchpad.DoubleCurrentStepPatternPage()

        self.assertEqual(patterns_module.length, 32)
        self.assertEqual(launchpad.StepOfs, 16)
        self.assertEqual(channels_module.grid[(0, 16)], 1)
        self.assertEqual(channels_module.grid[(0, 19)], 1)
        self.assertEqual(channels_module.grid[(0, 17)], 0)
        self.assertEqual(channels_module.step_params[(0, 1, 16, 0)], 100)

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
