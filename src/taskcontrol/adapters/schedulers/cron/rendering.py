"""Rendering managed cron artefacts, and reading them back again.

Everything here is pure: text in, text out, no filesystem and no clock. That is what makes
rule 7 of ADR 0026 — *rendering is deterministic* — testable rather than aspirational, and
it is why an apply can be verified by rendering again and comparing bytes.

## Managed identity

Every managed artefact carries a marker naming the task and the revision digest:

```text
# >>> taskcontrol task=nightly-backup id=0193... digest=sha256:ab12... >>>
0 2 * * *  /usr/bin/taskctl run nightly-backup
# <<< taskcontrol task=nightly-backup <<<
```

The marker is the whole basis of safety. Content between markers is TaskControl's and may
be rewritten; everything else belongs to somebody else and is never touched — not
reordered, not reformatted, not stripped of trailing whitespace.

The digest in the marker is what makes drift readable. An operator, or a verification pass,
can tell from the text alone whether what is deployed is what was published.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.deployment.strategies import DeploymentStrategy
from taskcontrol.ports.scheduler_management import DesiredArtefact

MARKER_PREFIX = "taskcontrol"
"""The word every managed marker contains. Deliberately distinctive."""

_BEGIN = re.compile(
    r"^#\s*>>>\s*taskcontrol\s+task=(?P<slug>\S+)\s+id=(?P<task_id>\S+)\s+"
    r"digest=(?P<digest>\S+)\s*>>>\s*$"
)
_END = re.compile(r"^#\s*<<<\s*taskcontrol\s+task=(?P<slug>\S+)\s*<<<\s*$")

_GENERATED_NOTICE = (
    "# Managed by TaskControl. Edits between the markers are overwritten on the next apply."
)


@runtime_checkable
class ManagedEntry(Protocol):
    """Something TaskControl wrote into a crontab and can identify as its own.

    A marked region and an entry inside the single managed block are different shapes on
    disk, but they answer the same three questions — whose is this, which capability, and
    what does it say — so the code that plans removals and reports drift treats them alike.
    """

    @property
    def slug(self) -> str:
        """The capability's stable name."""
        ...

    @property
    def task_id(self) -> str:
        """The capability's identifier."""
        ...

    @property
    def text(self) -> str:
        """The entry as text, newline-terminated."""
        ...


@dataclass(frozen=True, slots=True)
class ManagedRegion:
    """A marked region found in a crontab.

    Attributes:
        slug: The task's slug, from the marker.
        task_id: The task identifier, from the marker.
        digest: The revision digest the artefact was rendered from.
        start: Index of the begin marker line.
        end: Index of the end marker line, inclusive.
        lines: Every line of the region, markers included.
    """

    slug: str
    task_id: str
    digest: str
    start: int
    end: int
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        """The region as text, newline-terminated."""
        return "\n".join(self.lines) + "\n"


class AmbiguousManagedContentError(ValidationError):
    """Raised when managed identity on the host cannot be resolved.

    Two regions claiming one task, a begin marker with no end, an end with no begin, or a
    file whose name disagrees with its content. Every one of these is refused rather than
    guessed, because the alternative is eventually deleting somebody's unmanaged entry
    (rule 5, ADR 0026).
    """


def render_artefact(artefact: DesiredArtefact) -> str:
    """Render one artefact's managed content.

    Args:
        artefact: What to deploy.

    Returns:
        The rendered text, newline-terminated. Byte-identical for identical input.

    Raises:
        ValidationError: If the artefact cannot be rendered as its strategy requires.
    """
    match artefact.deployment.strategy:
        case DeploymentStrategy.RUN_PARTS_DIRECTORY:
            return _render_run_parts_script(artefact)
        case DeploymentStrategy.CRON_D_FILE:
            return _render_cron_d_file(artefact)
        case DeploymentStrategy.CRONTAB_SINGLE_BLOCK:
            return render_block_member(artefact)
        case _:
            return _render_crontab_region(artefact)


