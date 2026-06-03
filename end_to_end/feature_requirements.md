# Feature Requirements

## External Request Contract

The online caller should send only immutable transaction facts:

- `transaction_id`
- `transaction_timestamp`
- `sender_id`
- `receiver_id`
- `amount`
- `transaction_location`
- `transaction_type`
- optional `currency`
- optional `channel`
- optional `raw_attributes`

The caller should not send engineered historical features or graph context.
Those are computed internally to avoid feature skew and future-leakage errors.

## Required Internal State

The pipeline reproduces the trained model behavior by maintaining:

- sender history
- receiver history
- sender-receiver pair history
- recent global event window

This state supports both the tabular models and the Event-GNN.

## Tabular Features Built Internally

For `LightGBM` and `AdaBoost`, the online feature builder computes:

- source transaction count so far
- target transaction count so far
- location transaction count so far
- type transaction count so far
- source-target pair count so far
- source, target, and pair time gaps
- source, target, and pair historical mean amounts
- amount deviation from those historical means
- source seen target/location/type before flags
- sender/receiver/location/type frequency and count statistics

## Event-GNN Context Built Internally

For the `Event-Based GNN`, the online feature builder assembles a local graph
context that includes:

- recent global events
- recent events for the same sender
- recent events for the same receiver
- the current candidate event as the `test` node

That context is converted to the same event-graph representation used by the
training code.

## Explanation Inputs Retained

To support analyst-facing output, the pipeline retains:

- top tabular risk factors from the engineered feature row
- sender/receiver history sizes
- local graph context size used for Event-GNN scoring
