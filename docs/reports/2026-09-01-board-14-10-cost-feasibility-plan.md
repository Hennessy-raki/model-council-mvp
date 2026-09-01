# Board 14.10 Plan: Explicit Cost Feasibility Gate

Date: 2026-09-01

Status: frozen before implementation

## Trigger

Board 14.9 made a future Provider-input budget explicit. A follow-up local
review found that `max_total_cost` was bound and validated as a number, but a
high-input candidate had no bound price schedule from which to prove its
permitted token envelope fits that cost cap.

## Goal

Require every future Board 14 scope that expands the input/output token budget
to include an explicit, operator-declared price schedule and reject it during
preparation unless the worst allowed token envelope fits the declared cost
limit.

## Scope

- add `cost_estimate` with input-per-million, output-per-million, per-request,
  and currency fields;
- require it, along with both input and output token caps, whenever a scope
  expands either component token budget;
- require the price currency to match the bound cost currency;
- calculate worst-case cost from the two component caps plus per-request fee
  using decimal arithmetic;
- reject missing, malformed, non-positive per-token prices, inconsistent
  currency, or an envelope that exceeds `max_total_cost`;
- bind the normalized price schedule and all limits into existing experiment
  and start-approval scopes;
- cover safe passing and rejected synthetic pricing policies offline.

## Excluded

- a claim that declared prices are Provider-reported or current market prices;
- Provider balance lookup, price discovery, a real call, retry, replay, new
  candidate, or approval creation;
- changes to the existing default token/cost limits, permissions, transport,
  output contract, source integrity, or zero-retry rules;
- retention of raw Provider records, response text, credentials, paths, files,
  Artifacts, workspaces, Git data, push, tag, Release, or deployment.

## Next real-pilot boundary

This board creates no candidate and grants no execution authority. A later
candidate must present its exact declared price schedule, token caps and cost
cap for separate human approval.
