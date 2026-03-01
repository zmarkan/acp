"""ACP-Git envelope format: serialize and parse.

The envelope wraps a trace with plain-text headers for human scannability
and quick validation, followed by the compact JSON body.
"""

import json


def serialize(trace: dict) -> str:
    """Build an envelope string from a trace object.

    Format:
        ACP-Spec-Version: 0.1.0
        ACP-Trace-Id: <id>
        ACP-Trace-Hash: sha256:<hash>
        ACP-Event-Count: <n>
        ACP-Tool: <tool>
        ACP-Redaction: <mode>

        {"spec_version":"0.1.0",...}
    """
    tool = "unknown"
    if "tool_summary" in trace and "primary_tool" in trace["tool_summary"]:
        tool = trace["tool_summary"]["primary_tool"]

    headers = [
        f"ACP-Spec-Version: {trace['spec_version']}",
        f"ACP-Trace-Id: {trace['trace_id']}",
        f"ACP-Trace-Hash: {trace['integrity']['trace_hash']}",
        f"ACP-Event-Count: {trace['event_count']}",
        f"ACP-Tool: {tool}",
        f"ACP-Redaction: {trace['redaction_mode']}",
    ]
    # Compact single-line JSON body (not canonical -- canonical is only for hashing)
    body = json.dumps(trace, separators=(",", ":"), ensure_ascii=False)
    return "\n".join(headers) + "\n\n" + body


def parse_note_content(content: str) -> list[dict]:
    """Parse git note content into a list of trace objects.

    Implements the three consumer rules from the spec:
    1. Primary: split on \\n---\\n to get individual records
    2. Fallback: scan for ACP-Spec-Version: headers as record boundaries
    3. Bare JSON: content starts with { or [
    """
    content = content.strip()
    if not content:
        return []

    # Bare JSON fallback
    if content.startswith("{"):
        return [json.loads(content)]
    if content.startswith("["):
        return json.loads(content)

    # Primary: split on \n---\n
    if "\n---\n" in content:
        records = content.split("\n---\n")
        return [_parse_single_record(r.strip()) for r in records if r.strip()]

    # Single record or fallback
    # Check if there are multiple ACP-Spec-Version: headers (fallback for concatenated notes)
    lines = content.split("\n")
    header_indices = [
        i for i, line in enumerate(lines)
        if line.lower().startswith("acp-spec-version:")
    ]

    if len(header_indices) <= 1:
        # Single record
        return [_parse_single_record(content)]

    # Multiple records without --- separators (fallback parsing)
    traces = []
    for idx, start in enumerate(header_indices):
        end = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines)
        record = "\n".join(lines[start:end]).strip()
        if record:
            traces.append(_parse_single_record(record))
    return traces


def _parse_single_record(record: str) -> dict:
    """Parse a single envelope record (headers + JSON body) into a trace dict."""
    # Find the blank line separating headers from body
    parts = record.split("\n\n", 1)
    if len(parts) == 2:
        _headers_text, body = parts
        # Find the JSON body (the next non-empty line after the blank line)
        body = body.strip()
        if body.startswith("{"):
            return json.loads(body)

    # Fallback: scan for a line that starts with {
    for line in record.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)

    raise ValueError(f"Could not parse envelope record: no JSON body found")


def parse_headers(record: str) -> dict[str, str]:
    """Parse envelope headers from a single record into a dict.

    Headers are case-insensitive for matching. Returns lowercase keys.
    """
    headers = {}
    for line in record.split("\n"):
        line = line.strip()
        if not line:
            break  # End of headers
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return headers
