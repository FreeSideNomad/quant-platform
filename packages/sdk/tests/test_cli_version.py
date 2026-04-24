from quantplatform import __version__
from quantplatform.cli.main import app


def test_qp_version(runner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
