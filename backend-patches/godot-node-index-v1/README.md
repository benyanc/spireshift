# Headless Node.GetIndex support

The frozen game calls `Godot.Node.GetIndex(Boolean)` from the private
`ReattachPower.DoFadeOutOnAllSegments` presentation method. CLI56's support
assembly lacks that signature. The runtime fails while compiling the method,
before its normal empty-headless-scene return can run.

The patch adds the signature to a separate support build. It reports the index
in the existing plain headless sibling list, or -1 when detached. Its optional
argument matches the Godot binding. See the [Godot 4.5 index implementation](https://github.com/godotengine/godot/blob/4.5/scene/main/node.h#L499)
and [binding default](https://github.com/godotengine/godot/blob/4.5/scene/main/node.cpp#L3518).
Full renderer/internal-node modeling is outside this headless control.

The probe checks the exact method signature, plain-node ordering/removal and
direct compilation of the failing native method. The old library reproduces
the missing method; both fresh support builds compile it. The game assembly
and all CLI/gameplay source remain unchanged. Native effect controls additionally
check individual segment regeneration/targetability and completion when all
segments die. Runtime errors remain fatal.
