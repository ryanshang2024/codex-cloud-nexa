"""Process ownership prevents duplicate launches and stopping another session."""
import os
import subprocess
import sys
import time

import pytest

from scripts import dev


@pytest.mark.parametrize('platform',['linux','darwin'])
@pytest.mark.parametrize('case',['owned','stale_pid','wrong_command','foreign_group'])
def test_process_ownership_checks_command_group_and_start_time(tmp_path,monkeypatch,platform,case):
    marker='unrelated.module' if case=='wrong_command' else 'backend.jobs'
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)',marker],
        start_new_session=case!='foreign_group')
    try:
        record=tmp_path/'worker.pid'
        record.write_text(str(child.pid))
        if case=='stale_pid':
            old=time.time()-60
            os.utime(record,(old,old))
        monkeypatch.setattr(dev,'LOCAL',tmp_path)
        # Linux ps exposes the same C-locale lstart/command interface as macOS.
        monkeypatch.setattr(sys,'platform',platform)
        assert dev.owned_process(child.pid,'worker') is (case=='owned')
    finally:
        child.terminate()
        child.wait(timeout=5)
