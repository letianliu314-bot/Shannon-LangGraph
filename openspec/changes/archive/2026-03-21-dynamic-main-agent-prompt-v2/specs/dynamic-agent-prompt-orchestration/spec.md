## ADDED Requirements

### Requirement: Main Agent SHALL Execute a Mandatory Integration Gate
The orchestration prompt system SHALL require the main agent to execute an explicit information integration stage after receiving child-agent outputs and before generating final synthesis.

#### Scenario: Integration gate enforced before synthesis
- **WHEN** all child-agent tasks complete
- **THEN** the main agent MUST produce an integration artifact containing canonical facts, conflict analysis, uncertainty notes, and claim-to-evidence mapping before final synthesis is allowed

### Requirement: Main Agent SHALL Dynamically Define Child-Agent Identity and Contracts
The decomposition prompt SHALL instruct the main agent to define child-agent identities and task contracts based on query complexity, uncertainty, and decision objective, rather than fixed domain role templates.

#### Scenario: Complexity-driven child identity generation
- **WHEN** a user query is classified as simple, standard, or deep
- **THEN** the main agent MUST determine child-agent count and generate capability-based role definitions with explicit must-do and must-not-do constraints

### Requirement: Child Task Contracts SHALL Be Domain-Agnostic and Executable
Each child task contract SHALL include objective, scope boundaries, source guidance, evidence requirements, output format, acceptance criteria, and dependencies in a machine-consumable structure.

#### Scenario: Contract completeness validation
- **WHEN** a child task is generated
- **THEN** the contract MUST include all required fields and SHALL be rejected or retried if any required contract field is missing

### Requirement: Synthesis SHALL Depend on Integration Output Instead of Raw Parallel Outputs
Prompt dependency semantics SHALL ensure final synthesis depends on integration output as the authoritative upstream artifact, not directly on all parallel child outputs.

#### Scenario: Integration artifact as synthesis input
- **WHEN** final synthesis is prepared
- **THEN** synthesis MUST consume the integration artifact as primary evidence context and SHALL mark unsupported claims as uncertain
