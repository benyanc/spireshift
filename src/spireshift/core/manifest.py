from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

PATCH_MANIFEST_SCHEMA_VERSION = "patch-manifest-v1"
_MANIFEST_ID_PREFIX = "sha256:"
_ADMISSION_STATUSES = {"test_only", "pending_conformance", "admitted"}
_DIGEST_LENGTHS = {
    "sha256": 64,
    "git-commit-sha1": 40,
    "git-tree-sha1": 40,
}


@dataclass(frozen=True, slots=True)
class Digest:
    algorithm: str
    value: str

    @classmethod
    def from_mapping(cls, value: object, label: str) -> Digest:
        mapping = _mapping(value, label)
        _require_exact_keys(mapping, {"algorithm", "value"}, label)
        algorithm = _string(mapping, "algorithm", label)
        digest = _string(mapping, "value", label).casefold()
        expected_length = _DIGEST_LENGTHS.get(algorithm)
        if expected_length is None:
            raise ValueError(f"{label}.algorithm is unsupported: {algorithm}")
        if len(digest) != expected_length or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError(f"{label}.value is not a valid {algorithm} digest")
        return cls(algorithm=algorithm, value=digest)

    def as_dict(self) -> dict[str, str]:
        return {"algorithm": self.algorithm, "value": self.value}


