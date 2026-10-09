"""JSON-lines protocol used by benchmark adapters and the orchestrator."""

import json


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def decode_event(line: str, run_id: str, benchmark_id: str, expected_number: int) -> dict:
    event = json.loads(line, parse_constant=_reject_constant)
    if not isinstance(event, dict):
        raise ValueError("Event must be a JSON object")
    if event.get("protocol_version") != 1:
        raise ValueError("Unsupported event protocol")
    if event.get("run_id") != run_id or event.get("benchmark_id") != benchmark_id:
        raise ValueError("Event identity does not match its process")
    if type(event.get("event_number")) is not int or event["event_number"] != expected_number:
        raise ValueError("Event numbers must be contiguous, starting at 1")
    if not isinstance(event.get("event_type"), str) or not event["event_type"]:
        raise ValueError("event_type must be a nonempty string")
    if not isinstance(event.get("payload"), dict):
        raise ValueError("payload must be an object")
    timestamp = event.get("dataset_timestamp_ns")
    if timestamp is not None and type(timestamp) is not int:
        raise ValueError("Dataset timestamps must be integer nanoseconds")
    return event
