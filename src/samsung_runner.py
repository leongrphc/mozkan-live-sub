"""Join the parent's owned job BEFORE executing any helper or its descendants."""
import json
import subprocess
import sys
from windows_job import join_current_job


def run():
    try:
        if len(sys.argv)<4 or sys.argv[2]!='--':raise ValueError('Geçersiz yardımcı başlatma isteği.')
        join_current_job(sys.argv[1])
        print(json.dumps({'event':'_runner_ready'}),flush=True)
        child=subprocess.Popen(sys.argv[3:],stdin=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        return child.wait()
    except Exception as error:
        print(json.dumps({'event':'error','code':'start','text':str(error)},ensure_ascii=True),flush=True)
        return 1


if __name__=='__main__':raise SystemExit(run())
