import asyncio
from io import StringIO

class DiscordIO(StringIO):
    encoding = "utf-8"

    def __init__(self, message, **kwargs):
        super().__init__(newline="", **kwargs)
        self.message = message
        self._prev_content = ""

    def print(self, line):
        self.seek(0)
        self.write(line)
        self.flush()

    def write(self, line):
        cursor = 0
        output = self.getvalue()
        for c in line.replace("\x1b[A", "\x1b"):
            if c == "\r":
                cursor = output.rfind('\n', 0, cursor) + 1
                continue
            if c == "\x1b":
                line_start = output.rfind("\n", 0, cursor) + 1
                col = cursor - line_start
                prev_line_start = output.rfind("\n", 0, line_start) + 1
                cursor = min(prev_line_start + col, line_start - 2)
                continue
            space = 0 if c in ["\n"] else 1
            output = (output[:cursor] or "") + c + output[cursor + space:]
            cursor += 1

        self.seek(0)
        super().write(output)

    def flush(self):
        content = self.getvalue()
        if content != self._prev_content:
            asyncio.ensure_future(self.message.edit(content=content))
            self._prev_content = content
        super().flush()
