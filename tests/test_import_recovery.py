"""Import-time provider configuration must not contact the network or mutate env."""

import os
import subprocess
import sys
from pathlib import Path


def test_provider_import_is_offline_and_does_not_load_dotenv_into_environment(tmp_path):
    env_file = tmp_path / "local.env"
    env_file.write_text("BASETEN_API_KEY=unit-import-fake-key\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("BASETEN_API_KEY", None)
    env.pop("BASETEN_MODEL", None)
    env.pop("LABLENS_DISABLE_DOTENV", None)
    script = '''
import os
import socket
import sys
from pathlib import Path

def forbidden(*args, **kwargs):
    raise AssertionError("network access during module import")
socket.create_connection = forbidden
socket.socket.connect = forbidden
import provider_config
provider_config.ENV_FILE = Path(sys.argv[1])
provider_config.reload_dotenv()
import ask_muse
assert "BASETEN_API_KEY" not in os.environ
assert provider_config.get_api_key() == "unit-import-fake-key"
assert ask_muse.BASE_URL == "https://inference.baseten.co/v1"
'''
    result = subprocess.run(
        [sys.executable, "-c", script, str(env_file)],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
