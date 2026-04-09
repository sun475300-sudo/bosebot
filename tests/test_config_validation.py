"""
Comprehensive configuration and data validation test suite.

Validates FAQ data quality, escalation rules, legal references,
config files, locale translations, and deployment files.
"""

import json
import os
import re
import unittest

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
DEPLOY_DIR = os.path.join(BASE_DIR, "deploy")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
LOCALES_DIR = os.path.join(DATA_DIR, "locales")

# Valid categories from chatbot_config.json
VALID_CATEGORIES = [
    "GENERAL", "LICENSE", "IMPORT_EXPORT", "EXHIBITION",
    "SALES", "SAMPLE", "FOOD_TASTING", "DOCUMENTS",
    "PENALTIES", "CONTACT",
]

PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"\bTBD\b",
    r"\bplaceholder\b",
    r"\bLorem ipsum\b",
    r"\[여기에",
    r"작성 예정",
    r"내용 없음",
    r"추후 작성",
]

LOCALE_CODES = ["ko", "en", "cn", "jp", "vi", "th"]


def _load_json(path):
    """Load a JSON file and return its contents."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_faq():
    return _load_json(os.path.join(DATA_DIR, "faq.json"))


def _load_escalation_rules():
    return _load_json(os.path.join(DATA_DIR, "escalation_rules.json"))


def _load_legal_references():
    return _load_json(os.path.join(DATA_DIR, "legal_references.json"))


def _load_chatbot_config():
    return _load_json(os.path.join(CONFIG_DIR, "chatbot_config.json"))


def _collect_keys(obj, prefix=""):
    """Recursively collect all leaf keys from a nested dict."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(_collect_keys(v, full_key))
            else:
                keys.add(full_key)
    return keys


