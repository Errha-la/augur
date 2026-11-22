# wrapped-zip-export Specification

## Purpose

Let the viewer save every Wrapped card in one click.

## Requirements

### Requirement: Download all cards

The Wrapped overlay SHALL offer "Download all", which saves `augur-wrapped-<race_id>.zip` containing all 7 cards as 1080×1920 PNGs named as for single-card download.

#### Scenario: Zip contents

- **WHEN** the viewer clicks "Download all" for `2024-24-abu-dhabi-grand-prix`
- **THEN** `augur-wrapped-2024-24-abu-dhabi-grand-prix.zip` contains 7 PNG files from `augur-wrapped-2024-24-abu-dhabi-grand-prix-1-summary.png` to `augur-wrapped-2024-24-abu-dhabi-grand-prix-7-driver.png`
