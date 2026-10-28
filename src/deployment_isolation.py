"""Multi-deployment isolation: a startup invariant for one harness serving separate domains.

Contract: docs/runtime-work-packages/multi-deployment-isolation.md. Pure stdlib, no side effects
at import. Enforcement is opt-in (ODYSSEUS_DEPLOYMENT_ISOLATION=required) so an existing
single-household runtime is unchanged until the operator switches it on after acceptance.

Diagnostics name only variable names/roles and a short hash of the resolved path. They never
contain a full path, a file name, file content or a credential value.
"""

import hashlib
import errno
import hmac
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

MODE_VAR = "ODYSSEUS_DEPLOYMENT_ISOLATION"
ID_VAR = "ODYSSEUS_DEPLOYMENT_ID"
DOMAIN_VAR = "ODYSSEUS_DEPLOYMENT_DOMAIN"
DATA_VAR = "ODYSSEUS_DATA_DIR"
CREDENTIALS_VAR = "ODYSSEUS_CREDENTIAL_IDS"  # comma-separated NON-secret identifiers
INTERNAL_TOKEN_VAR = "ODYSSEUS_INTERNAL_TOKEN"  # in-process admin token; only its fingerprint is ever compared
PORT_VAR = "APP_PORT"
# Shell/python tools and admin shell routes cannot be path-confined, so they are refused while isolation
# is required unless the operator opts in (OS-level separation, e.g. a distinct service account, then applies).
SHELL_OPT_IN_VAR = "ODYSSEUS_ISOLATION_ALLOW_SHELL"

# Which environment variables point at a domain's source roots.
DOMAIN_ROOT_VARS = {
    "misumi": (
        "MISUMI_HOUSEHOLD_ROOT", "MISUMI_SOURCE_ROOT", "BBC_MISUMI_ROOT",
        "FLAT_KNOWLEDGEBASE_ROOT", "MISUMI_SEED_ORDER_ROOT", "MISUMI_CANONICAL_ROOT",
    ),
    "phd": ("BBC_OBSIDIAN_PHD_ROOT", "OBSIDIAN_PHD_ROOT"),
}
# Read-only paths that belong to no domain: allowed only inside the deployment's own roots or the application root.
SHARED_READ_VARS = ("BBC_ODYSSEUS_ROOT", "MISUMI_PERSONA_POLICY_PATH")
# Paths the runtime writes; each must live under the deployment's own data root.
WRITABLE_VARS = (
    "ODYSSEUS_MAIL_ATTACHMENTS_DIR",
    "ODYSSEUS_INSTAGRAM_EXPORTS_DIR",
    "FASTEMBED_CACHE_PATH",
    "MISUMI_ROUTING_STATE_ROOT",
    "MISUMI_PERSONA_STATE_ROOT",
    "MISUMI_DIALOGUE_STATE_ROOT",
    "MISUMI_EVENT_LOG",
    "ODYSSEUS_STT_TMP_DIR",
    "ODYSSEUS_META_EXPORT_BROWSER_PROFILE",
)

MARKER_NAME = ".odysseus-deployment.json"
_MARKER_MAX_BYTES = 4096
_NO_HARD_LINK_ERRNOS = frozenset(
    getattr(errno, name) for name in ("EPERM", "ENOTSUP", "EOPNOTSUPP", "ENOSYS", "EXDEV", "EMLINK") if hasattr(errno, name))
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_ON = frozenset({"required", "1", "true", "on"})
_OFF = frozenset({"", "0", "false", "off"})