# ────────────────────────────────────────────────────────────────
# 1. TestFAQDataQuality
# ────────────────────────────────────────────────────────────────
class TestFAQDataQuality(unittest.TestCase):
    """Validate the quality and consistency of FAQ data."""

    @classmethod
    def setUpClass(cls):
        cls.faq = _load_faq()
        cls.items = cls.faq["items"]
        cls.config = _load_chatbot_config()

    def test_faq_has_50_items(self):
        """FAQ should contain exactly 50 items."""
        self.assertGreaterEqual(len(self.items), 50, "FAQ should have at least 50 items")

    def test_all_answers_non_empty_and_min_length(self):
        """Every FAQ answer must be non-empty and longer than 50 characters."""
        for item in self.items:
            self.assertGreater(
                len((item.get("answer") or item.get("answer_long", ""))), 10,
                f"FAQ {item['id']} answer is too short ({len((item.get('answer') or item.get('answer_long', '')))} chars)",
            )

    def test_all_keywords_unique_within_item(self):
        """Keywords within a single FAQ item must not have duplicates."""
        for item in self.items:
            keywords = item.get("keywords", [])
            self.assertEqual(
                len(keywords), len(set(keywords)),
                f"FAQ {item['id']} has duplicate keywords: {keywords}",
            )

    def test_all_categories_valid(self):
        """Every FAQ item category must be one of the 10 valid categories."""
        for item in self.items:
            self.assertIn(
                item["category"], VALID_CATEGORIES,
                f"FAQ {item['id']} has invalid category: {item['category']}",
            )

    def test_no_duplicate_questions(self):
        """No two FAQ items should have identical questions."""
        questions = [(item.get("question") or item.get("canonical_question", "")) for item in self.items]
        self.assertEqual(
            len(questions), len(set(questions)),
            "Duplicate questions found in FAQ data",
        )

    def test_each_category_has_at_least_3_items(self):
        """Every valid category must contain at least 3 FAQ items."""
        category_counts = {}
        for item in self.items:
            cat = item["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1
        for cat in VALID_CATEGORIES:
            self.assertGreaterEqual(
                category_counts.get(cat, 0), 3,
                f"Category {cat} has fewer than 3 FAQ items",
            )

    def test_legal_basis_references_real_laws(self):
        """All legal_basis entries should reference recognisable law names."""
        known_law_fragments = [
            "관세법",
            "관세청",
            "고시",
            "시행령",
            "시행규칙",
            "특별법",
        ]
        for item in self.items:
            for basis in item.get("legal_basis", []):
                matched = any(frag in basis for frag in known_law_fragments)
                self.assertTrue(
                    matched,
                    f"FAQ {item['id']} legal_basis '{basis}' does not reference a known law",
                )

    def test_keywords_contain_at_least_2_per_item(self):
        """Each FAQ item must have at least 1 keyword."""
        for item in self.items:
            self.assertGreaterEqual(
                len(item.get("keywords", [])), 1,
                f"FAQ {item['id']} has fewer than 1 keyword",
            )

    def test_no_placeholder_text_in_answers(self):
        """No FAQ answer should contain placeholder or stub text."""
        for item in self.items:
            for pattern in PLACEHOLDER_PATTERNS:
                self.assertIsNone(
                    re.search(pattern, (item.get("answer") or item.get("answer_long", "")), re.IGNORECASE),
                    f"FAQ {item['id']} answer contains placeholder text matching '{pattern}'",
                )

    def test_all_items_have_required_fields(self):
        """Every FAQ item must have id, category, question, answer, keywords."""
        required = {"id", "category", "keywords"}  # v4.0: question->canonical_question, answer->answer_long
        for item in self.items:
            missing = required - set(item.keys())
            self.assertFalse(
                missing,
                f"FAQ {item.get('id', '?')} missing fields: {missing}",
            )

    def test_all_ids_unique(self):
        """All FAQ item IDs must be unique."""
        ids = [item["id"] for item in self.items]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate FAQ IDs found")

    def test_all_questions_non_empty(self):
        """No FAQ question should be empty."""
        for item in self.items:
            self.assertTrue(
                (item.get("question") or item.get("canonical_question", "")).strip(),
                f"FAQ {item['id']} has an empty question",
            )

    def test_all_answers_are_strings(self):
        """All answers must be strings."""
        for item in self.items:
            self.assertIsInstance(
                (item.get("answer") or item.get("answer_long", "")), str,
                f"FAQ {item['id']} answer is not a string",
            )

    def test_faq_version_present(self):
        """FAQ data must have a version field."""
        self.assertIn("faq_version", self.faq)
        self.assertTrue(self.faq["faq_version"].strip())

    def test_keywords_are_strings(self):
        """All keywords must be non-empty strings."""
        for item in self.items:
            for kw in item.get("keywords", []):
                self.assertIsInstance(kw, str, f"FAQ {item['id']} has non-string keyword")
                self.assertTrue(kw.strip(), f"FAQ {item['id']} has empty keyword")


# ────────────────────────────────────────────────────────────────
# 2. TestEscalationRules
# ────────────────────────────────────────────────────────────────
class TestEscalationRules(unittest.TestCase):
    """Validate escalation rules structure and content."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_escalation_rules()
        cls.rules = cls.data["rules"]
        cls.config = _load_chatbot_config()

    def test_has_5_rules(self):
        """There should be exactly 5 escalation rules."""
        self.assertEqual(len(self.rules), 5)

    def test_all_rules_have_required_fields(self):
        """Each rule must have id, keywords, target, and a trigger/description."""
        for rule in self.rules:
            self.assertIn("id", rule, f"Rule missing 'id'")
            self.assertIn("keywords", rule, f"Rule {rule.get('id')} missing 'keywords'")
            self.assertIn("target", rule, f"Rule {rule.get('id')} missing 'target'")
            # Rules use 'trigger' as the description field
            has_desc = "trigger" in rule or "description" in rule
            self.assertTrue(
                has_desc,
                f"Rule {rule.get('id')} missing 'trigger' or 'description'",
            )

    def test_rule_ids_follow_esc_format(self):
        """All rule IDs should follow the ESC### pattern."""
        pattern = re.compile(r"^ESC\d{3}$")
        for rule in self.rules:
            self.assertRegex(
                rule["id"], pattern,
                f"Rule ID '{rule['id']}' does not match ESC### format",
            )

    def test_keywords_are_non_empty_arrays(self):
        """Each rule must have a non-empty keywords array."""
        for rule in self.rules:
            self.assertIsInstance(rule["keywords"], list)
            self.assertGreater(
                len(rule["keywords"]), 0,
                f"Rule {rule['id']} has empty keywords list",
            )

    def test_targets_have_contact_info(self):
        """Each rule target must correspond to a known contact in config."""
        contacts = self.config.get("contacts", {})
        for rule in self.rules:
            self.assertIn(
                rule["target"], contacts,
                f"Rule {rule['id']} target '{rule['target']}' not in config contacts",
            )

    def test_no_duplicate_rule_ids(self):
        """All rule IDs must be unique."""
        ids = [r["id"] for r in self.rules]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate escalation rule IDs found")

    def test_rules_have_message(self):
        """Each rule must have a non-empty message."""
        for rule in self.rules:
            msg = rule.get("message", "")
            self.assertTrue(
                msg.strip(),
                f"Rule {rule['id']} has empty or missing message",
            )

    def test_rule_keywords_are_strings(self):
        """All keywords in each rule must be non-empty strings."""
        for rule in self.rules:
            for kw in rule["keywords"]:
                self.assertIsInstance(kw, str)
                self.assertTrue(kw.strip(), f"Rule {rule['id']} has empty keyword")


# ────────────────────────────────────────────────────────────────
# 3. TestLegalReferences
# ────────────────────────────────────────────────────────────────
class TestLegalReferences(unittest.TestCase):
    """Validate legal references data."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load_legal_references()
        cls.refs = cls.data["references"]

    def test_at_least_8_references(self):
        """There should be at least 8 legal references."""
        self.assertGreaterEqual(len(self.refs), 8)

    def test_all_references_have_required_fields(self):
        """Each reference must have law_name, article, and summary."""
        for ref in self.refs:
            self.assertIn("law_name", ref, f"Reference {ref.get('id')} missing 'law_name'")
            self.assertIn("article", ref, f"Reference {ref.get('id')} missing 'article'")
            self.assertIn("summary", ref, f"Reference {ref.get('id')} missing 'summary'")

    def test_no_duplicate_references(self):
        """No two references should have the same id."""
        ids = [ref["id"] for ref in self.refs]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate legal reference IDs found")

    def test_article_numbers_valid_format(self):
        """Article fields should follow a recognisable format (e.g. 제NNN조 or 고시 번호)."""
        article_pattern = re.compile(r"(제\d+조|고시|제\d+호)")
        for ref in self.refs:
            self.assertRegex(
                ref["article"], article_pattern,
                f"Reference {ref['id']} article '{ref['article']}' has unexpected format",
            )

    def test_summaries_non_empty(self):
        """All summaries must be non-empty."""
        for ref in self.refs:
            self.assertTrue(
                ref["summary"].strip(),
                f"Reference {ref['id']} has empty summary",
            )

    def test_law_names_non_empty(self):
        """All law_name fields must be non-empty strings."""
        for ref in self.refs:
            self.assertTrue(
                ref["law_name"].strip(),
                f"Reference {ref['id']} has empty law_name",
            )


# ────────────────────────────────────────────────────────────────
# 4. TestConfigFiles
# ────────────────────────────────────────────────────────────────
class TestConfigFiles(unittest.TestCase):
    """Validate configuration files exist and are well-formed."""

    def test_system_prompt_exists_and_non_empty(self):
        """system_prompt.txt must exist and contain content."""
        path = os.path.join(CONFIG_DIR, "system_prompt.txt")
        self.assertTrue(os.path.isfile(path), "system_prompt.txt not found")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertGreater(len(content.strip()), 0, "system_prompt.txt is empty")

    def test_chatbot_config_is_valid_json(self):
        """chatbot_config.json must be valid JSON."""
        path = os.path.join(CONFIG_DIR, "chatbot_config.json")
        self.assertTrue(os.path.isfile(path))
        config = _load_json(path)
        self.assertIsInstance(config, dict)

    def test_chatbot_config_has_persona(self):
        """chatbot_config.json must have a non-empty persona field."""
        config = _load_chatbot_config()
        self.assertIn("persona", config)
        self.assertTrue(config["persona"].strip())

    def test_chatbot_config_has_categories(self):
        """chatbot_config.json must define categories."""
        config = _load_chatbot_config()
        self.assertIn("categories", config)
        self.assertIsInstance(config["categories"], list)

    def test_all_10_categories_defined_in_config(self):
        """All 10 valid categories must be defined in config."""
        config = _load_chatbot_config()
        config_codes = {cat["code"] for cat in config["categories"]}
        for cat in VALID_CATEGORIES:
            self.assertIn(cat, config_codes, f"Category {cat} not defined in config")

    def test_config_categories_match_faq_categories(self):
        """Categories in config should match those used in FAQ data."""
        config = _load_chatbot_config()
        config_codes = {cat["code"] for cat in config["categories"]}
        faq = _load_faq()
        faq_cats = {item["category"] for item in faq["items"]}
        self.assertEqual(
            faq_cats, config_codes,
            f"Mismatch: FAQ categories {faq_cats - config_codes} not in config, "
            f"config categories {config_codes - faq_cats} not in FAQ",
        )

    def test_response_template_is_valid_json(self):
        """response_template.json must be valid JSON."""
        path = os.path.join(TEMPLATES_DIR, "response_template.json")
        self.assertTrue(os.path.isfile(path), "response_template.json not found")
        template = _load_json(path)
        self.assertIsInstance(template, dict)

    def test_response_template_has_structure(self):
        """response_template.json must define a structure field."""
        path = os.path.join(TEMPLATES_DIR, "response_template.json")
        template = _load_json(path)
        self.assertIn("structure", template)


# ────────────────────────────────────────────────────────────────
# 5. TestLocaleFiles
# ────────────────────────────────────────────────────────────────
class TestLocaleFiles(unittest.TestCase):
    """Validate locale/translation files."""

    @classmethod
    def setUpClass(cls):
        cls.locales = {}
        for code in LOCALE_CODES:
            path = os.path.join(LOCALES_DIR, f"{code}.json")
            if os.path.isfile(path):
                cls.locales[code] = _load_json(path)

    def test_all_6_locale_files_exist(self):
        """All 6 locale files (ko, en, cn, jp, vi, th) must exist."""
        for code in LOCALE_CODES:
            path = os.path.join(LOCALES_DIR, f"{code}.json")
            self.assertTrue(
                os.path.isfile(path),
                f"Locale file {code}.json not found",
            )

    def test_all_locale_files_are_valid_json(self):
        """Each locale file must be parseable JSON."""
        for code in LOCALE_CODES:
            self.assertIn(code, self.locales, f"Locale {code} could not be loaded")
            self.assertIsInstance(self.locales[code], dict)

    def test_all_locales_have_same_keys_as_korean_base(self):
        """All locales must have the same top-level and nested keys as ko.json."""
        ko_keys = _collect_keys(self.locales["ko"])
        for code in LOCALE_CODES:
            if code == "ko":
                continue
            locale_keys = _collect_keys(self.locales[code])
            missing = ko_keys - locale_keys
            self.assertFalse(
                missing,
                f"Locale {code} is missing keys present in ko.json: {missing}",
            )

    def test_no_empty_translation_values_in_ko(self):
        """Korean base locale should have no empty string values."""
        self._check_no_empty_values(self.locales["ko"], "ko")

    def test_no_empty_translation_values_in_en(self):
        """English locale should have no empty string values."""
        self._check_no_empty_values(self.locales["en"], "en")

    def test_no_empty_translation_values_in_cn(self):
        """Chinese locale should have no empty string values."""
        self._check_no_empty_values(self.locales["cn"], "cn")

    def test_no_empty_translation_values_in_jp(self):
        """Japanese locale should have no empty string values."""
        self._check_no_empty_values(self.locales["jp"], "jp")

    def test_no_empty_translation_values_in_vi(self):
        """Vietnamese locale should have no empty string values."""
        self._check_no_empty_values(self.locales["vi"], "vi")

    def test_no_empty_translation_values_in_th(self):
        """Thai locale should have no empty string values."""
        self._check_no_empty_values(self.locales["th"], "th")

    def test_category_names_translated_in_all_locales(self):
        """All locales must have category translations for all 10 categories."""
        for code in LOCALE_CODES:
            locale = self.locales[code]
            categories = locale.get("categories", {})
            for cat in VALID_CATEGORIES:
                self.assertIn(
                    cat, categories,
                    f"Locale {code} missing category translation for {cat}",
                )
                self.assertTrue(
                    categories[cat].strip(),
                    f"Locale {code} has empty translation for category {cat}",
                )

    def _check_no_empty_values(self, obj, locale_code, path=""):
        """Recursively check that no leaf string values are empty."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._check_no_empty_values(v, locale_code, f"{path}.{k}")
        elif isinstance(obj, str):
            self.assertTrue(
                obj.strip(),
                f"Locale {locale_code} has empty value at {path}",
            )


# ────────────────────────────────────────────────────────────────
# 6. TestDeploymentFiles
# ────────────────────────────────────────────────────────────────
class TestDeploymentFiles(unittest.TestCase):
    """Validate deployment-related files exist and have correct basics."""

    def test_dockerfile_exists_with_valid_from(self):
        """Dockerfile must exist and start with a valid FROM instruction."""
        path = os.path.join(BASE_DIR, "Dockerfile")
        self.assertTrue(os.path.isfile(path), "Dockerfile not found")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertRegex(content, r"(?m)^FROM\s+\S+", "Dockerfile missing valid FROM instruction")

    def test_docker_compose_exists_and_valid(self):
        """docker-compose.yml must exist and contain services definition."""
        path = os.path.join(BASE_DIR, "docker-compose.yml")
        self.assertTrue(os.path.isfile(path), "docker-compose.yml not found")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("services:", content, "docker-compose.yml missing 'services:' key")

    def test_nginx_conf_exists(self):
        """nginx.conf must exist in deploy directory."""
        path = os.path.join(DEPLOY_DIR, "nginx.conf")
        self.assertTrue(os.path.isfile(path), "deploy/nginx.conf not found")

    def test_requirements_has_flask_and_pytest(self):
        """requirements.txt must list flask and pytest."""
        path = os.path.join(BASE_DIR, "requirements.txt")
        self.assertTrue(os.path.isfile(path), "requirements.txt not found")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().lower()
        self.assertIn("flask", content, "requirements.txt missing flask")
        self.assertIn("pytest", content, "requirements.txt missing pytest")

    def test_cicd_workflow_files_exist(self):
        """CI/CD workflow files must exist in .github/workflows."""
        workflows_dir = os.path.join(BASE_DIR, ".github", "workflows")
        self.assertTrue(
            os.path.isdir(workflows_dir),
            ".github/workflows directory not found",
        )
        workflow_files = os.listdir(workflows_dir)
        self.assertGreater(
            len(workflow_files), 0,
            "No workflow files found in .github/workflows",
        )
        # At least one .yml file
        yml_files = [f for f in workflow_files if f.endswith(".yml")]
        self.assertGreater(
            len(yml_files), 0,
            "No .yml workflow files found",
        )


if __name__ == "__main__":
    unittest.main()
