import { describe, expect, it } from "vitest";
import { parseMarkup, plainText } from "./markup";

describe("parseMarkup", () => {
  it("marks narration and keeps glossary text", () => {
    expect(parseMarkup('{n}She nods.{/n} "See the {g|Encyclopedia:Warp}warp{/g}."')).toEqual([
      { t: "text", text: "She nods.", narration: true },
      { t: "text", text: ' "See the ', narration: false },
      { t: "text", text: "warp", narration: false },
      { t: "text", text: '."', narration: false },
    ]);
  });

  it("parses gendered text, placeholders and breaks", () => {
    expect(parseMarkup("Your {mf|Lordship|Ladyship}, {name}!{br}{petName}")).toEqual([
      { t: "text", text: "Your ", narration: false },
      { t: "variants", tag: "mf", options: ["Lordship", "Ladyship"], narration: false },
      { t: "text", text: ", ", narration: false },
      { t: "placeholder", name: "name", narration: false },
      { t: "text", text: "!", narration: false },
      { t: "break" },
      { t: "placeholder", name: "pet name", narration: false },
    ]);
  });

  it("keeps other variants and unknown markup", () => {
    expect(plainText("{nc|her|his} {nc|seen|}")).toBe("her/his seen/");
    expect(plainText("a {x|y} {zz} b")).toBe("a {x|y} {zz} b");
  });
});

describe("plainText", () => {
  it("strips markup and keeps both gender variants", () => {
    expect(plainText("{n}Hi{/n} {mf|sir|madam}, {name}.")).toBe("Hi sir/madam, <name>.");
  });
});
