def test_exec_runs_trivial_command(machine):
    result = machine.exec("uname", "-a")
    assert "Linux" in result.stdout
