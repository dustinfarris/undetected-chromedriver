import pytest

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
