"""Single contract for persisted and live subtitle appearance."""
import re
import math


def valid_offset(value):
    # Tenths retain the exact position of legacy integer-pixel preferences.
    return (type(value) in (int,float) and math.isfinite(value) and -40<=value<=40
            and math.isclose(value*10,round(value*10),abs_tol=1e-8))

DEFAULT_FONT_SIZE=28
BACKGROUND_RGB=(3,7,15)
STYLE_DEFAULTS = dict(position='above_region', color='#f6f8ff', opacity=84, stroke=2,
                      enabled=True, y_offset=0)
STYLE_RULES = {
    'position': lambda value: isinstance(value, str) and value in ('auto','above_region','top','bottom'),
    'color': lambda value: isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value) is not None,
    'opacity': lambda value: type(value) is int and 0 <= value <= 100,
    'stroke': lambda value: type(value) is int and 0 <= value <= 5,
    'enabled': lambda value: type(value) is bool,
    'y_offset': valid_offset,
}
HUD_LAYOUT_DEFAULTS=dict(x_offset=0,y_offset=0,scale=100)
HUD_LAYOUT_RULES={
    'x_offset':lambda value:type(value) is int and -40<=value<=40,
    'y_offset':lambda value:type(value) is int and -40<=value<=40,
    'scale':lambda value:type(value) is int and 70<=value<=150,
}


def validate_style(values):
    for key, value in values.items():
        if key not in STYLE_RULES or not STYLE_RULES[key](value):
            raise ValueError('Geçersiz altyazı görünümü: ' + key)
