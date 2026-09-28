"""Tests against a tiny synthetic export. Run with: python -m unittest discover tests"""

import json
import tempfile
import unittest
from pathlib import Path

from rt_dialogs import (
    Answer,
    AnswersList,
    Check,
    Cue,
    ExportError,
    load_cache,
    load_or_build,
    parse_export,
    save_cache,
)

TYPE = {
    "Dialog": "c8ff, BlueprintDialog",
    "Cue": "8eee, BlueprintCue",
    "Answer": "df78, BlueprintAnswer",
    "AnswersList": "52ca, BlueprintAnswersList",
    "Check": "ab80, BlueprintCheck",
    "Banter": "0aa1, BlueprintBarkBanter",
}
ABELARD = "!bp_51604d37ac0e499da70e2c4a4f086066"


def loc(key="", shared=None, path=""):
    return {
        "m_Key": key,
        "m_OwnerString": "",
        "m_OwnerPropertyPath": "",
        "m_JsonPath": path,
        "Shared": {"assetguid": "ff" * 16, "stringkey": shared} if shared else None,
    }


def cues(*ids, strategy="First"):
    return {"Cues": [f"!bp_{i}" for i in ids], "Strategy": strategy}


def bp(aid, kind, deleted=False, **data):
    return {
        "AssetId": aid,
        "Data": {
            "$type": TYPE[kind],
            "PrototypeLink": "",
            "m_Overrides": [],
            "Components": [],
            "Author": "x",
            "Comment": "",
            **data,
        },
        "Meta": {"ShadowDeleted": deleted},
    }


def string(key, en, speaker=None, sound=None):
    langs = [{"locale": "ruRU", "text": "ru " + en}, {"locale": "enGB", "text": en}]
    if sound:
        langs.append({"locale": "Sound", "text": sound})
    s = {
        "source": "ruRU",
        "key": key,
        "ownerGuid": "x",
        "languages": langs,
        "string_traits": [{"trait": "VO", "trait_date": "", "locale_text": ""}],
    }
    if speaker:
        s["speaker"] = speaker
    return s