def _require_schedule(artefact: DesiredArtefact) -> str:
    """Return the artefact's schedule, or explain why it is required.

    Raises:
        ValidationError: If the strategy needs a schedule and none was given.
    """
    if not artefact.schedule:
        raise ValidationError(
            f"A '{artefact.deployment.strategy}' artefact states when the work runs, so "
            "it needs a schedule. Give the revision a cron expression, or deploy it "
            "through a run-parts directory whose cadence comes from the directory.",
            details={"task_id": str(artefact.task_id), "slug": artefact.slug},
        )
    return artefact.schedule


def begin_marker(artefact: DesiredArtefact) -> str:
    """Return the begin marker line for an artefact."""
    return (
        f"# >>> {MARKER_PREFIX} task={artefact.slug} id={artefact.task_id} "
        f"digest={artefact.content_digest} >>>"
    )


def end_marker(slug: str) -> str:
    """Return the end marker line for a slug."""
    return f"# <<< {MARKER_PREFIX} task={slug} <<<"


def _description_comment(artefact: DesiredArtefact) -> list[str]:
    """Return the description as comment lines, if there is one.

    Newlines are collapsed so a multi-line description cannot escape its comment and
    become a cron directive.
    """
    if not artefact.description.strip():
        return []
    collapsed = " ".join(artefact.description.split())
    return [f"# {collapsed}"]


def _render_crontab_region(artefact: DesiredArtefact) -> str:
    """Render a marked region for a crontab-style target."""
    schedule = _require_schedule(artefact)
    user = artefact.deployment.execution_user
    entry = f"{schedule} {user} {artefact.command}" if user else f"{schedule} {artefact.command}"

    lines = [
        begin_marker(artefact),
        *_description_comment(artefact),
        entry,
        end_marker(artefact.slug),
    ]
    return "\n".join(lines) + "\n"


def _render_cron_d_file(artefact: DesiredArtefact) -> str:
    """Render a complete ``/etc/cron.d`` file.

    The file is wholly TaskControl's, so it still carries markers — that is what lets
    verification tell a managed file from one an administrator wrote by hand and happened
    to name the same thing.
    """
    schedule = _require_schedule(artefact)
    user = artefact.deployment.execution_user or "root"

    lines = [
        begin_marker(artefact),
        _GENERATED_NOTICE,
        *_description_comment(artefact),
        f"{schedule} {user} {artefact.command}",
        end_marker(artefact.slug),
    ]
    return "\n".join(lines) + "\n"


def _render_run_parts_script(artefact: DesiredArtefact) -> str:
    """Render an executable script for a run-parts directory.

    The directory supplies the cadence, so the script says only what to run. ``exec``
    replaces the shell rather than leaving it waiting, so the process cron supervises is
    the work itself — which is what makes its exit status and any signal it receives mean
    what TaskControl records them to mean.
    """
    if artefact.schedule:
        raise ValidationError(
            "A run-parts artefact takes its cadence from the directory, so a schedule "
            "here would be silently ignored.",
            details={"task_id": str(artefact.task_id), "schedule": artefact.schedule},
        )

    lines = [
        "#!/bin/sh",
        begin_marker(artefact),
        _GENERATED_NOTICE,
        *_description_comment(artefact),
        "set -eu",
        f"exec {artefact.command}",
        end_marker(artefact.slug),
    ]
    return "\n".join(lines) + "\n"