class IsolationError(Exception):
    """A deployment configuration violates the isolation contract. `.code` is stable."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class DeploymentProfile:
    deployment_id: str
    domain: str
    data_root: str
    source_roots: Tuple[Tuple[str, str], ...] = ()    # (role, path)
    writable_roots: Tuple[Tuple[str, str], ...] = ()  # (role, path)
    credential_ids: Tuple[str, ...] = ()
    port: Optional[int] = None


@dataclass(frozen=True)
class IsolationResult:
    enforced: bool
    profile: Optional[DeploymentProfile] = None
    data_root: str = ""
    identity: Tuple[int, int] = (0, 0)
    sources: Tuple[Tuple[str, str, Tuple[int, int]], ...] = ()  # (role, real path, identity) snapshot at startup
    shared_read: Tuple[str, ...] = ()                            # extra real roots allowed for SHARED_READ_VARS

    def recheck(self) -> None:
        """Detect a data root or source root swapped (link retargeted, directory replaced) after validation."""
        if not self.enforced:
            return
        if _real(self.data_root) != self.data_root or _identity(self.data_root) != self.identity:
            raise IsolationError("path_alias", f"{DATA_VAR} changed after validation (ref {_tag(self.data_root)})")
        for role, path, ident in self.sources:
            if _real(path) != path or _identity(path) != ident:
                raise IsolationError("path_alias", f"{role} changed after validation (ref {_tag(path)})")


def _real(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _tag(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8", "surrogatepass")).hexdigest()[:8]


def _identity(path: str) -> Tuple[int, int]:
    try:
        st = os.stat(path)
    except OSError:
        return (0, 0)
    return (st.st_dev, st.st_ino)


def _inside(child: str, parent: str) -> bool:
    """Both arguments are already realpath+normcase. True for equal or nested."""
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:  # different drives
        return False


def stat_is_regular(st) -> bool:
    import stat as _stat
    return _stat.S_ISREG(st.st_mode)


def _resolve_root(role: str, raw: str) -> str:
    """Resolve a configured root, refusing relative paths, `..` segments and link aliases."""
    if not raw or not raw.strip():
        raise IsolationError("missing_data_root" if role == DATA_VAR else "missing_path", f"{role} is not set")
    if not os.path.isabs(raw):
        raise IsolationError("path_not_absolute", f"{role} must be an absolute path")
    if ".." in re.split(r"[\\/]+", raw):
        raise IsolationError("path_alias", f"{role} contains a parent-directory segment (ref {_tag(os.path.normpath(raw))})")
    lexical = os.path.normcase(os.path.normpath(raw))
    real = _real(raw)
    if real != lexical:
        raise IsolationError("path_alias", f"{role} resolves through a link or alias (ref {_tag(real)})")
    return real


def _pin(role: str, raw: str) -> Tuple[str, Tuple[int, int]]:
    """Resolve a root and pin its identity in one consistent step. The identity reached through the configured path
    (links followed) must equal the identity of the resolved real path, so a directory swapped while being resolved is
    refused here, and one swapped afterwards is caught by IsolationResult.recheck() against this pin."""
    before = _identity(raw)
    real = _resolve_root(role, raw)
    after = _identity(real)
    if before != after:
        raise IsolationError("path_alias", f"{role} changed while being resolved (ref {_tag(real)})")
    return real, after


def _domain_vars(domain: str) -> Tuple[str, ...]:
    return DOMAIN_ROOT_VARS.get(domain, ())


def profile_from_env(env: Mapping[str, str]) -> DeploymentProfile:
    domain = (env.get(DOMAIN_VAR) or "").strip().lower()
    sources = tuple((v, env[v]) for v in _domain_vars(domain) if (env.get(v) or "").strip())
    writable = tuple((v, env[v]) for v in WRITABLE_VARS if (env.get(v) or "").strip())
    creds = tuple(c.strip() for c in (env.get(CREDENTIALS_VAR) or "").split(",") if c.strip())
    token = env.get(INTERNAL_TOKEN_VAR) or ""
    if token:  # two deployments given the same token would accept each other's loopback calls
        creds += ("internal-token:" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:16],)
    port = None
    if (env.get(PORT_VAR) or "").strip().isdigit():
        port = int(env[PORT_VAR])
    return DeploymentProfile(
        deployment_id=(env.get(ID_VAR) or "").strip(),
        domain=domain,
        data_root=(env.get(DATA_VAR) or "").strip(),
        source_roots=sources,
        writable_roots=writable,
        credential_ids=creds,
        port=port,
    )


def _resolved(profile: DeploymentProfile):
    data = _resolve_root(DATA_VAR, profile.data_root)
    sources = [(r, _resolve_root(r, p)) for r, p in profile.source_roots]
    writable = [(r, _resolve_root(r, p)) for r, p in profile.writable_roots]
    return data, sources, writable


def validate_profile(profile: DeploymentProfile, *, env: Optional[Mapping[str, str]] = None):
    """Fail-closed checks for one deployment. Raises IsolationError; returns (data root, pinned source roots,
    data-root identity or None), the resolved real paths and the identities pinned when they were first checked."""
    if not _ID_RE.match(profile.deployment_id or ""):
        raise IsolationError("missing_identity", f"{ID_VAR} must be set to a 1-64 char identifier")
    if not profile.domain:
        raise IsolationError("missing_identity", f"{DOMAIN_VAR} must be set")
    if profile.domain not in DOMAIN_ROOT_VARS:
        raise IsolationError("unknown_domain", f"{DOMAIN_VAR} must be one of: {', '.join(sorted(DOMAIN_ROOT_VARS))}")
    # Pin identities BEFORE anything is validated: every later check (containment, existence, markers) is made
    # against directories whose identity is already recorded, and any swap after this point is refused below or by
    # recheck(). Nothing is validated before the pin, so there is no earlier directory that could be substituted.
    pinned = tuple((role,) + _pin(role, raw) for role, raw in profile.source_roots)
    pinned_data = None
    if (profile.data_root or "").strip() and os.path.isdir(profile.data_root):
        pinned_data = _pin(DATA_VAR, profile.data_root)[1]
    data, sources, writable = _resolved(profile)
    if ([(r, p) for r, p, _ in pinned] != list(sources) or any(_identity(p) != i for _, p, i in pinned)
            or (pinned_data is not None and _identity(data) != pinned_data)):
        raise IsolationError("path_alias", "a configured root changed while the configuration was being validated")
    for role, path in sources:
        if not os.path.isdir(path):
            raise IsolationError("missing_source_root", f"{role} is not an existing directory (ref {_tag(path)})")

    for role, path in sources:
        if _inside(path, data) or _inside(data, path):
            raise IsolationError("source_root_in_data_root", f"{role} and {DATA_VAR} overlap (ref {_tag(path)})")
    for role, path in writable:
        if not _inside(path, data):
            raise IsolationError("writable_outside_data_root", f"{role} is outside {DATA_VAR} (ref {_tag(path)})")
        for srole, spath in sources:
            if _inside(path, spath) or _inside(spath, path):
                raise IsolationError("writable_outside_data_root", f"{role} overlaps {srole} (ref {_tag(path)})")

    if env is not None:
        from src.runtime_paths import get_app_root
        allowed_read = [data, _real(get_app_root())] + [p for _, p in sources]
        for name in SHARED_READ_VARS:
            raw = (env.get(name) or "").strip()
            if raw and not any(_inside(_resolve_root(name, raw), a) for a in allowed_read):
                raise IsolationError("foreign_root_configured", f"{name} points outside this deployment and the application")
    if env is not None:
        # An opposite-domain root left in the parent environment is a leak path even when the
        # deployment's own parameter for it is empty.
        for domain, names in DOMAIN_ROOT_VARS.items():
            if domain == profile.domain:
                continue
            for name in names:
                if (env.get(name) or "").strip():
                    raise IsolationError("opposite_domain_root_inherited", f"{name} is set but this deployment is domain '{profile.domain}'")
    if not profile.source_roots:  # after the opposite-domain scan, so an inherited foreign root is reported as such
        raise IsolationError("missing_source_root", f"no source root is set for domain '{profile.domain}' ({', '.join(_domain_vars(profile.domain))})")
    verify_marker(profile, data)
    _refuse_foreign_neighbours(data)
    return data, pinned, pinned_data


_SCAN_DEPTH = 3
_SCAN_LIMIT = 2000


def _refuse_foreign_neighbours(data: str) -> None:
    """A single process cannot see another deployment's configuration, but it can see its marker on disk:
    refuse a data root nested inside, or containing, any other deployment's marked data root."""
    parent = os.path.dirname(data)
    while parent and parent != os.path.dirname(parent):
        if os.path.lexists(os.path.join(parent, MARKER_NAME)):
            raise IsolationError("nested_data_root", f"{DATA_VAR} is inside another deployment's data root (ref {_tag(parent)})")
        parent = os.path.dirname(parent)
    budget = [_SCAN_LIMIT]

    def walk(path: str, depth: int) -> None:
        if depth > _SCAN_DEPTH or budget[0] <= 0:
            return
        try:
            with os.scandir(path) as it:
                for entry in it:
                    budget[0] -= 1
                    if budget[0] <= 0:
                        return
                    if entry.name == MARKER_NAME and depth > 0:
                        raise IsolationError("nested_data_root", f"{DATA_VAR} contains another deployment's data root (ref {_tag(path)})")
                    if depth < _SCAN_DEPTH and entry.is_dir(follow_symlinks=False):
                        walk(entry.path, depth + 1)
        except OSError:
            return

    if os.path.isdir(data):
        walk(data, 0)


