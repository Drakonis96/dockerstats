from pathlib import Path


def test_dockerfile_copies_all_root_python_modules():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert "COPY *.py ./" in content
