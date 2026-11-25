# RelayNest design system

The current visual source is the supplied “Merged: Linear × Relay” HTML and screenshot. The application implements its tokens in `desktop/styles.css`; that file is the source of truth for dark and light themes.

## Direction and tokens

Use the compact, dark-first workspace, the 220 px sidebar, 760 px maximum content width, indigo accents, fine borders, 36 px controls and 6/10/11 px control, card and chip radii from the supplied design. The type scale is 13 px body, 12 px supporting text, 11 px chips, 16 px section titles and 24 px page titles. Inter and JetBrains Mono are preferred when available, with system and monospace fallbacks so the app works without network font downloads.

## Layout and behavior

- The Transfer page has Receive and Send cards, a directional device flow and the corresponding form. Display the current status and provide access to the Activity page during and after a session.
- The Activity page shows actual current-session output and state, with an honest empty state. It does not invent sample history or imply persisted history.
- The Settings page offers light and dark appearance, plus default port and destination controls. These settings last for the current window session. File skipping is an always-on behavior, not an unsupported toggle.
- Preserve native folder browsing, sender network warning, real process state, cancel/stop actions and validation. Do not fabricate progress, completion or connection details.
- Navigation, inputs and actions are keyboard-operable, have visible focus, readable labels and responsive layouts. Use text for status in addition to color; support reduced-motion preferences.
- Dark is the default. Theme tokens, not hard-coded per-component colors, control both themes.

## Verification

Check Receive, Send, Activity, Settings, validation, active and failure states, keyboard navigation, narrow layouts, and both themes. Check live desktop transfers separately from browser-only visual tests. The current implementation uses local/system font fallbacks when the named fonts are not installed.
