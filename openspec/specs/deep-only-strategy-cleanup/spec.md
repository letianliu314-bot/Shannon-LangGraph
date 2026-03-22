# Purpose

Define cleanup and consistency requirements for removing legacy strategy residue under unified deep-only semantics.

## ADDED Requirements

### Requirement: Prompt Strategy Guidance SHALL Be Deep-Only
The llm-service decomposition and supervisor prompt system SHALL expose a single deep-oriented strategy guidance path and MUST NOT include legacy quick/standard strategy guidance branches.

#### Scenario: Decomposition prompt generation
- **WHEN** a decompose system prompt is built for research context
- **THEN** the prompt content MUST NOT include quick/standard strategy guidance blocks
- **AND** the emitted guidance MUST align to one canonical deep-oriented planning contract

### Requirement: Runtime Strategy Branching SHALL Be Semantically Unified
The llm-service runtime strategy normalization and derived planning semantics SHALL execute as one unified deep behavior path.

#### Scenario: Refine/decompose strategy handling
- **WHEN** strategy input is processed by refine and decompose flows
- **THEN** model tier and complexity semantics MUST resolve to unified deep behavior
- **AND** no strategy-specific branch behavior for quick/standard MAY remain in active runtime logic

### Requirement: Alias Observability Metadata SHALL Be Removed Post-Migration
The orchestrator runtime metadata surface SHALL remove deprecated alias observability fields after migration close.

#### Scenario: Workflow metadata emission
- **WHEN** a run is accepted and workflow/session/manifest events are emitted
- **THEN** payloads MUST NOT include `strategy_requested` or `strategy_alias_deprecated`
- **AND** payloads MUST continue to expose normalized `strategy`

### Requirement: Temporary Rollout Validation Artifacts SHALL Not Persist in Active Paths
One-time rollout validation scripts and generated stress reports SHALL be removed from active tracked paths after acceptance closeout.

#### Scenario: Repository cleanliness after rollout close
- **WHEN** deep-only rollout verification is complete
- **THEN** temporary script/report artifacts used only for checkpoint validation MUST be deleted from active report paths
- **AND** any long-term retention MUST be handled through explicit archive storage
