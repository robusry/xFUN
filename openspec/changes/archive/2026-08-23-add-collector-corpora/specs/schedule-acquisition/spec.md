## MODIFIED Requirements

### Requirement: Broadcast providers resolve from per-match data before league-level rights

Provider resolution SHALL consult per-match data from the schedule source first. Where the
source names no provider for a match, resolution SHALL fall back to a configured
`league -> US providers` rights table. Where neither answers, availability SHALL be
`unknown`. The rights table SHALL record, per entry, the date on which it was last
verified.

A competition absent from the rights table SHALL NOT be excluded from the slate on that
basis alone. Absence from the table is not a statement that a competition is unwatchable
in the US; it is a statement that no single league-wide line about it is true. Where the
source answers per match for such a competition, that answer SHALL resolve availability
and the match SHALL be admitted on the same terms as any other.

#### Scenario: The source names providers for a match

- **WHEN** the source returns one or more US providers for a match whose league also appears
  in the rights table
- **THEN** the providers from the source are used, because league-level rights cannot express
  a split-rights competition, and the match is admitted to the slate

#### Scenario: A split-rights competition the rights table deliberately omits

- **WHEN** the source returns US providers for a match in a competition whose rights are held
  per club, and which therefore has no rights-table entry
- **THEN** availability is `known` with the providers the source named, and the match is
  admitted to the slate — the absent table entry neither supplies a provider nor withholds one

#### Scenario: The source names no provider but the league has constant rights

- **WHEN** the source returns no provider for a match, and the match's competition appears in
  the rights table
- **THEN** the providers from the rights table are used, and availability is `known`

#### Scenario: Neither source nor table answers

- **WHEN** the source returns no provider and the competition is absent from the rights table
- **THEN** availability for that match is `unknown` with an empty provider list, and the
  match is not admitted to the slate

#### Scenario: A rights table entry lacks a verification date

- **WHEN** the rights table contains an entry with no verification date
- **THEN** loading the table fails, rather than serving a provider of unknown vintage
