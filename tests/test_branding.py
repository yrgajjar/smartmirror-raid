"""The author footer is a permanent attribution and must not change."""

from smartmirror.version import AUTHOR_NAME, AUTHOR_URL, FOOTER_TEXT


def test_footer_is_fixed() -> None:
    assert AUTHOR_NAME == "Yags"
    assert AUTHOR_URL == "https://www.yags.in"
    assert FOOTER_TEXT == "by Yags \u2022 www.yags.in"
