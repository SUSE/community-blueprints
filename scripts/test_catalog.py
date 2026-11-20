"""Unit tests for scripts/catalog.py: ClusterRepo rules and the stray-manifest check.

Run from the repo root:  python -m unittest -q scripts/test_catalog.py
"""
import importlib.util
import os
import shutil
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

_spec = importlib.util.spec_from_file_location("blueprint_catalog", os.path.join(HERE, "catalog.py"))
catalog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(catalog)

ROOT_DIR = catalog.FLEET_ROOT
REAL_ALLOWLIST = dict(catalog.ALLOWED_CLUSTERREPOS)
TEST_ALLOWLIST = {"good-repo": "https://charts.example.com/stable"}

CLUSTERREPO = """\
apiVersion: catalog.cattle.io/v1
kind: ClusterRepo
metadata:
  name: good-repo
spec:
  url: https://charts.example.com/stable
"""


def example_blueprint():
    with open(os.path.join(REPO, "example", "blueprints", "example-chatbot-1.0.0.yaml"),
              encoding="utf-8") as fh:
        return fh.read()


class TreeTestCase(unittest.TestCase):
    """Runs the validators against a temp tree by repointing the module's paths."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        patches = [
            mock.patch.object(catalog, "ROOT", self.tmp),
            mock.patch.object(catalog, "CATALOG_FILE", os.path.join(self.tmp, ROOT_DIR, "catalog.yaml")),
            mock.patch.object(catalog, "CLUSTERREPO_GLOB",
                              os.path.join(self.tmp, ROOT_DIR, "*", "clusterrepos", "*.yaml")),
            mock.patch.dict(catalog.GLOBS, {
                ROOT_DIR: os.path.join(self.tmp, ROOT_DIR, "*", "blueprints", "*.yaml"),
                "example": os.path.join(self.tmp, "example", "blueprints", "*.yaml"),
            }),
            mock.patch.object(catalog, "ALLOWED_CLUSTERREPOS", TEST_ALLOWLIST),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def write(self, rel, text):
        path = os.path.join(self.tmp, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def repo_file(self, name="good-repo", contributor="acme", text=CLUSTERREPO):
        return self.write(f"{ROOT_DIR}/{contributor}/clusterrepos/{name}.yaml", text)

    def validate(self):
        ok, summary = catalog.validate()
        return ok, summary

    def assertRejected(self, fragment):
        ok, summary = self.validate()
        self.assertFalse(ok, summary)
        self.assertIn(fragment, summary)

    def assertAccepted(self):
        ok, summary = self.validate()
        self.assertTrue(ok, summary)
        return summary


class ClusterRepoRules(TreeTestCase):
    def test_valid_accepted(self):
        self.repo_file()
        self.assertIn("1 ClusterRepo(s)", self.assertAccepted())

    def test_real_allowlist_entries_accepted(self):
        if not REAL_ALLOWLIST:
            self.skipTest("no real allowlist entries in this repo")
        with mock.patch.object(catalog, "ALLOWED_CLUSTERREPOS", REAL_ALLOWLIST):
            for name, url in REAL_ALLOWLIST.items():
                self.repo_file(name=name, text=CLUSTERREPO.replace("good-repo", name)
                               .replace("https://charts.example.com/stable", url))
            self.assertAccepted()

    def test_every_forbidden_spec_field_rejected(self):
        for field in ("clientSecret", "insecureSkipTLSVerify", "insecurePlainHttp", "caBundle",
                      "gitRepo", "gitBranch", "forceUpdate", "serviceAccount", "refreshInterval"):
            with self.subTest(field=field):
                self.repo_file(text=CLUSTERREPO + f"  {field}: x\n")
                self.assertRejected(f"spec.{field} is not allowed")

    def test_forbidden_metadata_fields_rejected(self):
        for field, value in (("namespace", "default"), ("labels", "{a: b}"), ("annotations", "{a: b}"),
                             ("ownerReferences", "[]"), ("finalizers", "[x]")):
            with self.subTest(field=field):
                self.repo_file(text=CLUSTERREPO.replace(
                    "  name: good-repo\n", f"  name: good-repo\n  {field}: {value}\n"))
                self.assertRejected(f"metadata.{field} is not allowed")

    def test_top_level_status_rejected(self):
        self.repo_file(text=CLUSTERREPO + "status: {}\n")
        self.assertRejected("status is not allowed")

    def test_wrong_api_version_and_kind(self):
        self.repo_file(text=CLUSTERREPO.replace("catalog.cattle.io/v1", "catalog.cattle.io/v2"))
        self.assertRejected("apiVersion must be")
        self.repo_file(text=CLUSTERREPO.replace("kind: ClusterRepo", "kind: ClusterRoleBinding"))
        self.assertRejected("kind must be 'ClusterRepo'")

    def test_name_must_match_file_name(self):
        self.repo_file(text=CLUSTERREPO.replace("name: good-repo", "name: other-repo"))
        self.assertRejected("must equal the file name 'good-repo'")

    def test_name_must_be_dns_label(self):
        for bad in ("Good_Repo", "-lead", "a" * 64, "dot.ted"):
            with self.subTest(name=bad):
                shutil.rmtree(os.path.join(self.tmp, ROOT_DIR), ignore_errors=True)
                with mock.patch.object(catalog, "ALLOWED_CLUSTERREPOS", {bad: TEST_ALLOWLIST["good-repo"]}):
                    self.repo_file(name=bad, text=CLUSTERREPO.replace("good-repo", bad))
                    self.assertRejected("DNS-1123 label")

    def test_wrong_url_rejected(self):
        for url in ("https://charts.example.com/stable/", "https://charts.example.com/other",
                    "https://evil.example.com/stable", "https://charts.example.com/stable "):
            with self.subTest(url=url):
                self.repo_file(text=CLUSTERREPO.replace("https://charts.example.com/stable", f"'{url}'"))
                self.assertRejected("maintainer-reviewed change")

    def test_http_url_rejected(self):
        self.repo_file(text=CLUSTERREPO.replace("https://", "http://"))
        self.assertRejected("must be an https:// URL")

    def test_missing_url_rejected(self):
        self.repo_file(text=CLUSTERREPO.replace("  url: https://charts.example.com/stable\n", "  {}\n"))
        self.assertRejected("spec.url is required")

    def test_multi_document_rejected(self):
        self.repo_file(text=CLUSTERREPO + "---\n" + CLUSTERREPO)
        self.assertRejected("exactly one YAML document")

    def test_second_document_smuggling_rejected(self):
        self.repo_file(text=CLUSTERREPO + "---\nkind: ClusterRoleBinding\n")
        self.assertRejected("exactly one YAML document")

    def test_duplicate_keys_rejected(self):
        self.repo_file(text=CLUSTERREPO + "  url: https://charts.example.com/stable\n")
        self.assertRejected("duplicate key")

    def test_unlisted_name_rejected(self):
        self.repo_file(name="mine", text=CLUSTERREPO.replace("good-repo", "mine"))
        self.assertRejected("ALLOWED_CLUSTERREPOS")

    def test_empty_allowlist_rejects_everything(self):
        with mock.patch.object(catalog, "ALLOWED_CLUSTERREPOS", {}):
            self.repo_file()
            self.assertRejected("ALLOWED_CLUSTERREPOS")

    def test_duplicate_name_across_contributors_rejected(self):
        self.repo_file(contributor="acme")
        self.repo_file(contributor="other")
        self.assertRejected("duplicate ClusterRepo 'good-repo'")

    def test_not_a_mapping(self):
        self.repo_file(text="- a\n- b\n")
        self.assertRejected("not a YAML mapping")


class StrayFiles(TreeTestCase):
    def assertStray(self, rel, text="a: b\n"):
        self.write(rel, text)
        self.assertRejected(f"**{rel}**")

    def test_named_manifests_rejected(self):
        for rel in ("fleet.yaml", "acme/fleet.yaml", "acme/kustomization.yaml", "acme/Chart.yaml",
                    "acme/blueprints/fleet.yaml"):
            with self.subTest(rel=rel):
                self.assertStray(f"{ROOT_DIR}/{rel}")
                os.remove(os.path.join(self.tmp, ROOT_DIR, *rel.split("/")))

    def test_clusterrolebinding_anywhere_rejected(self):
        crb = ("apiVersion: rbac.authorization.k8s.io/v1\nkind: ClusterRoleBinding\n"
               "metadata:\n  name: x\n")
        self.assertStray(f"{ROOT_DIR}/acme/extra/crb.yaml", crb)

    def test_yml_and_json_rejected(self):
        self.assertStray(f"{ROOT_DIR}/acme/blueprints/thing-1.0.0.yml")
        self.assertStray(f"{ROOT_DIR}/acme/clusterrepos/good-repo.json", "{}")

    def test_uppercase_extension_rejected(self):
        self.assertStray(f"{ROOT_DIR}/acme/blueprints/thing-1.0.0.YAML")
        self.assertStray(f"{ROOT_DIR}/acme/other.Json", "{}")

    def test_uppercase_extension_rejected_on_case_insensitive_glob(self):
        path = self.write(f"{ROOT_DIR}/acme/blueprints/example-chatbot-1.0.0.YAML", example_blueprint())
        with mock.patch.object(catalog, "blueprint_files", return_value=[path]):
            self.assertRejected("unexpected manifest")

    def test_nested_hidden_dir_rejected(self):
        self.assertStray(f"{ROOT_DIR}/acme/.hidden/deep/x.yaml")
        self.assertStray(f"{ROOT_DIR}/.hidden/blueprints/x.yaml")
        self.assertStray(f"{ROOT_DIR}/acme/blueprints/.hidden.yaml")

    def test_wrong_depth_rejected(self):
        self.assertStray(f"{ROOT_DIR}/acme/blueprints/sub/x.yaml")
        self.assertStray(f"{ROOT_DIR}/blueprints/x.yaml")

    def test_root_level_catalog_only_exception(self):
        self.write(f"{ROOT_DIR}/catalog.yaml", "a: b\n")
        self.assertAccepted()
        self.assertStray(f"{ROOT_DIR}/acme/catalog.yaml")

    def test_symlinked_manifest_rejected(self):
        target = self.write("outside.yaml", "a: b\n")
        link = os.path.join(self.tmp, ROOT_DIR, "acme", "blueprints", "link-1.0.0.yaml")
        os.makedirs(os.path.dirname(link))
        os.symlink(target, link)
        self.assertRejected("symlinked manifests are not allowed")

    def test_symlinked_directory_rejected(self):
        self.write("elsewhere/blueprints/x.yaml", "a: b\n")
        os.makedirs(os.path.join(self.tmp, ROOT_DIR))
        os.symlink(os.path.join(self.tmp, "elsewhere"), os.path.join(self.tmp, ROOT_DIR, "acme"))
        self.assertRejected("symlinked directories are not allowed")

    def test_markdown_and_images_ignored(self):
        self.write(f"{ROOT_DIR}/README.md", "# hi\n")
        self.write(f"{ROOT_DIR}/acme/README.md", "# hi\n")
        self.write(f"{ROOT_DIR}/acme/logo.png", "x")
        self.assertAccepted()

    def test_example_tree_is_not_scanned(self):
        self.write("example/blueprints/example-chatbot-1.0.0.yaml", example_blueprint())
        self.write("example/fleet.yaml", "a: b\n")
        self.assertAccepted()


class BlueprintsUnaffected(TreeTestCase):
    def test_blueprint_accepted_and_listed_in_catalog(self):
        self.write(f"{ROOT_DIR}/acme/blueprints/example-chatbot-1.0.0.yaml", example_blueprint())
        self.assertIn("1 blueprint(s)", self.assertAccepted())

    def test_gen_ignores_clusterrepos(self):
        self.write(f"{ROOT_DIR}/acme/blueprints/example-chatbot-1.0.0.yaml", example_blueprint())
        self.repo_file()
        names = [b["name"] for b in catalog.build_catalog()["spec"]["blueprints"]]
        self.assertEqual(names, ["example-chatbot"])

    def test_multi_document_blueprint_rejected(self):
        self.write(f"{ROOT_DIR}/acme/blueprints/example-chatbot-1.0.0.yaml",
                   example_blueprint() + "---\nkind: ClusterRoleBinding\n")
        ok, _ = self.validate()
        self.assertFalse(ok)

    def test_blueprint_named_clusterrepo_kind_rejected(self):
        self.write(f"{ROOT_DIR}/acme/blueprints/x-1.0.0.yaml", CLUSTERREPO)
        self.assertRejected("kind must be 'Blueprint'")


class RealContent(unittest.TestCase):
    def test_repo_content_validates(self):
        ok, summary = catalog.validate()
        self.assertTrue(ok, summary)
        self.assertTrue(catalog.gen(check_only=True))


if __name__ == "__main__":
    unittest.main()
