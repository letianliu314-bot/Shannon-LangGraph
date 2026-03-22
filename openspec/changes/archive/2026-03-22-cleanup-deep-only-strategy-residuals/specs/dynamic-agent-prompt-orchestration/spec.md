## MODIFIED Requirements

### Requirement: Main Agent SHALL Dynamically Define Child-Agent Identity and Contracts
The decomposition prompt SHALL instruct the main agent to define child-agent identities and task contracts based on query complexity, uncertainty, and decision objective, under unified deep-only strategy semantics rather than legacy quick/standard strategy tiers.

#### Scenario: Deep-only complexity-driven child identity generation
- **WHEN** a user query enters decomposition
- **THEN** the main agent MUST determine child-agent count and generate capability-based role definitions with explicit must-do and must-not-do constraints
- **AND** prompt instructions MUST NOT introduce quick/standard strategy-tier guidance as alternative planning modes
