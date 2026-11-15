import json
from dataclasses import asdict
from desktop import desktop_state


def require_visible_desktop():
    observed = desktop_state()
    if observed.state != 'unlocked':
        print(json.dumps(dict(status='NOT_RUN', precondition=asdict(observed)), ensure_ascii=True))
        raise SystemExit(77)