def _pair_collision(code: str, role_a: str, role_b: str, ref: str) -> IsolationError:
    return IsolationError(code, f"{role_a} and {role_b} collide (ref {ref})")


def validate_pair(a: DeploymentProfile, b: DeploymentProfile) -> None:
    """Two deployments sharing a harness (or a disk) must not overlap in identity or state."""
    if a.deployment_id == b.deployment_id:
        raise _pair_collision("shared_identifier", ID_VAR, ID_VAR, _tag(a.deployment_id))
    da, sa, wa = _resolved(a)
    db, sb, wb = _resolved(b)
    if da == db:
        raise _pair_collision("data_root_overlap", DATA_VAR, DATA_VAR, _tag(da))
    if _inside(da, db) or _inside(db, da):
        raise _pair_collision("nested_data_root", DATA_VAR, DATA_VAR, _tag(min(da, db, key=len)))
    for (ra, pa), (rb, pb) in ((x, y) for x in sa + [(DATA_VAR, da)] for y in sb + [(DATA_VAR, db)]):
        if _inside(pa, pb) or _inside(pb, pa):
            raise _pair_collision("source_root_overlap", ra, rb, _tag(pa))
    for ra, pa in wa:
        for rb, pb in wb:
            if _inside(pa, pb) or _inside(pb, pa):
                raise _pair_collision("shared_writable_path", ra, rb, _tag(pa))
    shared = set(a.credential_ids) & set(b.credential_ids)
    if shared:
        raise IsolationError("credential_collision", f"{CREDENTIALS_VAR} shares {len(shared)} identifier(s) across deployments")
    if a.port is not None and a.port == b.port:
        raise IsolationError("shared_identifier", f"{PORT_VAR} is shared across deployments")