@dataclass(frozen=True, slots=True)
class ComponentIdentity:
    component_id: str
    version: str
    revision: str
    source: str
    digest: Digest

    @classmethod
    def from_mapping(cls, value: object, label: str) -> ComponentIdentity:
        mapping = _mapping(value, label)
        _require_exact_keys(
            mapping,
            {"component_id", "version", "revision", "source", "digest"},
            label,
        )
        return cls(
            component_id=_string(mapping, "component_id", label),
            version=_string(mapping, "version", label),
            revision=_string(mapping, "revision", label),
            source=_string(mapping, "source", label),
            digest=Digest.from_mapping(mapping.get("digest"), f"{label}.digest"),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "version": self.version,
            "revision": self.revision,
            "source": self.source,
            "digest": self.digest.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class MechanicsIdentity:
    artifact_id: str
    kind: str
    version: str
    platform: str | None
    architecture: str | None
    digest: Digest
    size_bytes: int | None

    @classmethod
    def from_mapping(cls, value: object, label: str) -> MechanicsIdentity:
        mapping = _mapping(value, label)
        _require_exact_keys(
            mapping,
            {
                "artifact_id",
                "kind",
                "version",
                "platform",
                "architecture",
                "digest",
                "size_bytes",
            },
            label,
        )
        raw_size = mapping.get("size_bytes")
        if raw_size is not None and (not isinstance(raw_size, int) or raw_size <= 0):
            raise ValueError(f"{label}.size_bytes must be a positive integer or null")
        return cls(
            artifact_id=_string(mapping, "artifact_id", label),
            kind=_string(mapping, "kind", label),
            version=_string(mapping, "version", label),
            platform=_optional_string(mapping.get("platform"), f"{label}.platform"),
            architecture=_optional_string(mapping.get("architecture"), f"{label}.architecture"),
            digest=Digest.from_mapping(mapping.get("digest"), f"{label}.digest"),
            size_bytes=raw_size,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "version": self.version,
            "platform": self.platform,
            "architecture": self.architecture,
            "digest": self.digest.as_dict(),
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class PatchIdentity:
    patch_id: str
    game_version: str
    game_commit: str
    branch: str | None
    release_date: str | None
    steam_build_id: str | None

    @classmethod
    def from_mapping(cls, value: object) -> PatchIdentity:
        mapping = _mapping(value, "patch")
        _require_exact_keys(
            mapping,
            {
                "patch_id",
                "game_version",
                "game_commit",
                "branch",
                "release_date",
                "steam_build_id",
            },
            "patch",
        )
        return cls(
            patch_id=_string(mapping, "patch_id", "patch"),
            game_version=_string(mapping, "game_version", "patch"),
            game_commit=_string(mapping, "game_commit", "patch"),
            branch=_optional_string(mapping.get("branch"), "patch.branch"),
            release_date=_optional_string(mapping.get("release_date"), "patch.release_date"),
            steam_build_id=_optional_string(mapping.get("steam_build_id"), "patch.steam_build_id"),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "patch_id": self.patch_id,
            "game_version": self.game_version,
            "game_commit": self.game_commit,
            "branch": self.branch,
            "release_date": self.release_date,
            "steam_build_id": self.steam_build_id,
        }


@dataclass(frozen=True, slots=True)
class InterfaceIdentity:
    observation_schema: str
    action_schema: str
    information_policy_id: str

    @classmethod
    def from_mapping(cls, value: object) -> InterfaceIdentity:
        mapping = _mapping(value, "interface")
        _require_exact_keys(
            mapping,
            {"observation_schema", "action_schema", "information_policy_id"},
            "interface",
        )
        return cls(
            observation_schema=_string(mapping, "observation_schema", "interface"),
            action_schema=_string(mapping, "action_schema", "interface"),
            information_policy_id=_string(mapping, "information_policy_id", "interface"),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "observation_schema": self.observation_schema,
            "action_schema": self.action_schema,
            "information_policy_id": self.information_policy_id,
        }


@dataclass(frozen=True, slots=True)
class RulesetIdentity:
    manifest_id: str
    patch_id: str
    admission_status: str
    engine: ComponentIdentity
    adapter: ComponentIdentity
    mechanics: tuple[MechanicsIdentity, ...]
    interface: InterfaceIdentity

    def as_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "patch_id": self.patch_id,
            "admission_status": self.admission_status,
            "engine": self.engine.as_dict(),
            "adapter": self.adapter.as_dict(),
            "mechanics": [item.as_dict() for item in self.mechanics],
            "interface": self.interface.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class PatchManifest:
    manifest_id: str
    admission_status: str
    patch: PatchIdentity
    engine: ComponentIdentity
    adapter: ComponentIdentity
    mechanics: tuple[MechanicsIdentity, ...]
    interface: InterfaceIdentity

    @classmethod
    def from_mapping(cls, value: object) -> PatchManifest:
        mapping = _mapping(value, "manifest")
        _require_exact_keys(
            mapping,
            {
                "schema_version",
                "manifest_id",
                "admission_status",
                "patch",
                "engine",
                "adapter",
                "mechanics",
                "interface",
            },
            "manifest",
        )
        schema_version = _string(mapping, "schema_version", "manifest")
        if schema_version != PATCH_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"Unsupported patch manifest schema: {schema_version}")
        manifest_id = _string(mapping, "manifest_id", "manifest")
        admission_status = _string(mapping, "admission_status", "manifest")
        if admission_status not in _ADMISSION_STATUSES:
            raise ValueError(f"Unsupported admission status: {admission_status}")
        raw_mechanics = mapping.get("mechanics")
        if not isinstance(raw_mechanics, list) or not raw_mechanics:
            raise ValueError("manifest.mechanics must contain at least one artifact")
        mechanics = tuple(
            MechanicsIdentity.from_mapping(item, f"mechanics[{index}]")
            for index, item in enumerate(raw_mechanics)
        )
        artifact_ids = [item.artifact_id for item in mechanics]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("manifest.mechanics artifact_id values must be unique")
        manifest = cls(
            manifest_id=manifest_id,
            admission_status=admission_status,
            patch=PatchIdentity.from_mapping(mapping.get("patch")),
            engine=ComponentIdentity.from_mapping(mapping.get("engine"), "engine"),
            adapter=ComponentIdentity.from_mapping(mapping.get("adapter"), "adapter"),
            mechanics=mechanics,
            interface=InterfaceIdentity.from_mapping(mapping.get("interface")),
        )
        expected_id = manifest_identifier(manifest.body_dict())
        if manifest.manifest_id != expected_id:
            raise ValueError(
                "Patch manifest identity mismatch: "
                f"expected {expected_id}, got {manifest.manifest_id}"
            )
        return manifest

    def body_dict(self) -> dict[str, object]:
        return {
            "schema_version": PATCH_MANIFEST_SCHEMA_VERSION,
            "admission_status": self.admission_status,
            "patch": self.patch.as_dict(),
            "engine": self.engine.as_dict(),
            "adapter": self.adapter.as_dict(),
            "mechanics": [item.as_dict() for item in self.mechanics],
            "interface": self.interface.as_dict(),
        }

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": PATCH_MANIFEST_SCHEMA_VERSION,
            "manifest_id": self.manifest_id,
            "admission_status": self.admission_status,
            "patch": self.patch.as_dict(),
            "engine": self.engine.as_dict(),
            "adapter": self.adapter.as_dict(),
            "mechanics": [item.as_dict() for item in self.mechanics],
            "interface": self.interface.as_dict(),
        }

    def ruleset_identity(self) -> RulesetIdentity:
        return RulesetIdentity(
            manifest_id=self.manifest_id,
            patch_id=self.patch.patch_id,
            admission_status=self.admission_status,
            engine=self.engine,
            adapter=self.adapter,
            mechanics=self.mechanics,
            interface=self.interface,
        )


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def manifest_identifier(body: object) -> str:
    return f"{_MANIFEST_ID_PREFIX}{sha256_digest(body)}"


