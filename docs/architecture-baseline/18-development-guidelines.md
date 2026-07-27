# 18-development-guidelines.md

> **Project:** Lumora Probe
>
> **Document:** Development Guidelines
>
> **Status:** Architecture Baseline
>
> **Audience:** Engineers, Architects, QA, Plugin Developers, Claude Code, Codex

---

# 1. Purpose

This document defines the engineering standards and development practices for Lumora Probe.

It establishes shared expectations for code quality, project organization, collaboration, and AI-assisted development. Detailed implementation standards may evolve, but should remain consistent with these guidelines.

---

# 2. Objectives

Development practices SHALL:

- Promote maintainability
- Encourage consistency
- Reduce technical debt
- Support automation
- Enable parallel development
- Preserve architectural integrity

---

# 3. Engineering Principles

The project should emphasize:

- Simplicity
- Readability
- Modularity
- Testability
- Performance
- Security
- Observability

---

# 4. Repository Organization

Recommended top-level structure:

```
docs/
src/
tests/
examples/
scripts/
tools/
assets/
```

Each directory should have a clearly defined purpose.

---

# 5. Project Structure

The implementation should organize code into cohesive modules that align with:

- System architecture
- Domain model
- Event architecture
- Plugin architecture

Cross-module coupling should be minimized.

---

# 6. Coding Standards

Code should be:

- Consistent
- Self-documenting
- Strongly typed where practical
- Explicit rather than implicit
- Easy to review

Formatting should be automated.

---

# 7. Naming Conventions

Adopt consistent conventions for:

- Modules
- Packages
- Classes
- Functions
- Variables
- Events
- APIs
- Configuration keys

Names should clearly express intent.

---

# 8. Dependency Management

Dependencies should:

- Be minimized
- Be actively maintained
- Have compatible licenses
- Be version-pinned where appropriate
- Be periodically reviewed

---

# 9. Error Handling

Errors should:

- Be explicit
- Include sufficient context
- Avoid leaking sensitive information
- Support diagnostics
- Be logged appropriately

---

# 10. Logging

Logging should follow:

- Structured logging
- Correlation identifiers
- Appropriate severity levels
- Minimal sensitive data
- Consistent formatting

Refer to:

- 14-observability-architecture.md

---

# 11. Event Publishing

Modules should publish events in accordance with:

- 06-event-driven-architecture.md

Event contracts should remain stable.

---

# 12. Testing Expectations

Every contribution should include appropriate:

- Unit tests
- Integration tests
- Documentation updates
- Regression validation

Testing requirements are defined in:

- 13-testing-strategy.md

---

# 13. Documentation

Documentation should remain:

- Accurate
- Version controlled
- Discoverable
- Updated alongside code

Architecture changes should be accompanied by relevant documentation updates.

---

# 14. Git Workflow

Recommended workflow:

- Feature branches
- Small commits
- Descriptive commit messages
- Pull requests
- Code reviews

Mainline branches should remain deployable.

---

# 15. Code Review

Reviews should evaluate:

- Correctness
- Architecture alignment
- Security
- Performance
- Maintainability
- Test coverage
- Documentation

---

# 16. AI-Assisted Development

AI coding assistants should:

- Follow architecture documents
- Respect ADRs
- Avoid introducing undocumented patterns
- Update documentation when appropriate
- Preserve backward compatibility where practical

Generated code should receive the same review standards as manually written code.

---

# 17. Continuous Improvement

The engineering team should periodically review:

- Coding standards
- Tooling
- Dependencies
- Build performance
- Test quality
- Documentation quality

---

# 18. Acceptance Criteria

The development guidelines are complete when:

- Engineering principles are documented.
- Repository organization is defined.
- Coding standards are established.
- Review expectations are documented.
- AI development guidance is provided.
- Documentation responsibilities are defined.

---

# 19. References

- 03-system-architecture.md
- 04-technology-stack.md
- 06-event-driven-architecture.md
- 10-plugin-sdk.md
- 13-testing-strategy.md
- 14-observability-architecture.md
- 17-architecture-decision-records.md
