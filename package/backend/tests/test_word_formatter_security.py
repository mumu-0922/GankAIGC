from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
WORD_FORMATTER_ROOT = PACKAGE_ROOT / "backend" / "app" / "word_formatter"


def test_word_formatter_ooxml_parser_disables_external_entities():
    ooxml = (WORD_FORMATTER_ROOT / "utils" / "ooxml.py").read_text(encoding="utf-8")

    assert "XMLParser" in ooxml
    assert "resolve_entities=False" in ooxml
    assert "no_network=True" in ooxml
    assert "etree.fromstring" not in ooxml


def test_word_formatter_template_ids_use_secrets_not_random():
    template_generator = (WORD_FORMATTER_ROOT / "services" / "template_generator.py").read_text(encoding="utf-8")

    assert "import secrets" in template_generator
    assert "secrets.choice" in template_generator
    assert "import random" not in template_generator
    assert "random.choice" not in template_generator
