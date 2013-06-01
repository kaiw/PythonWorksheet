# PythonWorksheet
# A Sublime Text 2 command to provide a simple Python worksheet facility
# Copyright(C) 2013 Kai Willadsen, kai.willadsen@gmail.com
#
# Inspired by Reinteract and ScalaWorksheet

import code
import contextlib
import sys
import StringIO

import sublime
import sublime_plugin


OUTPUT_TAG = "worksheet-output"


@contextlib.contextmanager
def std_redirected(out_stream, err_stream):
    stdout, sys.stdout = sys.stdout, out_stream
    stderr, sys.stderr = sys.stderr, err_stream
    try:
        yield
    finally:
        sys.stdout = stdout
        sys.stderr = stderr


class ShowPythonWorksheetCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        view = self.view.window().new_file()
        view.set_syntax_file('Packages/Python/Python.tmLanguage')
        view.set_scratch(True)
        view.set_read_only(False)


class RedirectedConsole(code.InteractiveConsole):

    def __init__(self):
        code.InteractiveConsole.__init__(self)
        self.output_stream = StringIO.StringIO()
        self.error_stream = StringIO.StringIO()

    def push(self, line):
        with std_redirected(self.output_stream, self.error_stream):
            return code.InteractiveConsole.push(self, line)

    def get_output(self):
        output = self.output_stream.getvalue()
        error = self.error_stream.getvalue()
        self.output_stream = StringIO.StringIO()
        self.error_stream = StringIO.StringIO()
        return output, error


class RunPythonWorksheetCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        if not self.compile_check(self.view):
            return
        self.execute_sheet(self.view, edit)

    def compile_check(self, view):
        if not view.size():
            return True
        lines = view.split_by_newlines(sublime.Region(0, view.size()))
        text = "\n".join([view.substr(region) for region in lines]) + "\n"
        try:
            # FIXME: compile_command seems extremely bodgy; as long as there
            # is at least one valid command before it hits invalid input,
            # it will return a code object and pretend that everything is
            # just peachy-keen.
            compiled = code.compile_command(text)
            assert compiled is not None, "Input is incomplete"
        # TODO: These are different errors; we should handle them better
        except (AssertionError, SyntaxError, OverflowError, ValueError) as e:
            sublime.error_message("Python Worksheet error:\n   " + str(e))
        else:
            return True
        return False

    def execute_sheet(self, view, edit):
        view.run_command("clear_python_worksheet")

        console = RedirectedConsole()
        outputs = []
        point = 0
        line = view.full_line(point)
        while line:
            line_contents = view.substr(line)
            point = int(line.end())
            old_line, line = line, view.full_line(point)
            if line == old_line:
                break
            print repr(line_contents)

            if console.push(line_contents.rstrip('\r\n')):
                continue

            out, err = console.get_output()

            if out:
                offset = self.view.insert(edit, point, out)
                start, point = point, point + offset
                outputs.append(sublime.Region(start, point))
                line = view.full_line(point)

            if err:
                offset = self.view.insert(edit, point, err)
                start, point = point, point + offset
                outputs.append(sublime.Region(start, point))
                line = view.full_line(point)

        # TODO: Have a separate tag for errors with styling, etc.
        view.add_regions(OUTPUT_TAG, outputs, "mark", "dot",
                         sublime.DRAW_OUTLINED | sublime.PERSISTENT)
        view.sel().add(sublime.Region(point))


class ClearPythonWorksheetCommand(sublime_plugin.TextCommand):

    def run(self, edit):
        regions = self.view.get_regions(OUTPUT_TAG)
        if not regions:
            return

        current_selection = self.view.sel()
        print current_selection
        self.view.sel().clear()
        for r in regions:
            self.view.sel().add(r)
        self.view.run_command("add_to_kill_ring", {"forward": False})
        self.view.run_command("left_delete")
        self.view.erase_regions(OUTPUT_TAG)
        self.view.sel().clear()
        print current_selection
        self.view.sel().add_all(current_selection)
