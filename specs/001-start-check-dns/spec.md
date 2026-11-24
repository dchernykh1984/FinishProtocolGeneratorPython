# Feature Specification: A rider who missed the start check is DNS, and Disable DNS

**Feature Branch**: `docs/specifications`

**Created**: 2026-11-24

**Status**: Implemented in this pull request

**Input**: The maintainer, 2026-11-24: a rider without a mark in the start check list is not to
be disqualified but to be DNS, a status of its own; the protocol lists finishers, then DNF, then
DNS, with DSQ last; and a "Disable DNS" checkbox is needed beside the others.

**Decisions (maintainer, 2026-11-24)**:

- A rider without a valid start check mark who rode is still DNS, but his laps and his time stay
  in his row.
- A rider without a check mark who also has a DSQ mark is DSQ.
- "Disable DNS" means nobody is DNS: a rider without a check mark is scored as if he had one,
  and a rider whose start was never seen is DNF instead of DNS -- what "Disable DNF (everyone
  counts as finished)" is for the finish.

## User Scenarios & Testing

### User Story 1 - A rider who missed the start check is DNS (Priority: P1)

At a race with a start check list -- every rider is marked at the start before he goes -- the
referee generates the protocol. A rider with no mark in the check list later than his start
minus the registration period did not pass the start check. Today he is disqualified; he becomes
DNS instead, and the protocol lists him after the riders who did not finish and before the
disqualified ones. If he rode, his laps and his time stay in his row, so the referee can see
what he did.

**Why this priority**: A rider who did not pass the start check did not start as far as the
regulations go; he broke no rule on the course, and DSQ says that he did.

**Independent Test**: A group with the check list on: a finisher, a rider who started and did
not finish, a rider who rode and finished without a check mark, and a rider with a DSQ mark. The
protocol lists them 1, DNF, DNS with his laps and time, DSQ.

**Acceptance Scenarios**:

1. **Given** the check list is on and holds marks, and rider 12 has none later than his start
   minus the registration period, **When** the protocol is generated, **Then** his place column
   says DNS, he is not disqualified, and the log has the ERROR that 12 did not pass start
   registration.
2. **Given** rider 12 rode both his laps and has a finish mark, **When** the protocol is
   generated, **Then** his row shows both laps and his time, his place column says DNS, and no
   place number is spent on him.
3. **Given** rider 12 also has a DSQ mark, **When** the protocol is generated, **Then** he is
   DSQ.
4. **Given** a table with finishers, riders who did not finish, DNS riders and DSQ riders,
   **When** the protocol is generated, **Then** they come in that order, whatever laps each of
   them rode.
5. **Given** the check list holds no mark at all, **When** the protocol is generated, **Then**
   nobody is DNS because of it, as today.

---

### User Story 2 - Disable DNS (Priority: P2)

The referee ticks "Disable DNS" beside "Disable DNF" and "Disable DSQ". Nobody is DNS then: a
rider without a check mark is scored as if he had one, and a rider whose start was never seen is
DNF instead of DNS. The setting is kept with the race.

**Why this priority**: Like "Disable DNF" for the finish, it lets a meeting that does not want
DNS on its paper show every rider as started, without taking the start check list out of the
race.

**Independent Test**: The same group with the setting on: the rider without a check mark is
placed among the finishers by his result; a rider of a group that never started reads DNF.

**Acceptance Scenarios**:

1. **Given** "Disable DNS" is on and rider 12 has no check mark, **When** the protocol is
   generated, **Then** he is placed by his laps and time like every other rider, and the log
   still reports that he did not pass start registration.
2. **Given** "Disable DNS" is on and a rider's start was never seen -- his group has no start
   time, or in Custom Start he has no mark -- **When** the protocol is generated, **Then** he is
   DNF.
3. **Given** the setting is on and the race is saved, **When** the program is started again,
   **Then** the setting is still on; a race info file written before the setting existed loads
   with it off.

---

### Edge Cases

- A DNS rider who rode is printed under the same settings as any other DNS row: only with "Print
  DNS".
- A DNS rider takes no place in his group anywhere: not in the place column, not in brackets in
  the absolute protocol, not in the seeding protocol for the finals. Nor is he the leader that
  gaps are measured from; his own time stays, without a gap -- a gap measures a place -- even
  when nobody else finished.
- His laps still count in the lap statistics -- each lap's gap and rank -- as every rider's laps
  do there, a DNF's and a DSQ's included.
- Custom Start and Number of Tries check the start the same way, against the rider's first mark.
- With "Disable DSQ" a DSQ mark disqualifies nobody, so a rider without a check mark who has one
  is DNS.
- Eliminator Finals reads no start check list, and "Disable DNS" leaves it alone: there DNS says
  that a heat has not started yet, and DNF would claim it was ridden.

## Requirements

### Functional Requirements

- **FR-001**: With the start check list on and holding marks, a rider with no mark in it later
  than his start minus the registration period MUST be DNS, not DSQ, unless "Disable DNS" is on.
- **FR-002**: The rows of every table MUST go finishers first, then DNF, then DNS, then DSQ;
  inside each status the order MUST stay what it is today.
- **FR-003**: A DNS rider from the start check MUST keep the laps and the result time he rode in
  his row, MUST NOT take a place number -- in the place column, in brackets in the absolute
  protocol or in the seeding protocol -- and MUST be printed only when a DNS row is.
- **FR-004**: A rider disqualified by a DSQ mark MUST be DSQ whatever the start check says.
- **FR-005**: A setting "Disable DNS" MUST sit beside "Disable DNF" and "Disable DSQ". When it
  is on, no rider is DNS: the start check makes nobody DNS, and a rider whose start was never
  seen MUST be DNF and be printed as a DNF row is.
- **FR-006**: The setting MUST be saved with the race after every setting saved today, and a
  race info file without it MUST load with it off.
- **FR-007**: The log MUST keep reporting a rider who did not pass the start registration,
  whether or not "Disable DNS" is on.
- **FR-008**: The site document MUST show the same status as the HTML protocol; the live
  statistics MUST leave a DNS of the start check out of their numbering, gaps and packs, as they
  leave out a DSQ, and say DNS for his place.

### Key Entities

- **Rider status**: finisher, DNF, DNS or DSQ, decided once for every view of the protocol. A
  rider who missed the start check is DNS while still carrying the laps he rode.
- **Disable DNS**: a setting of the race, off by default, stored with the others.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In a race with a start check list, every rider without a valid check mark reads
  DNS and none of them reads DSQ, unless he has a DSQ mark.
- **SC-002**: In every table the statuses come in the order finishers, DNF, DNS, DSQ, with no
  exception.
- **SC-003**: With "Disable DNS" on, no row of a timed race's protocols reads DNS.
- **SC-004**: A race without a start check list and without "Disable DNS" generates the very
  same protocols as before, byte for byte.
- **SC-005**: The setting survives a save and a restart of the program.

## Assumptions

- "Disable DNF" does not undo a DNS from the start check: DNS says he did not start, which
  everyone counting as finished does not change. Only "Disable DNS" does.
- Inside the DNS status riders keep today's order: more laps first, then the time; riders who
  rode nothing by start delay, then by number.
- In the live statistics a DNS of the start check is left out as a DSQ rider is, before and
  after this feature alike: ranked after everyone still on the course, he would hand the last of
  them a gap to a rider laps ahead.
