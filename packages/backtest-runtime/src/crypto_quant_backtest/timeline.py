from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
import unicodedata

from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import (
    EventCursor,
    InputValidationFailure,
    MarketBundleError,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
)


OrderingKey = tuple[int, int, str, int]


class TimelineError(RuntimeError):
    """The timeline or its reader violated a fail-closed contract."""


class TimelineCursorError(TimelineError):
    """A cursor cannot be resumed against this timeline."""


class TimelineSegment(str, Enum):
    WARMUP = "warmup"
    ACTIVE_TRADING = "active_trading"


class TimelineFailureCode(str, Enum):
    MALFORMED_EVENT = "malformed_event"
    MISSING_SOURCE_SEQUENCE = "missing_source_sequence"
    DUPLICATE_ORDERING_KEY = "duplicate_ordering_key"
    ORDER_REGRESSION = "order_regression"


def _canonical_stream_key(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("stream key must be a string")
    if not value or value != value.strip():
        raise ValueError("stream key must be nonempty trimmed text")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError("stream key must be NFC-normalized")
    return value


def _validate_hash(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
    ):
        raise ValueError(f"{name} must be a canonical sha256 digest")
    try:
        int(value[7:], 16)
    except ValueError as error:
        raise ValueError(f"{name} must be a canonical sha256 digest") from error
    if value[7:] != value[7:].lower():
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


def _ordering_key_dict(key: OrderingKey) -> dict[str, object]:
    return {
        "epoch_nanoseconds": key[0],
        "phase_rank": key[1],
        "phase_code": key[2],
        "source_sequence": key[3],
    }


@dataclass(frozen=True, slots=True)
class TimelineWindow:
    data_start: UtcInstant
    trading_start: UtcInstant
    end_exclusive: UtcInstant

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, UtcInstant)
            for value in (self.data_start, self.trading_start, self.end_exclusive)
        ):
            raise TypeError("timeline boundaries must be UtcInstant")
        if not (
            self.data_start.epoch_nanoseconds
            <= self.trading_start.epoch_nanoseconds
            < self.end_exclusive.epoch_nanoseconds
        ):
            raise ValueError(
                "timeline window requires data_start <= trading_start < end_exclusive"
            )

    @property
    def window_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "timeline_window",
            "data_start": self.data_start,
            "trading_start": self.trading_start,
            "end_exclusive": self.end_exclusive,
        }


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    segment: TimelineSegment
    event: MarketEvent

    def __post_init__(self) -> None:
        if not isinstance(self.segment, TimelineSegment):
            raise TypeError("segment must be TimelineSegment")
        if not isinstance(self.event, MarketEvent):
            raise TypeError("event must be MarketEvent")

    @property
    def timeline_instant(self) -> SimulationInstant:
        return self.event.timeline_instant

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "timeline_event",
            "segment": self.segment.value,
            "event": self.event,
        }


@dataclass(frozen=True, slots=True)
class TimelineStreamCursor:
    stream_key: str
    cursor: EventCursor

    def __post_init__(self) -> None:
        _canonical_stream_key(self.stream_key)
        if not isinstance(self.cursor, EventCursor):
            raise TypeError("cursor must be EventCursor")
        if self.cursor.stream_manifest.stream_key != self.stream_key:
            raise TimelineCursorError("source cursor stream does not match stream_key")
        if self.cursor.batch_size != 1:
            raise TimelineCursorError("timeline source cursors must use batch_size 1")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "timeline_stream_cursor",
            "stream_key": self.stream_key,
            "cursor": self.cursor,
        }


