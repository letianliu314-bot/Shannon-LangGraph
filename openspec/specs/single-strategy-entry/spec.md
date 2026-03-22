# Purpose

Define product and backend requirements for deep-only strategy exposure, legacy alias compatibility behavior, and deprecation observability policy.

## ADDED Requirements

### Requirement: Product SHALL Expose a Single Strategy Entry
The system SHALL expose exactly one strategy option in product-facing run controls and SHALL remove user-facing selection of `quick` and `standard`.

#### Scenario: Single strategy selection in UI
- **WHEN** a user opens run controls in product UI
- **THEN** only one strategy entry is visible
- **AND** `quick` and `standard` are not selectable

### Requirement: Backend SHALL Map Legacy Strategy Aliases to Unified Semantics
The backend SHALL accept legacy strategy values `quick` and `standard` as compatibility aliases and MUST execute them with unified multi-agent semantics.

#### Scenario: Alias compatibility mapping
- **WHEN** a run request includes strategy `quick` or `standard`
- **THEN** the request is accepted
- **AND** runtime behavior is equivalent to the unified strategy path

### Requirement: Backend SHALL Emit Deprecation Signals for Legacy Aliases
The runtime SHALL emit deprecation metadata or logs whenever `quick` or `standard` is received.

#### Scenario: Legacy alias observability
- **WHEN** a run request includes a legacy strategy alias
- **THEN** the system records a deprecation signal containing the received alias and unified strategy mapping
