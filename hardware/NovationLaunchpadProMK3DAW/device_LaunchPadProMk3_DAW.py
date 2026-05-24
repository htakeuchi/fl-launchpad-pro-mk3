# name=NovationLaunchpadProMK3DAW
# url=
# supportedDevices=LPProMK3 DAW

import device
import midi

SessionButton = 0x5D

SysexDawModeOn = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x10, 0x01, 0xF7])
SysexDawModeOff = bytes([0xF0, 0x00, 0x20, 0x29, 0x02, 0x0E, 0x10, 0x00, 0xF7])

BridgeDispatchStatus = 0xF4
BridgeDispatchHeader = [0xF0, 0x00, 0x20, 0x29, 0x7D]
BridgeCommandToggleControllerMode = 0x01
BridgeCommandEnterControllerMode = 0x02

LayoutSession = 0


def DispatchToMidiScript(command):
    msg = bytearray(BridgeDispatchHeader + [command, 0xF7])
    device.dispatch(-1, BridgeDispatchStatus, bytes(msg))


def IsSessionButton(event):
    return (event.midiId in [midi.MIDI_NOTEON, midi.MIDI_NOTEOFF, midi.MIDI_CONTROLCHANGE]) and (event.data1 == SessionButton)


def IsLayoutChange(event, layout):
    return (
        event.status == midi.MIDI_BEGINSYSEX
        and len(event.sysex) == 11
        and event.sysex[0] == 0xF0
        and event.sysex[1] == 0x00
        and event.sysex[2] == 0x20
        and event.sysex[3] == 0x29
        and event.sysex[4] == 0x02
        and event.sysex[5] == 0x0E
        and event.sysex[6] == 0x00
        and event.sysex[7] == layout
    )


def OnInit():
    if device.isAssigned():
        print('NovationLaunchpadProMK3DAW: DAW mode on')
        device.midiOutSysex(SysexDawModeOn)


def OnDeInit():
    if device.isAssigned():
        print('NovationLaunchpadProMK3DAW: DAW mode off')
        device.midiOutSysex(SysexDawModeOff)


def OnMidiMsg(event):
    if IsSessionButton(event):
        event.handled = True
        if event.data2 > 0:
            DispatchToMidiScript(BridgeCommandToggleControllerMode)
        return

    event.handled = False


def OnMidiIn(event):
    if IsLayoutChange(event, LayoutSession):
        event.handled = True
        DispatchToMidiScript(BridgeCommandEnterControllerMode)
        return

    event.handled = False


def OnSysEx(event):
    if IsLayoutChange(event, LayoutSession):
        DispatchToMidiScript(BridgeCommandEnterControllerMode)
