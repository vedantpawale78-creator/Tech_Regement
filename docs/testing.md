# Testing Strategy

Testing is conducted using the `pytest` framework.

- **Rules Engine**: Unit tests validate geometric intersections, polygon point tests, and time-based duration thresholds.
- **Alert Manager**: Tests validate suppression logic (confidence, track age, cooldowns).
- **Database**: Tests validate schema creation, insertion, and retrieval of records.
- **Configuration**: Tests validate robust loading and missing file handling.

Run tests using: `pytest -v`
