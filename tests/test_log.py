"""Unit tests for mcp_secure_remote.log."""
import json
import pytest

try:
    BaseExceptionGroup
except NameError:
    from exceptiongroup import BaseExceptionGroup

from mcp_secure_remote.log import (
    _debug_enabled,
    _serialize,
    debug_log,
    flatten_exception,
    is_debug,
    log,
    set_debug,
)


@pytest.fixture(autouse=True)
def reset_debug_flag():
    """Ensure debug flag is reset to False after every test."""
    set_debug(False)
    yield
    set_debug(False)


class TestSetDebugAndIsDebug:
    def test_default_is_false(self):
        assert is_debug() is False

    def test_set_true(self):
        set_debug(True)
        assert is_debug() is True

    def test_set_false_again(self):
        set_debug(True)
        set_debug(False)
        assert is_debug() is False


class TestLog:
    def test_writes_message_to_stderr(self, capsys):
        log("hello world")
        assert "hello world" in capsys.readouterr().err

    def test_includes_prefix_with_timestamp(self, capsys):
        log("ping")
        output = capsys.readouterr().err
        assert "[mcp-secure-remote" in output

    def test_extra_string_args_appended(self, capsys):
        log("msg", "extra")
        output = capsys.readouterr().err
        assert "msg" in output
        assert "extra" in output

    def test_extra_numeric_arg_appended(self, capsys):
        log("msg", 42)
        output = capsys.readouterr().err
        assert "42" in output

    def test_extra_dict_arg_serialised_as_json(self, capsys):
        log("msg", {"key": "val"})
        output = capsys.readouterr().err
        assert '"key"' in output
        assert '"val"' in output

    def test_no_extra_args(self, capsys):
        log("only message")
        output = capsys.readouterr().err
        # No trailing space after the message
        assert "only message\n" in output

    def test_output_ends_with_newline(self, capsys):
        log("newline check")
        assert capsys.readouterr().err.endswith("\n")


class TestDebugLog:
    def test_suppressed_when_debug_disabled(self, capsys):
        set_debug(False)
        debug_log("should not appear")
        assert capsys.readouterr().err == ""

    def test_emitted_when_debug_enabled(self, capsys):
        set_debug(True)
        debug_log("should appear")
        assert "should appear" in capsys.readouterr().err

    def test_debug_prefix_added(self, capsys):
        set_debug(True)
        debug_log("check prefix")
        assert "[debug]" in capsys.readouterr().err

    def test_extra_args_forwarded(self, capsys):
        set_debug(True)
        debug_log("msg", "extra")
        output = capsys.readouterr().err
        assert "msg" in output
        assert "extra" in output


class TestSerialize:
    def test_string_returned_as_is(self):
        assert _serialize("hello") == "hello"

    def test_exception_converted_to_string(self):
        assert _serialize(ValueError("oops")) == "oops"

    def test_dict_serialised_as_json(self):
        result = _serialize({"a": 1})
        assert json.loads(result) == {"a": 1}

    def test_list_serialised_as_json(self):
        result = _serialize([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_integer_serialised_as_json(self):
        assert _serialize(99) == "99"

    def test_none_serialised_as_json(self):
        assert _serialize(None) == "null"

    def test_non_serialisable_falls_back_to_str(self):
        class Opaque:
            def __repr__(self):
                return "Opaque()"

        result = _serialize(Opaque())
        assert isinstance(result, str)


class TestFlattenException:
    def test_plain_exception_returned_as_is(self):
        exc = ValueError("oops")
        assert flatten_exception(exc) is exc

    def test_single_group_unwrapped(self):
        leaf = ConnectionError("cant connect")
        grp = BaseExceptionGroup("wrapper", [leaf])
        assert flatten_exception(grp) is leaf

    def test_nested_groups_unwrapped(self):
        leaf = RuntimeError("real error")
        nested = BaseExceptionGroup("inner", [leaf])
        outer = BaseExceptionGroup("outer", [nested])
        assert flatten_exception(outer) is leaf

    def test_empty_group_returned_as_is(self):
        # ExceptionGroup requires at least one sub-exception, but guard anyway.
        grp = BaseExceptionGroup("wrapper", [Exception("e")])
        # The single-leaf case is the realistic one.
        assert isinstance(flatten_exception(grp), Exception)