@dataclass(frozen=True, slots=True)
class TimelineCursor:
    timeline_id: str
    bundle_ref: MarketBundleRef
    window_hash: str
    streams: tuple[TimelineStreamCursor, ...]
    batch_size: int
    emitted_count: int = 0
    last_ordering_key: OrderingKey | None = None
    window_complete: bool = False

    def __post_init__(self) -> None:
        _validate_hash("timeline_id", self.timeline_id)
        if not isinstance(self.bundle_ref, MarketBundleRef):
            raise TypeError("bundle_ref must be MarketBundleRef")
        _validate_hash("window_hash", self.window_hash)
        if not self.streams:
            raise TimelineCursorError("timeline cursor requires source streams")
        ordered = tuple(sorted(self.streams, key=lambda item: item.stream_key))
        if ordered != self.streams:
            raise TimelineCursorError("timeline source cursors must be canonical-sorted")
        if len({item.stream_key for item in self.streams}) != len(self.streams):
            raise TimelineCursorError("timeline source cursor streams must be unique")
        if any(item.cursor.bundle_ref != self.bundle_ref for item in self.streams):
            raise TimelineCursorError("source cursor bundle does not match timeline")
        if isinstance(self.batch_size, bool) or not isinstance(self.batch_size, int):
            raise TypeError("batch_size must be an integer")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if isinstance(self.emitted_count, bool) or not isinstance(
            self.emitted_count, int
        ):
            raise TypeError("emitted_count must be an integer")
        if self.emitted_count < 0:
            raise ValueError("emitted_count must be nonnegative")
        if not isinstance(self.window_complete, bool):
            raise TypeError("window_complete must be a bool")
        if self.last_ordering_key is not None:
            if (
                not isinstance(self.last_ordering_key, tuple)
                or len(self.last_ordering_key) != 4
                or isinstance(self.last_ordering_key[0], bool)
                or not isinstance(self.last_ordering_key[0], int)
                or isinstance(self.last_ordering_key[1], bool)
                or not isinstance(self.last_ordering_key[1], int)
                or not isinstance(self.last_ordering_key[2], str)
                or isinstance(self.last_ordering_key[3], bool)
                or not isinstance(self.last_ordering_key[3], int)
            ):
                raise TimelineCursorError("last_ordering_key is malformed")

    @property
    def cursor_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "timeline_cursor",
            "timeline_id": self.timeline_id,
            "bundle_ref": self.bundle_ref,
            "window_hash": self.window_hash,
            "streams": self.streams,
            "batch_size": self.batch_size,
            "emitted_count": self.emitted_count,
            "last_ordering_key": (
                None
                if self.last_ordering_key is None
                else _ordering_key_dict(self.last_ordering_key)
            ),
            "window_complete": self.window_complete,
        }


@dataclass(frozen=True, slots=True)
class TimelineFailure:
    code: TimelineFailureCode
    cursor_hash: str
    subject_keys: tuple[str, ...]
    event_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, TimelineFailureCode):
            raise TypeError("code must be TimelineFailureCode")
        _validate_hash("cursor_hash", self.cursor_hash)
        subjects = tuple(sorted({_canonical_stream_key(item) for item in self.subject_keys}))
        if not subjects:
            raise ValueError("timeline failure requires a subject key")
        object.__setattr__(self, "subject_keys", subjects)
        hashes = tuple(sorted({_validate_hash("event_hash", item) for item in self.event_hashes}))
        object.__setattr__(self, "event_hashes", hashes)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "timeline_failure",
            "code": self.code.value,
            "cursor_hash": self.cursor_hash,
            "subject_keys": self.subject_keys,
            "event_hashes": self.event_hashes,
        }


@dataclass(frozen=True, slots=True)
class TimelineBatch:
    events: tuple[TimelineEvent, ...]
    next_cursor: TimelineCursor
    window_complete: bool

    def __post_init__(self) -> None:
        if not isinstance(self.events, tuple) or any(
            not isinstance(event, TimelineEvent) for event in self.events
        ):
            raise TypeError("events must be a tuple of TimelineEvent values")
        if not isinstance(self.next_cursor, TimelineCursor):
            raise TypeError("next_cursor must be TimelineCursor")
        if not isinstance(self.window_complete, bool):
            raise TypeError("window_complete must be a bool")
        if self.window_complete != self.next_cursor.window_complete:
            raise ValueError("batch completion must match next cursor")
        if self.next_cursor.emitted_count < len(self.events):
            raise ValueError("cursor emitted_count cannot precede the batch")

    @property
    def batch_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "timeline_batch",
            "events": self.events,
            "next_cursor": self.next_cursor,
            "window_complete": self.window_complete,
        }


