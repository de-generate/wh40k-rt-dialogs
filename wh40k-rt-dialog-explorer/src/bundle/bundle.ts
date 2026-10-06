import { BlobReader, TextWriter, ZipReader, configure, type Entry } from "@zip.js/zip.js";
import { BUNDLE_FORMAT, SUPPORTED_VERSION, type Dialog, type Index, type Manifest, type Strings } from "./types";

// Entries are small enough for the main thread; the native DecompressionStream does the work.
configure({ useWebWorkers: false, useCompressionStream: true });

export class BundleError extends Error {}

/** An opened bundle zip. Reads single entries on demand; only the central directory is read up front. */
export class Bundle {
  private dialogCache = new Map<string, Promise<Dialog>>();

  private constructor(
    private entries: Map<string, Entry>,
    readonly manifest: Manifest,
    readonly index: Index,
  ) {}

  static async open(blob: Blob): Promise<Bundle> {
    let list: Entry[];
    try {
      list = await new ZipReader(new BlobReader(blob)).getEntries();
    } catch {
      throw new BundleError("This file is not a zip archive.");
    }
    const entries = new Map(list.map((e) => [e.filename, e]));
    const manifest = await readJson<Manifest>(entries, "manifest.json").catch(() => null);
    if (!manifest || manifest.format !== BUNDLE_FORMAT) {
      throw new BundleError("This zip is not an explorer bundle (no valid manifest.json).");
    }
    if (manifest.version !== SUPPORTED_VERSION) {
      throw new BundleError(
        `Bundle version ${manifest.version} is not supported (expected ${SUPPORTED_VERSION}). ` +
          "Re-export it with a matching extractor: python -m rt_dialogs output explorer-bundle",
      );
    }
    const index = await readJson<Index>(entries, "index.json");
    return new Bundle(entries, manifest, index);
  }

  dialog(id: string): Promise<Dialog> {
    let p = this.dialogCache.get(id);
    if (!p) {
      p = readJson<Dialog>(this.entries, `dialogs/${id}.json`);
      p.catch(() => this.dialogCache.delete(id));
      this.dialogCache.set(id, p);
    }
    return p;
  }

  strings(locale: string): Promise<Strings> {
    return readJson<Strings>(this.entries, `strings/${locale}.json`);
  }
}

async function readJson<T>(entries: Map<string, Entry>, name: string): Promise<T> {
  const entry = entries.get(name);
  if (!entry || entry.directory) throw new BundleError(`The bundle has no ${name}.`);
  return JSON.parse(await entry.getData(new TextWriter())) as T;
}
