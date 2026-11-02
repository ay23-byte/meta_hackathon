"""Disable dotenv before test-module import unless live tests were requested."""
import os


def pytest_configure(config):
    if not config.getoption("--run-live", default=False):
        config._lablens_previous_dotenv_setting = os.environ.get("LABLENS_DISABLE_DOTENV")
        os.environ["LABLENS_DISABLE_DOTENV"] = "1"


def pytest_unconfigure(config):
    if hasattr(config, "_lablens_previous_dotenv_setting"):
        previous = config._lablens_previous_dotenv_setting
        if previous is None:
            os.environ.pop("LABLENS_DISABLE_DOTENV", None)
        else:
            os.environ["LABLENS_DISABLE_DOTENV"] = previous
