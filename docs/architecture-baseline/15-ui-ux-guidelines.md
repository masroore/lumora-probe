# 15-ui-ux-guidelines.md

> **Project:** Lumora Probe
>
> **Document:** UI / UX Guidelines
>
> **Status:** Architecture Baseline
>
> **Audience:** Product Designers, Frontend Engineers, Architects, QA, Claude Code, Codex

---

# 1. Purpose

This document defines the user experience and interface architecture for Lumora Probe.

It establishes consistent interaction patterns, layout principles, navigation, and usability expectations. Visual implementation details remain flexible provided they conform to these guidelines.

---

# 2. UX Vision

Lumora Probe is an engineering workstation—not a diagnostic viewer.

The interface should prioritize:

- Investigation
- Productivity
- Context
- Traceability
- Low cognitive load

The primary inspiration is a modern developer IDE rather than a clinical imaging workstation.

---

# 3. Design Principles

The interface should be:

- Fast
- Predictable
- Consistent
- Information-dense
- Keyboard-friendly
- Discoverable
- Accessible

---

# 4. Layout Philosophy

Recommended workspace:

```
+------------------------------------------------------+
| Toolbar                                               |
+------------------------------------------------------+
| Explorer | Viewer | Inspector                         |
|          |        |                                   |
+------------------------------------------------------+
| Timeline / Logs / Dataset / Console                  |
+------------------------------------------------------+
| Status Bar                                           |
+------------------------------------------------------+
```

Panels should be resizable and collapsible.

---

# 5. Navigation

Primary navigation may include:

- Dashboard
- Live Monitor
- Study Browser
- Capture
- Replay
- Reports
- Plugins
- Settings

Navigation should remain shallow and predictable.

---

# 6. Workspace Components

Core UI components include:

- Explorer
- Viewer
- Metadata Inspector
- Event Timeline
- Log Console
- Search Panel
- Status Bar
- Notifications

Components should synchronize automatically where appropriate.

---

# 7. Viewer Experience

The viewer should provide engineering-focused functionality including:

- Zoom
- Pan
- Window/Level
- Invert
- Cine
- Fullscreen

Diagnostic measurement tools are outside the scope of Lumora Probe.

---

# 8. Inspector Panels

Typical inspector tabs:

- Metadata
- Properties
- Transfer
- Analysis
- Events

Panels should support efficient searching and filtering.

---

# 9. Search Experience

Search should support:

- Studies
- Series
- Instances
- Events
- Logs
- Reports
- Plugins

Search should provide fast incremental results.

---

# 10. Event Timeline

The timeline should visualize:

- Associations
- DIMSE operations
- Capture events
- Replay events
- Analysis events
- Errors

Timeline interactions should synchronize with other workspace components.

---

# 11. Notifications

Notifications should be:

- Informational
- Actionable
- Non-intrusive

Critical failures should remain visible until acknowledged.

---

# 12. Keyboard Support

The interface should support:

- Keyboard navigation
- Command shortcuts
- Focus management
- Command palette
- Context-sensitive actions

Mouse interaction should not be mandatory.

---

# 13. Accessibility

The UI should support:

- Keyboard-only operation
- Screen readers where practical
- High-contrast themes
- Scalable typography
- Sufficient color contrast

Accessibility should be considered throughout the design.

---

# 14. Theming

The platform should support:

- Light theme
- Dark theme
- System preference
- Future custom themes

Theming should not affect functionality.

---

# 15. Responsiveness

Primary target:

- Desktop workstations

Secondary support:

- Large tablets

Mobile support is limited to basic monitoring and administrative functions.

---

# 16. Performance

The interface should:

- Render incrementally
- Remain responsive during background work
- Support large datasets
- Avoid unnecessary redraws

---

# 17. Extensibility

Plugins may contribute:

- Panels
- Viewer tools
- Menu items
- Commands
- Notifications
- Settings

Core navigation should remain consistent.

---

# 18. Acceptance Criteria

The UX architecture is complete when:

- Layout principles are defined.
- Navigation model is documented.
- Workspace components are identified.
- Viewer behavior is described.
- Accessibility guidance exists.
- Theming expectations are documented.
- Plugin extension points are identified.

---

# 19. References

- 01-product-vision.md
- 02-product-requirements-document.md
- 03-system-architecture.md
- 05-system-modules.md
- 10-plugin-sdk.md
- 14-observability-architecture.md
