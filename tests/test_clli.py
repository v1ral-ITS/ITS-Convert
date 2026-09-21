"""Tests for itsconvert.clli — Cross-Language Library Interface."""
import pytest

from itsconvert.clli import ConvertError, convert, inspect, languages


class TestConvert:
    def test_py_to_sh(self):
        result = convert('print("hello")\n', from_lang="py", to_lang="sh")
        assert "echo" in result

    def test_py_to_ps1(self):
        result = convert('print("hello")\n', from_lang="py", to_lang="ps1")
        assert "Write-Host" in result

    def test_py_to_go(self):
        result = convert('print("hello")\n', from_lang="py", to_lang="go")
        assert "fmt.Println" in result

    def test_py_to_js(self):
        result = convert('x = 1\nprint(x)\n', from_lang="py", to_lang="js")
        assert "console.log" in result

    def test_sh_to_py(self):
        result = convert('echo "hello"\n', from_lang="sh", to_lang="py")
        assert "print" in result

    def test_invalid_from_lang(self):
        with pytest.raises(ConvertError):
            convert('print("x")\n', from_lang="clli_invalid", to_lang="py")

    def test_invalid_to_lang(self):
        with pytest.raises(ConvertError):
            convert('print("x")\n', from_lang="py", to_lang="clli_invalid")

    def test_returns_string(self):
        result = convert('x = 42\n', from_lang="py", to_lang="sh")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiline_source(self):
        source = 'x = 1\ny = 2\nprint(x + y)\n'
        result = convert(source, from_lang="py", to_lang="rs")
        assert "fn main" in result


class TestInspect:
    def test_returns_dict(self):
        result = inspect('x = 42\n', lang="py")
        assert isinstance(result, dict)

    def test_source_language(self):
        result = inspect('x = 42\n', lang="py")
        assert result["source_language"] == "py"

    def test_nodes_present(self):
        result = inspect('x = 42\n', lang="py")
        assert "nodes" in result
        assert len(result["nodes"]) == 1

    def test_node_type(self):
        result = inspect('x = 42\n', lang="py")
        assert result["nodes"][0]["type"] == "assign"

    def test_warnings_key(self):
        result = inspect('x = 42\n', lang="py")
        assert "warnings" in result

    def test_invalid_lang(self):
        with pytest.raises(ConvertError):
            inspect('x = 1\n', lang="clli_invalid")

    def test_bash_source(self):
        result = inspect('echo "hello"\n', lang="sh")
        assert result["source_language"] == "sh"
        assert result["nodes"][0]["type"] == "print"


class TestLanguages:
    def test_returns_dict(self):
        result = languages()
        assert isinstance(result, dict)

    def test_has_parsers_key(self):
        result = languages()
        assert "parsers" in result

    def test_has_emitters_key(self):
        result = languages()
        assert "emitters" in result

    def test_parsers_is_list(self):
        result = languages()
        assert isinstance(result["parsers"], list)

    def test_emitters_is_list(self):
        result = languages()
        assert isinstance(result["emitters"], list)

    def test_py_in_parsers(self):
        assert "py" in languages()["parsers"]

    def test_go_in_emitters(self):
        assert "go" in languages()["emitters"]

    def test_parsers_sorted(self):
        result = languages()["parsers"]
        assert result == sorted(result)

    def test_emitters_sorted(self):
        result = languages()["emitters"]
        assert result == sorted(result)


class TestPublicAPI:
    """Verify the API is importable directly from the package."""

    def test_import_from_package(self):
        import itsconvert
        assert callable(itsconvert.convert)
        assert callable(itsconvert.inspect)
        assert callable(itsconvert.languages)
        assert issubclass(itsconvert.ConvertError, Exception)

    def test_convert_alias(self):
        import itsconvert
        result = itsconvert.convert('print("hi")\n', from_lang="py", to_lang="sh")
        assert "echo" in result
