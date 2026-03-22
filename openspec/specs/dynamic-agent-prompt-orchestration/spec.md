# Purpose

Define orchestration prompt requirements for dynamic main-agent decomposition, integration-gate handoff, and synthesis dependency semantics.

## ADDED Requirements

### Requirement: Main Agent SHALL Execute a Mandatory Integration Gate
The orchestration prompt system SHALL require the main agent to execute an explicit information integration stage after receiving child-agent outputs and before generating final synthesis.

#### Scenario: Integration gate enforced before synthesis
- **WHEN** all child-agent research tasks complete
- **THEN** the main agent MUST run an integration gate task (`task-merge`) that produces canonical facts, conflict analysis, uncertainty notes, and claim-to-evidence mapping
- **AND** final synthesis is not allowed before `task-merge` succeeds

### Requirement: Main Agent SHALL Dynamically Define Child-Agent Identity and Contracts
The decomposition prompt SHALL instruct the main agent to define child-agent identities and task contracts based on query complexity, uncertainty, and decision objective, under unified deep-only strategy semantics rather than legacy quick/standard strategy tiers.

#### Scenario: Deep-only complexity-driven child identity generation
- **WHEN** a user query enters decomposition
- **THEN** the main agent MUST determine child-agent count and generate capability-based role definitions with explicit must-do and must-not-do constraints
- **AND** prompt instructions MUST NOT introduce quick/standard strategy-tier guidance as alternative planning modes

### Requirement: Child Task Contracts SHALL Be Domain-Agnostic and Executable
Each child task contract SHALL include objective, scope boundaries, source guidance, evidence requirements, output format, acceptance criteria, and dependencies in a machine-consumable structure.

#### Scenario: Contract completeness validation
- **WHEN** a child task is generated
- **THEN** the contract MUST include all required fields and SHALL be rejected or retried if any required contract field is missing

### Requirement: Synthesis SHALL Depend on Integration Output Instead of Raw Parallel Outputs
Prompt dependency semantics SHALL ensure final synthesis depends on integration output as the authoritative upstream artifact, not directly on all parallel child outputs.

#### Scenario: Integration artifact as synthesis input
- **WHEN** final synthesis is prepared
- **THEN** synthesis MUST consume the integration artifact as primary evidence context
- **AND** synthesis MUST mark unsupported claims as uncertain

### Requirement: Decomposition SHALL Enforce Minimum Multi-Agent Topology
The decomposition planner SHALL enforce a minimum topology of two research tasks plus one integration gate task (`task-merge`) for eligible research runs.

#### Scenario: Minimum topology enforcement
- **WHEN** decomposition produces fewer than two research tasks or omits `task-merge`
- **THEN** plan correction MUST inject or expand tasks to include at least two research tasks and one `task-merge`
- **AND** downstream synthesis/transform tasks MUST depend on `task-merge` when present
