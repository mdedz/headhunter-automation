import sys
import argparse

class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"


def supports_color():
    #if cli supports colors
    return sys.stdout.isatty()

def paint_text(color: str, text: str) -> str:
    """If cli supports colors, then paint the string otherwise return initial one"""
    if supports_color():
        return f"{color}{text}{Color.RESET}"
    else:
        return text

class CustomHelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, width=150, max_help_position=50)
        
    def add_usage(self, usage, actions, groups, prefix=None):
        """Hardcoded usage line."""

        text = "".join((
            paint_text(Color.CYAN, "Usage: "),
            paint_text(Color.GREEN, "headhunter-automation "),
            paint_text(Color.MAGENTA, "[OPERATION] "),
            paint_text(Color.MAGENTA, "[OPERATION_OPTIONS] "),
            paint_text(Color.YELLOW, "[GLOBAL_OPTIONS] "),
            "\n",
            f"If you want to print help for operation then: ",
            paint_text(Color.CYAN, "headhunter-automation [OPERATION] --help"),
            "\n",
            "Help structure is: ",
            paint_text(Color.CYAN, "[ARGUMENT] [DESCRIPTION]([DEFAULT_VALUE])"),
            "\n"
        ))

        self._add_item(lambda: text, [])

    def _get_help_string(self, action):
        """Print default value for args"""
        help_text = action.help or ""
        if action.default is not argparse.SUPPRESS and action.default is not None:
            help_text += f"({paint_text(Color.CYAN, action.default)})"
        return help_text

    def start_section(self, heading):
        if heading:
            heading = paint_text(Color.CYAN, heading.capitalize())
        super().start_section(heading)

    def _format_action_invocation(self, action):
        """Format options"""
        if not action.option_strings:
            return super()._format_action_invocation(action)

        opts = ", ".join(paint_text(Color.GREEN, opt) for opt in action.option_strings)

        if action.type:
            _type_name = getattr(action.type, "__name__", str(action.type))
            type_name = paint_text(Color.MAGENTA, _type_name)
        else:
            type_name = None

        if action.metavar:
            _mv: str | tuple[str, ...] = action.metavar
            if type(_mv) is str: mv = paint_text(Color.YELLOW, _mv)
            else: mv = paint_text(Color.YELLOW, " ".join(_mv))
        else:
            mv = None

        if type_name and mv:
            return f"{opts} {type_name}:{mv}"
        if mv:
            return f"{opts} {mv}"
        if type_name:
            return f"{opts} {type_name}"

        return opts
    
    def _format_action(self, action):
        """Format positional arguments (operations)"""
        if isinstance(action, argparse._SubParsersAction):
            parts = []

            for choice, _ in action.choices.items():
                help_text = action._choices_actions[[a.dest for a in action._choices_actions].index(choice)].help

                choice_colored = paint_text(Color.GREEN, choice)
                help_colored = help_text or ""

                indent = " " * self._current_indent

                parts.append(f"{indent}{choice_colored:<20} {help_colored}")

            return "\n".join(parts) + "\n"

        return super()._format_action(action)
    
    