def find_managed_regions(content: str) -> tuple[ManagedRegion, ...]:
    """Find every managed region in a crontab-style text.

    Args:
        content: The full text, managed and unmanaged alike.

    Returns:
        The regions, in the order they appear.

    Raises:
        AmbiguousManagedContentError: If markers are unbalanced, mismatched, or two
            regions claim the same task.
    """
    lines = content.splitlines()
    regions: list[ManagedRegion] = []
    open_at: int | None = None
    opening: re.Match[str] | None = None

    for index, line in enumerate(lines):
        begin = _BEGIN.match(line)
        if begin:
            if open_at is not None:
                raise AmbiguousManagedContentError(
                    "A managed region begins inside another managed region. TaskControl "
                    "will not guess where one ends and the next starts.",
                    details={"line": index + 1},
                )
            open_at, opening = index, begin
            continue

        end = _END.match(line)
        if not end:
            continue
        if open_at is None or opening is None:
            raise AmbiguousManagedContentError(
                "A managed region ends without having begun.",
                details={"line": index + 1},
            )
        if end.group("slug") != opening.group("slug"):
            raise AmbiguousManagedContentError(
                "A managed region ends with a different task than it began with.",
                details={
                    "began_with": opening.group("slug"),
                    "ended_with": end.group("slug"),
                    "line": index + 1,
                },
            )

        regions.append(
            ManagedRegion(
                slug=opening.group("slug"),
                task_id=opening.group("task_id"),
                digest=opening.group("digest"),
                start=open_at,
                end=index,
                lines=tuple(lines[open_at : index + 1]),
            )
        )
        open_at, opening = None, None

    if open_at is not None:
        raise AmbiguousManagedContentError(
            "A managed region begins and never ends. Something truncated the file, or an "
            "end marker was deleted by hand.",
            details={"line": open_at + 1},
        )

    _assert_unique(regions)
    return tuple(regions)


def _assert_unique(regions: list[ManagedRegion]) -> None:
    """Raise if two regions claim the same task.

    Raises:
        AmbiguousManagedContentError: If a task appears twice.
    """
    seen: dict[str, int] = {}
    for region in regions:
        if region.task_id in seen:
            raise AmbiguousManagedContentError(
                f"Two managed regions claim the task '{region.slug}'. Rewriting either "
                "one could leave the other running stale work, so TaskControl will not "
                "choose between them. Remove the wrong region by hand.",
                details={
                    "task_id": region.task_id,
                    "first_line": seen[region.task_id] + 1,
                    "second_line": region.start + 1,
                },
            )
        seen[region.task_id] = region.start


def replace_region(content: str, slug: str, rendered: str) -> str:
    """Replace one task's managed region, leaving everything else byte-identical.

    Appends the region when the task has none. Unmanaged content is never reordered or
    reformatted — this is rule 1 of ADR 0026 and it is enforced by construction here:
    non-region lines are copied through untouched.

    Args:
        content: The current text.
        slug: The task whose region is being replaced.
        rendered: The new region text.

    Returns:
        The updated text.

    Raises:
        AmbiguousManagedContentError: If the existing managed content is ambiguous.
    """
    regions = find_managed_regions(content)
    existing = next((region for region in regions if region.slug == slug), None)

    if existing is None:
        if not content:
            return rendered
        separator = "" if content.endswith("\n") else "\n"
        return f"{content}{separator}{rendered}"

    lines = content.splitlines(keepends=True)
    replacement = rendered.splitlines(keepends=True)
    return "".join(lines[: existing.start] + replacement + lines[existing.end + 1 :])


def remove_region(content: str, slug: str) -> str:
    """Remove one task's managed region, leaving everything else byte-identical.

    Removing a region that is not present is not an error: undeploying something already
    undeployed should succeed quietly.

    Args:
        content: The current text.
        slug: The task whose region is being removed.

    Returns:
        The updated text.

    Raises:
        AmbiguousManagedContentError: If the existing managed content is ambiguous.
    """
    regions = find_managed_regions(content)
    existing = next((region for region in regions if region.slug == slug), None)
    if existing is None:
        return content

    lines = content.splitlines(keepends=True)
    return "".join(lines[: existing.start] + lines[existing.end + 1 :])


