## Why

The `sidebar-navigation` spec ends its mouse-capture requirement with "The sidebar SHALL NOT request mouse-motion reporting." That clause is factually wrong about the platform and it contradicts two requirements in the same spec: "reliably scroll in both directions ... for each recognized mouse-wheel step" and "the terminal reports **any supported encoding** of one downward mouse-wheel step."

On an ncurses built with mouse version 1 — macOS system ncurses, which every `python3` on the target machine links — there is no representation for button 5, so a wheel-down step is reported carrying the motion bit. Requesting motion reporting is therefore the only way `getmouse()` can decode a downward step at all; without it ncurses raises and the event is dropped. Obeying the clause made the other two requirements unsatisfiable and left wheel-down silently dead, while wheel-up kept working. Instrumenting the running pane showed 369 mouse events: 248 decoded upward steps and 118 downward steps that failed to decode at all.

The clause was introduced on the belief that motion reporting was unused. It was load-bearing.

## What Changes

- Correct the mouse-capture requirement so it no longer forbids motion reporting, and instead requires the sidebar to request whatever mouse events its platform needs to recognise a wheel step in **both** directions.
- Keep the rest of that requirement unchanged: the toggle still suspends and restores mouse handling, still frees the terminal's own selection while suspended, and is still advertised in the footer. Releasing the mouse for text selection remains the toggle's job — it was never the reason to drop motion reporting.
- No change to the scrolling requirements; this removes the conflict that made them impossible to satisfy.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `sidebar-navigation`: the "Mouse capture can be toggled for terminal selection" requirement drops its prohibition on mouse-motion reporting and instead requires requesting the events needed to decode wheel steps in both directions.

## Impact

- `openspec/specs/sidebar-navigation/spec.md`: one requirement's text, via this change's delta.
- No code change: `sidebar.py` was already corrected in commit `9548d61`, which restored the motion bit to the requested mouse mask and to the wheel-down set, and updated the test that had asserted the broken behaviour. This change brings the spec back in line with the code and with the platform.
- No dependencies, no user-visible behaviour change beyond wheel-down working again.
