import stat

import pytest

import undetected_chromedriver as uc
from undetected_chromedriver.patcher import Patcher


@pytest.mark.parametrize(
    ("machine", "expected"), [("arm64", "mac-arm64"), ("x86_64", "mac-x64")]
)
def test_chromedriver_download_matches_the_cpu(monkeypatch, machine, expected):
    # The x64 driver only ran on Apple Silicon via Rosetta, which macOS 27
    # removed: launching failed with "Bad CPU type in executable".
    monkeypatch.setattr("platform.machine", lambda: machine)
    monkeypatch.setattr(Patcher, "platform", "darwin")
    assert Patcher(version_main=150).platform_name == expected


def test_patched_driver_is_resigned_on_macos(monkeypatch, tmp_path):
    # Patching rewrites the driver's bytes and invalidates its signature;
    # macOS kills an arm64 binary with a broken signature on exec.
    driver = tmp_path / "chromedriver"
    driver.write_bytes(b"\0{window.cdc_adoQpoasnfa76pfcZLmcfl;}\0")
    calls = []
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(
        "subprocess.run", lambda cmd, **kw: calls.append(cmd)
    )
    patcher = Patcher(executable_path=str(driver), version_main=150)
    patcher.patch_exe()
    assert b"cdc_" not in driver.read_bytes()
    assert calls == [["codesign", "--force", "--sign", "-", str(driver)]]


def _fake_browser(tmp_path, output, exit_code=0):
    browser = tmp_path / "Google Chrome"
    browser.write_text(f"#!/bin/sh\necho '{output}'\nexit {exit_code}\n")
    browser.chmod(browser.stat().st_mode | stat.S_IEXEC)
    return str(browser)


def test_browser_version_main_reads_the_installed_browser(tmp_path):
    browser = _fake_browser(tmp_path, "Google Chrome 154.0.8037.97")
    assert uc.browser_version_main(browser) == 154


@pytest.mark.parametrize("path", [None, "/nonexistent/chrome"])
def test_browser_version_main_is_none_when_undetectable(path):
    assert uc.browser_version_main(path) is None


def test_unparseable_browser_version_is_none(tmp_path):
    assert uc.browser_version_main(_fake_browser(tmp_path, "garbage")) is None


def test_chrome_defaults_to_the_installed_browser_version(monkeypatch, tmp_path):
    # Without version_main, the latest Stable driver was fetched, which runs
    # ahead of the installed browser for days after each release.
    seen = {}

    class Stop(Exception):
        pass

    def fake_patcher(**kwargs):
        seen.update(kwargs)
        raise Stop

    monkeypatch.setattr(uc, "Patcher", fake_patcher)
    browser = _fake_browser(tmp_path, "Google Chrome 154.0.8037.97")
    with pytest.raises(Stop):
        uc.Chrome(browser_executable_path=browser)
    assert seen["version_main"] == 154
