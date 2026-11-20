## Purpose

Show the end-of-race Wrapped as full-screen story cards and let the viewer download them as Instagram-story-sized images to share how their model performed.

## ADDED Requirements

### Requirement: Wrapped entry point

The status bar SHALL show a "Wrapped" button that is disabled with a lock icon while the lap is lower than `total_laps` and enabled at the final lap. Clicking it SHALL request `/wrapped` for the current race, final lap, and focus driver, and open a full-screen overlay.

#### Scenario: Unlock at the final lap

- **WHEN** the replay moves from lap 57 to lap 58 of a 58-lap race
- **THEN** the button changes from locked to enabled

### Requirement: Story card sequence

The overlay SHALL show 7 cards in this order: Summary, Podium Call, Accuracy, Best Call, Biggest Miss, Biggest Moment, Driver, with 7 progress segments at the top. Right arrow or a click on the right half SHALL go to the next card, Left arrow or a click on the left half to the previous card, and Esc SHALL close the overlay. Each card SHALL use its accent colour from the design and the footer `AUGUR · <model name> by <author> · <event name> <year>`. A null highlight SHALL show "No resolved calls this race" (Best Call, Biggest Miss) or "No events this race" (Biggest Moment), and a null podium skill SHALL show "Order never changed — nothing to beat".

#### Scenario: Navigation bounds

- **WHEN** the viewer presses keys in the open overlay
- **THEN** the card changes as listed below

##### Example: key presses

| Current card | Input | Result |
| ------------ | ----- | ------ |
| 1 | Left arrow | stays on card 1 |
| 1 | Right arrow | card 2 |
| 7 | Right arrow | stays on card 7 |
| any | Esc | overlay closes |

#### Scenario: Accuracy card

- **WHEN** `score.position_skill_pct` is -3.2 and `score.lap_improvement_pct` is 12.5
- **THEN** the Accuracy card uses the `#f12f32` accent and reads "Podium calls: 3.2% worse than current order" and "Lap times: beat baseline by 12.5%"

#### Scenario: Podium Call card

- **WHEN** `podium_call` is lap 29, predicted VER, NOR, LEC, `correct` 2
- **THEN** the card reads "At lap 29 AUGUR's podium was VER, NOR, LEC — 2 of 3 correct" and shows each predicted driver's podium probability

### Requirement: Story card download

"Download card" SHALL save the current card as a 1080×1920 PNG named `augur-wrapped-<race_id>-<n>-<card>.png` after web fonts finish loading.

#### Scenario: Card export size

- **WHEN** the viewer clicks "Download card" on card 4 of `2024-24-abu-dhabi-grand-prix`
- **THEN** a PNG of 1080×1920 pixels named `augur-wrapped-2024-24-abu-dhabi-grand-prix-4-best-call.png` is saved