def freeze_patch_manifest(
    specification: object,
    *,
    base_directory: Path | None = None,
) -> PatchManifest:
    body = _resolve_local_artifacts(
        dict(_mapping(specification, "manifest specification")),
        Path.cwd() if base_directory is None else base_directory,
    )
    body.pop("manifest_id", None)
    body["schema_version"] = PATCH_MANIFEST_SCHEMA_VERSION
    document = {**body, "manifest_id": manifest_identifier(body)}
    return PatchManifest.from_mapping(document)


def load_patch_manifest(path: Path) -> PatchManifest:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load patch manifest {path}: {error}") from error
    return PatchManifest.from_mapping(value)


def write_frozen_manifest(manifest: PatchManifest, path: Path) -> None:
    encoded = json.dumps(manifest.as_dict(), indent=2, ensure_ascii=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable patch manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")


def verify_installation_identity(
    patch_manifest: PatchManifest,
    installation_manifest: object,
) -> tuple[str, ...]:
    installation = _mapping(installation_manifest, "game installation manifest")
    release = _mapping(installation.get("release"), "game installation release")
    assembly = _mapping(installation.get("assembly"), "game installation assembly")
    comparisons = (
        ("game version", release.get("version"), patch_manifest.patch.game_version),
        ("game commit", release.get("commit"), patch_manifest.patch.game_commit),
        ("Steam build", release.get("steam_build_id"), patch_manifest.patch.steam_build_id),
    )
    errors = [
        f"{label} mismatch: installation has {actual!r}, manifest requires {expected!r}"
        for label, actual, expected in comparisons
        if expected is not None and actual != expected
    ]

    actual_digest = assembly.get("sha256")
    actual_size = assembly.get("size_bytes")
    actual_platform = installation.get("platform")
    actual_architecture = installation.get("architecture")
    assembly_artifacts = tuple(
        item for item in patch_manifest.mechanics if item.kind == "authoritative-game-assembly"
    )
    if not assembly_artifacts:
        errors.append("patch manifest has no authoritative-game-assembly fingerprint")
    elif not any(
        item.digest.algorithm == "sha256"
        and item.digest.value == actual_digest
        and item.size_bytes == actual_size
        and (item.platform is None or item.platform == actual_platform)
        and (item.architecture is None or item.architecture == actual_architecture)
        for item in assembly_artifacts
    ):
        errors.append("game assembly hash or size does not match a supported build artifact")
    return tuple(errors)


def _resolve_local_artifacts(body: dict[str, object], base_directory: Path) -> dict[str, object]:
    resolved = dict(body)
    for key in ("engine", "adapter"):
        raw_component = resolved.get(key)
        if isinstance(raw_component, dict):
            resolved[key] = _resolve_local_digest(raw_component, base_directory, include_size=False)

    raw_mechanics = resolved.get("mechanics")
    if isinstance(raw_mechanics, list):
        resolved["mechanics"] = [
            _resolve_local_digest(item, base_directory, include_size=True)
            if isinstance(item, dict)
            else item
            for item in raw_mechanics
        ]
    return resolved


def _resolve_local_digest(
    value: dict[object, object],
    base_directory: Path,
    *,
    include_size: bool,
) -> dict[object, object]:
    resolved = dict(value)
    local_path = resolved.pop("local_path", None)
    if local_path is None:
        return resolved
    if "digest" in resolved:
        raise ValueError("A local artifact cannot also declare a digest")
    if not isinstance(local_path, str) or not local_path:
        raise ValueError("local_path must be a non-empty string")
    artifact_path = Path(local_path)
    if not artifact_path.is_absolute():
        artifact_path = base_directory / artifact_path
    digest, size = _hash_artifact(artifact_path)
    resolved["digest"] = {"algorithm": "sha256", "value": digest}
    if include_size:
        resolved["size_bytes"] = size
    return resolved


def _hash_artifact(path: Path) -> tuple[str, int]:
    if path.is_file():
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        if size == 0:
            raise ValueError(f"Cannot fingerprint empty artifact: {path}")
        return digest.hexdigest(), size
    if not path.is_dir():
        raise ValueError(f"Local artifact does not exist: {path}")

    digest = hashlib.sha256()
    size = 0
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise ValueError(f"Cannot fingerprint empty artifact directory: {path}")
    for item in files:
        relative = item.relative_to(path).as_posix().encode()
        content = item.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        size += len(content)
    return digest.hexdigest(), size


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _string(value: dict[str, object], key: str, label: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return result


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string or null")
    return value


def _require_exact_keys(value: dict[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise ValueError(f"{label} fields differ: missing={missing}, unexpected={unexpected}")
