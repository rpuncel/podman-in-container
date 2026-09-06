import subprocess
import sys


def run_pic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pic.cli", *args], capture_output=True, text=True
    )


def test_launch_then_teardown():
    launch = run_pic("launch", "--workspace", "clitest")
    try:
        assert launch.returncode == 0, launch.stderr
        assert "is up" in launch.stdout.lower()
    finally:
        teardown = run_pic("teardown", "--workspace", "clitest")
        assert teardown.returncode == 0, teardown.stderr
