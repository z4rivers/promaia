"""
Whisper CLI — send and check inter-agent messages from the terminal.

Usage:
    python -m promaia whisper send --to maia --subject "..." --body "..."
    python -m promaia whisper send --to maia --subject "..." --file path/to/file.md
    python -m promaia whisper inbox [agent]
    python -m promaia whisper thread <uuid>
"""
import sys
import argparse
import json
from pathlib import Path


def whisper_main(argv: list[str]):
    parser = argparse.ArgumentParser(prog="promaia whisper", description="Inter-agent messaging (Whispers)")
    sub = parser.add_subparsers(dest="command")

    # --- send ---
    send_p = sub.add_parser("send", help="Send a message to another agent")
    send_p.add_argument("--to", required=True, help="Recipient agent (e.g. maia, claude-code)")
    send_p.add_argument("--subject", "-s", required=True, help="Message subject")
    send_p.add_argument("--body", "-b", default="", help="Message body text")
    send_p.add_argument("--file", "-f", help="Read body from a file instead of --body")
    send_p.add_argument("--type", "-t", default="request",
                        choices=["request", "response", "correction", "heads_up", "handoff"],
                        help="Message type (default: request)")
    send_p.add_argument("--priority", "-p", default="normal",
                        choices=["normal", "high", "urgent"],
                        help="Priority (default: normal)")
    send_p.add_argument("--from", dest="from_agent", default="claude-code", help="Sender (default: claude-code)")
    send_p.add_argument("--context", "-c", help="JSON context payload string")
    send_p.add_argument("--reply-to", help="UUID of message being replied to")
    send_p.add_argument("--attach", "-a", nargs="*", help="File paths to include in context_payload.files_to_read")

    # --- inbox ---
    inbox_p = sub.add_parser("inbox", help="Check an agent's inbox")
    inbox_p.add_argument("agent", nargs="?", default="claude-code", help="Agent name (default: claude-code)")

    # --- thread ---
    thread_p = sub.add_parser("thread", help="View a message thread")
    thread_p.add_argument("uuid", help="Message UUID")

    # --- presence ---
    sub.add_parser("presence", help="Show online agents")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Late import so startup is fast
    from promaia.storage.signals_db import SignalsDB

    if args.command == "send":
        _cmd_send(args, SignalsDB())
    elif args.command == "inbox":
        _cmd_inbox(args, SignalsDB())
    elif args.command == "thread":
        _cmd_thread(args, SignalsDB())
    elif args.command == "presence":
        _cmd_presence(SignalsDB())


def _cmd_send(args, db):
    body = args.body
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"File not found: {args.file}")
            sys.exit(1)
        body = p.read_text(encoding="utf-8")

    context_payload = None
    if args.context:
        try:
            context_payload = json.loads(args.context)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in --context: {e}")
            sys.exit(1)

    if args.attach:
        if context_payload is None:
            context_payload = {}
        context_payload["files_to_read"] = args.attach

    uuid = db.send_message(
        from_agent=args.from_agent,
        to_agent=args.to,
        msg_type=args.type,
        subject=args.subject,
        body=body,
        context_payload=context_payload,
        priority=args.priority,
        reply_to=args.reply_to,
    )
    print(f"Sent. UUID: {uuid}")


def _cmd_inbox(args, db):
    messages = db.check_inbox(args.agent)
    if not messages:
        print(f"No messages for {args.agent}.")
        return
    for msg in messages:
        status = msg.get("status", "?")
        from_a = msg.get("from_agent", "?")
        subj = msg.get("subject", "(no subject)")
        uuid = msg.get("id", msg.get("uuid", "?"))
        pri = msg.get("priority", "normal")
        marker = "!" if pri == "urgent" else "^" if pri == "high" else " "
        print(f"[{status:^11}] {marker} {uuid[:8]}  from:{from_a:<12}  {subj}")


def _cmd_thread(args, db):
    thread = db.get_thread(args.uuid)
    if not thread:
        print(f"No thread found for {args.uuid}")
        return
    for msg in thread:
        from_a = msg.get("from_agent", "?")
        body = msg.get("body", "")
        ts = msg.get("created_at", "")
        print(f"\n--- {from_a} ({ts}) ---")
        print(body[:500] if len(body) > 500 else body)
        if len(body) > 500:
            print(f"  ... ({len(body)} chars total)")


def _cmd_presence(db):
    agents = db.get_online_agents()
    if not agents:
        print("No agents online.")
        return
    for a in agents:
        name = a.get("agent_name", "?")
        status = a.get("status", "?")
        working = a.get("working_on", "")
        print(f"  {name:<15} [{status}]  {working}")
