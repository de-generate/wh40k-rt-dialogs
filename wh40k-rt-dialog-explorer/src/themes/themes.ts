// Theme registry. A theme is a CSS file in this folder that overrides Tailwind's color variables under
// `[data-theme="<id>"]` (imported by `index.css`); list it here to offer it in the picker.

export const themes = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
] as const;

export type ThemeId = (typeof themes)[number]["id"];

export const defaultTheme: ThemeId = "dark";

export function isTheme(id: unknown): id is ThemeId {
  return themes.some((t) => t.id === id);
}
