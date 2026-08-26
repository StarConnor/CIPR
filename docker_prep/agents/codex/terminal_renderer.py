import json
import base64
import io

# Libraries for Terminal Emulation and Image Generation
import pyte
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
FONT_SIZE = 14
# Attempt to load a monospace font, fallback to default if not found
try:
    # Common path in linux containers
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", FONT_SIZE)
except OSError:
    try:
        FONT = ImageFont.truetype("arial.ttf", FONT_SIZE)
    except OSError:
        FONT = ImageFont.load_default()

class TerminalRenderer:
    def __init__(self, columns=120, lines=30):
        self.columns = columns
        self.lines = lines
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.ByteStream(self.screen)
        
        self.COLOR_MAP = {
            'black': (0, 0, 0), 'red': (205, 49, 49), 'green': (13, 188, 121),
            'brown': (229, 229, 16), 'blue': (36, 114, 200), 'magenta': (188, 63, 188),
            'cyan': (17, 168, 205), 'white': (229, 229, 229), 'default': (204, 204, 204),
        }
        
        bbox = FONT.getbbox("M")
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        # Fallback if font load failed and w is 0
        self.char_width = w if w > 0 else 7
        self.char_height = h + 4 if h > 0 else 14
        
        self.img_width = self.columns * self.char_width
        self.img_height = self.lines * self.char_height

    def feed(self, data):
        self.stream.feed(data)

    def get_screen_text(self):
        """Returns the full screen text joined by newlines."""
        return "\n".join(line.rstrip() for line in self.screen.display)

    def get_screen_lines(self):
        return [line.rstrip() for line in self.screen.display]

    def _resolve_color(self, color_val):
        # 1. Default/None
        if color_val == 'default' or not color_val:
            return (200, 200, 200) # Light grey text

        # 2. Named Colors (Basic 16)
        if color_val in self.COLOR_MAP:
            return self.COLOR_MAP[color_val]

        # 3. Hex Strings (TrueColor)
        if isinstance(color_val, str) and len(color_val) == 6:
            try:
                return tuple(int(color_val[i:i+2], 16) for i in (0, 2, 4))
            except ValueError:
                pass

        # 4. Integer (256-Color Mode)
        if isinstance(color_val, int):
            # Basic algorithm to convert 256-color code to RGB
            if 0 <= color_val <= 15:
                # Basic colors (mapped loosely to standard)
                # You could add a lookup for 0-15 if specific mapping needed
                return (200, 200, 200) 
            elif 16 <= color_val <= 231:
                # 6x6x6 Color Cube
                color_val -= 16
                b = color_val % 6
                color_val //= 6
                g = color_val % 6
                r = color_val // 6
                return (r * 51, g * 51, b * 51)
            elif 232 <= color_val <= 255:
                # Grayscale
                gray = 8 + (color_val - 232) * 10
                return (gray, gray, gray)

        return (200, 200, 200)

    def render_to_base64(self):
        image = Image.new('RGB', (self.img_width, self.img_height), color=(30, 30, 30))
        draw = ImageDraw.Draw(image)
        
        for y in range(self.lines):
            line_data = self.screen.buffer[y]
            for x in range(self.columns):
                char_data = line_data[x]
                char = char_data.data
                if not char or char == ' ':
                    continue
                fill = self._resolve_color(char_data.fg)
                draw.text((x * self.char_width, y * self.char_height), char, font=FONT, fill=fill)

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

def sse_message(event_type, data_dict):
    payload = {
        'type': event_type, 
        'data': data_dict if event_type != 'complete' else None,
        'outputs': data_dict if event_type == 'complete' else None
    }
    return f"event: message\ndata: {json.dumps(payload)}\n\n"