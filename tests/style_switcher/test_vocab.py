from vocab import WRAPPERS, load_roles

ROLES = {
    "header", "nav", "hero", "section", "card", "card-list", "media",
    "heading", "text", "button", "link", "input", "form", "tabs", "list",
    "table", "badge", "avatar", "price", "stat", "footer", "part",
}


def test_roles_match_spec():
    assert load_roles() == frozenset(ROLES | {"shell", "content", "sidebar"})


def test_stat_is_a_role():
    assert "stat" in load_roles()


def test_wrappers():
    assert WRAPPERS == ("shell", "content", "sidebar")


def test_markup_section_is_prose_only():
    from vocab import VOCAB_PATH

    text = VOCAB_PATH.read_text(encoding="utf-8")
    assert "## Markup" in text
    assert text.index("## Markup") < text.index("## Layout rules")
    section = text.split("## Markup", 1)[1].split("\n## ", 1)[0]
    assert 'data-sp="<role>"' in section
    assert "data-sp-variant" in section
    assert not any(line.lstrip().startswith("-") for line in section.splitlines())


def test_missing_section_fails_fast(tmp_path):
    import pytest

    path = tmp_path / "v.md"
    path.write_text("## Roles\n\n- `card` \u2014 a card\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Wrappers"):
        load_roles(path)


def test_duplicate_role_fails_fast(tmp_path):
    import pytest

    path = tmp_path / "v.md"
    path.write_text("## Roles\n\n- `card` \u2014 a\n- `card` \u2014 b\n\n## Wrappers\n\n- `shell` \u2014 s\n", encoding="utf-8")
    with pytest.raises(ValueError, match="card"):
        load_roles(path)
