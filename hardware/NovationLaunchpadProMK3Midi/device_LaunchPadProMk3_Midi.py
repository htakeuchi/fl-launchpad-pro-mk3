# name=NovationLaunchpadProMK3Midi
# url=
# supportedDevices=LPProMK3 MIDI
# receiveFrom=NovationLaunchpadProMK3DAW

import patterns
import channels
import mixer
import device
import transport
import arrangement
import general
import launchMapPages
import playlist
import ui

import midi
import utils
import math
import time

MaxInt = 2147483647
PadsW = 10
PadsH = 10
BtnMapLength = PadsH * PadsW;
# clips
ClipsX = 1
ClipsY = 1
ClipsW = 9
ClipsH = 9
SceneY = 8
# solid clips
SClipsX = 1
SClipsY = 1
SClipsW = 8
SClipsH = 8
# overview
OverX = 1
OverY = 1
OverW = 8
OverH = 8
# overlay
LayX = ClipsX
LayY = ClipsY
LayW = ClipsW
LayH = ClipsH
# stride
PadsStride = 10
ForbiddenPads = [0, 9, 90, 99] #corners
SessionButton = 0x5D
NoteButton = 0x5E
ChordButton = 0x5F
CustomButton = 0x60
Div127 = 1 / 127

SysexIdentityRequest = bytes([0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7])
SysexProgrammerModeOn = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x0E, 0x01, 0xF7])
SysexProgrammerModeOff = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x0E, 0x00, 0xF7])
SysexDawModeOn = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x10, 0x01, 0xF7])
SysexDawModeOff = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x10, 0x00, 0xF7])

BridgeDispatchStatus = 0xF4
BridgeDispatchHeader = [0xF0, 0x00, 0x20, 0x29, 0x7D]
BridgeCommandToggleControllerMode = 0x01
BridgeCommandEnterControllerMode = 0x02

LayoutSession = 0
LayoutChord = 2
LayoutCustom = 3
LayoutNote = 4

SurfaceModePerformance = 0
SurfaceModeStepSequencer = 1
StepChannelsPerPage = 4
StepRowsPerChannel = 2
StepStepsPerChannel = 16
StepMaxSteps = 512

StepChannelFallbackColors = (
    0x3F1206,
    0x063F18,
    0x0A243F,
    0x3F3006,
    0x3F0A24,
    0x0A3F3A,
    0x24123F,
    0x303F08,
)

StepSequencerRefreshFlags = (
    getattr(midi, 'HW_ChannelEvent', 0) |
    getattr(midi, 'HW_Dirty_ChannelRackGroup', 0) |
    getattr(midi, 'HW_Dirty_Patterns', 0) |
    getattr(midi, 'HW_Dirty_Colors', 0) |
    getattr(midi, 'HW_Dirty_Names', 0)
)

TopModeButtonLeds = {
    3: 0x3F3F3F, # Session / FL control mode
    4: 0x202020, # Note
    5: 0x202020, # Chord
    6: 0x202020,
    7: 0x202020,
    8: 0x202020,
}

ControllerModeDirectLeds = {
    93: 0x3F3F3F, # Session
    94: 0x202020, # Note
    95: 0x202020, # Chord
    96: 0x202020,
    97: 0x202020,
    98: 0x202020,
    3: 0x3F3F3F, # Mirrored fallback for firmware/coordinate differences
    4: 0x202020,
    5: 0x202020,
    6: 0x202020,
    7: 0x202020,
    8: 0x202020,
}

def BuildSelectLayoutSysex(Layout, Page=0):
    return bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x00, Layout, Page, 0x00, 0xF7])

MaxPads = PadsW * PadsH
NumBtns = 12

Btn_Overview = 0
Btn_ScenePlus = 1
Btn_Scene = 2
Btn_Queue = 3
Btn_Snap = 4
Btn_Spare = 5
Btn_Play = 6
Btn_Stop = 7
Btn_TapTempo = 8
Btn_TempoNudgePlus = 9
Btn_TempoNudgeMin = 10
Btn_VelLock = 11

LPBlinkShift = 24
LPBlink1 = 1 << LPBlinkShift
LPBlink2 = 2 << LPBlinkShift
LPBlink3 = 3 << LPBlinkShift
LPBlink4 = 4 << LPBlinkShift
LPBlinkMask = 0xFF << LPBlinkShift

class TBtnInfo():
    def __init__(self, Id, Num, Flags, Col):
        self.Id = Id
        self.Num = Num
        self.Flags = Flags
        self.Col = Col  # off, on, held

    def GetYX(self):
        return utils.DivModU(self.Num, PadsW)

BtnInfo = [TBtnInfo(Btn_Overview, 3, 0 ,(0x040404, 0x3F3F3F, 0x000000)), TBtnInfo(Btn_ScenePlus, 8 ,1 ,(0x020000, 0x1C0000 | LPBlink4, 0x3F0A00)), TBtnInfo(Btn_Scene, 7, 1, (0x020000, 0x1C0000 | LPBlink4, 0x3F0A00)), TBtnInfo(Btn_Queue, 6, 1, (0x000100, 0x000A00 | LPBlink4, 0x002C10)), TBtnInfo(Btn_Snap, 5, 1 ,(0x000004, 0x000020 | LPBlink4, 0x00023F)), TBtnInfo(Btn_Spare, 6, 0, (0x040404, 0x3F3F3F, 0x000000)), TBtnInfo(Btn_Play, 70, 0, (0, 0, 0)), TBtnInfo(Btn_Stop, 80, 0, (0x000200, 0x001C00, 0x000000)), TBtnInfo(Btn_TapTempo, 30, 0, (0x000102, 0x00163F, 0x000000)), TBtnInfo(Btn_TempoNudgePlus, 40, 0, (0x000102, 0x00163F | LPBlink4, 0x000000)), TBtnInfo(Btn_TempoNudgeMin, 50, 0, (0x000102, 0x00163F | LPBlink4, 0x000000)), TBtnInfo(Btn_VelLock, 60, 1, (0x020001, 0x1C0010 | LPBlink4, 0x3F0A20))]
BlinkColT = ((0x280102, 0x3F3F3F), (0x100002, 0x18002F), (0x100100, 0x181000), (0x000000, 0x3F3F3F))

