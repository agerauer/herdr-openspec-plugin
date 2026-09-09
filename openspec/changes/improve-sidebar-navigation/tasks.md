## 1. Adaptive layout

- [ ] 1.1 Add a pure main-view layout calculation that caps visible changes at 15, reserves the fixed detail/footer regions and a usable artifact area, degrades safely for short panes, and verify unit tests cover tall, medium, and minimum-height panes.
- [ ] 1.2 Use the calculated change and artifact windows in `draw_main`, keep the selected item visible as either list moves, and verify rendering-model tests cover selection near the beginning, middle, and end of lists.

## 2. Mouse interaction

- [ ] 2.1 Add testable rectangular hit-target registration that is rebuilt from rendered geometry on every draw, and verify unit tests cover matches, misses, overlapping boundaries, and targets clipped by pane width.
- [ ] 2.2 Enable curses mouse reporting and dispatch left-clicks on change rows to selection and artifact rows to the existing open-or-missing behavior, then verify tests cover existing artifacts, missing artifacts, and clicks outside targets.
- [ ] 2.3 Render main-view and viewer footer hints as individually clickable segments routed through shared semantic actions, and verify tests cover every visible hint plus omission of clipped hints.

## 3. Document scrolling

- [ ] 3.1 Separate viewer line scrolling from page scrolling, clamp both against the current wrapped document range, and verify unit tests cover one-line movement, one-page movement, and both boundaries.
- [ ] 3.2 Map viewer Up/Down and mouse-wheel events to line scrolling while retaining Page Up/Page Down as page scrolling, and verify input-dispatch tests distinguish all four paths.

## 4. Documentation and end-to-end verification

- [ ] 4.1 Update the README with the adaptive 15-change capacity, mouse controls, and line/page document navigation, and verify its controls table matches the implemented shortcuts.
- [ ] 4.2 Run `python3 -m unittest discover -s tests -v`, validate the OpenSpec change, and perform a live Herdr smoke test covering a 15-plus-change list, clickable changes/artifacts/footer actions, and one-line arrow/wheel document scrolling.
