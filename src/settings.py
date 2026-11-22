import json
import os
import shutil
import hashlib
from pathlib import Path
from types import MappingProxyType
from appearance import STYLE_RULES,HUD_LAYOUT_RULES
from regions import read_saved_areas
from subtitle_ocr import valid_quality,valid_interval
from samsung_protocol import valid_saved_host
from hotkeys import ACTIONS as HOTKEY_ACTIONS,valid_hotkey


class Settings:
    MAX_BYTES = 1024 * 1024

    @classmethod
    def read(cls, path):
        with path.open('rb') as source:
            return source.read(cls.MAX_BYTES + 1)

    def __init__(self, path=None):
        self.path = Path(path) if path else Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'AltyaziAtolyesi' / 'settings.json'
        self.values = {}
        self.warnings = []
        self.loaded_bytes = self.read(self.path) if self.path.is_file() else None
        self.primary_valid = True
        if self.loaded_bytes is not None:
            value = self.parse(self.loaded_bytes)
            if value is None:
                self.primary_valid = False
                backup = self.path.with_suffix('.json.bak')
                value = self.parse(self.read(backup)) if backup.is_file() else None
                self.warnings.append('Ayar dosyası okunamadı; geçerli yedek veya varsayılanlar kullanılıyor. Eski dosya korunacak.')
            if value is not None:
                self.values, invalid = self._validate_scalars(value)
                if 'overlay_y_offset' in self.values and 'overlay_offset_version' not in value:
                    legacy=self.values['overlay_y_offset']
                    if type(legacy) is int:
                        self.values['overlay_y_offset']=-legacy/10
                        self.values['overlay_offset_version']=1
                    else:
                        del self.values['overlay_y_offset']
                        invalid.append('overlay_y_offset')
                elif 'overlay_offset_version' in value and 'overlay_offset_version' not in self.values:
                    self.values.pop('overlay_y_offset',None)
                if invalid:
                    self.primary_valid = False
                    self.warnings.append('Geçersiz ayarlar varsayılanlara döndürüldü: ' + ', '.join(invalid))
        areas,self.region_issues=read_saved_areas(self.values.get('regions'))
        self.regions=MappingProxyType(areas)
        if self.region_issues:
            self.primary_valid=False
            self.warnings.extend(self.region_issues)

    @staticmethod
    def parse(data):
        if len(data) > 1024 * 1024:
            return None
        try:
            value = json.loads(data.decode('utf-8-sig'))
        except (ValueError, UnicodeDecodeError, RecursionError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _validate_scalars(value):
        rules = {
            'font_size': lambda v: type(v) is int and 14 <= v <= 64,
            'video_band': lambda v: type(v) is int and 15 <= v <= 50,
            'mode': lambda v: isinstance(v, str) and v in ('screen', 'movie'),
            'selection_scope': lambda v: isinstance(v, str) and v in ('subtitle', 'video'),
            'fallback': lambda v: type(v) is bool,
            'ui_sounds': lambda v: type(v) is bool,
            'reduced_motion': lambda v: type(v) is bool,
            'ignore_speaker':lambda v:type(v) is bool,
            'dialogue': lambda v: type(v) is bool,
            'hud_enabled':lambda v:type(v) is bool,
            'ocr_quality':valid_quality,
            'ocr_interval':valid_interval,
            'caption_mode': lambda v: isinstance(v,str) and v in ('single','dialogue'),
            'profile': lambda v: isinstance(v, str),
            'samsung_host':valid_saved_host,
            'overlay_offset_version': lambda v: type(v) is int and v==1,
        }
        rules.update({'overlay_' + key: rule for key, rule in STYLE_RULES.items()})
        rules.update({'hud_'+key:rule for key,rule in HUD_LAYOUT_RULES.items()})
        rules['hotkeys_enabled']=lambda v:type(v) is bool
        rules['prefer_cpu']=lambda v:type(v) is bool
        rules['low_priority']=lambda v:type(v) is bool
        rules.update({'hotkey_'+name:valid_hotkey for name,_,_ in HOTKEY_ACTIONS})
        cleaned = dict(value)
        invalid = []
        for key, rule in rules.items():
            if key in value and not rule(value[key]):
                del cleaned[key]
                invalid.append(key)
        return cleaned, invalid

    def save(self, **values):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if 'overlay_y_offset' in values:
            values.setdefault('overlay_offset_version',1)
        updated = {**self.values, **values}
        updated, invalid = self._validate_scalars(updated)
        if invalid:
            raise ValueError('Geçersiz ayarlar: ' + ', '.join(invalid))
        current = self.read(self.path) if self.path.exists() else None
        if current is not None and len(current) > self.MAX_BYTES:
            raise OSError('Ayar dosyası 1 MiB sınırını aşıyor; dosya değiştirilmedi.')
        if current != self.loaded_bytes:
            raise OSError('Ayar dosyası başka bir işlemde değişti. Uygulamayı yeniden açın.')
        encoded = bytearray()
        try:
            for part in json.JSONEncoder(ensure_ascii=False, indent=2).iterencode(updated):
                data = part.encode('utf-8')
                if len(encoded) + len(data) > self.MAX_BYTES:
                    raise ValueError('Ayar çıktısı 1 MiB sınırını aşıyor; dosya değiştirilmedi.')
                encoded.extend(data)
        except RecursionError as exc:
            raise ValueError('Ayar yapısı çok derin; dosya değiştirilmedi.') from exc
        persisted=self.parse(encoded)
        if persisted is None:
            raise ValueError('Ayar çıktısı tekrar okunamadı; dosya değiştirilmedi.')
        areas,region_issues=read_saved_areas(persisted.get('regions'))
        if 'regions' in values and region_issues:
            raise ValueError('Geçersiz alan ayarı: '+' '.join(region_issues))
        temporary = self.path.with_suffix('.tmp')
        temporary.write_bytes(encoded)
        if self.path.exists():
            backup = self.path.with_suffix('.json.bak') if self.primary_valid else self.path.with_name(
                'settings.invalid-' + hashlib.sha256(current).hexdigest() + '.json')
            if self.primary_valid or not backup.exists():
                shutil.copy2(self.path, backup)
        os.replace(temporary, self.path)
        # Own the exact serialized snapshot, not mutable caller objects or a
        # different writer's bytes that may arrive just after our commit.
        self.values = persisted
        self.loaded_bytes = bytes(encoded)
        self.regions=MappingProxyType(areas)
        self.region_issues=region_issues
        self.primary_valid = not region_issues
