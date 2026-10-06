// The game's inline text markup (DIALOG_STRUCTURE.md §5.5).

export type Segment =
  | { t: "text"; text: string; narration: boolean }
  // {mf|male|female} and other variant tags like {nc|a|b}: the game picks one; we show all.
  | { t: "variants"; tag: string; options: string[]; narration: boolean }
  | { t: "placeholder"; name: string; narration: boolean }
  | { t: "break" };

const TAG = /\{(\/?)([A-Za-z]+)((?:\|[^{}|]*)*)\}/g;

const PLACEHOLDERS: Record<string, string> = { name: "name", petname: "pet name" };

export function parseMarkup(text: string): Segment[] {
  const out: Segment[] = [];
  let narration = false;
  let last = 0;
  const pushText = (s: string) => {
    if (s) out.push({ t: "text", text: s, narration });
  };
  for (const m of text.matchAll(TAG)) {
    const [raw, close, rawTag, rawArgs] = m;
    const tag = rawTag.toLowerCase();
    const args = rawArgs ? rawArgs.slice(1).split("|") : [];
    pushText(text.slice(last, m.index));
    last = m.index + raw.length;
    if (tag === "n") narration = !close;
    else if (tag === "g" || tag === "d") {
      // Glossary links: keep only the inner text.
    } else if (!close && args.length >= 2) {
      out.push({ t: "variants", tag, options: args, narration });
    } else if (tag === "br" && !close) out.push({ t: "break" });
    else if (tag in PLACEHOLDERS && !close && args.length === 0) {
      out.push({ t: "placeholder", name: PLACEHOLDERS[tag], narration });
    } else pushText(raw);
  }
  pushText(text.slice(last));
  return out;
}

/** Plain text for searching and snippets; variant text keeps all options. */
export function plainText(text: string): string {
  return parseMarkup(text)
    .map((s) => {
      switch (s.t) {
        case "text":
          return s.text;
        case "variants":
          return s.options.join("/");
        case "placeholder":
          return `<${s.name}>`;
        case "break":
          return " ";
      }
    })
    .join("");
}
