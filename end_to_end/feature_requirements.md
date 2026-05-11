# Feature Requirements

## Shared Online Input

Every scoring request must provide:

- `event_id`
- `event_time`
- `source_id`
- `target_id`
- `amount`
- `location_id`
- `type_id`

## Required Historical State

The pipeline cannot reproduce the trained behavior from raw input alone. It also
needs a state layer with prior transactions keyed by:

- source
- target
- source-target pair
- global event order

## Required Tabular Features

### S-FFSD

- source transaction count so far
- target transaction count so far
- source-target pair count so far
- source time gap
- target time gap
- pair time gap
- source historical mean amount
- target historical mean amount
- pair historical mean amount
- amount deviation from source/target/pair history
- source seen target/location/type before flags

### PaySim

- origin and destination balance deltas
- amount-vs-balance consistency features
- zero-balance flags
- origin transaction count so far
- destination transaction count so far
- origin-destination pair count so far
- origin/destination step gaps
- origin/destination historical mean amount
- type one-hot or categorical encoding

## Required Graph Context

### Event-Based GNN

- previous global event
- previous event for the same source
- previous event for the same target
- source-node features
- target-node features

### Heterogeneous GNN

- event-to-source edges
- event-to-target edges
- event-to-location edges
- event-to-type edges
- optional direct entity-to-entity edges when enabled

## Output Explanation Inputs

To support analyst explanations later, retain:

- source history window used for scoring
- target history window used for scoring
- top contributing tabular features
- event-neighborhood IDs used by the event-GNN
