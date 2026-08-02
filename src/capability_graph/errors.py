"""Capability-graph errors. All validation errors fail closed."""


class CapabilityGraphError(RuntimeError):
    """Base error for graph construction, storage, and querying."""


class AdapterError(CapabilityGraphError):
    """A discovered source cannot be parsed completely."""


class ValidationError(CapabilityGraphError):
    """The graph violates a structural invariant."""


class ProvenanceError(ValidationError):
    """A node or edge has incomplete provenance."""


class DuplicateNodeError(ValidationError):
    """Two emissions disagree about a node's semantic value."""


class SchemaMismatchError(CapabilityGraphError):
    """An existing database uses a different schema version."""


class NoSourcesError(CapabilityGraphError):
    """No supported source files were found."""


class StaleGraphError(CapabilityGraphError):
    """A query attempted to use a stale graph without explicit consent."""


class QueryRefusedError(CapabilityGraphError):
    """A query is unroutable or targets a route that must be refused."""


class EvaluationError(CapabilityGraphError):
    """A held-out evaluation case failed."""

