#!/usr/bin/env python3
"""Type text into the Grok TUI window via X11 XTEST.

Usage: grok_type.py <window_id_hex> <text...>
Focuses the window, types the text, presses Enter.
"""
import sys, time, subprocess
from Xlib import display, X, XK
from Xlib.ext import xtest

WIN = sys.argv[1]
TEXT = " ".join(sys.argv[2:])

d = display.Display(":0")

# Focus the target window
subprocess.run(["wmctrl", "-i", "-a", WIN], check=True, env={"DISPLAY": ":0"})
time.sleep(0.6)

# Build reverse keymap: keysym -> (keycode, shift-level)
keymap = {}
for kc in range(d.display.info.min_keycode,
                d.display.info.max_keycode + 1):
    syms = d.get_keyboard_mapping(kc, 1)[0]
    for idx, ks in enumerate(syms[:4]):
        if ks != 0 and ks not in keymap:
            keymap[ks] = (kc, idx)

# find a spare keycode for remapping unknown chars
spare = None
for kc in range(d.display.info.max_keycode, d.display.info.min_keycode, -1):
    syms = d.get_keyboard_mapping(kc, 1)[0]
    if all(s == 0 for s in syms):
        spare = kc
        break

SHIFT_KC = keymap[XK.string_to_keysym("Shift_L")][0]
ALTGR_KC = None
ag = XK.string_to_keysym("ISO_Level3_Shift")
if ag in keymap:
    ALTGR_KC = keymap[ag][0]

def press(kc):
    xtest.fake_input(d, X.KeyPress, kc)
    d.sync()
    time.sleep(0.003)
    xtest.fake_input(d, X.KeyRelease, kc)
    d.sync()
    time.sleep(0.003)

def remap_and_press(ks):
    if not spare:
        print(f"skip char, no mapping: {hex(ks)}", file=sys.stderr)
        return
    d.change_keyboard_mapping(spare, [(ks, 0, 0, 0)])
    d.sync()
    time.sleep(0.02)
    press(spare)
    d.change_keyboard_mapping(spare, [(0, 0, 0, 0)])
    d.sync()
    time.sleep(0.02)

def type_keysym(ks):
    if ks in keymap:
        kc, idx = keymap[ks]
        if idx == 0:
            press(kc)
        elif idx == 1:
            xtest.fake_input(d, X.KeyPress, SHIFT_KC); d.sync()
            time.sleep(0.003)
            press(kc)
            xtest.fake_input(d, X.KeyRelease, SHIFT_KC); d.sync()
            time.sleep(0.003)
        elif idx == 2 and ALTGR_KC:
            xtest.fake_input(d, X.KeyPress, ALTGR_KC); d.sync()
            time.sleep(0.003)
            press(kc)
            xtest.fake_input(d, X.KeyRelease, ALTGR_KC); d.sync()
            time.sleep(0.003)
        elif idx == 3 and ALTGR_KC:
            xtest.fake_input(d, X.KeyPress, SHIFT_KC); d.sync()
            xtest.fake_input(d, X.KeyPress, ALTGR_KC); d.sync()
            press(kc)
            xtest.fake_input(d, X.KeyRelease, ALTGR_KC); d.sync()
            xtest.fake_input(d, X.KeyRelease, SHIFT_KC); d.sync()
        else:
            remap_and_press(ks)
    else:
        remap_and_press(ks)

def char_to_keysym(ch):
    if ch == "\n":
        return XK.string_to_keysym("Return")
    if ch == "\t":
        return XK.string_to_keysym("Tab")
    if ch == " ":
        return XK.string_to_keysym("space")
    ks = XK.string_to_keysym(ch)
    if ks == 0:
        ks = 0x1000000 + ord(ch)  # unicode keysym fallback
    return ks

for ch in TEXT:
    type_keysym(char_to_keysym(ch))

time.sleep(0.3)
type_keysym(XK.string_to_keysym("Return"))
d.sync()
print(f"typed {len(TEXT)} chars + Enter into {WIN}")
