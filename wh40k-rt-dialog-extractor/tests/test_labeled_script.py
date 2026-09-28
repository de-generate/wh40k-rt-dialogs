import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from rt_dialogs import parse_export
from rt_dialogs.cli import main
from rt_dialogs.describe import clean_markup
from rt_dialogs.formats.common import decode_escapes, select_dialogs
from rt_dialogs.formats.labeled_script import label_name

from .test_cache import make_export


class LabeledScriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_export(self.root / "data")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(
                [
                    "output",
                    "labeled-script-single",
                    "--data",
                    str(self.root / "data"),
                    "--cache",
                    str(self.root / "dialogs.json"),
                    *args,
                ]
            )
        return code, err.getvalue()

    def test_render(self):
        out = self.root / "out.txt"
        code, _ = self.run_cli("--output-file", str(out))
        self.assertEqual(code, 0)
        text = out.read_text(encoding="utf-8")
        self.assertIn("Intro_dialog", text)
        self.assertIn("on start: StartEtude", text)
        # c1 is reached from the dialog start and again from c2 (loop) -> labeled section
        self.assertIn("[A] ---", text)
        self.assertIn("AbelardCompanion: Hello.", text)
        self.assertIn('if: not seen "Again."', text)
        self.assertIn("1. [Logic, Easy] Continue.   <Faith +5>", text)
        self.assertIn("CHECK [Logic, Easy]", text)
        self.assertIn("2. <missing text k-missing>", text)
        self.assertIn("(1 unreachable node not shown)", text)

    def test_lang_and_selection(self):
        out = self.root / "out.txt"
        code, err = self.run_cli(
            "--lang",
            "ruRU",
            "--dialogs",
            "Intro_dialog, Nope",
            "--output-file",
            str(out),
        )
        self.assertEqual(code, 0)
        self.assertIn("no dialog named 'Nope'", err)
        self.assertIn("AbelardCompanion: ru Hello.", out.read_text(encoding="utf-8"))

    def test_helpers(self):
        self.assertEqual(decode_escapes(r"a\n\tb\\n"), "a\n\tb\\n")
        self.assertEqual(
            [label_name(i) for i in (0, 25, 26, 27, 701, 702)],
            ["A", "Z", "AA", "AB", "ZZ", "AAA"],
        )
        self.assertEqual(
            clean_markup(
                '"Hi." {n}He nods.{/n} {g|Encyclopedia:X}Emperor{/g} {mf|his|her} {name}'
            ),
            '"Hi." *He nods.* Emperor his/her <Name>',
        )
        db = parse_export(self.root / "data", workers=2)
        self.assertEqual(len(select_dialogs(db, "skip-deleted")), 1)
        self.assertEqual(
            len(
                select_dialogs(
                    db, "Blueprints/World/Dialogs/Ch0/Intro/Intro_dialog.jbp"
                )
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