def make_export(root: Path) -> None:
    d = root / "Blueprints/World/Dialogs/Ch0/Intro"
    files = {
        d / "Intro_dialog.jbp": bp(
            "d1",
            "Dialog",
            FirstCue=cues("c1"),
            Type="Common",
            Conditions={"Operation": "And", "Conditions": []},
            StartActions={
                "Actions": [
                    {
                        "$type": "aa, StartEtude",
                        "name": "$StartEtude$1",
                        "Etude": "!bp_" + "e" * 32,
                    }
                ]
            },
            FinishActions={"Actions": []},
            TurnPlayer=True,
            IsNarratorText=False,
        ),
        d / "Cue_0001.jbp": bp(
            "c1",
            "Cue",
            Text=loc("k-c1", path="Strings/Mechanics/Blueprints\\World\\x.json"),
            Speaker={"m_Blueprint": ABELARD, "NoSpeaker": False},
            Answers=["!bp_l1"],
            Continue=cues(),
            Animation="None",
            TurnSpeaker=True,
            Conditions={
                "Operation": "And",
                "Conditions": [
                    {
                        "$type": "cc, CueSeen",
                        "name": "$CueSeen$1",
                        "Not": True,
                        "m_Cue": "!bp_c2",
                    }
                ],
            },
            SoulMarkShift={"Direction": "None", "Value": 0},
        ),
        d / "AnswersList_0001.jbp": bp(
            "l1",
            "AnswersList",
            ParentAsset="c1",
            Answers=["!bp_a1", "!bp_a2"],
            Conditions={"Operation": "And", "Conditions": []},
        ),
        d / "Answer_0001.jbp": bp(
            "a1",
            "Answer",
            Text=loc(shared="k-cont"),
            NextCue=cues("ch1"),
            ShowCheck={"Type": "SkillLogic", "Difficulty": "Easy", "DC": 30},
            CharacterSelection={"SelectionType": "Clear", "ComparisonStats": []},
            SoulMarkShift={"Direction": "Faith", "Value": 5},
            AddToHistory=True,
        ),
        d / "Answer_0002.jbp": bp(
            "a2", "Answer", Text=loc("k-missing"), NextCue=cues()
        ),
        d / "Check_0001.jbp": bp(
            "ch1",
            "Check",
            Type="SkillLogic",
            DC=30,
            Difficulty="Easy",
            m_Success="!bp_c2",
            m_Fail="!bp_c3",
        ),
        d / "Cue_0002.jbp": bp(
            "c2", "Cue", Text=loc("k-c2"), Continue=cues("l1")
        ),  # loops back
        d / "Cue_0003.jbp": bp("c3", "Cue", Text=loc("k-c2")),
        d / "Cue_old.jbp": bp(
            "c4", "Cue", deleted=True, Text=loc("k-gone")
        ),  # unreachable + deleted
        root / "Blueprints/World/Dialogs/Banters/B1.jbp": bp(
            "b1",
            "Banter",
            m_Unit=ABELARD,
            m_Weight=1.0,
            FirstPhrase=[loc(shared="k-b1")],
            StrategySelectingResponse="Random",
            Conditions={
                "Unique": True,
                "MinChapter": 1,
                "ExtraConditions": {"Operation": "Or", "Conditions": []},
            },
            Responses=[
                {
                    "m_Unit": ABELARD,
                    "m_Weight": 0.0,
                    "Response": loc("k-b2"),
                    "ResponseCondition": {"Operation": "And", "Conditions": []},
                }
            ],
        ),
    }
    strings = {
        "World/Dialogs/Ch0/Intro/Cue_0001_Text.json": string(
            "k-c1", "Hello.", "AbelardCompanion", "VO_1"
        ),
        "World/Dialogs/Ch0/Intro/Cue_0002_Text.json": string("k-c2", "Again."),
        "World/Dialogs/CommonStrings/Continue_String.json": string(
            "k-cont", "Continue."
        ),
        "DLC/DLC1/Narrative/Banters/B1_String.json": string("k-b1", "Banter!"),
        "World/Dialogs/Banters/B1_Responses.json": string("k-b2", "Reply."),
    }
    for p, data in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data), encoding="utf-8")
    for rel, data in strings.items():
        p = root / "Strings/Blueprints" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_export(self.root / "data")

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse(self):
        db = parse_export(self.root / "data", workers=2)
        self.assertEqual(len(db.dialogs), 1)
        dlg = db.dialogs[0]
        self.assertEqual(
            (dlg.name, dlg.source, dlg.first_cue.cues),
            ("Intro_dialog", "World", ["c1"]),
        )
        self.assertEqual(dlg.start_actions[0].type, "StartEtude")
        self.assertEqual(dlg.start_actions[0].params, {"Etude": "!bp_" + "e" * 32})
        self.assertNotIn("TurnPlayer", dlg.extra)

        c1 = dlg.nodes["c1"]
        self.assertIsInstance(c1, Cue)
        self.assertEqual(c1.text.texts, {"ruRU": "ru Hello.", "enGB": "Hello."})
        self.assertEqual(c1.text.voice_over, "VO_1")
        self.assertEqual(
            (c1.speaker.name, c1.speaker.name_source), ("AbelardCompanion", "string")
        )
        self.assertEqual(c1.answers, ["l1"])
        cond = c1.conditions.conditions[0]
        self.assertEqual(
            (cond.type, cond.negated, cond.params),
            ("CueSeen", True, {"m_Cue": "!bp_c2"}),
        )
        self.assertIsNone(c1.soul_mark_shift)

        a1 = dlg.nodes["a1"]
        self.assertIsInstance(a1, Answer)
        self.assertTrue(a1.text.shared)
        self.assertEqual(a1.text.text(), "Continue.")
        self.assertEqual((a1.skill_check.type, a1.skill_check.dc), ("SkillLogic", 30))
        self.assertEqual(a1.soul_mark_shift.direction, "Faith")
        self.assertIsNone(a1.character_selection)
        self.assertTrue(dlg.nodes["a2"].text.missing)
        self.assertIsInstance(dlg.nodes["ch1"], Check)
        self.assertIsInstance(dlg.nodes["l1"], AnswersList)

        # speaker via the blueprint map (c2's string has no speaker, but no blueprint either)
        self.assertIsNone(dlg.nodes["c2"].speaker.name)
        self.assertTrue(
            all(
                dlg.nodes[i].reachable
                for i in ("c1", "l1", "a1", "a2", "ch1", "c2", "c3")
            )
        )
        self.assertFalse(dlg.nodes["c4"].reachable)
        self.assertTrue(dlg.nodes["c4"].deleted)

        banter = db.banters[0]
        self.assertEqual(banter.speaker, "AbelardCompanion")  # from speaker map
        self.assertEqual(
            banter.first_phrases[0].text(), "Banter!"
        )  # DLC folder, shared ref
        self.assertEqual(banter.responses[0].speaker, "AbelardCompanion")
        self.assertEqual(
            (banter.unique, banter.min_chapter, banter.conditions.operation),
            (True, 1, "Or"),
        )
        self.assertEqual(
            db.speakers, {"51604d37ac0e499da70e2c4a4f086066": "AbelardCompanion"}
        )
        self.assertTrue(any("k-missing" in i for i in db.issues))

    def test_roundtrip(self):
        db = parse_export(self.root / "data", workers=2)
        cache = self.root / "dialogs.json"
        save_cache(db, cache)
        self.assertEqual(load_cache(cache), db)
        self.assertTrue(
            cache.read_text(encoding="utf-8").startswith('{\n "schema_version": 1,')
        )

    def test_load_or_build_detects_changes(self):
        cache = self.root / "dialogs.json"
        log = []
        db1 = load_or_build(self.root / "data", cache, progress=log.append)
        self.assertTrue(any(m.startswith("found ") for m in log))  # parsed the export
        log.clear()
        self.assertEqual(
            load_or_build(self.root / "data", cache, progress=log.append), db1
        )
        self.assertEqual(log, [])  # served from the cache
        s = (
            self.root
            / "data/Strings/Blueprints/World/Dialogs/Ch0/Intro/Cue_0002_Text.json"
        )
        s.write_text(json.dumps(string("k-c2", "Changed text.")), encoding="utf-8")
        db2 = load_or_build(self.root / "data", cache, progress=log.append)
        self.assertTrue(any("changed" in m for m in log))
        self.assertEqual(db2.dialogs[0].nodes["c2"].text.text(), "Changed text.")

    def test_duplicate_asset_ids_fail(self):
        src = self.root / "data/Blueprints/World/Dialogs/Ch0/Intro"
        dst = self.root / "data/Blueprints/World/Dialogs/Copy/Intro"
        dst.mkdir(parents=True)
        for f in src.iterdir():
            (dst / f.name).write_bytes(f.read_bytes())
        with self.assertRaises(ExportError):
            parse_export(self.root / "data", workers=2)


if __name__ == "__main__":
    unittest.main()
