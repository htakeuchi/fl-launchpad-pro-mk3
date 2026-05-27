import unittest

from test_step_pattern_actions import DeviceScriptTestCase, FakeChannels, FakeMixer, FakeTransport, MidiEvent, make_module


def grid_data1(module, x, y):
    raw_y = module.ClipsH - module.ClipsY - y
    return (raw_y * module.PadsStride) + module.ClipsX + x


class StepModeRegressionTests(DeviceScriptTestCase):
    def test_session_button_toggles_fl_control_mode(self):
        module, _, _ = self.load_device_script()
        launchpad = module.LaunchPadPro

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.SessionButton, 127))
        self.assertTrue(launchpad.ControllerMode)
        self.assertEqual(launchpad.CurLayout, 3)

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.SessionButton, 127))
        self.assertFalse(launchpad.ControllerMode)
        self.assertEqual(launchpad.CurLayout, 0)

    def test_note_enters_step_mode_from_fl_control_mode(self):
        module, _, _ = self.load_device_script(channels_module=FakeChannels(count=4, selected=2))
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True

        event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.NoteButton, 127, midi_chan=1)
        launchpad.OnMidiMsg(event)

        self.assertTrue(event.handled)
        self.assertTrue(launchpad.IsStepSequencerMode())
        self.assertEqual(launchpad.StepChannelOfs, 0)
        self.assertEqual(launchpad.StepOfs, 0)

    def test_note_from_step_mode_exits_to_normal_note_mode(self):
        device_module = make_module(
            "device",
            isAssigned=lambda: True,
            createRefreshThread=lambda: None,
            destroyRefreshThread=lambda: None,
            fullRefresh=lambda: None,
            midiOutSysex=lambda data: None,
            stopRepeatMidiEvent=lambda: None,
        )
        module, _, _ = self.load_device_script(device_module=device_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.NoteButton, 127, midi_chan=1)
        launchpad.OnMidiMsg(event)

        self.assertTrue(event.handled)
        self.assertFalse(launchpad.ControllerMode)
        self.assertEqual(launchpad.SurfaceMode, module.SurfaceModePerformance)
        self.assertEqual(launchpad.LastStandaloneLayout, module.LayoutNote)

    def test_step_pad_toggles_mapped_channel_and_step(self):
        channels_module = FakeChannels(count=4)
        module, _, _ = self.load_device_script(channels_module=channels_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        launchpad.HandleStepSequencerMidi(MidiEvent(module.midi.MIDI_CONTROLCHANGE, grid_data1(module, 2, 3), 127))

        self.assertEqual(channels_module.set_grid_calls[-1], (1, 10, 1))
        self.assertEqual(channels_module.selected, 1)

    def test_step_navigation_moves_step_and_channel_pages(self):
        module, _, _ = self.load_device_script(channels_module=FakeChannels(count=10))
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        launchpad.HandleStepSequencerMidi(MidiEvent(module.midi.MIDI_CONTROLCHANGE, 0x5C, 127))
        self.assertEqual(launchpad.StepOfs, 16)

        launchpad.HandleStepSequencerMidi(MidiEvent(module.midi.MIDI_CONTROLCHANGE, 0x5B, 127))
        self.assertEqual(launchpad.StepOfs, 0)

        launchpad.HandleStepSequencerMidi(MidiEvent(module.midi.MIDI_CONTROLCHANGE, 0x46, 127))
        self.assertEqual(launchpad.StepChannelOfs, 4)

        launchpad.HandleStepSequencerMidi(MidiEvent(module.midi.MIDI_CONTROLCHANGE, 0x50, 127))
        self.assertEqual(launchpad.StepChannelOfs, 0)

    def test_step_mute_button_overlays_track_select_buttons(self):
        channels_module = FakeChannels(count=8)
        module, _, _ = self.load_device_script(channels_module=channels_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer
        launchpad.StepChannelOfs = 4

        mode_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackControlMuteButton, 127)
        launchpad.OnMidiMsg(mode_event)

        self.assertTrue(mode_event.handled)
        self.assertEqual(launchpad.StepTrackControlMode, module.StepTrackControlMute)
        self.assertEqual(launchpad.BtnMap[9][module.TrackControlMuteButton], module.StepMuteLed)
        self.assertEqual(launchpad.BtnMap[9][module.TrackControlSoloButton], module.StepSoloDimLed)

        track_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackSelectFirstButton, 127)
        launchpad.OnMidiMsg(track_event)

        self.assertTrue(track_event.handled)
        self.assertIn(0, channels_module.muted)
        self.assertEqual(channels_module.selected, 0)
        self.assertEqual(channels_module.mute_calls[-1], (0, -1, False))
        self.assertEqual(launchpad.GetStepTrackSelectButtonColor(module.TrackSelectFirstButton), module.StepMuteLed)

    def test_step_solo_button_overlays_track_select_buttons(self):
        channels_module = FakeChannels(count=8)
        module, _, _ = self.load_device_script(channels_module=channels_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer
        launchpad.StepChannelOfs = 4

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackControlSoloButton, 127))
        track_event = MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackSelectLastButton, 127)
        launchpad.OnMidiMsg(track_event)

        self.assertTrue(track_event.handled)
        self.assertIn(7, channels_module.soloed)
        self.assertEqual(channels_module.selected, 7)
        self.assertEqual(channels_module.solo_calls[-1], (7, -1, False))
        self.assertEqual(launchpad.GetStepTrackSelectButtonColor(module.TrackSelectLastButton), module.StepSoloLed)

    def test_step_mute_button_repress_clears_all_track_select_mutes(self):
        channels_module = FakeChannels(count=8)
        channels_module.muted.update({0, 2, 7})
        module, _, _ = self.load_device_script(channels_module=channels_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackControlMuteButton, 127))
        self.assertEqual(launchpad.GetStepTrackSelectButtonColor(module.TrackSelectFirstButton), module.StepMuteLed)

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackControlMuteButton, 127))

        self.assertEqual(channels_module.muted, set())
        self.assertEqual(channels_module.mute_calls[-3:], [(0, 0, False), (2, 0, False), (7, 0, False)])
        self.assertEqual(launchpad.StepTrackControlMode, module.StepTrackControlNone)
        self.assertEqual(launchpad.GetStepTrackSelectButtonColor(module.TrackSelectFirstButton), 0)

    def test_step_solo_button_repress_clears_last_selected_solo(self):
        channels_module = FakeChannels(count=8)
        module, _, _ = self.load_device_script(channels_module=channels_module)
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackControlSoloButton, 127))
        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackSelectFirstButton + 5, 127))
        self.assertIn(5, channels_module.soloed)

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, module.TrackControlSoloButton, 127))

        self.assertNotIn(5, channels_module.soloed)
        self.assertEqual(channels_module.solo_calls[-1], (5, -1, False))
        self.assertEqual(launchpad.StepTrackControlMode, module.StepTrackControlNone)
        self.assertEqual(launchpad.GetStepTrackSelectButtonColor(module.TrackSelectFirstButton + 5), 0)

    def test_play_button_toggles_transport_and_led_in_step_mode(self):
        midi_module = __import__("types").SimpleNamespace(PM_Playing=1)
        transport_module = FakeTransport(midi_module)
        module, _, _ = self.load_device_script(
            channels_module=FakeChannels(count=4),
            transport_module=transport_module,
        )
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer
        y, x = module.BtnInfo[module.Btn_Play].GetYX()

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, 0x14, 127))
        self.assertTrue(transport_module.playing)
        self.assertEqual(launchpad.BtnMap[y][x], module.PlayLedPlaying)

        launchpad.OnMidiMsg(MidiEvent(module.midi.MIDI_CONTROLCHANGE, 0x14, 127))
        self.assertFalse(transport_module.playing)
        self.assertEqual(launchpad.BtnMap[y][x], 0)

    def test_step_pad_colors_are_off_for_empty_steps_and_channel_color_for_active_steps(self):
        module, _, _ = self.load_device_script(channels_module=FakeChannels(count=1))
        launchpad = module.LaunchPadPro

        self.assertEqual(launchpad.GetStepPadColor(0, 1), 0)
        self.assertGreater(launchpad.GetStepPadColor(0, 0), 0)

    def test_playhead_led_overlays_visible_step_across_visible_channels(self):
        mixer_module = FakeMixer(song_step_pos=3)
        module, _, _ = self.load_device_script(
            channels_module=FakeChannels(count=4),
            mixer_module=mixer_module,
            transport_module=FakeTransport(__import__("types").SimpleNamespace(PM_Playing=1), playing=True),
        )
        launchpad = module.LaunchPadPro
        launchpad.ControllerMode = True
        launchpad.SurfaceMode = module.SurfaceModeStepSequencer

        launchpad.UpdateStepSequencerView(False)

        x = module.SClipsX + 3
        for channel_pos in range(0, module.StepChannelsPerPage):
            y = module.SClipsY + (channel_pos * module.StepRowsPerChannel)
            self.assertEqual(launchpad.BtnMap[y][x], module.StepPlayheadLed)


if __name__ == "__main__":
    unittest.main()