def validate_profiles(profiles: Sequence[DeploymentProfile]) -> None:
    for p in profiles:
        validate_profile(p)
    for i, a in enumerate(profiles):
        for b in profiles[i + 1:]:
            validate_pair(a, b)


def verify_marker(profile: DeploymentProfile, data: Optional[str] = None) -> bool:
    """Read-only. True if the marker exists and matches; False if absent; raises on mismatch."""
    root = data or _resolve_root(DATA_VAR, profile.data_root)
    path = os.path.join(root, MARKER_NAME)
    try:
        before = os.lstat(path)
        if not stat_is_regular(before):
            raise IsolationError("marker_mismatch", f"data-root marker is not a regular file (ref {_tag(root)})")
        # O_NOFOLLOW closes the check-then-open window on POSIX; the fstat comparison covers platforms without it.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise IsolationError("marker_mismatch", f"data-root marker changed while being read (ref {_tag(root)})")
            with os.fdopen(fd, "rb", closefd=False) as fh:
                raw = fh.read(_MARKER_MAX_BYTES + 1)
        finally:
            os.close(fd)
    except FileNotFoundError:
        return False
    except OSError:
        raise IsolationError("marker_mismatch", f"data-root marker unreadable (ref {_tag(root)})")
    try:
        doc = json.loads(raw[:_MARKER_MAX_BYTES].decode("utf-8")) if len(raw) <= _MARKER_MAX_BYTES else None
    except (ValueError, UnicodeDecodeError):
        doc = None
    if (not isinstance(doc, dict) or doc.get("deployment_id") != profile.deployment_id
            or doc.get("domain") != profile.domain):
        raise IsolationError("marker_mismatch", f"data root belongs to a different deployment (ref {_tag(root)})")
    return True