@dataclass(frozen=True, slots=True)
class TimelineReadOutcome:
    batch: TimelineBatch | None = None
    failure: TimelineFailure | None = None

    def __post_init__(self) -> None:
        if (self.batch is None) == (self.failure is None):
            raise ValueError("timeline outcome requires exactly one batch or failure")
        if self.batch is not None and not isinstance(self.batch, TimelineBatch):
            raise TypeError("batch must be TimelineBatch")
        if self.failure is not None and not isinstance(self.failure, TimelineFailure):
            raise TypeError("failure must be TimelineFailure")

    @classmethod
    def for_batch(cls, batch: TimelineBatch) -> TimelineReadOutcome:
        return cls(batch=batch)

    @classmethod
    def for_failure(cls, failure: TimelineFailure) -> TimelineReadOutcome:
        return cls(failure=failure)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "timeline_read_outcome",
            "batch": self.batch,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class DeterministicTimeline:
    reader: MarketBundleReader
    stream_keys: tuple[str, ...]
    window: TimelineWindow
    timeline_id: str

    @classmethod
    def open(
        cls,
        *,
        reader: MarketBundleReader,
        stream_keys: Iterable[str],
        window: TimelineWindow,
    ) -> DeterministicTimeline | InputValidationFailure:
        if not isinstance(reader, MarketBundleReader):
            raise TypeError("reader must satisfy MarketBundleReader")
        if not isinstance(window, TimelineWindow):
            raise TypeError("window must be TimelineWindow")
        keys = tuple(_canonical_stream_key(item) for item in stream_keys)
        if not keys:
            raise ValueError("timeline requires at least one stream")
        if len(set(keys)) != len(keys):
            raise ValueError("timeline stream keys must be unique")
        keys = tuple(sorted(keys))
        failure = reader.validate_requirements(required_streams=keys)
        if failure is not None:
            return failure
        timeline_id = canonical_sha256(
            {
                "type": "deterministic_timeline_config",
                "bundle_ref": reader.bundle_ref,
                "stream_keys": keys,
                "window": window,
            }
        )
        return cls(
            reader=reader,
            stream_keys=keys,
            window=window,
            timeline_id=timeline_id,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.reader, MarketBundleReader):
            raise TypeError("reader must satisfy MarketBundleReader")
        if not self.stream_keys or tuple(sorted(self.stream_keys)) != self.stream_keys:
            raise ValueError("stream_keys must be nonempty and canonical-sorted")
        if len(set(self.stream_keys)) != len(self.stream_keys):
            raise ValueError("stream_keys must be unique")
        if not isinstance(self.window, TimelineWindow):
            raise TypeError("window must be TimelineWindow")
        _validate_hash("timeline_id", self.timeline_id)
        expected_id = canonical_sha256(
            {
                "type": "deterministic_timeline_config",
                "bundle_ref": self.reader.bundle_ref,
                "stream_keys": self.stream_keys,
                "window": self.window,
            }
        )
        if self.timeline_id != expected_id:
            raise ValueError("timeline_id does not match timeline configuration")

    def open_cursor(self, *, batch_size: int) -> TimelineCursor:
        if isinstance(batch_size, bool) or not isinstance(batch_size, int):
            raise TypeError("batch_size must be an integer")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        source_cursors = []
        for stream_key in self.stream_keys:
            cursor = self.reader.open_cursor(stream_key, batch_size=1)
            if isinstance(cursor, InputValidationFailure):
                raise TimelineError("validated timeline stream became unavailable")
            source_cursors.append(TimelineStreamCursor(stream_key, cursor))
        streams = tuple(source_cursors)
        return TimelineCursor(
            timeline_id=self.timeline_id,
            bundle_ref=self.reader.bundle_ref,
            window_hash=self.window.window_hash,
            streams=streams,
            batch_size=batch_size,
            window_complete=bool(self._completion_status(streams)),
        )

    def resume_cursor(
        self, cursor: TimelineCursor, *, batch_size: int | None = None
    ) -> TimelineCursor:
        if not isinstance(cursor, TimelineCursor):
            raise TimelineCursorError("cursor must be TimelineCursor")
        if cursor.timeline_id != self.timeline_id:
            raise TimelineCursorError("cursor timeline identity does not match")
        if cursor.bundle_ref != self.reader.bundle_ref:
            raise TimelineCursorError("cursor bundle does not match timeline")
        if cursor.window_hash != self.window.window_hash:
            raise TimelineCursorError("cursor window does not match timeline")
        if tuple(item.stream_key for item in cursor.streams) != self.stream_keys:
            raise TimelineCursorError("cursor source streams do not match timeline")
        verified_streams = []
        previous_keys: list[OrderingKey] = []
        for item in cursor.streams:
            try:
                verified = self.reader.resume_cursor(item.cursor, batch_size=1)
            except MarketBundleError as error:
                raise TimelineCursorError(
                    f"source cursor cannot resume: {item.stream_key}"
                ) from error
            if verified.position != item.cursor.position:
                raise TimelineCursorError("reader changed source cursor position")
            verified_item = TimelineStreamCursor(item.stream_key, verified)
            verified_streams.append(verified_item)
            if verified.position > 0:
                previous = EventCursor(
                    bundle_ref=verified.bundle_ref,
                    stream_manifest=verified.stream_manifest,
                    position=verified.position - 1,
                    batch_size=1,
                )
                try:
                    batch, _ = self.reader.read_batch(previous)
                except MarketBundleError as error:
                    raise TimelineCursorError(
                        f"source cursor prefix cannot be verified: {item.stream_key}"
                    ) from error
                if len(batch) != 1 or not isinstance(batch[0], MarketEvent):
                    raise TimelineCursorError("source cursor prefix event is malformed")
                if not isinstance(batch[0].source_sequence, SourceSequence):
                    raise TimelineCursorError(
                        "source cursor prefix lacks source sequence evidence"
                    )
                previous_keys.append(batch[0].ordering_key)
        expected_last = max(previous_keys) if previous_keys else None
        if cursor.last_ordering_key != expected_last:
            raise TimelineCursorError("cursor source positions do not match last ordering key")
        completion = self._completion_status(tuple(verified_streams))
        if completion is not None and cursor.window_complete != completion:
            raise TimelineCursorError("cursor completion does not match source positions")
        resolved_size = cursor.batch_size if batch_size is None else batch_size
        return TimelineCursor(
            timeline_id=self.timeline_id,
            bundle_ref=self.reader.bundle_ref,
            window_hash=self.window.window_hash,
            streams=tuple(verified_streams),
            batch_size=resolved_size,
            emitted_count=cursor.emitted_count,
            last_ordering_key=cursor.last_ordering_key,
            window_complete=cursor.window_complete,
        )

    def _completion_status(
        self, streams: tuple[TimelineStreamCursor, ...]
    ) -> bool | None:
        available_times: list[int] = []
        for item in streams:
            if item.cursor.exhausted:
                continue
            try:
                batch, next_cursor = self.reader.read_batch(item.cursor)
            except MarketBundleError:
                return None
            if (
                len(batch) != 1
                or next_cursor.position != item.cursor.position + 1
                or not isinstance(batch[0], MarketEvent)
            ):
                return None
            available_times.append(batch[0].available_time.epoch_nanoseconds)
        if not available_times:
            return True
        return min(available_times) >= self.window.end_exclusive.epoch_nanoseconds

    def _failure(
        self,
        cursor: TimelineCursor,
        code: TimelineFailureCode,
        subject_keys: Iterable[str],
        event_hashes: Iterable[str] = (),
    ) -> TimelineReadOutcome:
        return TimelineReadOutcome.for_failure(
            TimelineFailure(
                code=code,
                cursor_hash=cursor.cursor_hash,
                subject_keys=tuple(subject_keys),
                event_hashes=tuple(event_hashes),
            )
        )

    def _head(
        self, cursor: TimelineStreamCursor, timeline_cursor: TimelineCursor
    ) -> tuple[MarketEvent, EventCursor] | TimelineReadOutcome | None:
        if cursor.cursor.exhausted:
            return None
        try:
            batch, next_cursor = self.reader.read_batch(cursor.cursor)
        except MarketBundleError:
            return self._failure(
                timeline_cursor,
                TimelineFailureCode.MALFORMED_EVENT,
                (cursor.stream_key,),
            )
        if len(batch) != 1 or next_cursor.position != cursor.cursor.position + 1:
            return self._failure(
                timeline_cursor,
                TimelineFailureCode.MALFORMED_EVENT,
                (cursor.stream_key,),
            )
        event = batch[0]
        if not isinstance(event, MarketEvent) or event.stream_key != cursor.stream_key:
            return self._failure(
                timeline_cursor,
                TimelineFailureCode.MALFORMED_EVENT,
                (cursor.stream_key,),
            )
        if not isinstance(event.source_sequence, SourceSequence):
            return self._failure(
                timeline_cursor,
                TimelineFailureCode.MISSING_SOURCE_SEQUENCE,
                (cursor.stream_key,),
            )
        return event, next_cursor

    def read_batch(self, cursor: TimelineCursor) -> TimelineReadOutcome:
        current = self.resume_cursor(cursor)
        if current.window_complete:
            return TimelineReadOutcome.for_batch(
                TimelineBatch((), current, window_complete=True)
            )

        source_cursors = {item.stream_key: item.cursor for item in current.streams}
        emitted: list[TimelineEvent] = []
        last_key = current.last_ordering_key
        complete = False

        while len(emitted) < current.batch_size:
            heads: list[tuple[OrderingKey, str, MarketEvent, EventCursor]] = []
            for stream_key in self.stream_keys:
                stream_cursor = TimelineStreamCursor(
                    stream_key, source_cursors[stream_key]
                )
                head = self._head(stream_cursor, current)
                if isinstance(head, TimelineReadOutcome):
                    return head
                if head is None:
                    continue
                event, head_next_cursor = head
                heads.append(
                    (event.ordering_key, stream_key, event, head_next_cursor)
                )

            if not heads:
                complete = True
                break

            minimum_key = min(item[0] for item in heads)
            minimum = [item for item in heads if item[0] == minimum_key]
            if len(minimum) != 1:
                return self._failure(
                    current,
                    TimelineFailureCode.DUPLICATE_ORDERING_KEY,
                    (item[1] for item in minimum),
                    (item[2].event_hash for item in minimum),
                )
            _, stream_key, event, next_source_cursor = minimum[0]
            if last_key is not None and minimum_key <= last_key:
                code = (
                    TimelineFailureCode.DUPLICATE_ORDERING_KEY
                    if minimum_key == last_key
                    else TimelineFailureCode.ORDER_REGRESSION
                )
                return self._failure(
                    current, code, (stream_key,), (event.event_hash,)
                )
            if (
                event.available_time.epoch_nanoseconds
                >= self.window.end_exclusive.epoch_nanoseconds
            ):
                complete = True
                break

            source_cursors[stream_key] = next_source_cursor
            last_key = minimum_key
            if (
                event.available_time.epoch_nanoseconds
                < self.window.data_start.epoch_nanoseconds
            ):
                continue
            segment = (
                TimelineSegment.WARMUP
                if event.available_time.epoch_nanoseconds
                < self.window.trading_start.epoch_nanoseconds
                else TimelineSegment.ACTIVE_TRADING
            )
            emitted.append(TimelineEvent(segment=segment, event=event))

        next_streams = tuple(
            TimelineStreamCursor(key, source_cursors[key]) for key in self.stream_keys
        )
        if not complete and self._completion_status(next_streams):
            complete = True
        timeline_cursor = TimelineCursor(
            timeline_id=self.timeline_id,
            bundle_ref=self.reader.bundle_ref,
            window_hash=self.window.window_hash,
            streams=next_streams,
            batch_size=current.batch_size,
            emitted_count=current.emitted_count + len(emitted),
            last_ordering_key=last_key,
            window_complete=complete,
        )
        return TimelineReadOutcome.for_batch(
            TimelineBatch(tuple(emitted), timeline_cursor, window_complete=complete)
        )
