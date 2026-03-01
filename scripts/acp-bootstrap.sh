#!/bin/bash
# acp-bootstrap.sh — manual trace attachment before git-whence exists
# Usage: ./acp-bootstrap.sh <commit-sha> <tool> <prompt-text>
#
# This script is Phase 1 of ACP dogfooding: it attaches ACP traces
# to commits using raw git notes, before the git-whence CLI exists.
#
# Requirements: bash, jq, openssl, git, shasum

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <commit-sha> [tool] [prompt-text]"
  echo ""
  echo "  commit-sha   The commit to attach the trace to"
  echo "  tool         AI tool identifier (default: claude-code)"
  echo "  prompt-text  The prompt used for this commit"
  exit 1
fi

SHA="$1"
TOOL="${2:-claude-code}"
PROMPT="${3:-}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
TRACE_ID=$(date -u +"%Y%m%dT%H%M%SZ")_$(openssl rand -hex 2)
EVENT_ID="evt_$(openssl rand -hex 4)"

# Validate the commit SHA exists
if ! git cat-file -t "$SHA" >/dev/null 2>&1; then
  echo "Error: $SHA is not a valid git object"
  exit 1
fi

# Hash the prompt
PROMPT_HASH="sha256:$(echo -n "$PROMPT" | shasum -a 256 | cut -d' ' -f1)"

# Build the trace JSON (single line, compact)
TRACE=$(jq -c -n \
  --arg sv "0.1.0" \
  --arg tid "$TRACE_ID" \
  --arg cat "$TIMESTAMP" \
  --arg ttype "git-commit" \
  --arg tid_target "$SHA" \
  --arg tool "$TOOL" \
  --arg rm "hash-response" \
  --arg eid "$EVENT_ID" \
  --arg ts "$TIMESTAMP" \
  --arg prompt "$PROMPT" \
  --arg phash "$PROMPT_HASH" \
  '{
    spec_version: $sv,
    trace_id: $tid,
    created_at: $cat,
    target: { type: $ttype, id: $tid_target },
    tool_summary: { primary_tool: $tool, tools_used: [$tool] },
    redaction_mode: $rm,
    event_count: 1,
    events: [{
      spec_version: $sv,
      event_id: $eid,
      timestamp: $ts,
      tool: $tool,
      prompt: $prompt,
      prompt_hash: $phash,
      response_captured: false
    }],
    integrity: { algorithm: "sha256-canonical-json" }
  }')

# Compute trace hash (excluding integrity, but we'll skip full canonical for bootstrap)
# In production git-whence, this would be proper canonical JSON hashing
TRACE_HASH="sha256:$(echo -n "$TRACE" | shasum -a 256 | cut -d' ' -f1)"

# Add trace_hash back into the JSON
TRACE=$(echo "$TRACE" | jq -c --arg th "$TRACE_HASH" '.integrity.trace_hash = $th')

# Build envelope
ENVELOPE="ACP-Spec-Version: 0.1.0
ACP-Trace-Id: $TRACE_ID
ACP-Trace-Hash: $TRACE_HASH
ACP-Event-Count: 1
ACP-Tool: $TOOL
ACP-Redaction: hash-response

$TRACE"

# Check if note already exists
EXISTING=$(git notes --ref=refs/notes/acp show "$SHA" 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  ENVELOPE="$EXISTING
---
$ENVELOPE"
fi

# Write the note
echo "$ENVELOPE" | git notes --ref=refs/notes/acp add -f --file=- "$SHA"

echo "ACP trace $TRACE_ID attached to $SHA"