class TLaunchPadPro():
    def __init__(self):
        self.Shift = False
        self.ClipOfs = 0
        self.TrackOfs = 0
        self.TrackOfs_Spare = 0
        self.ClipOfs_Spare = 0
        self.BlockOfs = False # make arrows work in pages

        self.BtnT = bytearray(NumBtns)
        self.ArrowT = bytearray(4)
        self.BlinkOnBars = 0
        self.BtnLastClip = [[0 for x in range(PadsW)] for y in range(PadsH)]
        self.BtnLastPressure = [[0 for x in range(PadsW)] for y in range(PadsH)]

        self.BtnMap = [[0 for x in range(PadsW)] for y in range(PadsH)]
        self.AnimBtnMap = [[0 for x in range(PadsW)] for y in range(PadsH)]
        self.ScreenCapBtnMap= [[0 for x in range(PadsW)] for y in range(PadsH)]
        self.OldBtnMap = [[0 for x in range(PadsW)] for y in range(PadsH)]

        self.NoFullRefresh = False
        self.BeatPos = 0
        self.BlinkLight = 2
        self.CurLayout = 0
        self.ControllerMode = False
        self.SurfaceMode = SurfaceModePerformance
        self.StepChannelOfs = 0
        self.StepOfs = 0
        self.LastStandaloneLayout = LayoutNote
        self.LastStandalonePage = 0
        self.SuppressNextSessionLayout = False

        self.BtnMapMode = 0 #animation
        self.BtnMapModeRefCount = 0

        self.ScreenCapZoom = 32
        #todo ScreenCapDIB1, ScreenCapDIB2: TDIB;
        #todo ScreenDC: HDC;
        self.ScreenCapTime = 0
        self.ColScaleT = bytearray(256)

    def ResetBtnLastClip(self):
        for y in range(0, PadsW):
            for x in range(0, PadsH):
                self.BtnLastClip[x][y] = utils.TClipLauncherLastClip(MaxInt, MaxInt, MaxInt)

    def ResetBtnMap(self, BtnMapObj, val):
        for y in range(0, PadsH):
            for x in range(0, PadsW):
                BtnMapObj[y][x] = val

    def UpdateBlinking(self):  #check if any blinking button
        for y in range(0, PadsH):
            for x in range(0, PadsW):
                if self.BtnMap[y][x] > 1:
                    self.FullRefresh_Btn()
                    return

    def OnMidiIn(self, event):
        if event.status == BridgeDispatchStatus:
            if len(event.sysex) >= 7 and list(event.sysex[0:5]) == BridgeDispatchHeader:
                command = event.sysex[5]
                if command == BridgeCommandToggleControllerMode:
                    self.SetControllerMode(not self.ControllerMode)
                elif command == BridgeCommandEnterControllerMode:
                    self.SetControllerMode(True)
                event.handled = True
                return

        if event.status == midi.MIDI_BEGINSYSEX:
            print ('midi in sysex', len(event.sysex), event.sysex[0], event.sysex[1], event.sysex[2], event.sysex[3], event.sysex[4], event.sysex[5], event.sysex[6], event.sysex[7], event.sysex[8], event.sysex[9]) #, event.sysex[10], event.sysex[11], event.sysex[12], event.sysex[13], event.sysex[14], event.sysex[15], event.sysex[16])
            #layout change
            if (len(event.sysex) == 11) & (event.sysex[5] == 0x0E) & (event.sysex[6] == 0x00):
                print('layout change')
                self.CurLayout = event.sysex[7]
                layout_page = event.sysex[8]
                if self.CurLayout == LayoutSession:
                    if self.SuppressNextSessionLayout:
                        self.SuppressNextSessionLayout = False
                    elif not self.ControllerMode:
                        self.SetControllerMode(True)
                elif not self.ControllerMode:
                    self.LastStandaloneLayout = self.CurLayout
                    self.LastStandalonePage = layout_page
            event.handled = True
        else:
            event.handled = False

    def Reset(self):
        self.ResetBtnMap(self.BtnMap, 0)
        self.ResetBtnMap(self.AnimBtnMap, 0)
        self.ResetBtnMap(self.ScreenCapBtnMap, 0)
        self.ResetBtnMap(self.OldBtnMap, 0xFF)
        self.ResetBtnLastClip()

    def IsSessionButton(self, event):
        return (event.midiId in [midi.MIDI_NOTEON, midi.MIDI_NOTEOFF, midi.MIDI_CONTROLCHANGE]) and (event.data1 == SessionButton)

    def IsNoteButton(self, event):
        return (event.midiId in [midi.MIDI_NOTEON, midi.MIDI_NOTEOFF, midi.MIDI_CONTROLCHANGE]) and (event.data1 == NoteButton)

    def IsModeExitButton(self, event):
        return (event.midiId in [midi.MIDI_NOTEON, midi.MIDI_NOTEOFF, midi.MIDI_CONTROLCHANGE]) and (event.data1 in [ChordButton, CustomButton])

    def SetStandaloneLayoutFromModeButton(self, data1):
        if data1 == NoteButton:
            self.LastStandaloneLayout = LayoutNote
            self.LastStandalonePage = 0
        elif data1 == ChordButton:
            self.LastStandaloneLayout = LayoutChord
            self.LastStandalonePage = 0
        elif data1 == CustomButton:
            self.LastStandaloneLayout = LayoutCustom

    def ApplyControllerModeButtonLeds(self):
        if not self.ControllerMode:
            return
        for x, color in TopModeButtonLeds.items():
            self.BtnMap[0][x] = color
        if self.SurfaceMode == SurfaceModeStepSequencer:
            self.BtnMap[0][4] = 0x003F3F | LPBlink4

    def SendControllerModeButtonLeds(self):
        if not self.ControllerMode or not device.isAssigned():
            return

        s = bytearray([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x03])
        for led_index, color in ControllerModeDirectLeds.items():
            if self.SurfaceMode == SurfaceModeStepSequencer and led_index in [94, 4]:
                color = 0x003F3F
            r, g, b = utils.ColorToRGB(color)
            s.extend([3, led_index, r, g, b])
        s.append(0xF7)
        device.midiOutSysex(bytes(s))

    def IsPlayButton(self, event):
        return (event.midiId in [midi.MIDI_NOTEON, midi.MIDI_NOTEOFF, midi.MIDI_CONTROLCHANGE]) and (event.data1 == 0x14)

    def TogglePlayback(self, event):
        if event.data2 <= 0:
            return
        if transport.isPlaying() == midi.PM_Playing:
            transport.stop()
        else:
            transport.start()

    def IsStepSequencerMode(self):
        return self.ControllerMode and (self.SurfaceMode == SurfaceModeStepSequencer)

    def SetStepSequencerMode(self, Enabled):
        if Enabled:
            self.SurfaceMode = SurfaceModeStepSequencer
            self.SyncStepChannelOffsetToSelected()
            self.NormalizeStepSequencerOffsets()
            self.Reset()
            self.SwitchLedsOff()
            self.UpdateStepSequencerView(True)
            self.FocusStepSequencerRect()
        else:
            self.SurfaceMode = SurfaceModePerformance
            self.Reset()
            self.SwitchLedsOff()
            for n in range(1, len(self.BtnT)):
                self.SetBtn(n, self.BtnT[n])
            self.OnUpdateLiveMode(playlist.trackCount())
            self.SetOfs(self.TrackOfs, self.ClipOfs)

    def SetControllerMode(self, Enabled):
        if Enabled == self.ControllerMode:
            return

        self.ControllerMode = Enabled

        if not device.isAssigned():
            self.CurLayout = 3 if Enabled else 0
            return

        if Enabled:
            print('NovationLaunchpadProMK3Midi: FL control mode on')
            if self.SurfaceMode != SurfaceModeStepSequencer:
                self.SurfaceMode = SurfaceModePerformance
            device.midiOutSysex(SysexIdentityRequest)
            device.midiOutSysex(SysexProgrammerModeOn)
            self.CurLayout = 3
            self.Reset()
            self.SwitchLedsOff()
            if self.SurfaceMode == SurfaceModeStepSequencer:
                self.UpdateStepSequencerView(True)
                self.FocusStepSequencerRect()
            else:
                for n in range(1, len(self.BtnT)):
                    self.SetBtn(n, self.BtnT[n])
                self.OnUpdateLiveMode(playlist.trackCount())
                self.SetOfs(self.TrackOfs, self.ClipOfs)
                self.ApplyControllerModeButtonLeds()
                device.fullRefresh()
                self.SendControllerModeButtonLeds()
        else:
            print('NovationLaunchpadProMK3Midi: normal Launchpad mode on')
            if self.CurLayout == 3:
                self.SwitchLedsOff()
            self.SurfaceMode = SurfaceModePerformance
            self.SuppressNextSessionLayout = True
            self.CurLayout = 0
            self.Reset()
            playlist.liveDisplayZone(-1, -1, -1, -1)
            playlist.lockDisplayZone(0, False)
            device.stopRepeatMidiEvent()
            device.midiOutSysex(SysexProgrammerModeOff)
            device.midiOutSysex(SysexDawModeOn)
            device.midiOutSysex(BuildSelectLayoutSysex(self.LastStandaloneLayout, self.LastStandalonePage))

    def OnMidiMsg(self, event):
        print (event.status, event.data1, event.data2)
        ColT = (0x000000, 0x2F0018 | LPBlink2)

        if self.IsStepSequencerMode() and self.IsPlayButton(event):
            event.handled = True
            self.TogglePlayback(event)
            return

        if event.midiChan > 0:
            return

        if self.IsSessionButton(event):
            event.handled = True
            if event.data2 > 0:
                self.SetControllerMode(not self.ControllerMode)
            return

        if self.IsNoteButton(event):
            if self.ControllerMode:
                event.handled = True
                if event.data2 > 0:
                    if self.SurfaceMode == SurfaceModeStepSequencer:
                        self.SetStandaloneLayoutFromModeButton(event.data1)
                        self.SetControllerMode(False)
                    else:
                        self.SetStepSequencerMode(True)
                return

        if self.ControllerMode and self.IsModeExitButton(event):
            event.handled = True
            if event.data2 > 0:
                self.SetStandaloneLayoutFromModeButton(event.data1)
                self.SetControllerMode(False)
            return

        if not self.ControllerMode:
            event.handled = False
            return

        if self.IsStepSequencerMode():
            self.HandleStepSequencerMidi(event)
            return

        if event.midiId == midi.MIDI_CHANAFTERTOUCH:
            event.midiId = midi.MIDI_CONTROLCHANGE
            event.status = event.status & 0x0F | event.midiId
            event.inEv = event.data1;
            event.outEv = round(event.inEv * (midi.FromMIDI_Max / 127))

            if self.ClipOfs < -1:
              event.midiChan = 15
              event.data1 = midi.CC_Special - 1 - self.ClipOfs
            else:
              # clips: 1 for all clips in channel aftertouch
              event.midiChan = 0
              event.data1 = midi.CC_Special

            event.midiChanEx = event.midiChan + ((device.getPortNumber() + 1) << 6)
            device.processMIDICC(event)
            return

        elif event.midiId == midi.MIDI_KEYAFTERTOUCH:
            event.midiId = midi.MIDI_CONTROLCHANGE
            event.status = event.status & 0x0F | event.midiId

            y = event.data1 // PadsStride
            x = event.data1 - y * PadsStride - ClipsX
            y = ClipsH - ClipsY - y
            if (x >= PadsW) | (y >= PadsH):
                return

            self.BtnLastPressure[y][x] = event.data2

            if self.ClipOfs < -1:
                x2 = y * LayW + x # get the custom page item index
                if (x2 < 0) | (x2 >= launchMapPages.getMapCount(-self.ClipOfs - 2)):
                    return                    
                if launchMapPages.getMapItemAftertouch(-self.ClipOfs - 2, x2) < 0: # no aftertouch CC defined, default behavior
                    # special pages: 1 per page
                    event.midiChan = 15
                    event.data1 = midi.CC_Special - 1 - self.ClipOfs
                    for m in range(0, ClipsH):
                        for n in range(0, ClipsW):
                            event.data2 = max(event.data2, self.BtnLastPressure[m][n]) # max of the page
                else:
                    # pierre : per clip aftertouch, if defined for that item in the custom page
                    event.midiChan = 15                    
                    event.data1 = launchMapPages.getMapItemAftertouch(-self.ClipOfs - 2, x2)
            else:
                event.midiChan = 0
                # clips: 1 per track
                event.data1 = midi.CC_Special + 8 + y * 16
                for n in range(0, ClipsW):
                    event.data2 = max(event.data2, self.BtnLastPressure[y][n]) # max of the track
            
            event.midiChanEx = event.midiChan + ((device.getPortNumber() + 1) << 6)

            event.inEv = event.data2
            event.outEv = round(event.inEv * (midi.FromMIDI_Max / 127))
            device.processMIDICC(event)
            return

        elif event.midiId in [midi.MIDI_NOTEON, midi.MIDI_NOTEOFF, midi.MIDI_CONTROLCHANGE]:
            if event.midiId == midi.MIDI_NOTEOFF:
                event.data2 = 0
            elif (self.BtnT[Btn_VelLock] > 0) & (event.data2 > 0):
                event.data2 = 0x7F

            y = event.data1 // PadsStride
            x = event.data1 + 90 - y * PadsStride * 2 # top-down index
            # system buttons
            for n in range(1, len(BtnInfo)):
                if BtnInfo[n].Num == x:
                    event.handled = True
                    m2 = self.BtnT[n]
                    if (m2 >= 2) & (event.data2 > 0):
                        m = 0
                        m2 = 0
                    else:
                        m = int(event.data2 > 0)
                        if (BtnInfo[n].Flags & 1 != 0) & (m > 0) & device.isDoubleClick(event.data1) & ((self.ClipOfs >= -1) | (n != 2)):
                            m += 1

                    o = int(event.data2 > 0) * 2
                    if n == Btn_Play:
                        self.TogglePlayback(event)
                    elif n == Btn_Stop:
                        transport.globalTransport(midi.FPT_Stop, o, event.pmeFlags)
                    elif n == Btn_TapTempo:
                        transport.globalTransport(midi.FPT_TapTempo, o, event.pmeFlags)
                    elif n == Btn_TempoNudgePlus:
                        transport.globalTransport(midi.FPT_NudgePlus, o, event.pmeFlags)
                    elif n == Btn_TempoNudgeMin:
                        transport.globalTransport(midi.FPT_NudgeMinus, o, event.pmeFlags)
                    if (m > 0) | (m2 <= 1):
                        self.SetBtn(n, m)
                    if (n == 2) & (self.ClipOfs < -1) & (event.data2 > 0):
                        launchMapPages.releaseMapItem(event, -self.ClipOfs - 2)
                    return
            #system
            # track offset
            if (event.data1 == 0x50) | (event.data1 == 0x46):
                if (event.data1 == 0x50):
                    a = 0
                else:    
                    a = 1
                event.handled = True
                BlockPages = (self.BtnT[Btn_Overview] > 0) | self.BlockOfs
                m = 150 + int(BlockPages) * 350; # faster in 1-pad increments
                device.repeatMidiEvent(event, m, m)
                if (event.data2 > 0) & (event.pmeFlags & midi.PME_System != 0):
                    m = a * 2 - 1
                    if BlockPages:
                        m = m * OverH
                    self.SetOfs(self.TrackOfs + m, self.ClipOfs)
                    self.BtnT[Btn_Overview] = int(self.BtnT[Btn_Overview] > 0) * 2; # so that session btn works as held
                
                self.ArrowT[a] = event.data2
                self.CheckSpecialSwitches()
                playlist.lockDisplayZone(1 + a, event.data2 > 0)
                return

            # clip offset
            elif (event.data1 == 0x5B) | (event.data1 == 0x5C):
                a = event.data1 - 0x5B
                event.handled = True
                BlockPages = (self.BtnT[Btn_Overview] > 0) | self.BlockOfs
                m = 150 + int(BlockPages) * 350 # faster in 1-pad increments
                device.repeatMidiEvent(event, m, m);
                if (event.data2 > 0) & (event.pmeFlags & midi.PME_System != 0):
                    m = (a) * 2 - 1
                    if self.ClipOfs >= 0:
                        if (self.ClipOfs == 0) & (m == -1):
                            o = -1
                        else:
                            if BlockPages:
                                m = m * OverW
                            o = max(self.ClipOfs + m, 0)
                    else:
                        o = self.ClipOfs + m
                    self.SetOfs(self.TrackOfs, o)
                    self.BtnT[Btn_Overview] = int(self.BtnT[Btn_Overview] > 0) * 2 # so that session btn works as held
                    if self.ClipOfs <= 0:
                        device.stopRepeatMidiEvent()
                self.ArrowT[2 + a] = event.data2
                    
                self.ArrowT[3] = event.data2
                self.CheckSpecialSwitches()
                playlist.lockDisplayZone(1 + a, event.data2 > 0)
                return

            elif (event.data1 == 0x5D):  # overview
                event.handled = True
                if (event.pmeFlags & midi.PME_System != 0):
                    if event.data2 > 0:
                        self.SetBtn(Btn_Overview, int(self.BtnT[Btn_Overview] > 0) ^ 1)
                    elif self.BtnT[Btn_Overview] == 2:
                        self.SetBtn(Btn_Overview, 0)
                return

            elif (event.data1 == 0x60): # spare state
                event.handled = True
                if (event.pmeFlags & midi.PME_System != 0):
                    if event.data2 > 0:
                        self.SetBtn(Btn_Spare, int(event.data2 > 0))
                return

            elif ((event.data1 >= 0x61) & (event.data1 <= 0x7F)) | (event.data1 in    [0x0A, 0x14, 0x1E, 0x28, 0x32, 0x3C, 0x46, 0x50]):
                return

            # live mode
            x = event.data1 - y * PadsStride - ClipsX
            y = ClipsH - ClipsY - y
            if (x >= PadsW) | (y >= PadsH):
                return

            # clip release safety
            if event.data2 == 0:

                if self.BtnLastClip[y][x].TrackNum != MaxInt:
                    if (event.pmeFlags & midi.PME_System_Safe != 0):
                        playlist.triggerLiveClip(self.BtnLastClip[y][x].TrackNum, self.BtnLastClip[y][x].SubNum, self.BtnLastClip[y][x].Flags | midi.TLC_Release)
                    if self.BtnLastClip[y][x].TrackNum == 0:
                        self.BtnMap[SClipsY + y][SClipsX + x] = ColT[0]
                        self.FullRefresh_Btn()

                    self.BtnLastClip[y][x].TrackNum = MaxInt;
                    event.handled = True
                    return

            if self.BtnT[Btn_Overview] > 0:
                # overview pick
                if event.data2 > 0:
                    if y < OverH - 1:
                        if x >= OverW:
                            self.SetOfs(self.TrackOfs, -y - 1)
                        else:
                            self.SetOfs(y * OverH, x * OverW)
                    elif x < OverW:
                        self.SetOfs(self.TrackOfs, -(x + 8) - 1)
                else:
                    self.SetBtn(Btn_Overview, 0)
                event.handled = True
            else:
                if self.ClipOfs < -1:
                    # custom pages
                    x2 = y * LayW + x
                    m = -self.ClipOfs - 2;
                    if x2 <= launchMapPages.getMapCount(m):
                        o = launchMapPages.getMapItemChannel(m, x2)
                        if o > -128:
                            m2 = event.data2
                            if (m2 == 0) & (self.BtnT[Btn_ScenePlus] > 0):
                                m2 = -MaxInt # user1=hold
                            launchMapPages.processMapItem(event, m, x2, m2)
                else:
                    if self.ClipOfs >= 0:
                        # first chance
                        launchMapPages.processMapItem(event, -1, y * PadsW + x, event.data2)
                        if event.handled:
                            return

                    if (event.pmeFlags & midi.PME_System_Safe != 0):
                        x2 = x;
                        y2 = y + self.TrackOfs + 1
                        if self.ClipOfs >= 0:
                            if event.data2 > 0:
                                # clip launch
                                m = midi.TLC_MuteOthers | midi.TLC_Fill
                                if y >= SceneY:
                                    y2 = 0
                                    m = m | midi.TLC_ColumnMode # column mode

                                if x2 >= SClipsW:
                                    x2 = -1
                                else:
                                    x2 += self.ClipOfs
                                m = midi.TLC_MuteOthers | midi.TLC_Fill
                                if self.BtnT[Btn_Queue] > 0:
                                    m = m | midi.TLC_Queue
                                if self.BtnT[Btn_Snap] > 0:
                                    m = m | midi.TLC_GlobalSnap # snap
                                if self.BtnT[Btn_ScenePlus] | (self.BtnT[Btn_Scene] > 0):
                                    m = m | midi.TLC_ColumnMode; # column mode
                                    if self.BtnT[Btn_ScenePlus] == 0:
                                        m = m | midi.TLC_WeakColumnMode # weak
                                    elif self.BtnT[Btn_Scene] > 0:
                                        m = m | midi.TLC_TriggerCheckColumnMode # trigger-check

                                if (self.BtnT[Btn_VelLock] > 0):
                                    playlist.triggerLiveClip(y2, x2, m)
                                else:
                                    playlist.triggerLiveClip(y2, x2, m, event.data2 * (1 / 127))

                                self.BtnLastClip[y][x].TrackNum = y2
                                self.BtnLastClip[y][x].SubNum = x2
                                self.BtnLastClip[y][x].Flags = m
                        elif event.data2 > 0:
                            # track properties
                            if (x2 == 2) | (x2 == 3):
                                playlist.incLivePosSnap(y2, (x2 - 2) * 2 - 1)
                            elif (x2 == 4) | (x2 == 5):
                                playlist.incLiveTrigSnap(y2, (x2 - 4) * 2 - 1)
                            elif (x2 == 6) | (x2 == 7):
                                playlist.incLiveLoopMode(y2, (x2 - 6) * 2 - 1);
                            elif x2 == 8        :
                                playlist.incLiveTrigMode(y2, 1);

                            playlist.refreshLiveClips()
                        event.handled = True
        else:
            event.handled = False

    def OnMidiOutMsg(self, event):

        if not self.ControllerMode:
            event.handled = False
            return

        print (event.status, event.data1, event.data2)
        event.handled = True
        ID = event.midiId
        n = 0
        if (ID == midi.MIDI_NOTEOFF) | (ID == midi.MIDI_NOTEON):
            NoteNum = event.note
            if ID == midi.MIDI_NOTEOFF:
                Velocity = 0
            else:
                Velocity = event.velocity

            if NoteNum >= 125:
                if NoteNum == 125:
                    if ID == midi.MIDI_NOTEON:
                        self.ScreenCapZoom = 1 + (Velocity >> 1)
                else:
                    if NoteNum == 126:
                        if ID == midi.MIDI_NOTEON:
                            self.BtnMapModeRefCount += 1
                            if self.BtnMapModeRefCount == 1:
                                device.fullRefresh()
                        else:
                            self.BtnMapModeRefCount -= 1
                            if self.BtnMapModeRefCount == 0:
                                device.fullRefresh()
                    elif ID == midi.MIDI_NOTEON:
                        m = Velocity >> 5
                        if self.BtnMapMode != m:
                            if m >= 3:
                                self.ScreenCapTime = time.time()
                            self.BtnMapMode = m
                            device.fullRefresh()
            else:
                # change pad
                Chan = event.midiChan
                if Chan < 3:
                    if (Chan > 0) & (ID == midi.MIDI_NOTEOFF):
                        return

                o, n = utils.DivModU(NoteNum, 12)
                if o < PadsH:
                    o = PadsH - 1 - o

                if utils.InterNoSwap(o, 0, PadsH) & utils.InterNoSwap(n, 0, PadsW - 1) & ((o < PadsH) | (n < PadsW - 1)): #light shouldn't be touched'
                    r, g, b = utils.ColorToRGB(self.AnimBtnMap[o][n])
                    if Chan == 0:
                        r = Velocity
                    elif Chan == 1:
                        g = Velocity
                    else:
                        b = Velocity
                    self.AnimBtnMap[o][n] = utils.RGBToColor(r, g, b)
                    self.FullRefresh_Anim()

        elif ID != midi.MIDI_CONTROLCHANGE:
            event.handled = False

    def OnDoFullRefresh(self):

        TempBtnMap = [[0 for x in range(PadsW)] for y in range(PadsH + 1)]
        TempAnimBtnMap = [[0 for x in range(PadsW)] for y in range(PadsH + 1)]

        if self.ControllerMode and (self.CurLayout == 3) and device.isAssigned():
            TempBtnMapMode = self.BtnMapMode

            if TempBtnMapMode >= 3:
                for y in range(0, PadsH):
                    for x in range(0, PadsW):
                        TempBtnMap[y][x] = self.BtnMap[y][x]
                TempBtnMap[0][PadsW - 1] = self.BtnMap[0][PadsW - 1] # bottom light
            else:
                if TempBtnMapMode < 2:
                    if self.BtnMapModeRefCount == 0:
                        for y in range(0, PadsH):
                            for x in range(0, PadsW):
                                TempBtnMap[y][x] = self.BtnMap[y][x]
                    else:
                        TempBtnMapMode = 2
                        TempBtnMap[0][PadsW - 1] = self.BtnMap[0][PadsW - 1] # bottom light

                if TempBtnMapMode > 0:
                    for y in range(0, PadsH):
                        for x in range(0, PadsW):
                            TempAnimBtnMap[y][x] = self.AnimBtnMap[y][x]

                # adapt anim map
                if TempBtnMapMode > 0:
                    for y in range(0, PadsH):
                        for x in range(0, PadsW):
                            r, g, b = utils.ColorToRGB(TempAnimBtnMap[y][x])
                            c = utils.HLSToRGB(g * Div127, r * Div127, b * Div127)
                            c = self.FixColor(c)
                            if (TempBtnMapMode >= 2) | (c > 0):
                                TempBtnMap[y][ x] = c

            # update blinking
            for y in range(0, PadsH):
                for x in range(0, PadsW):
                    o = TempBtnMap[y][x]
                    if o & LPBlinkMask != 0:
                        TempBtnMap[y][x] = utils.FadeColor(o, BlinkColT[min(o >> LPBlinkShift, 3)][0], self.BlinkLight)

            # build SysEx
            t = (0x030E02292000F0).to_bytes(8 + 5 * MaxPads, byteorder='little')
            s = bytearray(t)
            m = 7

            for y in range(0, PadsH):
                y2 = y * 10
                for x in range(0, PadsW):
                    p = 90 - y2 + x
                    # add to the list
                    if (TempBtnMap[y][x] != self.OldBtnMap[y][x]) & (not (p in ForbiddenPads)):
                        s[m] = 3
                        s[m + 1] = 90 - y2 + x
                        s[m + 2], s[m + 3], s[m + 4] = utils.ColorToRGB(TempBtnMap[y][x])
                        m += 5

            # send it
            if m > 8:
                s[m] = 0xF7;
                s = s[: m + 1]
                device.midiOutSysex(bytes(s))
                self.SendControllerModeButtonLeds()
                '''
                sf = ''
                for y in range(7, len(s)):
                    sf = sf + str(s[y]) + ', '
                    if (y - 6) % 5 == 0:
                        print(sf)
                        sf = ''
                print('---------------------')
                '''

            # backup
            for y in range(0, PadsH):
                for x in range(0, PadsW):
                    self.OldBtnMap[y][x] = TempBtnMap[y][x]

    def FullRefresh_Btn(self):

        if (self.BtnMapMode < 2) & (self.BtnMapModeRefCount == 0):
            device.fullRefresh()

    def FullRefresh_Anim(self):

        if ((self.BtnMapMode > 0) & (self.BtnMapMode < 3)) | (self.BtnMapModeRefCount != 0):
            device.fullRefresh()

    def SetOfs(self, SetTrackOfs, SetClipOfs):

        Col1 = 0x010900
        Col2 = 0x090100

        self.TrackOfs = utils.Limited(SetTrackOfs, 0, playlist.trackCount() - PadsH)
        self.ClipOfs = utils.Limited(SetClipOfs, -launchMapPages.length() - 1, 0x10000)
        if self.ControllerMode and device.isAssigned():
            # page buttons
            o = self.TrackOfs + 4
            v = utils.Limited(o, 0, 256)
            self.BtnMap[1][0] = utils.FadeColor(Col2, Col1, v)
            self.BtnMap[2][0] = utils.FadeColor(Col1, Col2, v)

            o = abs(self.ClipOfs) * 4
            if self.ClipOfs < 0:
                o = o * 4
            v = utils.Limited(o, 0, 256)
            self.BtnMap[0][1] = utils.FadeColor(Col2, Col1, v)
            self.BtnMap[0][2] = utils.FadeColor(Col1, Col2, v)

            if self.ClipOfs < -1:
                launchMapPages.updateMap(-self.ClipOfs - 2)
            else:
                launchMapPages.checkMapForHiddenItem()
            self.OnUpdateLiveMode(playlist.trackCount())

        if playlist.getDisplayZone() != 0:
            self.OnDisplayZone()

    def OnDisplayZone(self):
        if not self.ControllerMode:
            return

        if self.IsStepSequencerMode():
            self.FocusStepSequencerRect()
            return

        if (self.ClipOfs >= 0) & (playlist.getDisplayZone() != 0):
            playlist.liveDisplayZone(self.ClipOfs, self.TrackOfs + 1, self.ClipOfs + PadsW - 1, self.TrackOfs + 1 + PadsH)
        else:
            playlist.liveDisplayZone(-1, -1, -1, -1)

    def StepPadToChannelStep(self, x, y):
        return self.StepChannelOfs + (y // StepRowsPerChannel), self.StepOfs + ((y % StepRowsPerChannel) * SClipsW) + x

    def SyncStepChannelOffsetToSelected(self):
        selected_channel = channels.selectedChannel(1)
        if selected_channel >= 0:
            self.StepChannelOfs = (selected_channel // StepChannelsPerPage) * StepChannelsPerPage

    def NormalizeStepSequencerOffsets(self):
        channel_count = channels.channelCount()
        if channel_count <= 0:
            self.StepChannelOfs = 0
            self.StepOfs = 0
            return

        max_channel_ofs = max(0, channel_count - StepChannelsPerPage)
        self.StepChannelOfs = utils.Limited(self.StepChannelOfs, 0, max_channel_ofs)

        self.StepOfs = utils.Limited((self.StepOfs // StepStepsPerChannel) * StepStepsPerChannel, 0, StepMaxSteps - StepStepsPerChannel)

    def ScaleLaunchpadColor(self, Color, Scale):
        r, g, b = utils.ColorToRGB(Color)
        return utils.RGBToColor(
            utils.Limited(round(r * Scale), 0, 63),
            utils.Limited(round(g * Scale), 0, 63),
            utils.Limited(round(b * Scale), 0, 63),
        )

    def EnsureVisibleStepColor(self, Color, MinValue):
        r, g, b = utils.ColorToRGB(Color)
        peak = max(r, g, b)
        if peak == 0:
            return Color
        if peak >= MinValue:
            return Color
        return self.ScaleLaunchpadColor(Color, MinValue / peak)

    def GetStepChannelColor(self, ChannelIndex):
        color = self.FixColor(channels.getChannelColor(ChannelIndex))
        r, g, b = utils.ColorToRGB(color)
        if max(r, g, b) < 8:
            color = StepChannelFallbackColors[ChannelIndex % len(StepChannelFallbackColors)]
        return self.EnsureVisibleStepColor(color, 63)

    def GetStepPadColor(self, ChannelIndex, Step):
        if not utils.InterNoSwap(ChannelIndex, 0, channels.channelCount() - 1):
            return 0

        base_color = self.GetStepChannelColor(ChannelIndex)

        if channels.isGridBitAssigned(ChannelIndex) and channels.getGridBit(ChannelIndex, Step) > 0:
            return base_color

        return 0

    def FocusStepSequencerRect(self):
        channel_count = channels.channelCount()
        if device.isAssigned() and channel_count > 0:
            ui.crDisplayRect(
                self.StepOfs,
                self.StepChannelOfs,
                StepStepsPerChannel,
                min(StepChannelsPerPage, channel_count - self.StepChannelOfs),
                1000,
                midi.CR_ScrollToView,
            )

    def UpdateStepSequencerView(self, Force=False):
        if not self.IsStepSequencerMode():
            return

        self.NormalizeStepSequencerOffsets()
        for y in range(0, SClipsH):
            for x in range(0, SClipsW):
                channel_index, step = self.StepPadToChannelStep(x, y)
                self.BtnMap[SClipsY + y][SClipsX + x] = self.GetStepPadColor(channel_index, step)

        self.BtnMap[0][1] = 0x00083F if self.StepOfs > 0 else 0x000108
        self.BtnMap[0][2] = 0x00083F if self.StepOfs < StepMaxSteps - StepStepsPerChannel else 0x000108
        self.BtnMap[1][0] = 0x083F08 if self.StepChannelOfs > 0 else 0x010801
        self.BtnMap[2][0] = 0x083F08 if self.StepChannelOfs < max(0, channels.channelCount() - StepChannelsPerPage) else 0x010801

        self.ApplyControllerModeButtonLeds()
        if Force:
            device.fullRefresh()
            self.SendControllerModeButtonLeds()
        else:
            self.FullRefresh_Btn()

    def MoveStepPage(self, Delta):
        self.StepOfs = utils.Limited(self.StepOfs + (Delta * StepStepsPerChannel), 0, StepMaxSteps - StepStepsPerChannel)
        self.UpdateStepSequencerView(True)
        self.FocusStepSequencerRect()

    def MoveStepChannelPage(self, Delta):
        self.StepChannelOfs = utils.Limited(self.StepChannelOfs + (Delta * StepChannelsPerPage), 0, max(0, channels.channelCount() - StepChannelsPerPage))
        self.UpdateStepSequencerView(True)
        self.FocusStepSequencerRect()

    def ToggleStepSequencerPad(self, x, y):
        channel_index, step = self.StepPadToChannelStep(x, y)
        if not utils.InterNoSwap(channel_index, 0, channels.channelCount() - 1):
            return
        channels.selectOneChannel(channel_index)
        if not channels.isGridBitAssigned(channel_index):
            self.UpdateStepSequencerView(False)
            return

        general.saveUndo('Launchpad Pro MK3: Step seq edit', midi.UF_PR)
        channels.setGridBit(channel_index, step, int(channels.getGridBit(channel_index, step) == 0))
        self.UpdateStepSequencerView(False)
        self.FocusStepSequencerRect()

    def HandleStepSequencerMidi(self, event):
        event.handled = True

        if event.midiId == midi.MIDI_NOTEOFF:
            event.data2 = 0

        if event.data2 == 0:
            return

        if self.IsPlayButton(event):
            self.TogglePlayback(event)
            return
        if event.data1 == 0x50:
            self.MoveStepChannelPage(-1)
            return
        if event.data1 == 0x46:
            self.MoveStepChannelPage(1)
            return
        if event.data1 == 0x5B:
            self.MoveStepPage(-1)
            return
        if event.data1 == 0x5C:
            self.MoveStepPage(1)
            return

        y = event.data1 // PadsStride
        x = event.data1 - y * PadsStride - ClipsX
        y = ClipsH - ClipsY - y
        if utils.InterNoSwap(x, 0, SClipsW - 1) and utils.InterNoSwap(y, 0, SClipsH - 1):
            self.ToggleStepSequencerPad(x, y)
            return

    def CheckSpecialSwitches(self):

        if (self.ArrowT[0] + self.ArrowT[1] + self.ArrowT[2] + self.ArrowT[3]) >= 0x7F * 4:
            self.BlockOfs = not self.BlockOfs
            self.SetOfs(0, 0)
            device.stopRepeatMidiEvent()

    def SetBtn(self, Index, Value):

        self.BtnT[Index] = Value

        v = BtnInfo[Index].Col[utils.Limited(Value, 0, 2)]
        if v != -1:
            y, x = BtnInfo[Index].GetYX()
            self.BtnMap[y][x] = v
            self.FullRefresh_Btn()

        if Index > Btn_Overview:
            if Index == Btn_Spare:
                if Value > 0:
                    utils.SwapInt(self.TrackOfs, self.TrackOfs_Spare)
                    utils.SwapInt(self.ClipOfs, self.ClipOfs_Spare)
                    self.SetOfs(self.TrackOfs, self.ClipOfs)

                self.SetBtn(Btn_Overview, Value)
        else:
            #overview
            self.OnUpdateLiveMode(playlist.trackCount())
            device.stopRepeatMidiEvent() #  in case arrows were held
            playlist.lockDisplayZone(0, Value > 0)
        
    def OnIdle(self):
        if not self.ControllerMode:
            return

        if self.IsStepSequencerMode():
            self.ApplyControllerModeButtonLeds()
            self.UpdateBlinking()
            return

        BlinkSpeed = 0x20

        if device.isAssigned():
            # beat cycle (smooth fade)
            if transport.isPlaying() != midi.PM_Playing:
                v2 = math.sin((time.time() % BlinkSpeed) * math.pi / BlinkSpeed)
            else:
                v2 = mixer.getSongTickPos(midi.ST_Beat)
                v2 = math.sin(v2 * (math.pi / 2))

            v3 = mixer.getSongTickPos(midi.ST_PGB)
            v3 = 1 - v3
            c = utils.FadeColor(0x003F30, 0x000138, round(v3 * v3 * 256))

            # activity meters
            if (self.ClipOfs == -1) & (self.BtnT[Btn_Overview] == 0):
                for y in range(0, SClipsH):
                    m = self.TrackOfs + y + 1
                    v3 = playlist.getTrackActivityLevelVis(m) * 2
                    for x in range(SClipsX, SClipsX + 2):
                        self.BtnMap[SClipsY + y][ x] = utils.FadeColor(0x3F303F, 0x000000, utils.Limited(round(v3 * 256), 0, 256))
                        v3 = v3 - 1

            if not self.NoFullRefresh:
                if self.BtnMapMode == 3:
                    self.FullRefresh_Btn()

                self.BlinkLight = round(v2 * v2 * 256)
                if (self.BtnMap[0][3] != c) | (self.BtnMap[0][PadsW - 1] != c):
                    y, x = BtnInfo[Btn_Play].GetYX()
                    self.BtnMap[y][x] = c
                    self.BtnMap[0][PadsW - 1] = c
                    self.ApplyControllerModeButtonLeds()
                    self.FullRefresh_Btn()
                else:
                    self.ApplyControllerModeButtonLeds()
                    self.UpdateBlinking()

    def OnRefresh(self, flags):
        if not self.ControllerMode:
            return

        if self.IsStepSequencerMode():
            if (flags & StepSequencerRefreshFlags) != 0:
                self.UpdateStepSequencerView(False)
            return

        if flags & midi.HW_Dirty_RemoteLinks != 0:
            if self.ClipOfs < -1:
                self.SetOfs(self.TrackOfs, self.ClipOfs)
            launchMapPages.updateMap(-1)

    def SwitchLedsOff(self):
        t = (0x030E02292000F0).to_bytes(7 + 3 * MaxPads, byteorder='little')
        s = bytearray(t)
        m = 7
        for y in range(0, PadsH):
            y2 = y * 10
            for x in range(0, PadsW):
                p = 90 - y2 + x
                ForbiddenPads = [0, 9, 90, 99] #corners
                if (not (p in ForbiddenPads)):
                    s[m] = 0
                    s[m + 1] = y2 + x
                    s[m + 2] = 0
                    m += 3
        s[m] = 0xF7
        s = s[: m + 1]
        device.midiOutSysex(bytes(s))

    def OnSysEx(self, event):
        print('onSysex', event.sysex, event.senderId)


    def OnInit(self):
        NameStr = 'Novation Launchpad Pro'

        for n in range(0, len(self.ColScaleT)):
            v = n / 255
            self.ColScaleT[n] = min(round(v * v * v * 255 * 0.9), 63)

        # init mapping
        launchMapPages.createOverlayMap(1, 8, LayW, LayH)

        for y in range(0, LayH):
            for x in range(0, LayW):
                launchMapPages.setMapItemTarget(-1, y * LayW + x, y * PadsStride + x + 1)

        if device.isAssigned():
            device.midiOutSysex(SysexIdentityRequest)
            device.midiOutSysex(SysexProgrammerModeOff)
            device.midiOutSysex(SysexDawModeOn)
            self.CurLayout = 0

        # load mapping
        launchMapPages.init(NameStr, LayW, LayH)

        self.Reset()
        device.createRefreshThread()
        self.ControllerMode = False

    def OnDeInit(self):

        device.destroyRefreshThread()
        self.Reset()

        if device.isAssigned():
            if self.CurLayout == 3:
                self.SwitchLedsOff()
            self.CurLayout = 0
            self.ControllerMode = False
            # set back to normal Launchpad modes
            device.midiOutSysex(SysexProgrammerModeOff)
            device.midiOutSysex(SysexDawModeOff)

    def FixColor(self, Color):

        r, g, b = utils.ColorToRGB(Color)
        r = self.ColScaleT[r]
        g = self.ColScaleT[g]
        b = self.ColScaleT[b]
        #r = round((r / 256) * 127)
        #g = round((g / 256) * 127)
        #b = round((b / 256) * 127)
        return utils.RGBToColor(r, g, b)

    def OnUpdateLiveMode(self, LastTrackNum):
        if not self.ControllerMode:
            return

        if self.IsStepSequencerMode():
            self.UpdateStepSequencerView(False)
            return

        FirstTrackNum = 1
        StatusColT = [0, 0, 0, 0]
        LoopBtnColT = (0x3F0000, 0x002400, 0x000110, 0x000228, 0x00033F, 0x180018, 0x3F003F)
        TrigColT = (0x001000, 0x280800, 0x200018, 0x202020)
        SnapColT = (0x000420, 0x180000, 0x3F0000, 0x300808, 0x201010, 0x101818, 0x002020)
        OverviewColT = ((0x000000, 0x200000, 0x4200000), (0x000110, 0x00063F, 0x400063F))
        OnLight = 0x48
        OffLight = -0x60 #-0x1A
        R = utils.TRect(0, 0, 0, 0)
        R2 = utils.TRect(0, 0, 0, 0)

        if device.isAssigned():
            if (self.ClipOfs >= -1) | (self.BtnT[Btn_Overview] > 0):
                if self.BtnT[Btn_Overview] > 0:
                    # overview
                    R2.Left = self.ClipOfs;
                    if R2.Left < 0:
                        R2.Left -= 128
                    R2.Right = R2.Left + SClipsW - 1
                    R2.Top = 1 + self.TrackOfs
                    R2.Bottom = R2.Top + SClipsH - 1
                    for y in range(0, OverH + 1):
                        for x in range(0, OverW + 1):
                            v = OverviewColT[0][0]
                            if (x < OverW) & (y < OverH):
                                R.Left = x * SClipsW
                                R.Right = R.Left + SClipsW - 1
                                R.Top = 1 + y * SClipsH
                                R.Bottom = R.Top + SClipsH - 1
                                o = patterns.getBlockSetStatus(R.Left, R.Top, R.Right, R.Bottom)
                                v = OverviewColT[utils.RectOverlapEqual(R, R2)][o]
                            elif (x == SClipsW) & (y < SClipsH):
                                v = OverviewColT[y == (-1 - self.ClipOfs)][int(y <= launchMapPages.length())]
                            elif (y == SClipsH) & (x < SClipsW):
                                v = OverviewColT[x + 8 == (-1 - self.ClipOfs)][int(x + 8 <= launchMapPages.length())]
                            self.BtnMap[OverY + y][OverX + x] = v
                else:
                    # scene buttons
                    y = SClipsH + 1
                    for x in range(0, ClipsW):
                        v = launchMapPages.getMapItemColor(-1,(y - 1) * ClipsW + x)
                        if v < 0:
                            v = 0x010000
                        else:
                            v = self.FixColor(v)
                        self.BtnMap[SClipsY + y - 1][SClipsX + x] = v


                    Ofs = self.TrackOfs
                    for y in range(max(FirstTrackNum - Ofs, 1), min(LastTrackNum - Ofs, SClipsH) + 1):  #todo
                        StatusColT[2] = TrigColT[playlist.getLiveTriggerMode(y + Ofs)]

                        if self.ClipOfs >= 0:
                            # clips
                            for x in range(0, ClipsW):
                                v = launchMapPages.getMapItemColor(-1, (y - 1) * ClipsW + x)
                                if v < 0:
                                    if x < SClipsW:
                                        m = self.ClipOfs + x
                                        o = playlist.getLiveBlockStatus(y + Ofs, m, midi.LB_Status_Simple)
                                        if o == 0:
                                            v = 0
                                        else:
                                            v = playlist.getLiveBlockColor(y + Ofs, m)
                                            if o > 1:
                                                v = utils.LightenColor(v, OnLight)
                                            else:
                                                v = utils.LightenColor(v, OffLight)

                                            v = self.FixColor(v)
                                        if o == 2:
                                            v = v | LPBlink1
                                    else:
                                        o = playlist.getLiveStatus(y + Ofs, midi.LB_Status_Simple)
                                        if o == 0:
                                            v = 0
                                        else:
                                            v = playlist.getLiveBlockColor(y + Ofs, -1)
                                            if o == 2:
                                                v = utils.LightenColor(v, 0x20)
                                            elif o > 1:
                                                v = utils.LightenColor(v, OnLight)
                                            else:
                                                v = utils.LightenColor(v, OffLight)

                                            v = self.FixColor(v)
                                else:
                                    v = self.FixColor(v)
                                self.BtnMap[SClipsY + y - 1][SClipsX + x] = v
                        else:
                            # track properties
                            v = 0
                            for x in range(0, ClipsW):
                                if (x == 2) | (x == 3):
                                    v = SnapColT[min(playlist.getLivePosSnap(y + Ofs), len(SnapColT))-1]
                                elif (x == 4) | (x == 5):
                                    v = SnapColT[min(playlist.getLiveTrigSnap(y + Ofs), len(SnapColT))-1]
                                elif (x == 6) | (x == 7):
                                    v = LoopBtnColT[playlist.getLiveLoopMode(y + Ofs)]
                                elif x == 8:
                                    v = StatusColT[2]
                                else:
                                    continue
                                self.BtnMap[SClipsY + y - 1][SClipsX + x] = v
                                

                            self.NoFullRefresh = True
                            self.OnIdle() # activity meters
                            self.NoFullRefresh = False
            else:
                #custom pages
                for y in range(0, LayH):
                    for x in range(0, LayW):
                        self.BtnMap[LayY + y][LayX + x] = self.FixColor(launchMapPages.getMapItemColor(-self.ClipOfs - 2, y * LayW + x))

            self.ApplyControllerModeButtonLeds()
            self.FullRefresh_Btn()

LaunchPadPro = TLaunchPadPro()

def OnInit():
    LaunchPadPro.OnInit()

def OnDeInit():
    LaunchPadPro.OnDeInit()

def OnMidiMsg(event):
    LaunchPadPro.OnMidiMsg(event)

def OnMidiOutMsg(event):
    LaunchPadPro.OnMidiOutMsg(event)

def OnDoFullRefresh():
    LaunchPadPro.OnDoFullRefresh()

def OnDisplayZone():
    LaunchPadPro.OnDisplayZone()

def OnIdle():
    LaunchPadPro.OnIdle()

def OnRefresh(Flags):
    LaunchPadPro.OnRefresh(Flags)

def OnUpdateLiveMode(LastTrackNum):
    LaunchPadPro.OnUpdateLiveMode(LastTrackNum)

def OnMidiIn(event):
    LaunchPadPro.OnMidiIn(event)

def OnSysEx(event):
    LaunchPadPro.OnSysEx(event)
