# Role prompts

One file per role prompt, `<name>.md` (for example `interviewer.md`, `planner.md`,
`writer.md`, `editor.md`, `judge.md`). Each file is owned by the block that owns the role
(spec 004 § 3 and § 5.5); spec 010 (B6) only publishes them.

`app.commons.observability.load_prompt(name)` reads the file and, when Langfuse is on,
publishes it to Langfuse prompt management under the same name with the label
`production`, creating a new Langfuse version only when the content changed. The returned
`PromptRef.version` (the Langfuse version number, or `sha-<hash>` offline) is recorded on
every model call that uses the prompt, in the Langfuse generation and in the `llm_call`
table of the story bible.

Prompts that produce the novel's prose may be written in Spanish; everything else here is
in English.
