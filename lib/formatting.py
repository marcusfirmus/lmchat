# -*- coding: utf-8 -*-
#
# formatting.py - Text formatting utilities for terminal output
# Copyright (c) 2026 Marcus Firmus. Licensed under the MIT License.
#

""" Module for formatting strings. Universal module, independent of content and domain of application. """

import rich, rich.console, rich.markdown
import io

from rich.text import Text

def markdown( text, line_length=None, left_padding=None ):
    sio = io.StringIO()
    cons = rich.console.Console( file=sio, 
                                 color_system="standard",
                                 width=line_length )
    md = rich.markdown.Markdown( text )

    if left_padding:
        cons.print( rich.padding.Padding(md, (0, 0, 0, left_padding)) )
    else:
        cons.print( md )

    sio.flush()
    buf = sio.getvalue()

    sio.close()
    return buf

def richprint( text, line_length=None, left_padding=None, markup=True, end=None ):
    sio = io.StringIO()
    cons = rich.console.Console( file=sio, 
                                 color_system="standard",
                                 width=line_length )

    data = text if markup else Text(text)

    if left_padding:
        cons.print( rich.padding.Padding(data, (0, 0, 0, left_padding)), end=end )
    else:
        cons.print( data, end=end )

    sio.flush()
    buf = sio.getvalue()
    sio.close()
    return buf

class TextFormatter:
    """ Class for formatting strings by adding indentation and line breaking.
        The result is printed using the given `output_string` and `output_flush` functions.
    """    
    def __init__(self, padding, line_length, output_string, output_flush):
        # If padding is an integer, convert it to the appropriate number of spaces.
        # If it's already a string (e.g., "> "), use it directly.
        if isinstance(padding, int):
            self.padding_str = " " * padding
        else:
            self.padding_str = str(padding)

        self.line_length = line_length
        self.output_string = output_string
        self.output_flush = output_flush

        # Internal state
        self.current_word = ""          # Currently built word
        self.current_line_words = []    # Words accepted to the current line

    def _flush_line(self):
        """Flushes the contents of the line buffer to the physical output."""
        if self.current_line_words:
            # Joins the words with a single space and adds padding at the beginning and a new line at the end
            line = self.padding_str + " ".join(self.current_line_words) + "\n"
            self.output_string(line)
            self.output_flush()
            self.current_line_words = []

    def _handle_word_boundary(self):
        """Helper method called when a word ends."""
        if not self.current_word:
            return

        # Calculate the length of the line if we were to add the current word to it:
        # padding + length of existing words + spaces between them + new word
        pad_len = len(self.padding_str)
        existing_words_len = sum(len(w) for w in self.current_line_words)
        spaces_len = len(self.current_line_words) # number of spaces between words
        
        projected_length = pad_len + existing_words_len + spaces_len + len(self.current_word)

        if not self.current_line_words:
            # If the line is empty, we must add the word (even if it exceeds line_length)
            self.current_line_words.append(self.current_word)
        elif projected_length <= self.line_length:
            # The word fits in the current line
            self.current_line_words.append(self.current_word)
        else:
            # The word does not fit in the current line – push the current line and start a new one with this word
            self._flush_line()
            self.current_line_words.append(self.current_word)

        self.current_word = ""

    def put(self, ch):
        """Virtually prints one character.  At appropriate times, flushes data to the output."""
        if ch == '\n':
            # Encountered a forced line end
            if self.current_word:
                self._handle_word_boundary()
                self._flush_line()
            elif self.current_line_words:
                self._flush_line()
            else:
                # Empty line (e.g., double enter) - keep it
                self.output_string(self.padding_str + "\n")
                self.output_flush()
        elif ch.isspace():
            # Space, tab, etc. indicate end of word
            self._handle_word_boundary()
        else:
            # Regular character - build the word
            self.current_word += ch

    def output(self, s: str):
        """Helper method for sending entire strings"""
        for c in s:
            self.put(c)

    def flush(self):
        """Final output of the buffer if anything is in it."""
        if self.current_word:
            self._handle_word_boundary()
        if self.current_line_words:
            self._flush_line()