def claim_data_root(profile: DeploymentProfile) -> str:
    """Create the data root and its marker (atomic, O_EXCL). Call only after validation passed."""
    root = _resolve_root(DATA_VAR, profile.data_root)
    os.makedirs(root, exist_ok=True)
    if _real(root) != root:
        raise IsolationError("path_alias", f"{DATA_VAR} changed during creation (ref {_tag(root)})")
    path = os.path.join(root, MARKER_NAME)
    body = json.dumps({"schema": 1, "deployment_id": profile.deployment_id, "domain": profile.domain}).encode("utf-8")
    # Publish a complete file with a hard link: it fails if the marker exists, and a concurrent starter can
    # never observe a created-but-empty marker (which O_EXCL + later write would allow).
    temp = os.path.join(root, f".{MARKER_NAME}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(body)
        try:
            os.link(temp, path)
        except FileExistsError:
            verify_marker(profile, root)
        except OSError as exc:
            if exc.errno not in _NO_HARD_LINK_ERRNOS:
                raise  # permissions, space, read-only: reported by enforce_startup as data_root_unwritable
            # No hard links (FAT/exFAT, some network shares). Windows rename never overwrites, so it is still exclusive;
            # elsewhere there is no exclusive fallback, so refuse rather than risk replacing another deployment's marker.
            if os.name != "nt":
                raise IsolationError("marker_unsupported", f"{DATA_VAR} filesystem cannot publish the marker atomically (ref {_tag(root)})")
            try:
                os.rename(temp, path)
            except FileExistsError:
                verify_marker(profile, root)
            except OSError:
                raise IsolationError("marker_unsupported", f"{DATA_VAR} filesystem cannot publish the marker atomically (ref {_tag(root)})")
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass
    return root


def enforce_startup(env: Optional[Mapping[str, str]] = None) -> IsolationResult:
    env = os.environ if env is None else env
    mode = (env.get(MODE_VAR) or "").strip().lower()
    if mode in _OFF:
        return IsolationResult(enforced=False)
    if mode not in _ON:
        raise IsolationError("invalid_mode", f"{MODE_VAR} must be 'required' or unset")
    profile = profile_from_env(env)
    data, pinned_sources, pinned_data = validate_profile(profile, env=env)
    # A data root that did not exist when it was validated could not be pinned: re-run the on-disk checks that depend on
    # its contents immediately before it is claimed, and again once it is claimed, so a directory created or swapped in
    # between (for example one holding another deployment's marker) is refused rather than adopted.
    if pinned_data is None:
        verify_marker(profile, data)
        _refuse_foreign_neighbours(data)
    try:
        root = claim_data_root(profile)
    except OSError as exc:
        raise IsolationError("data_root_unwritable", f"{DATA_VAR} cannot be created or written ({type(exc).__name__})")
    if root != data:
        raise IsolationError("path_alias", f"{DATA_VAR} changed between validation and creation (ref {_tag(data)})")
    if pinned_data is None:
        _refuse_foreign_neighbours(root)
    if pinned_data is not None and _identity(root) != pinned_data:
        raise IsolationError("path_alias", f"{DATA_VAR} was replaced between validation and creation (ref {_tag(root)})")
    result = IsolationResult(enforced=True, profile=profile, data_root=root, identity=_identity(root), sources=pinned_sources)
    result.recheck()  # a source root swapped between validation and this snapshot is refused, not admitted
    set_active(result)
    return result


def enforce_startup_or_exit(env: Optional[Mapping[str, str]] = None) -> IsolationResult:
    """Process-start wrapper: print the non-sensitive diagnostic and exit non-zero on refusal."""
    try:
        return enforce_startup(env)
    except IsolationError as exc:
        print(f"[isolation] startup refused: {exc}", file=sys.stderr)
        raise SystemExit(78)


def ensure_within_deployment(result: IsolationResult, path: str, *, role: str = "target") -> str:
    """Boundary check for dispatch/schedule/retrieval targets: refuse a path outside this
    deployment's data root and own source roots before anything is persisted or read."""
    if not result.enforced:
        return path
    real = _real(path)
    allowed = [result.data_root] + [_real(p) for _, p in result.profile.source_roots]
    if not any(_inside(real, a) for a in allowed):
        raise IsolationError("cross_domain_target", f"{role} is outside this deployment (ref {_tag(real)})")
    return real


def check_credential(result: IsolationResult, credential_id: str) -> None:
    """Reject a credential identity that this deployment does not own, without echoing it."""
    if result.enforced and credential_id not in result.profile.credential_ids:
        raise IsolationError("credential_collision", "credential identity is not registered to this deployment")


# ---------------------------------------------------------------------------
# Process-wide active result and the helpers shared boundaries call
# ---------------------------------------------------------------------------
_ACTIVE: Optional[IsolationResult] = None


def set_active(result: Optional[IsolationResult]) -> None:
    global _ACTIVE
    _ACTIVE = result if result is not None and result.enforced else None


def get_active() -> Optional[IsolationResult]:
    return _ACTIVE


def confined_roots(result: Optional[IsolationResult] = None) -> Optional[list]:
    """The only roots filesystem tools may touch while isolation is required (data root first), or
    None when it is not required. No shared temp directories and no settings-supplied extras."""
    result = result or _ACTIVE
    if result is None or not result.enforced:
        return None
    result.recheck()  # a source or data root swapped after startup must never become an allowed root
    return [result.data_root] + [path for _, path, _ in result.sources]


def path_allowed(path: str, result: Optional[IsolationResult] = None) -> bool:
    roots = confined_roots(result)
    if roots is None:
        return True
    real = _real(path)
    return any(_inside(real, r) for r in roots)


def bind_credential(raw: str, deployment_id: str, data_root: str) -> str:
    """The effective value of a configured shared secret for ONE deployment. The same inherited environment value
    yields a different effective credential per deployment identity and data root, so it cannot cross."""
    msg = f"{deployment_id}\0{data_root}".encode("utf-8")
    return hmac.new(raw.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def effective_credential(raw: str) -> str:
    """Bind `raw` to the active deployment, or return it unchanged when isolation is not required."""
    if _ACTIVE is None or not _ACTIVE.enforced:
        return raw
    return bind_credential(raw, _ACTIVE.profile.deployment_id, _ACTIVE.data_root)


def shell_blocked(env: Optional[Mapping[str, str]] = None) -> bool:
    if _ACTIVE is None or not _ACTIVE.enforced:
        return False
    env = os.environ if env is None else env
    return (env.get(SHELL_OPT_IN_VAR) or "").strip() != "1"


def require_shell_allowed(role: str) -> None:
    if shell_blocked():
        raise IsolationError("shell_disabled", f"{role} is unavailable while deployment isolation is required")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """`python -m src.deployment_isolation check ENV.json ENV.json ...` - pair-check deployments before
    starting them. Each file is a JSON object of the environment one deployment will receive."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["validate"]:  # preflight for launchers: validates os.environ, creates nothing
        try:
            profile = profile_from_env(os.environ)
            if (os.environ.get(MODE_VAR) or "").strip().lower() not in _ON:
                raise IsolationError("invalid_mode", f"{MODE_VAR} must be 'required' for validation")
            validate_profile(profile, env=os.environ)
        except IsolationError as exc:
            print(f"[isolation] refused: {exc}", file=sys.stderr)
            return 78
        print("[isolation] configuration is valid")
        return 0
    if len(argv) < 2 or argv[0] != "check":
        print("usage: python -m src.deployment_isolation check ENV.json [ENV.json ...]", file=sys.stderr)
        return 2
    try:
        envs = []
        for name in argv[1:]:
            with open(name, encoding="utf-8") as fh:
                envs.append(json.load(fh))
        validate_profiles([profile_from_env(e) for e in envs])
    except IsolationError as exc:
        print(f"[isolation] refused: {exc}", file=sys.stderr)
        return 78
    except (OSError, ValueError) as exc:
        print(f"[isolation] cannot read configuration ({type(exc).__name__})", file=sys.stderr)
        return 2
    print(f"[isolation] {len(envs)} deployment(s) are separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
