# Specifications

Finish Protocol Generator is developed spec-first for changes to its file formats, its exchange
with the cycling site and what the referee sees, with [Spec Kit](https://github.com/github/spec-kit),
whose skills both coding agents here (Claude Code and Codex) carry.

```
specs/
  app/                        the program as it works today
    generator.md              a run, the window, the log, the start board
    files.md                  the files it reads and writes, fpg_info.txt among them
    scoring.md                race types, laps, statuses, order, places, checks
    protocols.md              the group and absolute protocols, the site document
    eliminator-finals.md      ladders, heats and the finals protocol
    site-exchange.md          the cycling site and FTP
  <NNN>-<short-name>/         one feature
    spec.md                   what and why, for the referee and the readers of the files
    plan.md, tasks.md         how it will be built, once the spec is reviewed
```

The principles every plan is checked against are in
[`.specify/memory/constitution.md`](../.specify/memory/constitution.md).

**Keep `app/` true.** A change that alters described behaviour updates it in the same pull request.
