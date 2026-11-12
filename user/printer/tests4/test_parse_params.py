from ..hhprint4 import ParseParams


class TestParseParams:

    def test_full(self) -> None:
        data = 'hhprint:will-pass?printer=tcp%3A%2F%2F127.0.0.1%3A99990&amp;model=TEST-1&amp;label=zgv&amp;backend=network&codes=foo;bar;baz'
        result = ParseParams.parse_arguments(data)
        assert 'will-pass' == result.path, 'The path is different'
        assert ['foo', 'bar', 'baz'] == list(map(str, result.codes)), 'The codes are different'
        assert 'zgv' == result.label, 'The label is different'
        # the rest of params is ignored1

    def test_defaults(self) -> None:
        data = 'hhprint:not-work?codes='
        result = ParseParams.parse_arguments(data)
        assert 'not-work' == result.path, 'The path is different'
        assert [] == result.codes, 'The codes are different'
        assert '62' == result.label, 'The label is different'
        # the rest of params is ignored