# -- the single managed block ----------------------------------------------------------
#
# One region holds every managed line, which is what an operator asks for when they want
# TaskControl's entries in one place they can read at a glance. The region markers name the
# block rather than a task; each entry inside carries its own identity comment.
#
#     # >>> taskcontrol block >>>
#     # Managed by TaskControl. ...
#     # taskcontrol task=nightly-backup id=task_0193... digest=sha256:ab...
#     0 2 * * *  /usr/bin/taskctl activate nightly-backup
#     # <<< taskcontrol block <<<
#
# Per-entry identity inside the block is not decoration. Without it, updating one
# capability would mean rewriting entries belonging to others from whatever the caller
# happened to know about, and removing one would mean guessing which line was whose.

_BLOCK_BEGIN = re.compile(r"^#\s*>>>\s*taskcontrol\s+block\s*>>>\s*$")
_BLOCK_END = re.compile(r"^#\s*<<<\s*taskcontrol\s+block\s*<<<\s*$")
_MEMBER = re.compile(
    r"^#\s*taskcontrol\s+task=(?P<slug>\S+)\s+id=(?P<task_id>\S+)\s+digest=(?P<digest>\S+)\s*$"
)

BLOCK_BEGIN_MARKER = "# >>> taskcontrol block >>>"
BLOCK_END_MARKER = "# <<< taskcontrol block <<<"


@dataclass(frozen=True, slots=True)
class BlockMember:
    """One capability's entry inside the single managed block.

    Attributes:
        slug: The task's slug, from its identity comment.
        task_id: The task identifier.
        digest: The revision digest the entry was rendered from.
        lines: The entry's lines, identity comment included.
    """

    slug: str
    task_id: str
    digest: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        """The entry as text, newline-terminated."""
        return "\n".join(self.lines) + "\n"


def render_block_member(artefact: DesiredArtefact) -> str:
    """Render one capability's entry for the single managed block.

    Args:
        artefact: What to deploy.

    Returns:
        The entry text, newline-terminated.

    Raises:
        ValidationError: If the artefact has no schedule.
    """
    schedule = _require_schedule(artefact)
    user = artefact.deployment.execution_user
    entry = f"{schedule} {user} {artefact.command}" if user else f"{schedule} {artefact.command}"

    lines = [
        f"# {MARKER_PREFIX} task={artefact.slug} id={artefact.task_id} "
        f"digest={artefact.content_digest}",
        *_description_comment(artefact),
        entry,
    ]
    return "\n".join(lines) + "\n"


def find_block_members(content: str) -> tuple[BlockMember, ...]:
    """Return every capability entry inside the single managed block.

    Args:
        content: The full crontab text.

    Returns:
        The entries, in the order they appear. Empty when there is no block.

    Raises:
        AmbiguousManagedContentError: If the block is unterminated, appears twice, or two
            entries claim the same capability.
    """
    bounds = _block_bounds(content)
    if bounds is None:
        return ()

    lines = content.splitlines()
    start, end = bounds
    members: list[BlockMember] = []
    current: re.Match[str] | None = None
    body: list[str] = []

    for line in lines[start + 1 : end]:
        identity = _MEMBER.match(line)
        if identity:
            if current is not None:
                members.append(_member(current, body))
            current, body = identity, [line]
            continue
        if current is not None:
            body.append(line)

    if current is not None:
        members.append(_member(current, body))

    _assert_members_unique(members)
    return tuple(members)


def _member(identity: re.Match[str], lines: list[str]) -> BlockMember:
    """Build a member from its identity comment and following lines."""
    return BlockMember(
        slug=identity.group("slug"),
        task_id=identity.group("task_id"),
        digest=identity.group("digest"),
        lines=tuple(lines),
    )


def _assert_members_unique(members: list[BlockMember]) -> None:
    """Raise if two entries in the block claim the same capability.

    Raises:
        AmbiguousManagedContentError: If a capability appears twice.
    """
    seen: set[str] = set()
    for member in members:
        if member.task_id in seen:
            raise AmbiguousManagedContentError(
                f"The managed block contains two entries for '{member.slug}'. Rewriting "
                "either could leave the other running stale work, so TaskControl will not "
                "choose between them. Remove the wrong entry by hand.",
                details={"slug": member.slug, "task_id": member.task_id},
            )
        seen.add(member.task_id)


