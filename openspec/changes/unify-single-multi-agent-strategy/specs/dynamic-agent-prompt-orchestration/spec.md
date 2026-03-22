## MODIFIED Requirements

### Requirement: Main Agent SHALL Execute a Mandatory Integration Gate
The orchestration prompt system SHALL require the main agent to execute an explicit information integration stage after receiving child-agent outputs and before generating final synthesis.

#### Scenario: Integration gate enforced before synthesis
- **WHEN** all child-agent research tasks complete
- **THEN** the main agent MUST run an integration gate task (`task-merge`) that produces canonical facts, conflict analysis, uncertainty notes, and claim-to-evidence mapping
- **AND** final synthesis is not allowed before `task-merge` succeeds

### Requirement: Main Agent SHALL Dynamically Define Child-Agent Identity and Contracts
The decomposition prompt SHALL instruct the main agent to define child-agent identities and task contracts under a unified multi-agent strategy, rather than exposing separate quick/standard/deep strategy semantics.

#### Scenario: Unified strategy decomposition behavior
- **WHEN** a user request enters decomposition
- **THEN** the main agent MUST generate capability-based role definitions with explicit must-do and must-not-do constraints
- **AND** the generated plan MUST satisfy minimum multi-agent topology requirements

### Requirement: Synthesis SHALL Depend on Integration Output Instead of Raw Parallel Outputs
Prompt dependency semantics SHALL ensure final synthesis depends on integration output as the authoritative upstream artifact, not directly on all parallel child outputs.

#### Scenario: Integration artifact as synthesis input
- **WHEN** final synthesis is prepared
- **THEN** synthesis MUST consume the integration artifact as primary evidence context
- **AND** synthesis MUST mark unsupported claims as uncertain

## ADDED Requirements

### Requirement: Decomposition SHALL Enforce Minimum Multi-Agent Topology
The decomposition planner SHALL enforce a minimum topology of two research tasks plus one integration gate task (`task-merge`) for eligible research runs.

#### Scenario: Minimum topology enforcement
- **WHEN** decomposition produces fewer than two research tasks or omits `task-merge`
- **THEN** plan correction MUST inject or expand tasks to include at least two research tasks and one `task-merge`
- **AND** downstream synthesis/transform tasks MUST depend on `task-merge` when present
