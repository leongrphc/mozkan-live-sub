"""Parsed saved selections and immutable bindings for a running capture.

Monitor facts describe a display configuration, not proof of hardware identity.
Missing EDID fields remain unknown; active ownership also retains QScreen objects.
"""
from dataclasses import dataclass
import math
from coordinates import screen_for_region

AREA_LABELS={'subtitle':'altyazı','hud':'görev/HUD'}


def rectangle(value,*,selection=False):
    if (not isinstance(value,(list,tuple)) or len(value)!=4 or
            any(type(item) is not int for item in value)):
        raise ValueError('Alan dört tam sayıdan oluşmalı.')
    x,y,w,h=value
    if w<=0 or h<=0:
        raise ValueError('Alan boyutu pozitif olmalı.')
    if selection and not (40<=w<=30000 and 18<=h<=20000 and all(abs(item)<100000 for item in value)):
        raise ValueError('Seçim boyutu desteklenen ekran alanı sınırlarının dışında.')
    return tuple(value)


@dataclass(frozen=True,slots=True)
class Monitor:
    geometry: tuple
    ratio: float
    name: str|None
    manufacturer: str|None
    model: str|None
    serial: str|None

    @classmethod
    def from_screen(cls,screen):
        def field(name):
            getter=getattr(screen,name,None)
            return getter() if getter else None
        return cls.from_wire(dict(geometry=list(screen.geometry().getRect()),ratio=screen.devicePixelRatio(),
            name=field('name'),manufacturer=field('manufacturer'),model=field('model'),serial=field('serialNumber')))

    @classmethod
    def from_wire(cls,value):
        keys={'geometry','ratio','name','manufacturer','model','serial'}
        if not isinstance(value,dict) or len(value)!=6 or set(value)!=keys:
            raise ValueError('Kayıtlı monitör bilgisi eksik veya tanınmıyor.')
        ratio=value['ratio']
        try:
            valid=type(ratio) in (int,float) and math.isfinite(ratio) and ratio>0
        except OverflowError:
            valid=False
        if not valid:
            raise ValueError('Kayıtlı monitör ölçeği geçersiz.')
        for key in ('name','manufacturer','model','serial'):
            item=value[key]
            if item is not None and (not isinstance(item,str) or len(item)>512):
                raise ValueError('Kayıtlı monitör etiketi geçersiz.')
        return cls(rectangle(value['geometry']),ratio,*(value[key] for key in ('name','manufacturer','model','serial')))

    def to_wire(self):
        return dict(geometry=list(self.geometry),ratio=self.ratio,name=self.name,
                    manufacturer=self.manufacturer,model=self.model,serial=self.serial)


@dataclass(frozen=True,slots=True)
class SelectedArea:
    logical: tuple
    monitor: Monitor
    purpose: str='subtitle'

    @classmethod
    def create(cls,region,screens,*,purpose='subtitle'):
        if purpose not in ('subtitle','video','hud'):
            raise ValueError('Alan türü tanınmıyor.')
        logical=rectangle(region,selection=True)
        return cls(logical,Monitor.from_screen(screen_for_region(logical,screens)),purpose)

    @classmethod
    def from_wire(cls,value):
        if not isinstance(value,dict) or len(value)!=3 or set(value)!={'logical','monitor','purpose'}:
            raise ValueError('Kayıtlı alan biçimi tanınmıyor.')
        if value['purpose'] not in ('subtitle','video','hud'):
            raise ValueError('Kayıtlı alan türü tanınmıyor.')
        logical=rectangle(value['logical'],selection=True)
        monitor=Monitor.from_wire(value['monitor'])
        x,y,w,h=logical
        sx,sy,sw,sh=monitor.geometry
        if x<sx or y<sy or x+w>sx+sw or y+h>sy+sh:
            raise ValueError('Kayıtlı alan kendi monitörünün dışında.')
        return cls(logical,monitor,value['purpose'])

    def resolve(self,screens):
        screen=screen_for_region(self.logical,screens)
        if Monitor.from_screen(screen)!=self.monitor:
            raise ValueError('Monitör konumu, ölçeği veya bilgisi değişti; alanı yeniden seçin.')
        return screen

    def to_wire(self):
        return dict(logical=list(self.logical),monitor=self.monitor.to_wire(),purpose=self.purpose)


def read_saved_areas(raw):
    if raw is None:
        return {},()
    if (not isinstance(raw,dict) or len(raw)!=3 or set(raw)!={'version','subtitle','hud'} or
            type(raw['version']) is not int or raw['version']!=1):
        return {},('Kayıtlı alan sürümü/biçimi tanınmıyor; alanları yeniden seçin.',)
    areas={}
    issues=[]
    for role in ('subtitle','hud'):
        if raw[role] is None:
            continue
        try:
            area=SelectedArea.from_wire(raw[role])
            if area.purpose not in (('subtitle','video') if role=='subtitle' else ('hud',)):
                raise ValueError('Kayıtlı alan türü bu seçimle uyuşmuyor.')
            areas[role]=area
        except ValueError as exc:
            issues.append(f'{AREA_LABELS[role]}: {exc}')
    return areas,tuple(issues)


def save_areas(areas):
    return dict(version=1,**{role:areas[role].to_wire() if role in areas else None for role in ('subtitle','hud')})


def desktop_signature(screens):
    return tuple((id(screen),Monitor.from_screen(screen)) for screen in screens)


@dataclass(frozen=True,slots=True)
class BoundArea:
    role: str
    area: SelectedArea
    owner: object
    physical: tuple

    def validate(self,screens,mapper):
        try:
            if self.area.resolve(screens) is not self.owner:
                raise ValueError('Yakalamanın bağlı olduğu ekran değişti; alanı yeniden seçin.')
            if mapper is not None and rectangle(mapper(self.area.logical,screens))!=self.physical:
                raise ValueError('Fiziksel ekran eşlemesi değişti; alanı yeniden seçin.')
        except (ValueError,OSError,RuntimeError) as exc:
            raise CaptureBindingChanged(self.role,str(exc)) from exc


class CaptureBindingChanged(ValueError):
    def __init__(self,role,reason):
        self.role=role
        super().__init__(f'{AREA_LABELS[role]}: {reason}')


@dataclass(frozen=True,slots=True)
class CapturePlan:
    subtitle: BoundArea
    hud: BoundArea|None

    @classmethod
    def create(cls,subtitle,hud,screens,mapper):
        def bind(role,region):
            area=SelectedArea.create(region,screens,purpose=role)
            return BoundArea(role,area,area.resolve(screens),rectangle(mapper(area.logical,screens)))
        return cls(bind('subtitle',subtitle),bind('hud',hud) if hud is not None else None)

    def validate(self,screens,mapper=None):
        self.subtitle.validate(screens,mapper)
        if self.hud is not None:
            self.hud.validate(screens,mapper)
