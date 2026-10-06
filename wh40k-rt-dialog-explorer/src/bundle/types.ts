// Types of the explorer bundle, version 1 (../wh40k-rt-dialog-extractor/EXPLORER_BUNDLE.md).
// Optional fields are omitted by the extractor when they have their default value.

export const SUPPORTED_VERSION = 1;
export const BUNDLE_FORMAT = "rt-dialogs-explorer-bundle";

export interface Manifest {
  format: string;
  version: number;
  generatedAt: string;
  sourceFingerprint: string;
  locales: string[];
  fallbackLocale: string;
  companions: string[];
  counts: { dialogs: number; nodes: number };
}

export interface IndexEntry {
  id: string;
  name: string;
  path: string;
  tags?: string[];
  chapter?: number;
  source: string;
  type: string;
  deleted?: boolean;
  nodes?: number;
  speakers?: string[];
}

export interface Index {
  dialogs: IndexEntry[];
}

export interface Strings {
  locale: string;
  dialogs: Record<string, Record<string, string>>;
  fallback?: string[];
}

// §6 conditions

export interface ConditionGroup {
  op: "and" | "or";
  not?: boolean;
  items: Condition[];
}

export interface ConditionLeaf {
  type: string;
  not?: boolean;
  label: string;
  node?: string;
  dialog?: string;
  text?: string;
  scope?: "dialog";
  companion?: string;
  [field: string]: unknown;
}

export type Condition = ConditionGroup | ConditionLeaf;

export function isGroup(c: Condition): c is ConditionGroup {
  return "op" in c;
}

// §5 dialogs and nodes

export interface CueList {
  alts: string[];
  random?: boolean;
}

export type Actions = Record<string, string[]>;
export type Once = "dialog" | "always";

export interface SoulMark {
  shift?: { dir: string; value?: number };
  requires?: { dir: string; value?: number; rank?: number };
}

interface NodeBase {
  comment?: string;
  deleted?: boolean;
  actions?: Actions;
  once?: Once;
  if?: ConditionGroup;
  soulMark?: SoulMark;
}

export interface CueNode extends NodeBase {
  kind: "cue";
  text?: string;
  speaker?: string;
  narrator?: boolean;
  continue?: CueList;
  answers?: string[];
}

export interface AnswersNode extends NodeBase {
  kind: "answers";
  answers?: string[];
}

export interface AnswerNode extends NodeBase {
  kind: "answer";
  text?: string;
  next?: CueList;
  show?: ConditionGroup;
  select?: ConditionGroup;
  tag?: string;
  fakeTags?: string[];
  by?: string;
}

export interface CheckNode extends NodeBase {
  kind: "check";
  tag?: string;
  hidden?: boolean;
  success?: string;
  fail?: string;
}

export interface SequenceNode extends NodeBase {
  kind: "sequence";
  cues?: string[];
  exit?: string;
}

export interface ExitNode extends NodeBase {
  kind: "exit";
  answers?: string[];
  continue?: CueList;
}

export interface PageNode extends NodeBase {
  kind: "page";
  cues?: string[];
  answers?: string[];
}

export type DialogNode = CueNode | AnswersNode | AnswerNode | CheckNode | SequenceNode | ExitNode | PageNode;

export interface Dialog {
  id: string;
  name: string;
  deleted?: boolean;
  comment?: string;
  if?: ConditionGroup;
  start?: CueList;
  actions?: Actions;
  nodes?: Record<string, DialogNode>;
}
