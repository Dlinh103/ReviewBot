"""Unit tests for RepoConfig loader (.reviewbot.yml)."""

from reviewbot.core.config_loader import RepoConfig, parse_repo_config


def test_parse_valid_repo_config() -> None:
    yaml_text = """
    language: en
    min_confidence: 0.8
    max_comments: 10
    ignore:
      - "generated/**"
      - "*.tmp"
    focus:
      - "security"
    rules:
      strict_mode: true
    """
    config = parse_repo_config(yaml_text)
    assert config.language == "en"
    assert config.min_confidence == 0.8
    assert config.max_comments == 10
    assert "generated/**" in config.ignore
    assert "security" in config.focus
    assert config.rules.get("strict_mode") is True


def test_parse_empty_or_whitespace_returns_defaults() -> None:
    config_empty = parse_repo_config("")
    assert config_empty.language == "vi"
    assert config_empty.min_confidence == 0.6
    assert config_empty.max_comments == 15
    assert config_empty.ignore == []

    config_spaces = parse_repo_config("   \n  \t  ")
    assert config_spaces.language == "vi"


def test_parse_invalid_yaml_returns_defaults() -> None:
    bad_yaml = "foo: [unterminated list"
    config = parse_repo_config(bad_yaml)
    assert isinstance(config, RepoConfig)
    assert config.language == "vi"
    assert config.min_confidence == 0.6


def test_parse_non_dict_yaml_returns_defaults() -> None:
    list_yaml = "- item 1\n- item 2"
    config = parse_repo_config(list_yaml)
    assert config.language == "vi"
    assert config.max_comments == 15


def test_parse_partial_config_merges_defaults() -> None:
    yaml_text = "min_confidence: 0.85"
    config = parse_repo_config(yaml_text)
    assert config.min_confidence == 0.85
    assert config.language == "vi"
    assert config.max_comments == 15
