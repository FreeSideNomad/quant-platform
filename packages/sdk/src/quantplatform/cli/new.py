"""`pq new <project_name> [--template <tmpl>]` — scaffold a project from a Jinja template.

Flat command (no subgroup): the only thing `pq new` creates today is a
strategy project, so requiring a `strategy` verb is just noise. If we
ever scaffold something else (e.g. a dataset adapter), it gets its own
top-level verb (`pq dataset new ...`) rather than retrofitting a subgroup.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from datetime import date
from importlib.resources import files
from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from rich.console import Console

console = Console()


# Template key → directory name under quantplatform/templates/.
_TEMPLATE_DIR_BY_NAME = {
    "hello-world": "hello-world-vol-har",
    # "returns": "hello-world-returns",  # M4 — designed to fail the gate
}


def _git_user_name() -> str:
    try:
        r = subprocess.run(
            ["git", "config", "--get", "user.name"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "you"


def _find_template_dir(template_key: str) -> Path:
    """Resolve the template directory inside the installed quantplatform package."""
    template_folder = _TEMPLATE_DIR_BY_NAME.get(template_key)
    if template_folder is None:
        if template_key == "returns":
            raise NotImplementedError(
                "the `returns` template lands in M4 (companion expected-to-fail strategy)"
            )
        choices = ", ".join(sorted(_TEMPLATE_DIR_BY_NAME))
        raise ValueError(f"unknown template: {template_key!r}. Choose: {choices}")

    templates_root = files("quantplatform").joinpath("templates")
    tdir = Path(str(templates_root)) / template_folder
    if not tdir.is_dir():
        raise FileNotFoundError(
            f"template directory not found at {tdir}. Is quantplatform installed correctly?"
        )
    return tdir


def new(
    name: str = typer.Argument(..., help="Project name (e.g. my-strategy). Becomes ./<name>/."),
    template: str = typer.Option(
        "hello-world",
        "--template",
        "-t",
        help="Template to scaffold from (default: hello-world).",
    ),
    target_dir: Path | None = typer.Option(
        None, "--dir", "-d", help="Destination; default ./<name>/"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite a non-empty target directory"
    ),
) -> None:
    """Scaffold a new strategy project from a template."""
    # Validate name (conservative: letters, digits, hyphen; no leading digit)
    if not name or not name[0].isalpha() or not all(c.isalnum() or c == "-" for c in name):
        console.print(
            f"[red]invalid name {name!r}: must start with a letter and contain only letters, digits, and hyphens[/red]"
        )
        raise typer.Exit(code=2)

    try:
        source = _find_template_dir(template)
    except NotImplementedError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(code=3)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)

    dest = target_dir or Path(name)
    if dest.exists() and any(dest.iterdir()) and not force:
        console.print(
            f"[red]target directory {dest} is not empty; re-run with --force to overwrite[/red]"
        )
        raise typer.Exit(code=1)

    dest.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(source)),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    context = {
        "name": name,
        "description": "HAR-style realized-variance forecast on SPY daily OHLCV",
        "author": _git_user_name(),
        "year": str(date.today().year),
    }

    rendered_files: list[Path] = []
    for root, dirs, files_ in _walk_sorted(source):
        rel = root.relative_to(source)
        if rel.parts:
            rel_rendered = Path(*[_render_segment(seg, env, context) for seg in rel.parts])
        else:
            rel_rendered = rel
        out_dir = dest / rel_rendered
        out_dir.mkdir(parents=True, exist_ok=True)

        for fname in files_:
            src_file = root / fname
            if fname.endswith(".j2"):
                rel_template_path = str((rel / fname).as_posix())
                tmpl = env.get_template(rel_template_path)
                content = tmpl.render(**context)
                out_name = fname[:-3]
                out_name = _render_segment(out_name, env, context)
                out_path = out_dir / out_name
                out_path.write_text(content)
                rendered_files.append(out_path)
            else:
                out_name = _render_segment(fname, env, context)
                out_path = out_dir / out_name
                shutil.copyfile(src_file, out_path)
                src_mode = src_file.stat().st_mode
                if src_mode & stat.S_IEXEC or str(rel).startswith(".githooks"):
                    out_path.chmod(out_path.stat().st_mode | stat.S_IEXEC | stat.S_IRWXU)
                rendered_files.append(out_path)

    console.print(
        f"[green]✔ Scaffolded {template!r} into {dest} ({len(rendered_files)} files).[/green]"
    )


def _walk_sorted(root: Path):
    """os.walk but deterministic and returning Paths."""
    yield from _walk_recurse(root)


def _walk_recurse(root: Path):
    entries = sorted(root.iterdir())
    files_here = [e.name for e in entries if e.is_file()]
    dirs_here = [e for e in entries if e.is_dir()]
    yield root, [d.name for d in dirs_here], files_here
    for d in dirs_here:
        yield from _walk_recurse(d)


def _render_segment(seg: str, env: Environment, context: dict) -> str:
    """If a path segment contains {{...}}, render it."""
    if "{{" in seg:
        return env.from_string(seg).render(**context)
    return seg
