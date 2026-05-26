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
    def __init__(self):
        super().__init__("channels")
        self.grid = {(0, 0): 1, (0, 3): 1}
        self.step_params = {}
        self.set_grid_calls = []

    def channelCount(self):
        return 1

    def isGridBitAssigned(self, index):
        return index == 0

    def getChannelIndex(self, index):
        return index

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


class RaisingChannels(FakeChannels):
    def setGridBit(self, index, step, value):
        raise AssertionError("setGridBit should not be called")


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
    def load_device_script(self, patterns_module=None, channels_module=None):
        patterns_module = patterns_module or FakePatterns()
        channels_module = channels_module or FakeChannels()

        fakes = {
            "patterns": patterns_module,
            "channels": channels_module,
            "mixer": make_module("mixer", getSongStepPos=lambda: -1),
            "device": make_module(
                "device",
                isAssigned=lambda: False,
                createRefreshThread=lambda: None,
                destroyRefreshThread=lambda: None,
                fullRefresh=lambda: None,
                midiOutSysex=lambda data: None,
                stopRepeatMidiEvent=lambda: None,
            ),
            "transport": make_module("transport", isPlaying=lambda: 0, start=lambda: None, stop=lambda: None),
            "arrangement": make_module("arrangement"),
            "general": make_module("general", saveUndo=lambda *args: None, getVersion=lambda: 40),
            "launchMapPages": make_module("launchMapPages"),
            "playlist": make_module("playlist"),
            "ui": make_module("ui", getVersion=lambda: 40, crDisplayRect=lambda *args: None),
            "midi": make_midi_module(),
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