def _block_bounds(content: str) -> tuple[int, int] | None:
    """Return the block's begin and end line indices, or ``None`` when there is no block.

    Raises:
        AmbiguousManagedContentError: If the block is unterminated or appears twice.
    """
    lines = content.splitlines()
    start: int | None = None
    end: int | None = None

    for index, line in enumerate(lines):
        if _BLOCK_BEGIN.match(line):
            if start is not None:
                raise AmbiguousManagedContentError(
                    "The crontab contains two managed blocks. TaskControl will not choose "
                    "between them.",
                    details={"first_line": start + 1, "second_line": index + 1},
                )
            start = index
        elif _BLOCK_END.match(line):
            if start is None:
                raise AmbiguousManagedContentError(
                    "A managed block ends without having begun.", details={"line": index + 1}
                )
            end = index

    if start is None:
        return None
    if end is None:
        raise AmbiguousManagedContentError(
            "The managed block begins and never ends. Something truncated the file, or an "
            "end marker was deleted by hand.",
            details={"line": start + 1},
        )
    return start, end


def upsert_block_member(content: str, slug: str, member: str) -> str:
    """Insert or replace one capability's entry in the single managed block.

    Creates the block when there is none. Every other entry, and every line outside the
    block, is preserved exactly — which is the whole reason entries carry their own
    identity rather than being addressed by position.

    Args:
        content: The current crontab text.
        slug: The capability whose entry is being written.
        member: The rendered entry.

    Returns:
        The updated text.

    Raises:
        AmbiguousManagedContentError: If the existing block is ambiguous.
    """
    bounds = _block_bounds(content)

    if bounds is None:
        block = f"{BLOCK_BEGIN_MARKER}\n{_GENERATED_NOTICE}\n{member}{BLOCK_END_MARKER}\n"
        if not content:
            return block
        separator = "" if content.endswith("\n") else "\n"
        return f"{content}{separator}{block}"

    members = find_block_members(content)
    rebuilt: list[str] = []
    replaced = False

    # Existing entries keep their positions. Rewriting the block in a different order every
    # apply would make a crontab diff unreadable, and an unreadable diff is how a review
    # stops catching anything.
    for existing in members:
        if existing.slug == slug:
            rebuilt.append(member)
            replaced = True
        else:
            rebuilt.append(existing.text)
    if not replaced:
        rebuilt.append(member)

    return _rewrite_block(content, bounds, rebuilt)


def remove_block_member(content: str, slug: str) -> str:
    """Remove one capability's entry from the single managed block.

    Removing the last entry removes the block itself: an empty pair of markers is litter in
    somebody's crontab, and TaskControl should not leave any behind once it manages nothing.

    Args:
        content: The current crontab text.
        slug: The capability to remove.

    Returns:
        The updated text.

    Raises:
        AmbiguousManagedContentError: If the existing block is ambiguous.
    """
    bounds = _block_bounds(content)
    if bounds is None:
        return content

    remaining = [member.text for member in find_block_members(content) if member.slug != slug]

    if not remaining:
        lines = content.splitlines(keepends=True)
        start, end = bounds
        return "".join(lines[:start] + lines[end + 1 :])

    return _rewrite_block(content, bounds, remaining)


def _rewrite_block(content: str, bounds: tuple[int, int], members: list[str]) -> str:
    """Rewrite the managed block's contents, leaving everything outside it untouched."""
    start, end = bounds
    lines = content.splitlines(keepends=True)
    block = f"{BLOCK_BEGIN_MARKER}\n{_GENERATED_NOTICE}\n{''.join(members)}{BLOCK_END_MARKER}\n"
    return "".join(lines[:start] + [block] + lines[end + 1 :])
