"""One owner for the shipped helper JSON-line facts and display-independent IPs."""
from dataclasses import dataclass,replace
import ipaddress
import json
from urllib.parse import urlsplit

MAX_LINE=80_000  # Reference UI examines <20k Unicode chars; at most4UTF8bytes/char.


def ipv4(value):
    if not isinstance(value,str):raise ValueError('TV için geçerli bir IPv4 adresi yazın.')
    address=ipaddress.IPv4Address(value)
    if address.is_unspecified or address.is_multicast:raise ValueError('TV için geçerli bir IPv4 adresi yazın.')
    return str(address)


def valid_saved_host(value):
    try:return value=='' or ipv4(value)==value
    except ValueError:return False


@dataclass(frozen=True)
class SamsungTV:
    ip:str
    name:str
    model:str=''
    dev_mode:bool|None=None
    dev_ip:str=''
    pc_ip:str=''


@dataclass(frozen=True)
class Notice:
    kind:str
    text:str=''
    step:str=''
    percent:int|None=None
    url:str=''
    tv:SamsungTV|None=None
    tizen:str=''
    code:str=''
    hint:str=''


def parse_notice(raw):
    if len(raw)>MAX_LINE:raise ValueError('Samsung çıktı satırı kapasiteyi aştı.')
    try:value=json.loads(raw)
    except (ValueError,UnicodeDecodeError,RecursionError) as exc:raise ValueError('Samsung çıktı satırı geçerli JSON değil.') from exc
    if not isinstance(value,dict):raise ValueError('Samsung çıktısı bir nesne olmalı.')
    def text(key):
        result=value.get(key)
        if result is None:return ''
        if not isinstance(result,str):raise ValueError(f'Samsung {key} alanı metin olmalı.')
        return result
    kind=value.get('event')
    if kind=='step':
        step=text('step');url=text('url') if step=='login' else ''
        parsed=urlsplit(url)
        if not (parsed.scheme=='https' and parsed.hostname=='account.samsung.com'
                and not parsed.username and not parsed.password and parsed.port in (None,443)):
            url=''
        percent=value.get('percent')
        return Notice(kind,text('text'),step,percent if type(percent) is int and 0<=percent<=100 else None,url)
    if kind=='tv':
        dev_mode=value.get('devMode')
        return Notice(kind,tv=SamsungTV(ipv4(text('ip')),text('name') or 'Samsung TV',text('model'),
                      dev_mode if type(dev_mode) is bool else None,text('devIp'),text('pcIp')))
    if kind=='device':return Notice(kind,tizen=text('tizen'))
    if kind=='error':return Notice(kind,text('text'),code=text('code'),hint=text('hint'))
    if kind=='done':return Notice(kind,text('text'))
    if kind=='_runner_ready':return Notice(kind)
    return None


@dataclass(frozen=True)
class SamsungState:
    action:str=''
    text:str=''
    step:str=''
    percent:int|None=None
    url:str=''
    tvs:tuple[SamsungTV,...]=()
    tizen:str=''
    error:str=''
    hint:str=''
    code:str=''
    done:bool=False
    scanned:bool=False
    cancelled:bool=False
    host:str=''
    cleanup_error:str=''
    log_truncated:bool=False

    def notice(self,event):
        if event.kind=='step':return replace(self,text=event.text,step=event.step,percent=event.percent,url=event.url)
        if event.kind=='tv':
            values=[tv for tv in self.tvs if tv.ip!=event.tv.ip]+[event.tv]
            if len(values)>32:raise ValueError('En fazla32SamsungTV listelenebilir.')
            return replace(self,tvs=tuple(sorted(values,key=lambda tv:ipaddress.IPv4Address(tv.ip))))
        if event.kind=='device':return replace(self,tizen=event.tizen)
        if event.kind=='error':return replace(self,error=event.text,hint=event.hint,code=event.code,percent=None,url='')
        if event.kind=='done':
            if self.action=='scan':return replace(self,scanned=True,text=f'{len(self.tvs)} Samsung TV bulundu.',percent=None,url='')
            return replace(self,done=True,text=event.text or 'Uygulama Samsung TV’ye yüklendi.',percent=None,url='')
        return self
