import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.check_repository import ROOT, validate
from scripts import setup_repository as setup


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('.git', '__pycache__'))

    def test_current_repository_is_valid(self):
        self.assertEqual(validate(self.root), [])

    def test_duplicate_yaml_and_broken_links_are_rejected(self):
        (self.root / '.github/ISSUE_TEMPLATE/config.yml').write_text('blank_issues_enabled: true\nblank_issues_enabled: false\n')
        with (self.root / 'README.md').open('a') as file:
            file.write('\n[Broken](missing-file.md)\n')
        errors = validate(self.root)
        self.assertTrue(any('Duplicate YAML key' in error for error in errors))
        self.assertTrue(any('invalid local link' in error for error in errors))

    def test_publication_cannot_drop_repository_gate(self):
        path = self.root / '.github/workflows/ci.yaml'
        path.write_text(path.read_text().replace('needs: [repository-checks, validate]', 'needs: validate'))
        self.assertIn('Publication must require repository and image validation', validate(self.root))

    def test_bypass_and_missing_required_checks_are_rejected(self):
        path = self.root / '.github/rulesets/ci.json'
        rule = json.loads(path.read_text())
        rule['bypass_actors'] = [{'actor_id': 1, 'actor_type': 'User', 'bypass_mode': 'always'}]
        rule['rules'][0]['parameters']['required_status_checks'].pop()
        path.write_text(json.dumps(rule))
        errors = validate(self.root)
        self.assertIn('ci ruleset must not grant bypass privileges', errors)
        self.assertIn('Ruleset must require both GitHub Actions checks', errors)

    def test_both_checks_are_required_on_the_exact_head(self):
        from unittest.mock import patch
        _, rule = setup.rulesets(0)
        responses = [{'commit': {'sha': 'new-head'}}, {'check_runs': [
            {'name': 'Repository checks', 'app': {'id': 15368}, 'status': 'completed', 'conclusion': 'success'}]}]
        with patch.object(setup, 'api', side_effect=responses) as api:
            self.assertFalse(setup.check_ready('repos/owner/project', 'main', rule))
        self.assertIn('/commits/new-head/check-runs', api.call_args_list[-1].args[1])


if __name__ == '__main__':
    unittest.main()
