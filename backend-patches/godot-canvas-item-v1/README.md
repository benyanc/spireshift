# CanvasItem support for Test Subject

The frozen game calls `Godot.CanvasItem.SetSelfModulate(Color)` when Test Subject
applies or removes its visual tint during Intangible. This patch adds the exact
method signature and writes the existing per-instance `SelfModulate` property.

Apply to the separately qualified support build 57 source under `src/`. The
probe compiles Test Subject's color method against both candidates, checks the
property assignment and inventories Godot method references with a TypeRef
parent. Generic TypeSpec targets, dynamic calls and runtime reachability lie
outside that inventory. The live control exercises both revivals, Intangible
application and removal, and the post-boss reward owner.
