# -*- coding: utf-8 -*-
"""Macro recording and playback utilities."""

from collections import defaultdict

from qtpy.QtCore import QObject
from qtpy.QtGui import QKeyEvent

from .state import KeyInfo


class MacroManager:
    """Store and play back recorded macros."""

    def __init__(self):
        #: Mapping of register names to recorded :class:`KeyInfo` instances
        self.registers = defaultdict(list)
        #: Whether a macro is currently being recorded
        self.is_recording = False
        #: Register being used for recording
        self.reg_name_for_record = ""
        #: Editor currently connected to receive key events during recording
        self.editor_connected = None
        #: Register to execute
        self.reg_name_for_execute = ""
        #: Number of times to execute the macro
        self.num_execute = 0

    def set_info_for_execute(self, register, count):
        """Configure macro execution.

        Args:
            register: Name of the register to execute.
            count: Number of times to repeat execution.
        """
        self.reg_name_for_execute = register
        self.num_execute = count

    def start_record(self, register):
        """Begin recording keystrokes.

        Args:
            register: Name of the register to store the recording in.
        """
        self.reg_name_for_record = register
        self.is_recording = True

        if register.lower() == register:
            self.registers[register] = list()

    def stop_record(self):
        """Finish recording and clean up."""
        # Remove the trailing ``q`` when finishing recording
        self.remove_last_key("q")
        self.reg_name_for_record = ""
        self.is_recording = False

    def remove_last_key(self, text):
        """Remove a trailing key from the recording if it matches ``text``.

        Args:
            text: Character to remove from the end of the recorded sequence.
        """
        key_list = self.registers[self.reg_name_for_record]
        if key_list:
            last_key = key_list[-1]
            if last_key.text == text:
                self.registers[self.reg_name_for_record] = key_list[:-1]

    def add_vim_keyevent(self, event: QKeyEvent):
        """Record a key event coming from the Vim command line."""
        if self.is_recording:
            self.registers[self.reg_name_for_record].append(
                KeyInfo(event.key(), event.text(), event.modifiers(), 0)
            )

    def add_editor_keyevent(self, event: QKeyEvent):
        """Record a key event originating in the editor."""
        self.registers[self.reg_name_for_record].append(
            KeyInfo(event.key(), event.text(), event.modifiers(), 1)
        )

    def connect_to_editor(self, editor: QObject, slot):
        """Start receiving key events from ``editor``.

        Args:
            editor: Editor emitting ``sig_key_pressed``.
            slot: Slot connected to the editor signal.
        """
        self.editor_connected = editor
        editor.sig_key_pressed.connect(slot)

    def disconnect_from_editor(self, slot):
        """Stop receiving key events from the previously connected editor."""
        editor = self.editor_connected
        if editor:
            try:
                editor.sig_key_pressed.disconnect(slot)
            except (TypeError, RuntimeError):
                # Already disconnected or editor deleted
                pass
        self.editor_connected = None




