"""Local forum-style research journal contracts and artifacts."""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


MAX_POSTS = 200
MAX_REPLIES = 800
MAX_TAGS = 8
MAX_LINKED_ARTIFACTS = 8
MAX_TITLE_LENGTH = 120
MAX_CONTENT_LENGTH = 6000
MAX_REPLY_LENGTH = 2400
ALLOWED_ARTIFACT_PREFIXES = (
    "artifacts/backtests/",
    "artifacts/chat/",
    "artifacts/code_workspace/",
    "artifacts/diagnostics/",
    "artifacts/news/",
    "artifacts/paper/",
    "artifacts/portfolio/",
    "artifacts/quant_lab/",
    "artifacts/quantlib/",
    "artifacts/workflows/",
    "market_data/",
)
ALLOWED_ARTIFACT_EXTENSIONS = {".csv", ".ipynb", ".json", ".jsonl", ".md", ".txt"}
SECRET_PATTERNS = (
    re.compile(
        r"[\"']?(api[\s_-]*key|apikey|access[\s_-]*token|refresh[\s_-]*token|"
        r"secret[\s_-]*key|client[\s_-]*secret|private[\s_-]*key|password|"
        r"passphrase|pin|token|secret)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bauthorization\s*:\s*[^,\s]+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
)

CHANNELS: tuple[dict[str, str], ...] = (
    {
        "channel_id": "crypto-corner",
        "label": "Crypto Corner",
        "description": "Local crypto market notes and paper-trading observations.",
    },
    {
        "channel_id": "general-discussion",
        "label": "General Discussion",
        "description": "Cross-workspace notes, questions, and local terminal workflow ideas.",
    },
    {
        "channel_id": "market-analysis",
        "label": "Market Analysis",
        "description": "Research threads linked to news, markets, portfolio, and backtest artifacts.",
    },
    {
        "channel_id": "trading-strategies",
        "label": "Trading Strategies",
        "description": "Strategy journal entries for dry-run, paper, and backtest work.",
    },
)
CHANNEL_IDS = {channel["channel_id"] for channel in CHANNELS}
DEFAULT_CHANNEL = CHANNELS[0]["channel_id"]


class ForumError(ValueError):
    """Raised when local forum state or requests violate journal rules."""


def default_forum_state() -> dict[str, Any]:
    return {
        "active_channel_id": DEFAULT_CHANNEL,
        "selected_post_id": None,
        "posts": {},
        "replies": {},
        "updated_at": "not started",
    }


def forum_safety_payload() -> dict[str, bool | str]:
    return {
        "local_posts_only": True,
        "cloud_publish": False,
        "external_network": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "private_api_required": False,
        "credentials_persisted": False,
        "broker_mutation": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives_execution": False,
        "output": "local_research_journal",
    }


def normalize_forum_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_forum_state()
    invalid_posts = _invalid_map(state.get("invalid_posts"))
    invalid_replies = _invalid_map(state.get("invalid_replies"))
    if strict and invalid_posts:
        first_key, first_value = next(iter(invalid_posts.items()))
        raise ForumError(f"Forum state is invalid: {first_key}: {first_value}")
    if strict and invalid_replies:
        first_key, first_value = next(iter(invalid_replies.items()))
        raise ForumError(f"Forum state is invalid: {first_key}: {first_value}")

    raw_posts = state.get("posts")
    posts: dict[str, dict[str, Any]] = {}
    if isinstance(raw_posts, dict):
        if len(raw_posts) > MAX_POSTS:
            message = f"Forum posts exceed limit of {MAX_POSTS}"
            if strict:
                raise ForumError(message)
            invalid_posts["posts"] = message
            raw_posts = {}
        for post_id, raw_post in raw_posts.items():
            if not isinstance(raw_post, dict):
                if strict:
                    raise ForumError(f"Stored forum post {post_id} must be an object")
                invalid_posts[str(post_id)] = "Stored forum post must be an object"
                continue
            try:
                post = normalize_post(raw_post, fallback_id=str(post_id))
            except ForumError as exc:
                if strict:
                    raise ForumError(f"Stored forum post {post_id} is invalid: {exc}") from exc
                invalid_posts[str(post_id)] = str(exc)
                continue
            posts[post["post_id"]] = post
    elif raw_posts not in (None, {}):
        if strict:
            raise ForumError("Stored forum posts must be an object")
        invalid_posts["posts"] = "Stored forum posts must be an object"

    raw_replies = state.get("replies")
    replies: dict[str, dict[str, Any]] = {}
    if isinstance(raw_replies, dict):
        if len(raw_replies) > MAX_REPLIES:
            message = f"Forum replies exceed limit of {MAX_REPLIES}"
            if strict:
                raise ForumError(message)
            invalid_replies["replies"] = message
            raw_replies = {}
        for reply_id, raw_reply in raw_replies.items():
            if not isinstance(raw_reply, dict):
                if strict:
                    raise ForumError(f"Stored forum reply {reply_id} must be an object")
                invalid_replies[str(reply_id)] = "Stored forum reply must be an object"
                continue
            try:
                reply = normalize_reply(raw_reply, fallback_id=str(reply_id))
            except ForumError as exc:
                if strict:
                    raise ForumError(f"Stored forum reply {reply_id} is invalid: {exc}") from exc
                invalid_replies[str(reply_id)] = str(exc)
                continue
            if reply["post_id"] not in posts:
                if strict:
                    raise ForumError(f"Stored forum reply {reply_id} points to a missing post")
                invalid_replies[str(reply_id)] = "Reply points to a missing post"
                continue
            replies[reply["reply_id"]] = reply
    elif raw_replies not in (None, {}):
        if strict:
            raise ForumError("Stored forum replies must be an object")
        invalid_replies["replies"] = "Stored forum replies must be an object"

    posts = _with_reply_counts(posts, replies)
    active_channel_id = _channel_id_or_default(state.get("active_channel_id"))
    selected_post_id = str(state.get("selected_post_id") or "")
    if selected_post_id not in posts:
        selected_post_id = _latest_post_id(posts, active_channel_id)

    return {
        **default,
        "active_channel_id": active_channel_id,
        "selected_post_id": selected_post_id or None,
        "posts": posts,
        "replies": replies,
        "invalid_posts": invalid_posts,
        "invalid_replies": invalid_replies,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def forum_payload(
    state: dict[str, Any],
    context: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    forum_state = normalize_forum_state(state, strict=False)
    selected_id = forum_state["selected_post_id"]
    selected_post = copy.deepcopy(forum_state["posts"].get(selected_id)) if selected_id else None
    artifact_root = root if isinstance(root, Path) else Path(".")
    return {
        "active_channel_id": forum_state["active_channel_id"],
        "selected_post_id": selected_id,
        "first_use": not forum_state["posts"],
        "channels": _channel_payload(forum_state),
        "posts": _post_list(forum_state),
        "selected_post": selected_post,
        "replies": _reply_list(forum_state, selected_id),
        "leaderboard": _leaderboard(forum_state),
        "activity": _activity(forum_state),
        "artifact_suggestions": _artifact_suggestions(context),
        "artifact_health": forum_artifact_health(artifact_root, forum_state),
        "invalid_posts": forum_state["invalid_posts"],
        "invalid_replies": forum_state["invalid_replies"],
        "commands": ["New Post", "Save Local Post", "Add Reply", "Link Artifact"],
        "artifact_root": "artifacts/forum",
        "safety": forum_safety_payload(),
    }


def select_forum_channel(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    forum_state = normalize_forum_state(copy.deepcopy(state))
    channel_id = _channel_id(request.get("channel_id"))
    forum_state["active_channel_id"] = channel_id
    forum_state["selected_post_id"] = _latest_post_id(forum_state["posts"], channel_id) or None
    forum_state["updated_at"] = _utc_now()
    return forum_state


def select_forum_post(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    forum_state = normalize_forum_state(copy.deepcopy(state))
    post_id = _post_id(request.get("post_id"))
    if post_id not in forum_state["posts"]:
        raise ForumError("Forum post was not found")
    post = dict(forum_state["posts"][post_id])
    post["views"] = _bounded_int(post.get("views"), "Post views", 0, 1_000_000) + 1
    post["updated_at"] = _utc_now()
    forum_state["posts"][post_id] = post
    forum_state["active_channel_id"] = post["channel_id"]
    forum_state["selected_post_id"] = post_id
    forum_state["updated_at"] = post["updated_at"]
    return forum_state


def create_forum_post(
    state: dict[str, Any], request: dict[str, Any], root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    forum_state = normalize_forum_state(copy.deepcopy(state))
    if len(forum_state["posts"]) >= MAX_POSTS:
        raise ForumError(f"Forum posts exceed limit of {MAX_POSTS}")

    now = _utc_now()
    post_id = f"post-{uuid4().hex[:12]}"
    channel_id = _channel_id(request.get("channel_id") or forum_state["active_channel_id"])
    post = normalize_post(
        {
            "post_id": post_id,
            "title": _text(request.get("title"), "Title", 3, MAX_TITLE_LENGTH),
            "content": _text(request.get("content"), "Content", 1, MAX_CONTENT_LENGTH),
            "channel_id": channel_id,
            "tags": _tags(request.get("tags")),
            "linked_artifacts": _linked_artifacts(request.get("linked_artifacts")),
            "author": "Local User",
            "status": "local_saved",
            "cloud_published": False,
            "views": 0,
            "reply_count": 0,
            "created_at": now,
            "updated_at": now,
            "artifact_dir": f"artifacts/forum/{post_id}",
            "artifacts": {
                "post": f"artifacts/forum/{post_id}/post.json",
                "replies": f"artifacts/forum/{post_id}/replies.json",
                "thread": f"artifacts/forum/{post_id}/thread.md",
            },
        }
    )
    forum_state["posts"][post_id] = post
    forum_state["active_channel_id"] = channel_id
    forum_state["selected_post_id"] = post_id
    forum_state["updated_at"] = now
    write_forum_artifacts(root, post, [])
    return forum_state, post


def add_forum_reply(
    state: dict[str, Any], request: dict[str, Any], root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    forum_state = normalize_forum_state(copy.deepcopy(state))
    if len(forum_state["replies"]) >= MAX_REPLIES:
        raise ForumError(f"Forum replies exceed limit of {MAX_REPLIES}")
    post_id = _post_id(request.get("post_id") or forum_state.get("selected_post_id"))
    if post_id not in forum_state["posts"]:
        raise ForumError("Forum post was not found")

    now = _utc_now()
    reply_id = f"reply-{uuid4().hex[:12]}"
    reply = normalize_reply(
        {
            "reply_id": reply_id,
            "post_id": post_id,
            "content": _text(request.get("content"), "Reply", 1, MAX_REPLY_LENGTH),
            "author": "Local User",
            "status": "local_saved",
            "created_at": now,
        }
    )
    forum_state["replies"][reply_id] = reply
    post = dict(forum_state["posts"][post_id])
    post["updated_at"] = now
    post["reply_count"] = len(_reply_list({**forum_state, "posts": {post_id: post}}, post_id))
    forum_state["posts"][post_id] = post
    forum_state["selected_post_id"] = post_id
    forum_state["active_channel_id"] = post["channel_id"]
    forum_state["updated_at"] = now
    write_forum_artifacts(root, post, _reply_list(forum_state, post_id))
    return normalize_forum_state(forum_state), reply


def normalize_post(raw: dict[str, Any], *, fallback_id: str | None = None) -> dict[str, Any]:
    post_id = _post_id(raw.get("post_id") or fallback_id)
    title = _text(raw.get("title"), "Title", 3, MAX_TITLE_LENGTH)
    content = _text(raw.get("content"), "Content", 1, MAX_CONTENT_LENGTH)
    channel_id = _channel_id(raw.get("channel_id"))
    artifacts = _artifact_map(raw.get("artifacts"), post_id)
    return {
        "post_id": post_id,
        "title": title,
        "content": content,
        "channel_id": channel_id,
        "channel_label": _channel_label(channel_id),
        "tags": _tags(raw.get("tags")),
        "linked_artifacts": _linked_artifacts(raw.get("linked_artifacts")),
        "author": _author(raw.get("author")),
        "status": "local_saved",
        "cloud_published": False,
        "views": _bounded_int(raw.get("views"), "Post views", 0, 1_000_000),
        "reply_count": _bounded_int(raw.get("reply_count"), "Reply count", 0, MAX_REPLIES),
        "created_at": str(raw.get("created_at") or "not started")[:40],
        "updated_at": str(raw.get("updated_at") or "not started")[:40],
        "artifact_dir": f"artifacts/forum/{post_id}",
        "artifacts": artifacts,
    }


def normalize_reply(raw: dict[str, Any], *, fallback_id: str | None = None) -> dict[str, Any]:
    return {
        "reply_id": _reply_id(raw.get("reply_id") or fallback_id),
        "post_id": _post_id(raw.get("post_id")),
        "content": _text(raw.get("content"), "Reply", 1, MAX_REPLY_LENGTH),
        "author": _author(raw.get("author")),
        "status": "local_saved",
        "created_at": str(raw.get("created_at") or "not started")[:40],
    }


def write_forum_artifacts(root: Path, post: dict[str, Any], replies: list[dict[str, Any]]) -> None:
    post_id = _post_id(post.get("post_id"))
    artifact_dir = _safe_post_dir(root, post_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "post.json", post)
    _write_json(artifact_dir / "replies.json", {"post_id": post_id, "replies": replies})
    (artifact_dir / "thread.md").write_text(_thread_markdown(post, replies), encoding="utf-8")


def forum_artifact_health(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    forum_state = normalize_forum_state(copy.deepcopy(state), strict=False)
    posts = forum_state["posts"]
    expected_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for post in sorted(posts.values(), key=lambda item: str(item["updated_at"]), reverse=True):
        post_id = post["post_id"]
        for kind, relative_path in post["artifacts"].items():
            path = _safe_existing_artifact_path(root, relative_path, post_id)
            exists = path.is_file()
            row = {
                "post_id": post_id,
                "title": post["title"],
                "kind": kind,
                "path": relative_path,
                "exists": exists,
                "bytes": _path_size(path) if exists else 0,
                "repair_action": "rewrite_from_forum_state",
            }
            expected_rows.append(row)
            if not exists:
                missing_rows.append(row)

    orphan_dirs = _orphan_post_dirs(root, posts)
    invalid_count = len(forum_state["invalid_posts"]) + len(forum_state["invalid_replies"])
    status = "healthy"
    if invalid_count:
        status = "state_invalid"
    elif missing_rows:
        status = "repair_available"
    elif orphan_dirs:
        status = "orphan_review"
    return {
        "status": status,
        "summary": {
            "post_count": len(posts),
            "expected_artifact_count": len(expected_rows),
            "missing_artifact_count": len(missing_rows),
            "orphan_dir_count": len(orphan_dirs),
            "invalid_state_count": invalid_count,
            "repairable_post_count": len({row["post_id"] for row in missing_rows}),
        },
        "missing": missing_rows[:12],
        "orphan_dirs": orphan_dirs[:12],
        "expected_sample": expected_rows[:12],
        "safety": {
            "source_of_truth": "artifacts/forum/forum_state.json",
            "repair_actions_enabled": bool(missing_rows) and not invalid_count,
            "repair_action": "rewrite derivative post/replies/thread artifacts from local state",
            "prune_actions_enabled": False,
            "destructive_actions_enabled": False,
            "external_network": False,
            "credentials_required": False,
            "cloud_publish": False,
        },
    }


def repair_forum_artifacts(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    forum_state = normalize_forum_state(copy.deepcopy(state))
    before = forum_artifact_health(root, forum_state)
    rewritten_artifact_count = 0
    for post in forum_state["posts"].values():
        replies = _reply_list(forum_state, post["post_id"])
        write_forum_artifacts(root, post, replies)
        rewritten_artifact_count += len(post["artifacts"])
    after = forum_artifact_health(root, forum_state)
    return {
        "status": "repaired" if rewritten_artifact_count else "nothing_to_repair",
        "rewritten_post_count": len(forum_state["posts"]),
        "rewritten_artifact_count": rewritten_artifact_count,
        "missing_before": before["summary"]["missing_artifact_count"],
        "missing_after": after["summary"]["missing_artifact_count"],
        "orphan_dir_count": after["summary"]["orphan_dir_count"],
        "destructive_actions_enabled": False,
        "artifact_health": after,
    }


def _channel_payload(state: dict[str, Any]) -> list[dict[str, Any]]:
    posts = state["posts"]
    return [
        {
            **channel,
            "post_count": sum(
                1 for post in posts.values() if post["channel_id"] == channel["channel_id"]
            ),
            "active": channel["channel_id"] == state["active_channel_id"],
        }
        for channel in CHANNELS
    ]


def _post_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    active_channel_id = state["active_channel_id"]
    posts = [
        copy.deepcopy(post)
        for post in state["posts"].values()
        if post["channel_id"] == active_channel_id
    ]
    return sorted(posts, key=lambda post: str(post["updated_at"]), reverse=True)


def _reply_list(state: dict[str, Any], post_id: str | None) -> list[dict[str, Any]]:
    if not post_id:
        return []
    replies = [
        copy.deepcopy(reply)
        for reply in state["replies"].values()
        if reply["post_id"] == post_id
    ]
    return sorted(replies, key=lambda reply: str(reply["created_at"]))


def _leaderboard(state: dict[str, Any]) -> list[dict[str, Any]]:
    posts_by_channel = {
        channel["channel_id"]: sum(
            1 for post in state["posts"].values() if post["channel_id"] == channel["channel_id"]
        )
        for channel in CHANNELS
    }
    return [
        {
            "label": _channel_label(channel_id),
            "posts": posts,
            "replies": sum(
                1
                for reply in state["replies"].values()
                if state["posts"].get(reply["post_id"], {}).get("channel_id") == channel_id
            ),
        }
        for channel_id, posts in sorted(posts_by_channel.items(), key=lambda item: item[1], reverse=True)
    ]


def _activity(state: dict[str, Any]) -> list[dict[str, str]]:
    post_items = [
        {
            "kind": "post",
            "label": post["title"],
            "channel": post["channel_label"],
            "created_at": post["updated_at"],
        }
        for post in state["posts"].values()
    ]
    reply_items = [
        {
            "kind": "reply",
            "label": state["posts"].get(reply["post_id"], {}).get("title", "Reply"),
            "channel": state["posts"].get(reply["post_id"], {}).get("channel_label", "Forum"),
            "created_at": reply["created_at"],
        }
        for reply in state["replies"].values()
    ]
    return sorted(post_items + reply_items, key=lambda item: item["created_at"], reverse=True)[:12]


def _artifact_suggestions(context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(context, dict):
        return []
    suggestions: list[dict[str, Any]] = []
    artifacts = context.get("artifacts") if isinstance(context.get("artifacts"), list) else []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        path = str(artifact.get("path") or "")
        try:
            safe_path = _linked_artifact_path(path)
        except ForumError:
            continue
        suggestions.append(
            {
                "kind": str(artifact.get("kind") or "artifact")[:40],
                "label": str(artifact.get("label") or artifact.get("artifact_id") or safe_path)[:80],
                "path": safe_path,
                "updated_at": str(artifact.get("updated_at") or "")[:80],
            }
        )
        if len(suggestions) >= 8:
            return suggestions

    sources = context.get("sources") if isinstance(context.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        path = str(source.get("cache_path") or "")
        try:
            safe_path = _linked_artifact_path(path)
        except ForumError:
            continue
        suggestions.append(
            {
                "kind": "provider_cache",
                "label": str(source.get("label") or source.get("source_id") or safe_path)[:80],
                "path": safe_path,
                "updated_at": str(source.get("updated_at") or "")[:80],
            }
        )
        if len(suggestions) >= 8:
            break
    return suggestions


def _with_reply_counts(
    posts: dict[str, dict[str, Any]], replies: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    counted = copy.deepcopy(posts)
    for post_id, post in counted.items():
        post["reply_count"] = sum(1 for reply in replies.values() if reply["post_id"] == post_id)
    return counted


def _latest_post_id(posts: dict[str, dict[str, Any]], channel_id: str) -> str:
    channel_posts = [post for post in posts.values() if post["channel_id"] == channel_id]
    if not channel_posts:
        return ""
    return max(channel_posts, key=lambda post: str(post["updated_at"]))["post_id"]


def _artifact_map(raw: Any, post_id: str) -> dict[str, str]:
    default = {
        "post": f"artifacts/forum/{post_id}/post.json",
        "replies": f"artifacts/forum/{post_id}/replies.json",
        "thread": f"artifacts/forum/{post_id}/thread.md",
    }
    if not isinstance(raw, dict):
        return default
    artifacts = {str(key): _forum_artifact_path(value, post_id) for key, value in raw.items()}
    return {**default, **artifacts}


def _forum_artifact_path(raw: Any, post_id: str) -> str:
    value = str(raw or "").replace("\\", "/").strip()
    prefix = f"artifacts/forum/{post_id}/"
    if not value.startswith(prefix):
        raise ForumError("Forum artifact path must stay under the post artifact directory")
    if ".." in Path(value).parts:
        raise ForumError("Forum artifact path must not contain parent traversal")
    return value[:240]


def _linked_artifacts(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
    elif isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
    else:
        raise ForumError("Linked artifacts must be a list or comma-separated string")
    if len(values) > MAX_LINKED_ARTIFACTS:
        raise ForumError(f"Linked artifacts exceed limit of {MAX_LINKED_ARTIFACTS}")
    return [_linked_artifact_path(value) for value in values]


def _linked_artifact_path(raw: str) -> str:
    value = raw.replace("\\", "/").strip()
    if not value or "://" in value or value.startswith("/") or value.startswith("~"):
        raise ForumError("Linked artifact path must be repo-relative")
    if ".." in Path(value).parts:
        raise ForumError("Linked artifact path must not contain parent traversal")
    if not any(value.startswith(prefix) for prefix in ALLOWED_ARTIFACT_PREFIXES):
        raise ForumError("Linked artifact must be under allowed local artifact paths")
    if Path(value).suffix.lower() not in ALLOWED_ARTIFACT_EXTENSIONS:
        raise ForumError("Linked artifact extension is not allowed")
    return value[:240]


def _tags(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    values = raw.split(",") if isinstance(raw, str) else raw
    if not isinstance(values, list):
        raise ForumError("Tags must be a list or comma-separated string")
    tags = []
    for item in values[:MAX_TAGS]:
        value = re.sub(r"[^A-Za-z0-9 _.-]", "", str(item)).strip()[:28]
        if value and value not in tags:
            tags.append(value)
    return tags


def _text(raw: Any, label: str, minimum: int, maximum: int) -> str:
    value = str(raw or "").strip()
    if len(value) < minimum:
        raise ForumError(f"{label} is required")
    if len(value) > maximum:
        raise ForumError(f"{label} exceeds limit of {maximum}")
    if _contains_secret(value):
        raise ForumError(f"{label} appears to contain credential material")
    return value


def _author(raw: Any) -> str:
    value = str(raw or "Local User").strip()[:80]
    if _contains_secret(value):
        raise ForumError("Author appears to contain credential material")
    return value or "Local User"


def _channel_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if value not in CHANNEL_IDS:
        raise ForumError("Forum channel is not supported")
    return value


def _channel_id_or_default(raw: Any) -> str:
    value = str(raw or "").strip()
    return value if value in CHANNEL_IDS else DEFAULT_CHANNEL


def _channel_label(channel_id: str) -> str:
    return next(channel["label"] for channel in CHANNELS if channel["channel_id"] == channel_id)


def _post_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not re.fullmatch(r"post-[a-f0-9]{12}", value):
        raise ForumError("Forum post id is invalid")
    return value


def _reply_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not re.fullmatch(r"reply-[a-f0-9]{12}", value):
        raise ForumError("Forum reply id is invalid")
    return value


def _bounded_int(raw: Any, label: str, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ForumError(f"{label} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ForumError(f"{label} must be between {minimum} and {maximum}")
    return value


def _contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _invalid_map(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _safe_post_dir(root: Path, post_id: str) -> Path:
    path = (root / "artifacts" / "forum" / post_id).resolve()
    forum_root = (root / "artifacts" / "forum").resolve()
    if not (path == forum_root / post_id and path.is_relative_to(forum_root)):
        raise ForumError("Forum artifact directory must stay under artifacts/forum")
    return path


def _safe_existing_artifact_path(root: Path, relative_path: str, post_id: str) -> Path:
    expected_prefix = f"artifacts/forum/{post_id}/"
    if not relative_path.startswith(expected_prefix):
        raise ForumError("Forum artifact path must stay under the post artifact directory")
    path = (root / relative_path).resolve()
    post_dir = _safe_post_dir(root, post_id)
    if not path.is_relative_to(post_dir):
        raise ForumError("Forum artifact path must stay under the post artifact directory")
    return path


def _orphan_post_dirs(root: Path, posts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    forum_root = (root / "artifacts" / "forum").resolve()
    if not forum_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        candidates = list(forum_root.iterdir())
    except OSError:
        return []
    for path in candidates:
        if not path.is_dir() or not re.fullmatch(r"post-[a-f0-9]{12}", path.name):
            continue
        if path.name in posts:
            continue
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
            file_count = sum(1 for child in path.iterdir() if child.is_file())
        except ValueError:
            continue
        except OSError:
            file_count = 0
        rows.append(
            {
                "post_id": path.name,
                "path": relative,
                "file_count": file_count,
                "safe_action": "manual_review_only",
            }
        )
    return sorted(rows, key=lambda row: row["path"])[:50]


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _thread_markdown(post: dict[str, Any], replies: list[dict[str, Any]]) -> str:
    reply_lines = "\n".join(
        f"- {reply['created_at']} {reply['author']}: {reply['content']}" for reply in replies
    )
    if not reply_lines:
        reply_lines = "- No local replies yet."
    tags = ", ".join(post["tags"]) if post["tags"] else "none"
    links = "\n".join(f"- {path}" for path in post["linked_artifacts"]) or "- none"
    return (
        f"# {post['title']}\n\n"
        f"Channel: {post['channel_label']}\n"
        f"Status: {post['status']}\n"
        "Cloud published: false\n"
        f"Tags: {tags}\n\n"
        "## Post\n\n"
        f"{post['content']}\n\n"
        "## Linked Local Artifacts\n\n"
        f"{links}\n\n"
        "## Replies\n\n"
        f"{reply_lines}\n"
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
