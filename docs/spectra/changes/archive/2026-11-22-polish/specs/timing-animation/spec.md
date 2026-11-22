## Purpose

Make overtakes and pit-stop shuffles visible in the timing list by moving rows instead of redrawing them.

## ADDED Requirements

### Requirement: Animated position changes

When the order of drivers changes between displayed laps, the timing list SHALL animate each row to its new place with ease `cubic-bezier(0.2, 1, 0.2, 1)` over 0.75 s, and SHALL NOT animate rows whose position did not change.

#### Scenario: Two drivers swap

- **WHEN** P3 and P4 swap between lap 20 and lap 21
- **THEN** only those two rows animate
