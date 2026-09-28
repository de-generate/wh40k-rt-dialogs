import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from rt_dialogs.cli import main
from rt_dialogs.formats.explorer_bundle import VERSION, dialog_chapter, dialog_tags

from .test_cache import ABELARD, bp, loc, make_export, string

INTRO = "data/Blueprints/World/Dialogs/Ch0/Intro"


class ExplorerBundleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_export(self.root / "data")
        # c3 (the check's fail branch): nested OrAndLogic group, companion condition, Conditional action
        c3 = bp(
            "c3",
            "Cue",
            Text=loc("k-c2"),
            ShowOnceCurrentDialog=True,
            Conditions={
                "Operation": "And",
                "Conditions": [
                    {
                        "$type": "x, OrAndLogic",
                        "Not": True,
                        "ConditionsChecker": {
                            "Operation": "Or",
                            "Conditions": [
                                {
                                    "$type": "x, CompanionInParty",
                                    "Not": False,
                                    "m_companion": ABELARD,
                                    "MatchWhenActive": True,
                                    "MatchWhenDetached": False,
                                    "MatchWhenRemote": True,
                                    "MatchWhenEx": False,
                                    "IncludeDead": False,
                                },
                                {"$type": "x, PcFemale", "Not": False},
                            ],
                        },
                    },
                    {
                        "$type": "x, AnswerSelected",
                        "Not": False,
                        "m_Answer": "!bp_a1",
                        "CurrentDialog": True,
                    },
                ],
            },
            OnShow={
                "Actions": [
                    {
                        "$type": "x, Conditional",
                        "ConditionsChecker": {
                            "Operation": "And",
                            "Conditions": [{"$type": "x, PcMale", "Not": False}],
                        },
                        "IfTrue": {
                            "Actions": [
                                {"$type": "x, StartEtude", "Etude": "!bp_" + "e" * 32}
                            ]
                        },
                    }
                ]
            },
        )
        (self.root / INTRO / "Cue_0003.jbp").write_text(json.dumps(c3), encoding="utf-8")
        # a string without a ruRU text -> enGB fallback in the ruRU table
        s = string("k-c1", "Hello.", "AbelardCompanion")
        s["languages"] = [l for l in s["languages"] if l["locale"] != "ruRU"]
        p = self.root / "data/Strings/Blueprints/World/Dialogs/Ch0/Intro/Cue_0001_Text.json"
        p.write_text(json.dumps(s), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *args: str) -> tuple[int, str, dict]:
        out = self.root / "bundle.zip"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(
                [
                    "output",
                    "explorer-bundle",
                    "--data",
                    str(self.root / "data"),
                    "--cache",
                    str(self.root / "dialogs.json"),
                    "--output-file",
                    str(out),
                    *args,
                ]
            )
        files = {}
        if code == 0:
            with zipfile.ZipFile(out) as z:
                files = {n: json.loads(z.read(n)) for n in z.namelist()}
        return code, err.getvalue(), files

    def test_bundle(self):
        code, _, files = self.build()
        self.assertEqual(code, 0)
        self.assertEqual(
            sorted(files),
            [
                "dialogs/d1.json",
                "index.json",
                "manifest.json",
                "strings/enGB.json",
                "strings/ruRU.json",
            ],
        )
        manifest = files["manifest.json"]
        self.assertEqual(
            (manifest["format"], manifest["version"]),
            ("rt-dialogs-explorer-bundle", VERSION),
        )
        self.assertEqual(manifest["locales"], ["enGB", "ruRU"])
        self.assertEqual(manifest["companions"], ["AbelardCompanion"])
        self.assertEqual(manifest["counts"], {"dialogs": 1, "nodes": 7})

        self.assertEqual(
            files["index.json"]["dialogs"],
            [
                {
                    "id": "d1",
                    "name": "Intro_dialog",
                    "path": "World/Dialogs/Ch0/Intro",
                    "tags": ["Ch0", "Intro"],
                    "chapter": 0,
                    "source": "World",
                    "type": "Common",
                    "nodes": 7,
                    "speakers": ["AbelardCompanion"],
                }
            ],
        )

        d = files["dialogs/d1.json"]
        self.assertEqual(d["start"], {"alts": ["c1"]})
        self.assertEqual(d["actions"], {"start": ["StartEtude(eeeeeeee)"]})
        nodes = d["nodes"]
        self.assertNotIn("c4", nodes)  # unreachable
        self.assertEqual(
            nodes["c1"],
            {
                "kind": "cue",
                "text": "k-c1",
                "speaker": "AbelardCompanion",
                "if": {
                    "op": "and",
                    "items": [
                        {
                            "type": "CueSeen",
                            "not": True,
                            "label": 'not seen "Again."',
                            "node": "c2",
                            "dialog": "d1",
                            "text": "k-c2",
                        }
                    ],
                },
                "answers": ["l1"],
            },
        )
        self.assertEqual(nodes["l1"], {"kind": "answers", "answers": ["a1", "a2"]})
        self.assertEqual(
            nodes["a1"],
            {
                "kind": "answer",
                "text": "k-cont",
                "next": {"alts": ["ch1"]},
                "tag": "Logic, Easy",
                "soulMark": {"shift": {"dir": "Faith", "value": 5}},
            },
        )
        self.assertEqual(nodes["a2"]["text"], "k-missing")
        self.assertEqual(
            nodes["ch1"],
            {"kind": "check", "tag": "Logic, Easy", "success": "c2", "fail": "c3"},
        )
        self.assertEqual(nodes["c2"]["continue"], {"alts": ["l1"]})

        c3 = nodes["c3"]
        self.assertEqual(c3["once"], "dialog")
        self.assertEqual(
            c3["if"]["items"][0],
            {
                "op": "or",
                "not": True,
                "items": [
                    {
                        "type": "CompanionInParty",
                        "label": "AbelardCompanion in party",
                        "companion": "AbelardCompanion",
                        "match": ["active", "remote"],
                    },
                    {"type": "PcFemale", "label": "player is female"},
                ],
            },
        )
        selected = c3["if"]["items"][1]
        self.assertEqual(
            (selected["node"], selected["scope"], selected["text"]),
            ("a1", "dialog", "k-cont"),
        )
        self.assertEqual(
            c3["actions"], {"show": ["if player is male: StartEtude(eeeeeeee)"]}
        )

        en, ru = files["strings/enGB.json"], files["strings/ruRU.json"]
        self.assertEqual(
            en["dialogs"],
            {"d1": {"k-c1": "Hello.", "k-cont": "Continue.", "k-c2": "Again."}},
        )
        self.assertEqual(en["fallback"], [])
        self.assertEqual(ru["dialogs"]["d1"]["k-c1"], "Hello.")  # from enGB
        self.assertEqual(ru["dialogs"]["d1"]["k-c2"], "ru Again.")
        self.assertEqual(ru["fallback"], ["k-c1"])

    def test_locale_selection(self):
        code, err, files = self.build("--locales", "ruRU, xxXX")
        self.assertEqual(code, 0)
        self.assertIn("locale 'xxXX' not in the data", err)
        self.assertEqual(files["manifest.json"]["locales"], ["ruRU"])
        self.assertNotIn("strings/enGB.json", files)
        code, err, _ = self.build("--locales", "xxXX")
        self.assertEqual(code, 2)
        self.assertIn("no valid locale", err)

    def test_tags(self):
        self.assertEqual(
            dialog_tags("DLC/DLC1/Narrative/Bridge/MasterOfDiscipline", "MasterOfDiscipline"),
            ["DLC1", "Bridge"],
        )
        self.assertEqual(
            dialog_tags("World/Dialogs/Ch2_VS/Area/Foo", "Foo"), ["Ch2_VS", "Area"]
        )
        self.assertEqual(dialog_chapter(["Ch2_VS", "Area"]), 2)
        self.assertEqual(dialog_chapter(["TravelPrompts", "Chapter3"]), 3)
        self.assertIsNone(dialog_chapter(["Companions", "Chorus"]))


if __name__ == "__main__":
    unittest.main()
