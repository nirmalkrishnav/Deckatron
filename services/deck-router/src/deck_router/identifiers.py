"""Stateless service affinity for task and context identifiers."""

import base64
import binascii

from a2a.types import Message, Task
from a2a.utils.errors import InvalidParamsError

from deck_router.selection import Target

PREFIX = "dr1."


def encode_id(target: Target, value: str) -> str:
    """Namespace a downstream ID so any router process can resolve its owner."""
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{PREFIX}{target}.{encoded}"


def decode_id(value: str) -> tuple[Target, str]:
    """Reject malformed or unknown route IDs without treating them as endpoints."""
    fields = value.split(".", 2)
    if len(fields) != 3 or fields[0] != "dr1" or fields[1] not in ("create", "edit"):
        raise InvalidParamsError(message="Use the task/context ID returned by deck-router")
    target: Target = "create" if fields[1] == "create" else "edit"
    try:
        raw = base64.b64decode(
            fields[2] + "=" * (-len(fields[2]) % 4), altchars=b"-_", validate=True
        ).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        raise InvalidParamsError(message="Invalid router task/context ID") from error
    if not raw or encode_id(target, raw) != value:
        raise InvalidParamsError(message="Invalid router task/context ID")
    return target, raw


def bound_target(message: Message) -> Target | None:
    """Resolve follow-ups without allowing an LLM to switch their service."""
    targets: set[Target] = set()
    if message.task_id:
        targets.add(decode_id(message.task_id)[0])
    if message.context_id.startswith(PREFIX):
        targets.add(decode_id(message.context_id)[0])
    if len(targets) > 1:
        raise InvalidParamsError(message="Task and context belong to different services")
    return next(iter(targets), None)


def unwrap_message(message: Message, target: Target) -> None:
    """Restore IDs on a copied outbound request, leaving API content intact."""
    if message.task_id:
        owner, raw = decode_id(message.task_id)
        if owner != target:
            raise InvalidParamsError(message="Task belongs to another service")
        message.task_id = raw
    if message.context_id.startswith(PREFIX):
        owner, raw = decode_id(message.context_id)
        if owner != target:
            raise InvalidParamsError(message="Context belongs to another service")
        message.context_id = raw
    references = []
    for reference in message.reference_task_ids:
        owner, raw = decode_id(reference)
        if owner != target:
            raise InvalidParamsError(message="Referenced task belongs to another service")
        references.append(raw)
    del message.reference_task_ids[:]
    message.reference_task_ids.extend(references)


def wrap_message(message: Message, target: Target) -> None:
    """Make response IDs routable without altering text, metadata, or files."""
    if message.task_id:
        message.task_id = encode_id(target, message.task_id)
    if message.context_id:
        message.context_id = encode_id(target, message.context_id)
    references = [encode_id(target, value) for value in message.reference_task_ids]
    del message.reference_task_ids[:]
    message.reference_task_ids.extend(references)


def wrap_task(task: Task, target: Target) -> Task:
    """Copy a downstream task, preserving status, layout review, and artifacts."""
    result = Task()
    result.CopyFrom(task)
    result.id = encode_id(target, task.id)
    if result.context_id:
        result.context_id = encode_id(target, result.context_id)
    if result.status.HasField("message"):
        wrap_message(result.status.message, target)
    for message in result.history:
        wrap_message(message, target)
    return result
