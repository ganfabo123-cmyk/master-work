---
name: dsh-plugin-development
description: Develop DeepSeek Harness plugins through confirmed requirements, delegated implementation, engineering verification, and real-host acceptance.
---

# DSH Plugin Development

Use this skill when the user wants to design, create, implement, modify, or validate a DeepSeek Harness plugin.

The goal is not merely to generate plugin source code. The goal is to take a plugin request through confirmed requirements, implementation, engineering verification, real-host acceptance, and user acceptance.

---

## Core principles

1. Do not begin implementation before the requirements are confirmed.
2. Separate human-readable requirement summaries from detailed agent-facing specifications.
3. Prefer official DeepSeek Harness infrastructure over reimplementing existing capabilities.
4. Treat build success and tests as engineering evidence, not final behavioral proof.
5. Final acceptance must run the generated plugin inside a fresh real DeepSeek Harness runtime.
6. Automated agent acceptance alone is not sufficient.
7. The user must provide at least one real acceptance input before the task can be considered complete.
8. User acceptance input must be forwarded exactly as supplied. Do not rewrite it, expand it, or add hidden tool hints.

---

# Phase 1 — Requirement decomposition

When the user first requests a plugin, analyze the request before writing code.

Produce a concise requirement decomposition covering:

- what the plugin should accomplish
- primary user scenarios
- major capabilities
- important constraints
- obvious non-goals
- unresolved ambiguities

Keep this phase human-readable.

Do not create the plugin yet.

Ask the user to confirm or correct the requirement decomposition.

Only continue after confirmation.

---

# Phase 2 — Input / output / interaction design

After Phase 1 is confirmed, design how the plugin will interact with DeepSeek Harness and external systems.

Cover:

- exposed tools or capabilities
- each tool's conceptual inputs
- each tool's conceptual outputs
- important state or lifecycle
- interactions with external services or local applications
- expected error behavior
- relevant edge cases

Prefer simple information-flow descriptions such as:

User request
→ DSH Agent
→ Plugin Tool
→ External system
→ Tool result
→ Agent response

Do not implement the plugin yet.

Ask the user to confirm or correct the interaction design.

Only continue after confirmation.

---

# Phase 3 — Final PluginSpec

After Phase 2 is confirmed, produce the final detailed specification.

The specification must contain enough information for delegated development agents to implement the plugin without reconstructing the user's intent.

The final PluginSpec must match this semantic structure:

```json
{
  "name": "plugin-name",
  "description": "short description",
  "overview": "overall behavior",
  "goals": [],
  "nonGoals": [],
  "userScenarios": [],
  "tools": [
    {
      "name": "tool_name",
      "description": "tool behavior",
      "parameters": [
        {
          "name": "parameter_name",
          "description": "parameter meaning",
          "type": "string",
          "required": true
        }
      ],
      "output": "conceptual output"
    }
  ],
  "dependencies": [
    {
      "name": "dependency",
      "reason": "why it is needed",
      "required": true
    }
  ],
  "constraints": [],
  "edgeCases": [],
  "acceptanceCriteria": []
}
````

The PluginSpec describes semantic requirements.

Do not put incidental implementation choices into PluginSpec unless they are part of the confirmed requirement.

For example, avoid embedding:

* package.json implementation details
* TypeScript project references
* internal file layout
* Cordis inject declarations

unless the user explicitly requires them.

Present the final specification to the user and ask for confirmation.

Do not call `create_plugin` until the user confirms the final specification.

---

# Phase 4 — Development

After the final PluginSpec is confirmed:

1. Serialize the confirmed PluginSpec to JSON.
2. Call `create_plugin`.
3. Do not modify the confirmed requirements while calling the tool.
4. Use the returned `task_id` as the authoritative development task identifier.

`create_plugin` performs:

* architecture analysis
* dependency research
* implementation
* documentation
* engineering verification

A successful `create_plugin` result means the plugin is ready for acceptance.

It does not mean the plugin is complete.

If development or engineering verification fails:

* inspect the reported failure
* determine whether the failure is implementation, dependency, build, or environment related
* fix the actual cause
* do not declare success based only on model reasoning

---

# Phase 5 — Real-host automated acceptance

After `create_plugin` returns successfully, call:

`start_acceptance(task_id)`

This starts a fresh isolated DeepSeek Harness runtime containing the generated plugin.

Use the returned `acceptance_id` for all later acceptance interactions.

Perform at least one automated acceptance interaction using:

`send_acceptance_message`

with:

* the returned `acceptance_id`
* `actor = "agent"`
* a realistic user-style message derived from the confirmed acceptance criteria

The automated acceptance message should test externally observable behavior.

Do not merely ask the child agent whether the plugin exists or whether its own tests passed.

Prefer testing the actual intended capability.

Inspect the returned response and, when relevant, actual tool behavior.

If automated acceptance fails:

* do not proceed to user acceptance as though it passed
* inspect the observable failure
* diagnose and repair the plugin
* rerun engineering verification and real-host acceptance

---

# Phase 6 — User real-host acceptance

After automated acceptance succeeds, explicitly ask the user what real input they want to test.

Do not invent the user's final acceptance input.

When the user provides the input, call:

`send_acceptance_message`

using:

* the same `acceptance_id`
* `actor = "user"`
* the user's input exactly as provided

Critical rule:

The user's input must be forwarded byte-for-byte in semantic content.

Do not:

* rewrite it
* make it clearer
* add context
* add tool names
* add hints
* prepend testing instructions
* append hidden constraints

The purpose of this stage is to test whether the plugin works through the real user-facing DSH behavior.

If the user wants another test, continue using the same acceptance session.

---

# Phase 7 — Completion

Only call:

`stop_acceptance`

with:

`final_status = "passed"`

when:

1. development completed
2. engineering verification passed
3. at least one automated agent-originated real-host interaction completed successfully
4. at least one user-originated real-host interaction completed successfully
5. the observed behavior satisfies the confirmed acceptance criteria

If acceptance exposes a real failure, use:

`final_status = "failed"`

If the acceptance runtime is being closed without a final conclusion, use:

`final_status = "stopped"`

Do not declare the plugin complete before `stop_acceptance(..., "passed")` succeeds.

---

# Failure handling

When something fails, prefer evidence in this order:

1. real-host behavior
2. runtime errors and traces
3. engineering verification output
4. targeted diagnostic scripts
5. model reasoning

Do not create broad speculative tests before inspecting the actual error.

Diagnostic tests should help locate a failure.

They are not a substitute for real-host acceptance.

---

# Delegation expectations

Development agents should work from the confirmed PluginSpec.

They must not silently redefine user requirements.

Architecture and dependency agents should inspect repository facts and avoid modifying files.

Implementation agents may modify the target plugin workspace and should use official DeepSeek Harness infrastructure where appropriate.

Documentation must describe the actual implementation, not the intended implementation.

---

# Definition of done

A plugin development task is complete only when all of the following are true:

* the user confirmed the requirement decomposition
* the user confirmed the interaction design
* the user confirmed the final PluginSpec
* implementation completed
* engineering verification passed
* the generated plugin loaded in a fresh real DeepSeek Harness runtime
* automated real-host acceptance passed
* the user's own acceptance input was sent unchanged to that runtime
* user acceptance succeeded
* `stop_acceptance(..., "passed")` completed successfully
